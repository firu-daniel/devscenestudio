"""Run mode's engine: `start_run` and `continue_run`, which drive a walk through the caller's
`Executor` until it reaches a `RunExit`.

The rule:

- Each call constructs its own `AttemptBook` and `UndeliveredBreaker(undelivered_limit)` before
  touching the walker, so a limit below 1 raises the breaker's `ValueError` with the store unread
  and unwritten.
- `start_run` takes its first step from `Walker.start(entry, resume=resume)`; `continue_run` from
  `Walker.next(outcome)` when `outcome` is given (resuming a graph `Interrupt` with its
  `resume_outcome`), otherwise from `Walker.current()` (continuing after a `Halt` or a crash).
- Every walker call runs through `asyncio.to_thread`, so the `StateStore` is never called on the
  event loop's thread.
- A `Dispatch` runs as a set of one, a `DispatchSet` as its `dispatches`, each through
  `execute_set`. A `Wait` is never dispatched: `Walker.current()`, the set of gates still out, is
  taken in its place, and if that is itself a `Wait` the call returns `Refused("the saved walk's
  pending action is a wait, which names no dispatch")`. An `End`, `Stop`, `Interrupt` or
  `Refused` is returned.
- After `execute_set`, every record of its `SetResult` is recorded through `Walker.next`, in order:
  a gate of a set as `(outcome, node, detail)`, a lone dispatch as `(outcome, node)` with no
  detail, because the walk records a detail only for a gate and the host already has it in the
  `Launch` row. A refusal does not stop the remaining records from being recorded.
- Then the first `Refused` is returned if any record was refused; otherwise the `SetResult.halt`
  if set; otherwise the last record's step is the next step.
- A `StateStore` error and an exception out of `Executor.run` propagate unchanged.
- On `asyncio.CancelledError` during `execute_set`, that call cancels and awaits its runs and the
  loop re-raises, recording nothing of that set. During a walker call, the thread finishes its
  call and the loop re-raises: the saved walk is what a later `continue_run` reads.
- Hooks run through the `hooks` host. After the book and the breaker and before any walker call,
  each call walks `walker.graph.nodes` in key order, and within a node its `before` names, then
  its `after` names, and raises `ValueError` with the store unread and unwritten: with `hooks`
  `None`, for the first name, `the graph names hook '<name>' and no hook host was given`;
  otherwise for the first name `hooks.provides` refuses, `the graph names hook '<name>', which
  the hook host does not provide`. A graph naming no hook runs whatever `hooks` is.
- A step is taken when it is the call's first step, the `current` step taken in place of a
  `Wait`, or the last record's step once no record was refused and the `SetResult` has no halt. A
  `Wait` and a `Refused` are never taken. Taking a step, before the loop acts on it, runs: for
  each `RoundPassage` in its `passed`, in order, that round node's after-hooks with
  `AfterRound(passage, step)`; then, for a `DispatchSet`, its round node's before-hooks with
  `BeforeRound(dispatch_set)`; for an `End`, its terminal node's before-hooks with
  `BeforeEnd(end)`.
- `execute_set` is given a `before_dispatch` running the dispatched node's before-hooks with the
  `BeforeDispatch` it receives, once per attempt; `None` when no dispatch node declares `before`.
- After each record is recorded through `Walker.next`, unless the step returned is `Refused`, the
  recorded node's after-hooks run with `AfterDispatch(record, step)`, before the next record is
  recorded.
- Each node's hooks run in declared order, awaited one at a time on the loop's thread, in the
  order above.
- An exception out of a hook propagates unchanged, and what the walker saved stays saved: a later
  `continue_run` takes `current` again, re-running that step's round after-hooks and
  before-hooks, and never re-runs a dispatch's after-hooks for a record already saved.

Deliberately not covered:

- Keeping the walk, the dispatch total and anything else across a pause, a stop or a crash: the
  host's, through its `StateStore` and `DispatchCounter`.
- A helper for a synchronous executor: `graphscene.model.execution` is the guidance.
- Offloading the synchronous host protocols `RunSignals`, `DispatchCounter` and `LaunchSink`: they
  are called on the loop thread, and the host keeps them fast.
- An inactivity timeout: the executor's (#421).
- A deadline of the loop's own: it has none. The only time limit is `run_timeout_seconds`,
  applied by `execute_set`.
- What a hook does: the host's.
- Hooks in step mode: `Walker` runs none.
- Re-running a dispatch after-hook lost to a crash after its record was saved: a host that must
  not lose one makes it re-derivable from what `current` returns, as the harness's round and
  ledger hooks are.
"""

import asyncio
from collections.abc import Awaitable, Callable

from graphscene.engine.attempts import AttemptBook
from graphscene.engine.breaker import UndeliveredBreaker
from graphscene.engine.set_execution import execute_set
from graphscene.engine.walker import Walker
from graphscene.model.execution import Executor
from graphscene.model.flow_graph import DispatchNode, FlowGraph, Node, RoundNode, TerminalNode
from graphscene.model.hooks import (
    AfterDispatch,
    AfterRound,
    BeforeDispatch,
    BeforeEnd,
    BeforeRound,
    HookCall,
    HookHost,
)
from graphscene.model.run_control import (
    DispatchCounter,
    ExecutionLimits,
    LaunchSink,
    RunExit,
    RunSignals,
)
from graphscene.model.walk_actions import (
    Action,
    Dispatch,
    DispatchSet,
    End,
    Refused,
    RoundPassage,
    Step,
    Wait,
)
from graphscene.model.walk_state import RoundResume


async def start_run(
    walker: Walker,
    executor: Executor,
    *,
    signals: RunSignals,
    counter: DispatchCounter,
    sink: LaunchSink,
    limits: ExecutionLimits,
    failure_outcome: str,
    undelivered_limit: int = 3,
    entry: str | None = None,
    resume: RoundResume | None = None,
    hooks: HookHost | None = None,
) -> RunExit:
    book = AttemptBook()
    breaker = UndeliveredBreaker(undelivered_limit)
    _refuse_unprovided(walker.graph, hooks)
    step = await asyncio.to_thread(walker.start, entry, resume=resume)
    return await _drive(
        walker,
        executor,
        step,
        signals,
        counter,
        sink,
        book,
        breaker,
        limits,
        failure_outcome,
        hooks,
    )


async def continue_run(
    walker: Walker,
    executor: Executor,
    *,
    signals: RunSignals,
    counter: DispatchCounter,
    sink: LaunchSink,
    limits: ExecutionLimits,
    failure_outcome: str,
    undelivered_limit: int = 3,
    outcome: str | None = None,
    hooks: HookHost | None = None,
) -> RunExit:
    book = AttemptBook()
    breaker = UndeliveredBreaker(undelivered_limit)
    _refuse_unprovided(walker.graph, hooks)
    if outcome is None:
        step = await asyncio.to_thread(walker.current)
    else:
        step = await asyncio.to_thread(walker.next, outcome)
    return await _drive(
        walker,
        executor,
        step,
        signals,
        counter,
        sink,
        book,
        breaker,
        limits,
        failure_outcome,
        hooks,
    )


def _before(node: Node | None) -> tuple[str, ...]:
    return (node.before or ()) if node is not None else ()


def _after(node: Node | None) -> tuple[str, ...]:
    if isinstance(node, TerminalNode) or node is None:
        return ()
    return node.after or ()


def _refuse_unprovided(graph: FlowGraph, hooks: HookHost | None) -> None:
    asked: set[str] = set()
    for node in graph.nodes.values():
        for name in (*_before(node), *_after(node)):
            if hooks is None:
                raise ValueError(f"the graph names hook '{name}' and no hook host was given")
            if name in asked:
                continue
            asked.add(name)
            if not hooks.provides(name):
                raise ValueError(
                    f"the graph names hook '{name}', which the hook host does not provide"
                )


async def _run_hooks(hooks: HookHost | None, names: tuple[str, ...], call: HookCall) -> None:
    for name in names:
        # `_refuse_unprovided` let no named hook through without a host.
        assert hooks is not None
        await hooks.run(name, call)


async def _take(graph: FlowGraph, hooks: HookHost | None, step: Action) -> None:
    for passage in step.passed if not isinstance(step, Wait) else ():
        if isinstance(passage, RoundPassage):
            node = graph.nodes.get(passage.round)
            if isinstance(node, RoundNode):
                await _run_hooks(hooks, _after(node), AfterRound(passage, step))
    if isinstance(step, DispatchSet):
        await _run_hooks(hooks, _before(graph.nodes.get(step.round)), BeforeRound(step))
    elif isinstance(step, End):
        await _run_hooks(hooks, _before(graph.nodes.get(step.node)), BeforeEnd(step))


def _before_dispatch(
    graph: FlowGraph, hooks: HookHost | None
) -> Callable[[BeforeDispatch], Awaitable[None]] | None:
    if not any(isinstance(n, DispatchNode) and n.before for n in graph.nodes.values()):
        return None

    async def run(call: BeforeDispatch) -> None:
        await _run_hooks(hooks, _before(graph.nodes.get(call.dispatch.node)), call)

    return run


async def _drive(
    walker: Walker,
    executor: Executor,
    step: Step,
    signals: RunSignals,
    counter: DispatchCounter,
    sink: LaunchSink,
    book: AttemptBook,
    breaker: UndeliveredBreaker,
    limits: ExecutionLimits,
    failure_outcome: str,
    hooks: HookHost | None,
) -> RunExit:
    graph = walker.graph
    before_dispatch = _before_dispatch(graph, hooks)
    while True:
        if isinstance(step, Wait):
            step = await asyncio.to_thread(walker.current)
            if isinstance(step, Wait):
                return Refused("the saved walk's pending action is a wait, which names no dispatch")
        if isinstance(step, Refused):
            return step
        await _take(graph, hooks, step)
        if isinstance(step, Dispatch):
            dispatches: tuple[Dispatch, ...] = (step,)
            is_set = False
        elif isinstance(step, DispatchSet):
            dispatches = step.dispatches
            is_set = True
        else:
            return step
        result = await execute_set(
            dispatches,
            executor,
            signals=signals,
            counter=counter,
            sink=sink,
            book=book,
            breaker=breaker,
            limits=limits,
            failure_outcome=failure_outcome,
            before_dispatch=before_dispatch,
        )
        last: Step | None = None
        refused: Refused | None = None
        for record in result.records:
            detail = record.detail if is_set else None
            last = await asyncio.to_thread(walker.next, record.outcome, record.node, detail)
            if isinstance(last, Refused):
                if refused is None:
                    refused = last
                continue
            await _run_hooks(
                hooks, _after(graph.nodes.get(record.node)), AfterDispatch(record, last)
            )
        if refused is not None:
            return refused
        if result.halt is not None:
            return result.halt
        # execute_set returns no halt only once every dispatch is recorded, so `last` is set.
        assert last is not None
        step = last
