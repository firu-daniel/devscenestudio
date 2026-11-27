"""The plain types and host protocols the execution rules compute over: the host-supplied
`ExecutionLimits`, the `RunSignals`, `DispatchCounter` and `LaunchSink` protocols, the `Launch`
observation row, the run-level `Halt`, a node's `NodeRecord`, its `Settlement` (`Recorded`, `Retry`
or `Redispatch`), the `SetResult` of one executed set and the `RunExit`, what a run of a walk ends
on.

The rule:

- The limits are the host's to pass. The defaults in `ExecutionLimits` are GraphScene's, not any
  host's constants, and a value out of range is refused with `ValueError`.
- `max_concurrent_dispatches` is how many runs of one set are in flight at once, applied by
  `graphscene.engine.set_execution`. The graph format sets no limit.
- An `undelivered` result's re-dispatch uses up no attempt: `Redispatch` carries no attempt number.
- A halt is returned as a `Halt`, never raised.
- `NodeResult` carries no usage. A host joins usage to a `Launch` from its own executor's usage
  sink.
- Each variant carries its discriminator as a `ClassVar[Literal[...]]` named `kind`, as
  `graphscene.model.walk_actions` does.

Deliberately not covered:

- Where STOP and PAUSE live: the host's, answered through `RunSignals`.
- What the dispatch counter counts across runs and where it is kept, and where a `Launch` row is
  written: the host's, through `DispatchCounter` and `LaunchSink`.
- Driving a walk with these: graphscene.engine.run_loop (start_run, continue_run).
"""

from dataclasses import dataclass
from typing import ClassVar, Literal, NoReturn, Protocol, TypeAlias

from graphscene.model.execution import NodeResult
from graphscene.model.walk_actions import End, Interrupt, Refused, Stop

HaltReason: TypeAlias = Literal["stop", "pause", "cap", "undelivered"]


@dataclass(frozen=True)
class ExecutionLimits:
    max_attempts: int = 3
    backoff_seconds: float = 60.0
    dispatch_cap: int | None = None
    run_timeout_seconds: float | None = None
    max_concurrent_dispatches: int = 10

    def __post_init__(self) -> None:
        if not self.max_attempts >= 1:
            _refuse("max_attempts", ">= 1", self.max_attempts)
        if not self.backoff_seconds >= 0:
            _refuse("backoff_seconds", ">= 0", self.backoff_seconds)
        if self.dispatch_cap is not None and not self.dispatch_cap >= 1:
            _refuse("dispatch_cap", ">= 1", self.dispatch_cap)
        if self.run_timeout_seconds is not None and not self.run_timeout_seconds > 0:
            _refuse("run_timeout_seconds", "> 0", self.run_timeout_seconds)
        if not self.max_concurrent_dispatches >= 1:
            _refuse("max_concurrent_dispatches", ">= 1", self.max_concurrent_dispatches)


def _refuse(field: str, condition: str, value: object) -> NoReturn:
    raise ValueError(f"ExecutionLimits: {field} must be {condition}, got {value}")


class RunSignals(Protocol):
    """Answers whether the host has asked the run to stop or to pause."""

    def stop_requested(self) -> bool: ...

    def pause_requested(self) -> bool: ...


class DispatchCounter(Protocol):
    """Counts the sessions launched; `increment` counts one launch and returns the new total."""

    def total(self) -> int: ...

    def increment(self) -> int: ...


@dataclass(frozen=True)
class Launch:
    seq: int
    node: str
    agent: str
    attempt: int
    max_attempts: int
    result: NodeResult


class LaunchSink(Protocol):
    """Receives one `Launch` row per session launched whose run returned a result."""

    def record(self, launch: Launch) -> None: ...


@dataclass(frozen=True)
class Halt:
    kind: ClassVar[Literal["halt"]] = "halt"
    reason: HaltReason
    detail: str


@dataclass(frozen=True)
class NodeRecord:
    """The arguments a caller passes to `Walker.next(outcome, node, detail)`."""

    node: str
    outcome: str
    detail: str | None


@dataclass(frozen=True)
class Recorded:
    kind: ClassVar[Literal["recorded"]] = "recorded"
    record: NodeRecord


@dataclass(frozen=True)
class Retry:
    """`attempt` is the attempt number the re-dispatch will be."""

    kind: ClassVar[Literal["retry"]] = "retry"
    node: str
    attempt: int
    reason: str


@dataclass(frozen=True)
class Redispatch:
    kind: ClassVar[Literal["redispatch"]] = "redispatch"
    node: str
    reason: str


Settlement: TypeAlias = Recorded | Retry | Redispatch


@dataclass(frozen=True)
class SetResult:
    records: tuple[NodeRecord, ...]
    halt: Halt | None


RunExit: TypeAlias = End | Stop | Interrupt | Halt | Refused
