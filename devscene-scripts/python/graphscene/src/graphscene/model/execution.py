"""Running a node: the `Executor` protocol a host or an adapter implements, and the `NodeResult` it
returns, `Completed` or `Failed` with a `FailureClass`.

The rule:

- `run` takes one `Dispatch`. `graphscene.engine.set_execution.execute_set` fans out a
  `DispatchSet`, one `run` per gate, with at most `ExecutionLimits.max_concurrent_dispatches` runs
  concurrent on one event loop.
- `Completed.outcome` is what the caller passes to `Walker.next(outcome, node, detail)`, with
  `node` being `dispatch.node`. `Completed.detail` is passed as `detail` only for a gate of a set:
  the walk records no detail for a lone dispatch. Whether the outcome is one the node declares is
  the walk's to refuse, never the executor's to check.
- An anticipated failure is returned as a `Failed`, never raised. An exception out of `run` is a
  defect and propagates.
- The failure classes:
  - `infra`: the run failed for a reason outside the agent's own judgement, such as a crash, a
    session that ended in error, a stall the executor detected itself, or a return that was
    absent, could not be parsed, or failed the schema the executor names. Retryable for that
    node alone, a bounded number of times.
  - `agent`: the agent finished and reported that it failed.
  - `undelivered`: the run delivered nothing the executor could read at all, such as no result
    from the provider or the provider being unavailable. It says nothing about the node, so a
    re-dispatch of it is not one of the node's attempts; repeated, it is a run-level condition.
- `run` is cancellable. On `asyncio.CancelledError` it releases what it holds and re-raises, and
  never turns cancellation into a result. The limit on a run's total time is
  `ExecutionLimits.run_timeout_seconds`, set by the host and applied by
  `graphscene.engine.set_execution`, which settles an expiry as an `infra` failure. It is not an
  inactivity timeout: a stall, a session gone silent, is the executor's to detect and return as
  `Failed("infra", …)`.
- A run may be repeated for the same dispatch (a retry, an interrupt's resume), so an executor's
  side effects must be repeatable.
- Each result variant carries its discriminator as a `ClassVar[Literal[...]]` named `kind`, as
  `graphscene.model.walk_actions` does.

Deliberately not covered:

- Sandboxing, permission modes and allowed tools: the host passes them in when it constructs its
  executor, and `run` carries none.
- A helper for a synchronous executor: none is offered. A blocking implementation wraps its work
  with `await asyncio.to_thread(…)`, and a cancelled `to_thread` call does not stop its thread.
- What is done with each failure class: `graphscene.engine.attempts`, `graphscene.engine.breaker`
  and `graphscene.engine.set_execution`.
- Driving a walk with an executor: graphscene.engine.run_loop.
"""

from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, TypeAlias

from graphscene.model.walk_actions import Dispatch

FailureClass: TypeAlias = Literal["infra", "agent", "undelivered"]


@dataclass(frozen=True)
class Completed:
    kind: ClassVar[Literal["completed"]] = "completed"
    outcome: str
    detail: str | None = None


@dataclass(frozen=True)
class Failed:
    kind: ClassVar[Literal["failed"]] = "failed"
    failure: FailureClass
    reason: str


NodeResult: TypeAlias = Completed | Failed


class Executor(Protocol):
    """Runs one dispatched node and returns its result, under this module's rule."""

    async def run(self, dispatch: Dispatch) -> NodeResult: ...
