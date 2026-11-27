"""The walk's transitions: every move that takes a walk from one node to the next, over one
engine-internal mutable draft, `WalkDraft`.

The rule:

- Every transition sets `draft.pending` and `draft.awaiting` and returns a `Step`; on a `Refused`
  the caller discards the draft. Nothing here raises.
- `arrive` lands on a node. A terminal node ends the walk with its binding and the recorded
  reports in the graph's `reports` order. A round node opens its round. A dispatch node asks the
  host each of its `skip` entries in order, on every arrival and never from a cache: an entry
  that holds records its report, a `SkipPassage` and the node's `skipped` entry; an arrival
  where no entry holds clears that entry. When an entry holds, the walk
  moves on to the entry's `to` with no dispatch; a node reached twice in one arrival is refused,
  and so is a predicate the host cannot answer. Otherwise the node is dispatched, carrying the
  round number of the round it is a gate of, with that round's convergence when it is a review
  loop, or the round number of the review loop it writes (`graphscene.engine.review_loop`).
- `follow_edge` takes a binding edge to `take_binding`; on a routed edge it resets, then
  increments (a counter reaching its cap takes `onCap` and goes no further), then advances the
  named round's number, records the edge's report and ledger entry, sets or clears the target's
  prompt, and arrives at `to`.
- `take_binding` routes on the binding declaration's class: an interrupt pauses at the node,
  carrying the closed round it was given, a stop ends the walk, and an end on an edge is refused.
- `open_round` skips its gates as `arrive` skips a node, without following a skip's `to`, and
  dispatches the remaining gates as one set; with none due, it closes at once. `close_round`
  fails when any recorded gate's outcome declares verdict fail, records a `RoundPassage`, and
  follows the round's outcome declaring that verdict, advancing the round's number on fail only.
- Routing reads declared primitives only: an outcome's `verdict`, the binding's class, the
  round's `records` and a predicate's `records` and `in_round_counts`, never a name.

Deliberately not covered:

- A graph that did not pass `load_graph`: its guarantees are relied on, never re-checked.
- Path templates, heartbeats and round files: the host's.
- Recording a gate's outcome and the held join (`graphscene.engine.rounds`), and validating a
  caller's step and reading or writing state (`graphscene.engine.walker`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from graphscene.engine.review_loop import is_converging, review_loop, review_loops
from graphscene.model.flow_graph import (
    BindingEdge,
    DispatchNode,
    Edge,
    EndBinding,
    FlowGraph,
    InterruptBinding,
    RoundNode,
    SkipEntry,
    TerminalNode,
    Verdict,
)
from graphscene.model.walk_actions import (
    Action,
    Dispatch,
    DispatchSet,
    End,
    GateRecord,
    Interrupt,
    LedgerPassage,
    Passage,
    Refused,
    RoundPassage,
    SkipPassage,
    Step,
    Stop,
)
from graphscene.model.walk_state import Awaiting, OpenRound, PredicateHost, WalkState


@dataclass
class WalkDraft:
    flow: str
    node: str
    awaiting: Awaiting
    pending: Action | None
    counters: dict[str, int]
    round_numbers: dict[str, int]
    open_round: OpenRound | None
    prompts: dict[str, str]
    reports: dict[str, str]
    skipped: dict[str, str]
    passed: list[Passage]

    @classmethod
    def fresh(cls, graph: FlowGraph) -> "WalkDraft":
        return cls(
            flow=graph.flow,
            node=graph.start,
            awaiting="dispatch",
            pending=None,
            counters={name: 0 for name in graph.counters},
            round_numbers={
                node_id: 0 for node_id, node in graph.nodes.items() if isinstance(node, RoundNode)
            },
            open_round=None,
            prompts={},
            reports={},
            skipped={},
            passed=[],
        )

    @classmethod
    def from_state(cls, state: WalkState) -> "WalkDraft":
        return cls(
            flow=state.flow,
            node=state.node,
            awaiting=state.awaiting,
            pending=state.pending,
            counters=dict(state.counters),
            round_numbers=dict(state.round_numbers),
            open_round=state.open_round,
            prompts=dict(state.prompts),
            reports=dict(state.reports),
            skipped=dict(state.skipped),
            passed=[],
        )

    def freeze(self) -> WalkState:
        assert self.pending is not None, "a draft is frozen only after a transition set pending"
        return WalkState(
            flow=self.flow,
            node=self.node,
            awaiting=self.awaiting,
            pending=self.pending,
            counters=MappingProxyType(dict(self.counters)),
            round_numbers=MappingProxyType(dict(self.round_numbers)),
            open_round=self.open_round,
            prompts=MappingProxyType(dict(self.prompts)),
            reports=MappingProxyType(dict(self.reports)),
            skipped=MappingProxyType(dict(self.skipped)),
        )


def _settle(draft: WalkDraft, node_id: str, awaiting: Awaiting, step: Action) -> Action:
    draft.node = node_id
    draft.awaiting = awaiting
    draft.pending = step
    return step


def _record_report(draft: WalkDraft, report: Mapping[str, str] | None) -> None:
    if report is not None:
        draft.reports.update(report)


def _taken_skip(
    graph: FlowGraph, host: PredicateHost, draft: WalkDraft, node: DispatchNode
) -> SkipEntry | Refused | None:
    for entry in node.skip or ():
        answer = host.answer(entry.when, node.id)
        if answer is None:
            return Refused(f"the host cannot answer predicate '{entry.when}' for node '{node.id}'")
        if answer:
            _record_report(draft, entry.report)
            draft.passed.append(
                SkipPassage(node.id, graph.vocabulary.predicates[entry.when].records)
            )
            draft.skipped[node.id] = entry.when
            return entry
    draft.skipped.pop(node.id, None)
    return None


def _dispatch(
    graph: FlowGraph,
    draft: WalkDraft,
    node: DispatchNode,
    closed_round: tuple[GateRecord, ...],
    passed: tuple[Passage, ...],
) -> Dispatch:
    round_number: int | None = None
    converging: bool | None = None
    gate_of = next(
        (n for n in graph.nodes.values() if isinstance(n, RoundNode) and node.id in n.gates),
        None,
    )
    if gate_of is not None:
        round_number = draft.round_numbers[gate_of.id]
        loop = review_loop(gate_of)
        if loop is not None:
            converging = is_converging(loop, draft.counters)
    else:
        written = next((lp for lp in review_loops(graph) if lp.writer == node.id), None)
        if written is not None:
            round_number = draft.round_numbers[written.round]
    return Dispatch(
        node=node.id,
        agent=node.agent,
        prompt_variant=draft.prompts.get(node.id),
        counters=MappingProxyType(dict(draft.counters)),
        round_number=round_number,
        converging=converging,
        closed_round=closed_round,
        passed=passed,
    )


def arrive(
    graph: FlowGraph,
    host: PredicateHost,
    draft: WalkDraft,
    node_id: str,
    *,
    closed_round: tuple[GateRecord, ...] = (),
) -> Step:
    visited: set[str] = set()
    while True:
        if node_id in visited:
            return Refused(f"skip entries loop through node '{node_id}'")
        visited.add(node_id)
        node = graph.nodes[node_id]
        if isinstance(node, TerminalNode):
            reports = tuple(
                (slot, draft.reports[slot]) for slot in graph.reports if slot in draft.reports
            )
            end = End(node.binding, node_id, reports=reports, passed=tuple(draft.passed))
            return _settle(draft, node_id, "done", end)
        if isinstance(node, RoundNode):
            return open_round(graph, host, draft, node_id)
        taken = _taken_skip(graph, host, draft, node)
        if isinstance(taken, Refused):
            return taken
        if taken is None:
            dispatch = _dispatch(graph, draft, node, closed_round, tuple(draft.passed))
            return _settle(draft, node_id, "dispatch", dispatch)
        node_id = taken.to


def follow_edge(
    graph: FlowGraph,
    host: PredicateHost,
    draft: WalkDraft,
    node_id: str,
    edge: Edge,
    *,
    advance: str | None = None,
    closed_round: tuple[GateRecord, ...] = (),
    open_gates: tuple[str, ...] = (),
    held: tuple[GateRecord, ...] = (),
) -> Step:
    if isinstance(edge, BindingEdge):
        return take_binding(
            graph,
            draft,
            node_id,
            edge.binding,
            reason=edge.reason,
            resume=edge.resume,
            summary=edge.summary,
            round_counts=edge.round_counts,
            evidence=edge.evidence,
            open_gates=open_gates,
            held=held,
            closed_round=closed_round,
        )
    if edge.reset is not None:
        draft.counters[edge.reset] = 0
    if edge.increment is not None:
        draft.counters[edge.increment] += 1
        cap = graph.counters[edge.increment].cap
        if draft.counters[edge.increment] >= cap and edge.on_cap is not None:
            on_cap = edge.on_cap
            return take_binding(
                graph,
                draft,
                node_id,
                on_cap.binding,
                reason=on_cap.reason,
                resume=None,
                summary=on_cap.summary,
                round_counts=on_cap.round_counts,
                evidence=on_cap.evidence,
                cap=cap,
                open_gates=open_gates,
                held=held,
                closed_round=closed_round,
            )
    if advance is not None and isinstance(graph.nodes.get(advance), RoundNode):
        draft.round_numbers[advance] += 1
    _record_report(draft, edge.report)
    if edge.ledger is not None:
        draft.passed.append(LedgerPassage(edge.ledger))
    if edge.prompt is not None:
        draft.prompts[edge.to] = edge.prompt
    else:
        draft.prompts.pop(edge.to, None)
    return arrive(graph, host, draft, edge.to, closed_round=closed_round)


def take_binding(
    graph: FlowGraph,
    draft: WalkDraft,
    node_id: str,
    name: str,
    *,
    reason: str | None,
    resume: str | None,
    summary: str | None,
    round_counts: tuple[str, ...] | None,
    evidence: str | None,
    cap: int | None = None,
    open_gates: tuple[str, ...] = (),
    held: tuple[GateRecord, ...] = (),
    closed_round: tuple[GateRecord, ...] = (),
) -> Step:
    binding = graph.vocabulary.bindings[name]
    node = graph.nodes[node_id]
    agent = node.agent if isinstance(node, DispatchNode) else None
    if isinstance(binding, EndBinding):
        return Refused(f"binding '{name}' is an end; only a terminal node takes one")
    if isinstance(binding, InterruptBinding):
        if resume is None:
            return Refused(f"binding '{name}' is an interrupt and needs resume")
        interrupt = Interrupt(
            name, node_id, agent, resume, binding.resume_outcome, tuple(draft.passed), closed_round
        )
        return _settle(draft, node_id, "interrupt", interrupt)
    if reason is None:
        return Refused(f"binding '{name}' is a stop and needs reason")
    if summary is not None:
        if cap is not None:
            summary = summary.replace("{cap}", str(cap))
        summary = summary.replace("{open_gates}", ", ".join(open_gates))
    counted = tuple(
        n
        for n in round_counts or ()
        if n not in draft.skipped or graph.vocabulary.predicates[draft.skipped[n]].in_round_counts
    )
    stop = Stop(
        binding=name,
        node=node_id,
        agent=agent,
        reason=reason,
        summary=summary,
        evidence=evidence,
        round_counts=counted,
        held=held,
        closed_round=closed_round,
        passed=tuple(draft.passed),
    )
    return _settle(draft, node_id, "done", stop)


def open_round(graph: FlowGraph, host: PredicateHost, draft: WalkDraft, round_id: str) -> Step:
    node = graph.nodes[round_id]
    assert isinstance(node, RoundNode)
    due: list[DispatchNode] = []
    for gate_id in node.gates:
        gate = graph.nodes[gate_id]
        assert isinstance(gate, DispatchNode)
        taken = _taken_skip(graph, host, draft, gate)
        if isinstance(taken, Refused):
            return taken
        if taken is None:
            due.append(gate)
    if not due:
        return close_round(graph, host, draft, round_id)
    number = draft.round_numbers[round_id]
    draft.open_round = OpenRound(
        round_id, number, tuple(g.id for g in due), records=MappingProxyType({})
    )
    dispatches = tuple(_dispatch(graph, draft, gate, (), ()) for gate in due)
    dispatch_set = DispatchSet(round_id, number, dispatches, tuple(draft.passed))
    return _settle(draft, round_id, "set", dispatch_set)


def close_round(graph: FlowGraph, host: PredicateHost, draft: WalkDraft, round_id: str) -> Step:
    node = graph.nodes[round_id]
    assert isinstance(node, RoundNode)
    records: Mapping[str, GateRecord] = {}
    if draft.open_round is not None and draft.open_round.round == round_id:
        records = draft.open_round.records
    outcomes = graph.vocabulary.outcomes
    failing = tuple(
        g
        for g in node.gates
        if g in records
        and (declared := outcomes.get(records[g].outcome)) is not None
        and declared.verdict == "fail"
    )
    verdict: Verdict = "fail" if failing else "pass"
    draft.passed.append(RoundPassage(round_id, draft.round_numbers[round_id], verdict))
    closed = tuple(records[g] for g in node.gates if g in records)
    draft.open_round = None
    for outcome, edge in node.outcomes.items():
        declared = outcomes.get(outcome)
        if declared is not None and declared.verdict == verdict:
            return follow_edge(
                graph,
                host,
                draft,
                round_id,
                edge,
                advance=round_id if verdict == "fail" else None,
                closed_round=closed,
                open_gates=failing,
            )
    return Refused(f"round '{round_id}' declares no outcome with verdict '{verdict}'")
