"""The findings files the writer's next revision carries: the host's own per-branch file.

Plays the part of `flow-walker.sh`'s `revision_findings` state key. Branch `b`'s file is
`<repo_root>/<stateDir>/.flow_walker_state/revision_findings/<quote(b, safe="")>.json`. This
module stores and reads; when the record is written or cleared is the caller's.

The rule:
- The record plays bash's one `revision_findings` key, whose last writer wins: `next`'s
  `dispatch` branch keeps `--findings` for an outcome that is not a round gate's verdict, and
  `next`'s `answer` branch keeps it with `answered`; a round's close and `start` clear it. Bash's
  `close_round` writes the closed round's files into the key; here the record is cleared instead,
  and those files are the closed round's `GateRecord` details, which the `commands` layer prints
  when the record is empty. A held outcome recorded in an open set (`record_in_set`) never
  touches it.
- Every write and clear happens while the caller holds `RefusalStore`'s lock; this module takes
  no lock of its own. `read` takes none, because `write` replaces the file whole.
- The store writes only its file and its temporary files, all inside `revision_findings/`.

Deliberately not covered:
- Rendering the record as `arg.findings_file:` or `findings_file:` lines: the `commands` layer's.
- Removing a finished branch's file.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Final
from urllib.parse import quote

from devscene_flow_host.host.store import STATE_DIRECTORY

REVISION_FINDINGS_DIRECTORY: Final = "revision_findings"
_VERSION: Final = 1
_DOCUMENT_KEYS: Final = ("version", "files")


def revision_findings_path(repo_root: Path, state_dir: str, branch: str) -> Path:
    if not branch:
        raise ValueError("a walk's branch is empty")
    return (
        repo_root
        / state_dir
        / STATE_DIRECTORY
        / REVISION_FINDINGS_DIRECTORY
        / (quote(branch, safe="") + ".json")
    )


class RevisionFindingsStore:
    """Branch `branch`'s kept findings files."""

    def __init__(self, repo_root: Path, state_dir: str, branch: str) -> None:
        self._path = revision_findings_path(repo_root, state_dir, branch)

    def read(self) -> tuple[str, ...]:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return ()
        try:
            return _decode(raw)
        except ValueError as error:
            raise ValueError(f"{self._path}: {error}") from None

    def write(self, files: tuple[str, ...]) -> None:
        document = {"version": _VERSION, "files": list(files)}
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{self._path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump(document, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


def _decode(raw: bytes) -> tuple[str, ...]:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("not valid JSON") from None
    if not isinstance(document, dict):
        raise ValueError("the document is not an object")
    for key in _DOCUMENT_KEYS:
        if key not in document:
            raise ValueError(f"the document has no {key}")
    for key in document:
        if key not in _DOCUMENT_KEYS:
            raise ValueError(f"the document has an unexpected key {json.dumps(key)}")
    version = document["version"]
    if type(version) is not int or version != _VERSION:
        raise ValueError(f"version {json.dumps(version)} is not {_VERSION}")
    files = document["files"]
    if not isinstance(files, list):
        raise ValueError("files is not a list")
    for index, item in enumerate(files):
        if not isinstance(item, str):
            raise ValueError(f"files[{index}] is not a string")
    return tuple(files)
