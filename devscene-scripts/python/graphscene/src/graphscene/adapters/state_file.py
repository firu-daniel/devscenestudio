"""`FileStateStore`, the `graphscene.model.walk_state.StateStore` that keeps a walk's state in one
JSON file at a path the caller names, encoded by `graphscene.adapters.walk_json`.

The rule:

- The store writes only the state file and its sibling lock file `<name>.lock`.
- `write` goes through a temporary file in the same directory and `os.replace`, so a `read`
  taken without the lock sees the old document or the new one, never a torn one.
- `lock` is `fcntl.flock(LOCK_EX | LOCK_NB)` on the lock file, polled every 0.1 s until
  `lock_timeout` seconds have passed, then `TimeoutError` naming the lock file.
- The lock is released and its descriptor closed in a `finally`.

Deliberately not covered:

- Platforms without `fcntl`.
- A lock file left behind: it is harmless, because a `flock` dies with its process.
"""

import contextlib
import fcntl
import os
import pathlib
import tempfile
import time
from collections.abc import Iterator

from graphscene.adapters.walk_json import state_from_json, state_to_json
from graphscene.model.walk_state import WalkState

_POLL_SECONDS = 0.1


class FileStateStore:
    """A walk's state in the file at `path`, behind the exclusive lock `<path>.lock`."""

    def __init__(self, path: pathlib.Path, *, lock_timeout: float = 120.0) -> None:
        self._path = path
        self._lock_path = path.with_name(path.name + ".lock")
        self._lock_timeout = lock_timeout

    def read(self) -> WalkState | None:
        """Return the saved state, or `None` when the file does not exist."""
        try:
            data = self._path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            return state_from_json(data.decode("utf-8"))
        except ValueError as error:
            raise ValueError(f"{self._path}: {error}") from error

    def write(self, state: WalkState) -> None:
        """Replace the file with `state`'s document, atomically."""
        text = state_to_json(state)
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
        temporary = pathlib.Path(handle.name)
        try:
            with handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        """Hold the exclusive lock for the body of the `with` block."""
        # A fresh open on every call is a separate open file description, so two threads of one
        # process exclude each other as two processes do.
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            deadline = time.monotonic() + self._lock_timeout
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"{self._lock_path}: not acquired within {self._lock_timeout} s"
                        ) from None
                    time.sleep(_POLL_SECONDS)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
