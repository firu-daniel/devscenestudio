"""`StubExecutor`, the built-in `graphscene.model.execution.Executor` for tests, and the script
types it runs: `ScriptedOutcome`, `ScriptedFailure` and `ScriptedStall`, together `Scripted`.

The rule:

- The script is copied at construction into one queue per node id, so a later change to the
  caller's mapping or sequences changes nothing. Each `run` takes the next entry of its node's
  queue, so a repeated dispatch (a retry, a resume) takes the next entry; a node with no entry
  left raises `LookupError`, a mistake in the test's script rather than a node failure.
- `started` holds node ids in the order `run` was called, `finished` in the order a run returned
  a result, and `cancelled` those whose run was cancelled. Concurrent runs on one event loop share
  one record with no lock, because the loop runs one coroutine at a time between awaits.
- An outcome or a failure is returned after its `delay`, in seconds.
- A stall ends only by cancellation.
- On `asyncio.CancelledError`, during a delay or a stall, the node is recorded in `cancelled` and
  the error re-raised, never turned into a result: the deadline is the caller's, per
  `graphscene.model.execution`.

Deliberately not covered:

- Asserting a delay against the wall clock: order is observable only through the record.
- Structured return documents: a script holds results, not documents.
- Running in a thread or a process.
"""

import asyncio
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from graphscene.model.execution import Completed, Failed, FailureClass, NodeResult
from graphscene.model.walk_actions import Dispatch


def _check_delay(owner: object, delay: float) -> None:
    if not delay >= 0:
        raise ValueError(f"{type(owner).__name__}: delay must be >= 0, got {delay}")


@dataclass(frozen=True)
class ScriptedOutcome:
    outcome: str
    detail: str | None = None
    delay: float = 0.0

    def __post_init__(self) -> None:
        _check_delay(self, self.delay)


@dataclass(frozen=True)
class ScriptedFailure:
    failure: FailureClass
    reason: str
    delay: float = 0.0

    def __post_init__(self) -> None:
        _check_delay(self, self.delay)


@dataclass(frozen=True)
class ScriptedStall:
    pass


Scripted: TypeAlias = ScriptedOutcome | ScriptedFailure | ScriptedStall


class StubExecutor:
    """Runs each dispatched node from its script, under this module's rule."""

    def __init__(self, script: Mapping[str, Sequence[Scripted]]) -> None:
        self._queues: dict[str, deque[Scripted]] = {
            node: deque(entries) for node, entries in script.items()
        }
        self._started: list[str] = []
        self._finished: list[str] = []
        self._cancelled: list[str] = []

    @property
    def started(self) -> tuple[str, ...]:
        return tuple(self._started)

    @property
    def finished(self) -> tuple[str, ...]:
        return tuple(self._finished)

    @property
    def cancelled(self) -> tuple[str, ...]:
        return tuple(self._cancelled)

    async def run(self, dispatch: Dispatch) -> NodeResult:
        node = dispatch.node
        self._started.append(node)
        queue = self._queues.get(node)
        if not queue:
            raise LookupError(f"{node}: the stub has no scripted run left")
        entry = queue.popleft()
        try:
            result = await _play(entry)
        except asyncio.CancelledError:
            self._cancelled.append(node)
            raise
        self._finished.append(node)
        return result


async def _play(entry: Scripted) -> NodeResult:
    if isinstance(entry, ScriptedStall):
        await asyncio.Event().wait()
        raise AssertionError("unreachable: a stall's event is never set")
    await asyncio.sleep(entry.delay)
    if isinstance(entry, ScriptedOutcome):
        return Completed(entry.outcome, entry.detail)
    return Failed(entry.failure, entry.reason)
