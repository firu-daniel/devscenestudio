"""Recording a gate's outcome while its round's set is out, and the join once every gate is in.

The rule: a gate's outcome is recorded once; a held outcome waits for the gates still out and
never cancels them; the join takes the first held gate's edge in the round's `gates` order, or
else closes the round through `graphscene.engine.transitions.close_round`. `record_gate` refuses,
in this order, a gate not due in the open round, a gate already recorded, an outcome its node
does not declare, and an outcome declaring neither a verdict nor held. A verdict outcome records
its edge's report; its edge's `to` is the round and is not followed. `enter_round` opens a round
as `open_round` does, refuses a record for a gate skipped on this arrival, then records each
record through `record_gate` in `gates` order; it returns the set of gates still out, or the
join's step once every due gate is recorded.

Deliberately not covered:

- Whether a set is pending at all and whether a gate was named, and reading or writing state:
  `graphscene.engine.walker`'s. `record_gate` assumes `draft.open_round` is set.
- Refusing a record for a gate outside the round, a repeated gate or a negative round number,
  and setting the round's number before `enter_round`: `graphscene.engine.walker`'s. Deciding
  which round to enter and with which records: the host's.
"""

from types import MappingProxyType

from graphscene.engine.transitions import (
    WalkDraft,
    close_round,
    follow_edge,
    open_round,
    take_binding,
)
from graphscene.model.flow_graph import BindingEdge, FlowGraph, RoundNode, RouteEdge, TerminalNode
from graphscene.model.walk_actions import DispatchSet, GateRecord, Refused, Step, Wait
from graphscene.model.walk_state import OpenRound, PredicateHost


def enter_round(
    graph: FlowGraph,
    host: PredicateHost,
    draft: WalkDraft,
    round_id: str,
    records: tuple[GateRecord, ...],
) -> Step:
    number = draft.round_numbers[round_id]
    opened = open_round(graph, host, draft, round_id)
    if isinstance(opened, Refused) or not records:
        return opened
    round_node = graph.nodes[round_id]
    assert isinstance(round_node, RoundNode)
    by_gate = {r.gate: r for r in records}
    ordered = tuple(by_gate[g] for g in round_node.gates if g in by_gate)
    current = draft.open_round
    due = current.due if current is not None and current.round == round_id else ()
    for r in ordered:
        if r.gate not in due:
            return Refused(
                f"'{r.gate}' is skipped in round {number}: a skipped gate carries no record"
            )
    step: Step = opened
    for r in ordered:
        step = record_gate(graph, host, draft, r.gate, r.outcome, r.detail)
        if isinstance(step, Refused):
            return step
    if isinstance(step, Wait):
        pending = draft.pending
        assert isinstance(pending, DispatchSet)
        return pending
    return step


def record_gate(
    graph: FlowGraph,
    host: PredicateHost,
    draft: WalkDraft,
    gate: str,
    outcome: str,
    detail: str | None,
) -> Step:
    current = draft.open_round
    assert current is not None, "record_gate is called only while a round's set is out"
    number = current.number
    if gate not in current.due:
        return Refused(f"'{gate}' is not pending in round {number}")
    if gate in current.records:
        return Refused(f"an outcome for '{gate}' is already recorded in round {number}")
    node = graph.nodes[gate]
    assert not isinstance(node, TerminalNode)
    edge = node.outcomes.get(outcome)
    if edge is None:
        return Refused(f"outcome '{outcome}' is not declared by node '{gate}'")
    declared = graph.vocabulary.outcomes.get(outcome)
    if declared is None or (declared.verdict is None and not declared.held):
        return Refused(
            f"outcome '{outcome}' of round gate '{gate}' declares neither a verdict nor held"
        )

    record = GateRecord(gate, outcome, detail)
    records = MappingProxyType({**current.records, gate: record})
    opened = OpenRound(current.round, number, current.due, records)
    draft.open_round = opened
    if declared.verdict is not None and isinstance(edge, RouteEdge) and edge.report is not None:
        draft.reports.update(edge.report)

    round_node = graph.nodes[current.round]
    assert isinstance(round_node, RoundNode)
    gates_order = round_node.gates
    out = tuple(g for g in gates_order if g in current.due and g not in records)
    if out:
        stored = draft.pending
        assert isinstance(stored, DispatchSet)
        draft.pending = DispatchSet(
            stored.round,
            stored.number,
            tuple(d for d in stored.dispatches if d.node in out),
            stored.passed,
        )
        draft.awaiting = "set"
        return Wait(current.round, recorded=record, pending=out)

    held = tuple(
        records[g]
        for g in gates_order
        if g in records and graph.vocabulary.outcomes[records[g].outcome].held
    )
    if not held:
        return close_round(graph, host, draft, current.round)
    draft.open_round = None
    first = held[0]
    first_node = graph.nodes[first.gate]
    assert not isinstance(first_node, TerminalNode)
    held_edge = first_node.outcomes[first.outcome]
    if isinstance(held_edge, BindingEdge):
        return take_binding(
            graph,
            draft,
            first.gate,
            held_edge.binding,
            reason=held_edge.reason,
            resume=held_edge.resume,
            summary=held_edge.summary,
            round_counts=held_edge.round_counts,
            evidence=held_edge.evidence,
            held=held,
        )
    return follow_edge(graph, host, draft, first.gate, held_edge, held=held)
