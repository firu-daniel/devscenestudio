"""The `graphscene` command line: `check`, `start`, `next` and `current`, a thin entry point over
loading a graph and walking it one step at a time over a state file the caller names.

The rule: every command prints one ASCII-only JSON document on stdout, followed by a newline, and
exits by this contract; `--help`, on the command line or on a command, is the one exception: it
prints argparse's help text on stdout and exits `0`.

- `0`: the graph loaded (`check`), or the walk returned an action.
- `1`: the graph was rejected; every command loads the graph first and prints the check document.
- `2`: usage, with argparse's usage text on stderr.
- `3`: the walk returned `Refused`.
- `4`: an input could not be read or used (`OSError`, a malformed state or resume file's
  `ValueError`, a lock's `TimeoutError`): one `graphscene: <message>` line on stderr and nothing
  on stdout.

Every document it prints is owned by `graphscene.adapters.check_json` (the check document) or
`graphscene.adapters.walk_json` (the step document); this module encodes none itself.

Deliberately not covered:

- `RoundResume` validity, which is `Walker.start`'s.
- Configuration, which the CLI reads none of.
- Platforms without `fcntl`, which `FileStateStore` does not cover.
- DevScene's `key: value` wire, which is #418's.
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn, TextIO

from graphscene.adapters.check_json import check_document
from graphscene.adapters.state_file import FileStateStore
from graphscene.adapters.walk_json import resume_from_json, step_document
from graphscene.engine.walker import Walker
from graphscene.facade.loading import load_graph_file
from graphscene.model.errors import GraphError
from graphscene.model.flow_graph import FlowGraph
from graphscene.model.walk_actions import Refused, Step
from graphscene.model.walk_state import RoundResume

_PROG = "graphscene"
_ANSWER_VALUES = {"true": True, "false": False}


class _ParserExit(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


class _Parser(argparse.ArgumentParser):
    """An `ArgumentParser` that writes to the injected streams and raises instead of exiting."""

    def __init__(self, *, stdout: TextIO, stderr: TextIO, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._stdout = stdout
        self._stderr = stderr

    def print_help(self, file: object = None) -> None:
        self._stdout.write(self.format_help())

    def print_usage(self, file: object = None) -> None:
        self._stderr.write(self.format_usage())

    def _print_message(self, message: str, file: object = None) -> None:
        if message:
            self._stderr.write(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._stderr.write(message)
        raise _ParserExit(status)

    def error(self, message: str) -> NoReturn:
        self.print_usage()
        self.exit(2, f"{self.prog}: error: {message}\n")


class _AnswerHost:
    """A `PredicateHost` answering each predicate by name, whatever the node; `None` if unnamed."""

    def __init__(self, answers: Mapping[str, bool]) -> None:
        self._answers = dict(answers)

    def answer(self, predicate: str, node: str) -> bool | None:
        return self._answers.get(predicate)


def _parser(stdout: TextIO, stderr: TextIO) -> tuple[_Parser, dict[str, _Parser]]:
    parser = _Parser(stdout=stdout, stderr=stderr, prog=_PROG)
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")
    subparsers: dict[str, _Parser] = {}

    def command(name: str, summary: str, walk: bool) -> _Parser:
        sub = commands.add_parser(name, help=summary, stdout=stdout, stderr=stderr)
        sub.add_argument("graph")
        if walk:
            sub.add_argument("state")
        subparsers[name] = sub
        return sub

    command("check", "load and check a graph", walk=False)

    start = command("start", "start a walk", walk=True)
    start.add_argument("--entry")
    start.add_argument("--resume")

    step = command("next", "record an outcome and step the walk", walk=True)
    step.add_argument("--outcome", required=True)
    step.add_argument("--node")
    step.add_argument("--detail")

    for asking in (start, step):
        asking.add_argument(
            "--answer", action="append", default=[], metavar="<predicate>=true|false"
        )

    command("current", "re-print the pending action", walk=True)

    return parser, subparsers


def _answers(parser: _Parser, given: Sequence[str]) -> dict[str, bool]:
    answers: dict[str, bool] = {}
    for raw in given:
        name, separator, value = raw.partition("=")
        if not separator or not name:
            parser.error(f"--answer {raw!r}: expected <predicate>=true|false")
        if value not in _ANSWER_VALUES:
            parser.error(f"--answer {raw!r}: the value must be 'true' or 'false'")
        if name in answers:
            parser.error(f"--answer: predicate {name!r} is given twice")
        answers[name] = _ANSWER_VALUES[value]
    return answers


def _emit(stdout: TextIO, document: dict[str, object]) -> None:
    stdout.write(json.dumps(document) + "\n")


def _walk(args: argparse.Namespace, graph: FlowGraph, answers: Mapping[str, bool]) -> Step:
    walker = Walker(graph, FileStateStore(Path(args.state)), _AnswerHost(answers))
    if args.command == "start":
        resume: RoundResume | None = None
        if args.resume is not None:
            path = Path(args.resume)
            try:
                resume = resume_from_json(path.read_bytes().decode("utf-8"))
            except ValueError as error:
                raise ValueError(f"{path}: {error}") from error
        entry: str | None = args.entry
        return walker.start(entry, resume=resume)
    if args.command == "next":
        outcome: str = args.outcome
        node: str | None = args.node
        detail: str | None = args.detail
        return walker.next(outcome, node, detail)
    return walker.current()


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the command line on `argv` (default `sys.argv[1:]`) and return its exit status."""
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser, commands = _parser(out, err)
    try:
        args = parser.parse_args(argv)
        command: str = args.command
        given: list[str] = getattr(args, "answer", [])
        answers = _answers(commands[command], given)
    except _ParserExit as stop:
        return stop.status

    try:
        graph = load_graph_file(Path(args.graph))
    except GraphError as error:
        _emit(out, check_document(error))
        return 1
    except OSError as error:
        err.write(f"{_PROG}: {error}\n")
        return 4
    if command == "check":
        _emit(out, check_document(None))
        return 0

    try:
        step = _walk(args, graph, answers)
    except (OSError, ValueError, TimeoutError) as error:
        err.write(f"{_PROG}: {error}\n")
        return 4
    _emit(out, step_document(step))
    return 3 if isinstance(step, Refused) else 0


if __name__ == "__main__":
    raise SystemExit(main())
