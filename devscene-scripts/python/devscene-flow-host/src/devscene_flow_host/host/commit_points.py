"""The two side effects every planning hook is built from: one artifact commit through the main
checkout's commit wrapper, and one ledger-entry flip.

The rule:
- `commit_artifact` is `prl_artifact_commit` (`cli/templates/scripts/lib/planning-record-lib.sh`)
  in the call spelling the autonomous fork gives
  (`plugin/instructions/task_plan_writing_instructions_autonomous.md` → `## Override 4 — commit
  the task plan after it converges`, **Commit mechanism**): `bash <wrapper> --repo <worktree>
  --artifact <kind> [--round <n>] [--entry <id>] --push`, one fixed argument vector with no
  shell, its working directory the worktree, stdout and stderr both captured. Exit `0` is `True`
  (committed), exit `3` is `False` (nothing to commit), any other exit is a `CommitPointError`
  naming the kind, the exit and the last stdout `error: ` line's cause, or `no message`. On
  `asyncio.CancelledError` the child is killed and awaited, and the cancellation re-raised.
- `flip_ledger_entry` is `prl_ledger_flip`'s file half: the first line opening an entry's mark
  decides; `- [ ] <id>.` becomes `- [x] <id>.` with the rest of the line kept and returns `True`;
  `[x]` or `[-]` leaves the file untouched and returns `False`. The file is replaced atomically,
  through a temporary file in its own directory and `os.replace`, with mode `0o644`. It writes the
  file only; the `ledger-flip` commit is the caller's next `commit_artifact` call.

Deliberately not covered:
- Resolving the wrapper's path: the caller's, which passes the main checkout's copy.
- Which artifact a step owes: `host/planning_hooks.py`'s.
- The wrapper's own subjects and path sets (`unit-commit-lib.sh` → `ucl_artifact`), its re-sync
  of a commit that landed with exit 1, and its push.
"""

import asyncio
import contextlib
import os
import tempfile
from pathlib import Path
from typing import Final

from devscene_flow_host.records.errors import RecordError
from devscene_flow_host.records.ledger import (
    DONE_MARK,
    OPEN_MARK,
    PLANNING_ENTRIES,
    SKIPPED_MARK,
    ledger_path,
)

COMMITTED_EXIT: Final = 0
NOTHING_TO_COMMIT_EXIT: Final = 3
_ERROR_PREFIX: Final = "error: "
_NO_MESSAGE: Final = "no message"
_LEDGER_MODE: Final = 0o644


class CommitPointError(Exception):
    """A commit point's call failed; the message is one line naming the call and its cause."""


async def commit_artifact(
    wrapper: Path,
    worktree: Path,
    kind: str,
    *,
    round_number: int | None = None,
    entry: str | None = None,
) -> bool:
    argv = [
        "bash",
        str(wrapper),
        "--repo",
        str(worktree),
        "--artifact",
        kind,
        *(["--round", str(round_number)] if round_number is not None else []),
        *(["--entry", entry] if entry is not None else []),
        "--push",
    ]
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=worktree,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await process.communicate()
    except asyncio.CancelledError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise
    rc = process.returncode
    if rc == COMMITTED_EXIT:
        return True
    if rc == NOTHING_TO_COMMIT_EXIT:
        return False
    cause = _last_error(stdout.decode("utf-8", errors="replace"))
    raise CommitPointError(f"commit-on-branch.sh --artifact {kind} exited {rc}: {cause}")


def _last_error(stdout: str) -> str:
    cause = _NO_MESSAGE
    for line in stdout.splitlines():
        if line.startswith(_ERROR_PREFIX):
            cause = line[len(_ERROR_PREFIX) :]
    return cause


def flip_ledger_entry(repo_root: Path, state_dir: str, branch: str, entry: str) -> bool:
    if entry not in PLANNING_ENTRIES:
        raise ValueError(f"flip_ledger_entry takes P1, P2 or P3, not '{entry}'")
    path = ledger_path(repo_root, state_dir, branch)
    rel = path.relative_to(repo_root).as_posix()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"the ledger '{rel}' does not exist") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None
    open_line = OPEN_MARK + f"{entry}."
    resolved_lines = (DONE_MARK + f"{entry}.", SKIPPED_MARK + f"{entry}.")
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.startswith(resolved_lines):
            return False
        if line.startswith(open_line):
            lines[index] = DONE_MARK + f"{entry}." + line[len(open_line) :]
            _replace(path, "\n".join(lines))
            return True
    raise RecordError(f"the ledger '{rel}' carries no {entry} line")


def _replace(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".progress.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(text.encode("utf-8"))
        os.chmod(temporary, _LEDGER_MODE)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise
