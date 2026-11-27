"""Where a branch's walk is saved: GraphScene's own `FileStateStore`, one file per branch.

The rule: branch `b`'s walk is the file `<repo_root>/<stateDir>/.flow_walker_state/<quote(b,
safe="")>.json`. The branch is percent-encoded with no safe character, so the encoding is
injective and a `/` never makes a subdirectory. Everything the store writes — the state file, its
`.lock` sibling and `FileStateStore`'s temporary files — stays inside
`<stateDir>/.flow_walker_state/`.

Deliberately not covered:
- Two branch names that differ only in case, on a case-insensitive filesystem: they share a file.
- Removing a finished branch's file.
- A flat file already at `<stateDir>/.flow_walker_state`, the retired bash walker's: the first
  write or lock raises an `OSError`, which propagates unchanged. `flow-walker.sh` removes such a
  file before this command runs.
"""

from pathlib import Path
from typing import Final
from urllib.parse import quote

from graphscene import FileStateStore

STATE_DIRECTORY: Final = ".flow_walker_state"


def walk_state_path(repo_root: Path, state_dir: str, branch: str) -> Path:
    if not branch:
        raise ValueError("a walk's branch is empty")
    return repo_root / state_dir / STATE_DIRECTORY / (quote(branch, safe="") + ".json")


def walk_store(
    repo_root: Path, state_dir: str, branch: str, *, lock_timeout: float = 120.0
) -> FileStateStore:
    return FileStateStore(walk_state_path(repo_root, state_dir, branch), lock_timeout=lock_timeout)
