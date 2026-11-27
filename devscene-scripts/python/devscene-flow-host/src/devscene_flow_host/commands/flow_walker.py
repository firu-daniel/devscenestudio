"""The `devscene-flow-walker` command: `flow-walker.sh`'s four verbs over the host.

The rule: the command answers as `cli/templates/scripts/flow-walker.sh` does, by its header's
`EXIT CODES`:
- `0`: an action was rendered to stdout; `check-round-file` found the file valid, printing
  nothing.
- `1`: a `UsageError`; a `Refused` step, whose cause is the predicate host's `last_refusal` when
  it has one, else the refusal's reason; `next` or `current` with no saved walk; no
  `<flows>/<flow>.graph.json`.
- `2`: not inside a git repository; a graph that does not load, or declares another flow; and
  every other exception, mapped by `failure` — an unanticipated type as `internal error:`.
- `3`: `check-round-file` found the file invalid or absent.
Every non-zero exit writes exactly one `flow-walker: <cause>` line to stderr, a newline in the
cause flattened, and nothing to stdout; no exception but `KeyboardInterrupt` and `SystemExit`
escapes `main`. The checks run in bash's order: the command line; the root, from a bare
`git rev-parse --show-toplevel`; `check-round-file`, which reads no configuration or graph; the
configuration's `stateDir`; the graph file, its loading and its `flow`; the saved walk for `next`
and `current`; then the verb. The walk is reached only through the host's entry points —
`open_walker` with `start_walk`, `record_outcome` and `current_step` — never through `Walker`'s
own methods, which would skip the round-file check, the refusal count and the `refused:` lines.

Deliberately not covered:
- The launch route and `uv`: `cli/templates/scripts/flow-walker.sh`'s.
- A flat bash state file at `<stateDir>/.flow_walker_state`: `flow-walker.sh` deletes it before
  this command runs.
- Comparing this command with the retired bash walker: `devscene-flow-host/README.md` → the
  differences section.
- A rendering fault after `start` or `next` has saved the walk: the walk stays saved, where bash
  renders before it writes.
"""

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, TextIO

from graphscene import FlowGraph, GraphError, Refused, Walker, load_graph_file

from devscene_flow_host.commands.arguments import Invocation, UsageError, parse
from devscene_flow_host.commands.render import render
from devscene_flow_host.host.predicates import HarnessPredicateHost
from devscene_flow_host.host.re_entry import current_step, start_walk
from devscene_flow_host.host.round_gates import HostStep, record_outcome
from devscene_flow_host.host.store import walk_state_path, walk_store
from devscene_flow_host.host.walking import open_walker
from devscene_flow_host.records.config import read_config
from devscene_flow_host.records.errors import RecordError
from devscene_flow_host.records.round_files import round_file_path, round_file_problem

PREFIX: Final = "flow-walker: "
GRAPH_SUFFIX: Final = ".graph.json"
NOT_IN_REPOSITORY: Final = "not inside a git repository"


class _Exit(Exception):
    """An exit `main` decided on, carrying its status and its one stderr cause."""

    def __init__(self, status: int, cause: str) -> None:
        super().__init__(cause)
        self.status = status
        self.cause = cause


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        text = _run(arguments, Path.cwd() if cwd is None else cwd)
    except _Exit as stop:
        status, cause = stop.status, stop.cause
    except Exception as error:
        status, cause = failure(error)
    else:
        out.write(text)
        return 0
    err.write(PREFIX + " ".join(cause.splitlines()) + "\n")
    return status


def failure(error: BaseException) -> tuple[int, str]:
    if isinstance(error, RecordError):
        return 2, str(error)
    if isinstance(error, GraphError):
        return 2, str(error.violations[0])
    if isinstance(error, TimeoutError):
        return 2, str(error)
    if isinstance(error, (OSError, ValueError)):
        return 2, str(error)
    return 2, f"internal error: {type(error).__name__}: {error}"


def _run(argv: list[str], cwd: Path) -> str:
    try:
        invocation = parse(argv)
    except UsageError as error:
        raise _Exit(1, str(error)) from None
    repo_root = _repo_root(cwd)
    if invocation.command == "check-round-file":
        findings = _given(invocation.findings)
        reason = round_file_problem(round_file_path(repo_root, findings))
        if reason is not None:
            raise _Exit(3, f"{findings}: {reason}")
        return ""
    flow = _given(invocation.flow)
    branch = _given(invocation.branch)
    state_dir = read_config(repo_root).state_dir
    graph = _graph(repo_root, _given(invocation.flows), flow)
    if invocation.command in ("next", "current"):
        if walk_store(repo_root, state_dir, branch).read() is None:
            path = walk_state_path(repo_root, state_dir, branch)
            raise _Exit(1, f"no walk in progress at {path}: run 'start' first")
    walker = open_walker(repo_root, branch, graph, skipped=invocation.skipped)
    step = _step(invocation, walker, repo_root, branch)
    if isinstance(step.action, Refused):
        host = walker.host
        known = host.last_refusal if isinstance(host, HarnessPredicateHost) else None
        raise _Exit(1, step.action.reason if known is None else known)
    return render(step, graph=graph, repo_root=repo_root, state_dir=state_dir, branch=branch)


def _step(invocation: Invocation, walker: Walker, repo_root: Path, branch: str) -> HostStep:
    if invocation.command == "start":
        return start_walk(walker, repo_root, branch, invocation.entry)
    if invocation.command == "next":
        return record_outcome(
            walker,
            repo_root,
            branch,
            _given(invocation.outcome),
            node=invocation.node,
            findings=invocation.findings,
        )
    return current_step(walker, repo_root, branch)


def _repo_root(cwd: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        raise _Exit(2, NOT_IN_REPOSITORY) from None
    top = result.stdout.rstrip("\n")
    if result.returncode != 0 or not top:
        raise _Exit(2, NOT_IN_REPOSITORY)
    return Path(top)


def _graph(repo_root: Path, flows: str, flow: str) -> FlowGraph:
    directory = Path(flows)
    path = (directory if directory.is_absolute() else repo_root / directory) / (flow + GRAPH_SUFFIX)
    if not path.is_file():
        raise _Exit(1, f"unknown flow '{flow}': no {path}")
    try:
        graph = load_graph_file(path)
    except GraphError as error:
        raise _Exit(2, f"cannot load {path}: {failure(error)[1]}") from None
    if graph.flow != flow:
        raise _Exit(2, f"graph {path} declares flow '{graph.flow}', not '{flow}'")
    return graph


def _given(value: str | None) -> str:
    """A value `parse` guarantees for the verb."""
    if value is None:
        raise ValueError("a required flag reached the command without a value")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
