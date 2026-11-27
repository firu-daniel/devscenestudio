"""Running one dispatch set under the execution rules: `execute_set`, which fans a set out through
the caller's `Executor`, settles each result through `AttemptBook` and re-dispatches what the
rules send back, returning a `SetResult`.

The rule:

- Every pass, the first being the whole set, is cleared by `clear_set` before anything of it goes
  out; a `Halt` from it is returned with the records settled so far, and nothing of that pass is
  launched.
- Each dispatch of a cleared pass starts in set order, at most
  `ExecutionLimits.max_concurrent_dispatches` at once; the next one starts as soon as a running one
  finishes, after the results found finished with it are handled. A dispatch takes its
  `Launch.seq` from `DispatchCounter.increment` and its attempt from `AttemptBook.attempt` when it
  starts, never when its pass is cleared.
- The whole of a cleared pass goes out: a STOP or PAUSE raised while a pass runs holds back none of
  its queued dispatches and is honoured by `clear_set` at the next pass.
- With `ExecutionLimits.run_timeout_seconds` set, each run's total time is under that deadline,
  which runs from the run's start and never counts the wait for a slot; a run that passes it is
  cancelled and becomes `Failed("infra", "timed out: no result within <run_timeout_seconds>s")`.
  A timeout is an `infra` failure.
- With `before_dispatch` given, each dispatch that starts awaits
  `before_dispatch(BeforeDispatch(dispatch, seq, attempt))` after taking its `seq` and attempt,
  inside its own task, before `Executor.run` and outside the `run_timeout_seconds` deadline, so a
  hook's time never counts against the run. It is awaited once per attempt: a retried or
  redispatched node awaits it again with its new `seq` and attempt.
- Results are handled in finish order; runs found finished together are taken in set order. Each
  writes one `Launch` row to the `LaunchSink` and is settled: a `Recorded` from a `Completed` joins
  the outcomes, a `Recorded` from a `Failed` joins the held failures, and a `Retry` or `Redispatch`
  sends its node to the next pass.
- A failing node never cancels a sibling; a pass ends when every run of it has finished.
- After a pass that had a `Redispatch`, `UndeliveredBreaker.observe(True)` is called, and once the
  breaker is tripped `Halt("undelivered", "<strikes> consecutive sets had an undelivered result")`
  is returned; its limit is the breaker's own. A pass whose every node was recorded calls
  `observe(False)`. A pass with a `Retry` and no `Redispatch` leaves the breaker unchanged: an
  infrastructure retry counts neither towards the strikes nor as a delivered set
  (`docs/flow-graph-walker.md` → `### How each runs a parallel round` → **Cost.**).
- The next pass is the retried and redispatched nodes' original `Dispatch` objects, together, in
  set order, after `ExecutionLimits.backoff_seconds` when it is above 0.
- `SetResult.records` is always the outcomes, then the held failures, each in finish order.
- If `execute_set` is cancelled, it cancels its outstanding runs, awaits them and re-raises.
- An exception out of `Executor.run` or `before_dispatch` is a defect: the outstanding runs are
  cancelled and awaited, then it propagates. A dispatch whose hook raised runs no `Executor.run`
  and writes no `Launch` row, though it has taken its `seq`.
- On either, a dispatch not yet started is never started: it takes no `seq` and writes no row.

Deliberately not covered:

- Recording the records through the walker, and acting on a `Halt`: the caller's.
- Persisting the book, the breaker and the counter across processes: the host's.
- Usage: the host's, through its executor's usage sink.
- Detecting a stalled (inactive) session: the executor's, since only the executor sees the
  session's activity, and it returns that stall as `Failed("infra", …)` (#421).
- A `Launch` row for a run cancelled because `execute_set` was cancelled or another run raised:
  such a run has taken its `seq` from `DispatchCounter.increment` but returns no `NodeResult`,
  so it writes no row.
- Recording the records through the walker and driving the walk: graphscene.engine.run_loop.
- Which hooks a node runs, and every hook other than the `before_dispatch` call: the caller's
  (graphscene.engine.run_loop).
"""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Sequence

from graphscene.engine.attempts import AttemptBook
from graphscene.engine.breaker import UndeliveredBreaker
from graphscene.engine.safety import clear_set
from graphscene.model.execution import Completed, Executor, Failed, NodeResult
from graphscene.model.hooks import BeforeDispatch
from graphscene.model.run_control import (
    DispatchCounter,
    ExecutionLimits,
    Halt,
    Launch,
    LaunchSink,
    NodeRecord,
    Recorded,
    RunSignals,
    SetResult,
)
from graphscene.model.walk_actions import Dispatch


async def execute_set(
    dispatches: Sequence[Dispatch],
    executor: Executor,
    *,
    signals: RunSignals,
    counter: DispatchCounter,
    sink: LaunchSink,
    book: AttemptBook,
    breaker: UndeliveredBreaker,
    limits: ExecutionLimits,
    failure_outcome: str,
    before_dispatch: Callable[[BeforeDispatch], Awaitable[None]] | None = None,
) -> SetResult:
    outcomes: list[NodeRecord] = []
    held: list[NodeRecord] = []
    current: tuple[Dispatch, ...] = tuple(dispatches)
    while True:
        halt = clear_set(current, signals, counter, limits)
        if halt is not None:
            return SetResult((*outcomes, *held), halt)
        again, undelivered = await _run_pass(
            current,
            executor,
            counter,
            sink,
            book,
            limits,
            failure_outcome,
            outcomes,
            held,
            before_dispatch,
        )
        if undelivered:
            breaker.observe(True)
            if breaker.tripped:
                detail = f"{breaker.strikes} consecutive sets had an undelivered result"
                return SetResult((*outcomes, *held), Halt("undelivered", detail))
        elif not again:
            breaker.observe(False)
        current = tuple(d for d in current if d.node in again)
        if not current:
            return SetResult((*outcomes, *held), None)
        if limits.backoff_seconds > 0:
            await asyncio.sleep(limits.backoff_seconds)


async def _run_pass(
    current: tuple[Dispatch, ...],
    executor: Executor,
    counter: DispatchCounter,
    sink: LaunchSink,
    book: AttemptBook,
    limits: ExecutionLimits,
    failure_outcome: str,
    outcomes: list[NodeRecord],
    held: list[NodeRecord],
    before_dispatch: Callable[[BeforeDispatch], Awaitable[None]] | None,
) -> tuple[set[str], bool]:
    again: set[str] = set()
    undelivered = False
    queued: deque[Dispatch] = deque(current)
    launched: dict[asyncio.Task[NodeResult], tuple[Dispatch, int, int]] = {}
    outstanding: set[asyncio.Task[NodeResult]] = set()
    try:
        while True:
            while queued and len(outstanding) < limits.max_concurrent_dispatches:
                dispatch = queued.popleft()
                seq = counter.increment()
                attempt = book.attempt(dispatch.node)
                task = asyncio.create_task(
                    _run(
                        executor,
                        dispatch,
                        seq,
                        attempt,
                        limits.run_timeout_seconds,
                        before_dispatch,
                    )
                )
                launched[task] = (dispatch, seq, attempt)
                outstanding.add(task)
            if not outstanding:
                break
            done, outstanding = await asyncio.wait(outstanding, return_when=asyncio.FIRST_COMPLETED)
            for task in [t for t in launched if t in done]:
                dispatch, seq, attempt = launched[task]
                result = task.result()
                sink.record(
                    Launch(seq, dispatch.node, dispatch.agent, attempt, limits.max_attempts, result)
                )
                settlement = book.settle(dispatch.node, result, limits, failure_outcome)
                if isinstance(settlement, Recorded):
                    (outcomes if isinstance(result, Completed) else held).append(settlement.record)
                else:
                    again.add(settlement.node)
                    if settlement.kind == "redispatch":
                        undelivered = True
    except BaseException:
        for task in launched:
            task.cancel()
        await asyncio.gather(*launched, return_exceptions=True)
        raise
    return again, undelivered


async def _run(
    executor: Executor,
    dispatch: Dispatch,
    seq: int,
    attempt: int,
    run_timeout_seconds: float | None,
    before_dispatch: Callable[[BeforeDispatch], Awaitable[None]] | None,
) -> NodeResult:
    if before_dispatch is not None:
        await before_dispatch(BeforeDispatch(dispatch, seq, attempt))
    if run_timeout_seconds is None:
        return await executor.run(dispatch)
    deadline = asyncio.timeout(run_timeout_seconds)
    try:
        async with deadline:
            return await executor.run(dispatch)
    except TimeoutError:
        if not deadline.expired():
            raise
        return Failed("infra", f"timed out: no result within {run_timeout_seconds}s")
