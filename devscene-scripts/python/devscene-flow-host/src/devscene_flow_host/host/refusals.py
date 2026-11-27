"""A round's reviewer-file refusals: the host's own per-branch file beside the walk.

Plays the part of `flow-walker.sh`'s `round.refused.<gate>`, `round.refusal.<gate>` and
`round.redo.<gate>` state keys (`refuse_round_file`, `refused_line`, `refusals_spent`), plus the
`refused:` lines the last printed step carried. Branch `b`'s file is
`<repo_root>/<stateDir>/.flow_walker_state/round_refusals/<quote(b, safe="")>.json`. This module
stores and reads; when a refusal is counted, re-dispatched or held is the caller's.

The rule:
- A count applies only to the round and round number it was recorded for: `read` for another
  round or number returns the empty record, carrying only the file's `announced`.
- Every caller that records a gate takes `lock()` before the walk's own lock and never inside it,
  so the two locks cannot deadlock.
- The file is position, never a record: a lost or stale file costs at most two extra
  re-dispatches, never a wrong route.
- The store writes only its file, `<file>.lock` and its temporary files, all inside
  `round_refusals/`.

Deliberately not covered:
- A crash between this file's write and the walk's write: the count is left one step behind.
- Removing a finished branch's file.
"""

import contextlib
import fcntl
import json
import os
import tempfile
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final
from urllib.parse import quote

from devscene_flow_host.host.store import STATE_DIRECTORY

ROUND_FILE_ATTEMPTS: Final = 3
REFUSALS_DIRECTORY: Final = "round_refusals"
_VERSION: Final = 1
_POLL_SECONDS: Final = 0.1
_DOCUMENT_KEYS: Final = ("version", "round", "number", "gates", "announced")
_GATE_KEYS: Final = ("attempts", "reason", "redo")
_REFUSAL_KEYS: Final = ("gate", "attempt", "reason")


@dataclass(frozen=True)
class Refusal:
    """One `refused: <gate> attempt <attempt> of 3: <reason>` line's content."""

    gate: str
    attempt: int
    reason: str


@dataclass(frozen=True)
class GateRefusals:
    attempts: int
    reason: str
    redo: bool


@dataclass(frozen=True)
class RoundRefusals:
    """`announced` holds the refusals the last step written carried."""

    round: str
    number: int
    gates: Mapping[str, GateRefusals]
    announced: tuple[Refusal, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "gates", MappingProxyType(dict(self.gates)))

    @classmethod
    def empty(cls, round: str, number: int) -> "RoundRefusals":
        return cls(round=round, number=number, gates={}, announced=())

    def refusal(self, gate: str) -> Refusal:
        recorded = self.gates[gate]
        return Refusal(gate=gate, attempt=recorded.attempts, reason=recorded.reason)


def refusals_path(repo_root: Path, state_dir: str, branch: str) -> Path:
    if not branch:
        raise ValueError("a walk's branch is empty")
    return (
        repo_root
        / state_dir
        / STATE_DIRECTORY
        / REFUSALS_DIRECTORY
        / (quote(branch, safe="") + ".json")
    )


class RefusalStore:
    """Branch `branch`'s refusal file, behind the exclusive lock `<file>.lock`."""

    def __init__(
        self, repo_root: Path, state_dir: str, branch: str, *, lock_timeout: float = 120.0
    ) -> None:
        self._path = refusals_path(repo_root, state_dir, branch)
        self._lock_path = self._path.with_name(self._path.name + ".lock")
        self._lock_timeout = lock_timeout

    def read(self, round: str, number: int) -> RoundRefusals:
        stored = self._load()
        if stored is None:
            return RoundRefusals.empty(round, number)
        if stored.round != round or stored.number != number:
            return RoundRefusals(round=round, number=number, gates={}, announced=stored.announced)
        return stored

    def read_announced(self) -> tuple[Refusal, ...]:
        stored = self._load()
        return () if stored is None else stored.announced

    def write(self, refusals: RoundRefusals) -> None:
        document = {
            "version": _VERSION,
            "round": refusals.round,
            "number": refusals.number,
            "gates": {
                gate: {"attempts": entry.attempts, "reason": entry.reason, "redo": entry.redo}
                for gate, entry in refusals.gates.items()
            },
            "announced": [
                {"gate": item.gate, "attempt": item.attempt, "reason": item.reason}
                for item in refusals.announced
            ],
        }
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

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
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
                            f"cannot lock {self._lock_path} within {self._lock_timeout} s"
                        ) from None
                    time.sleep(_POLL_SECONDS)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def _load(self) -> RoundRefusals | None:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            return _decode(raw)
        except ValueError as error:
            raise ValueError(f"{self._path}: {error}") from None


def _decode(raw: bytes) -> RoundRefusals:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("not valid JSON") from None
    fields = _fields(document, _DOCUMENT_KEYS, "the document")
    version = fields["version"]
    if type(version) is not int or version != _VERSION:
        raise ValueError(f"version {json.dumps(version)} is not {_VERSION}")
    round = _string(fields["round"], "round")
    number = _integer(fields["number"], "number")
    gates = fields["gates"]
    if not isinstance(gates, dict):
        raise ValueError("gates is not an object")
    announced = fields["announced"]
    if not isinstance(announced, list):
        raise ValueError("announced is not a list")
    return RoundRefusals(
        round=round,
        number=number,
        gates={gate: _gate(entry, f"gates.{gate}") for gate, entry in gates.items()},
        announced=tuple(
            _refusal(item, f"announced[{index}]") for index, item in enumerate(announced)
        ),
    )


def _gate(value: object, where: str) -> GateRefusals:
    fields = _fields(value, _GATE_KEYS, where)
    redo = fields["redo"]
    if not isinstance(redo, bool):
        raise ValueError(f"{where}.redo is not a boolean")
    return GateRefusals(
        attempts=_integer(fields["attempts"], f"{where}.attempts"),
        reason=_string(fields["reason"], f"{where}.reason"),
        redo=redo,
    )


def _refusal(value: object, where: str) -> Refusal:
    fields = _fields(value, _REFUSAL_KEYS, where)
    return Refusal(
        gate=_string(fields["gate"], f"{where}.gate"),
        attempt=_integer(fields["attempt"], f"{where}.attempt"),
        reason=_string(fields["reason"], f"{where}.reason"),
    )


def _fields(value: object, keys: tuple[str, ...], where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{where} is not an object")
    for key in keys:
        if key not in value:
            raise ValueError(f"{where} has no {key}")
    for key in value:
        if key not in keys:
            raise ValueError(f"{where} has an unexpected key {json.dumps(key)}")
    return value


def _integer(value: object, where: str) -> int:
    # A JSON `true` decodes to a `bool`, which is an `int` subclass.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} is not an integer")
    return value


def _string(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where} is not a string")
    return value
