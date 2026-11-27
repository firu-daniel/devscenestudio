"""The walk's driver, `Walker`: it reads the saved walk from a `StateStore`, steps it through
`graphscene.engine.transitions` and `graphscene.engine.rounds`, and writes the result back.

The rule:

- Only `start` replaces a saved walk. It sets every counter to 0 and every round number to 0
  except the round a `RoundResume` names, which takes its `number`; entering that round with
  records records them as `next` would.
- `start` refuses a resume it cannot place: a round that is not a round of the flow, a number
  below 0, records given while the walk enters elsewhere, a record for a gate outside the round,
  and a second record for one gate.
- `start` and `next` hold the store's lock from before the read until after the write.
- `next` and `current` refuse a walk of another flow.
- `current` takes no lock and changes nothing: it re-returns the saved pending action.
- A `Refused` leaves the store unwritten.

Deliberately not covered:

- Reading round evidence at `start`, which round to resume and whether its records are
  consistent: the host's.
- What a host does with a review loop's round number, convergence and findings: the host's;
  which round is a review loop is `graphscene.engine.review_loop`'s.
"""

from graphscene.engine.rounds import enter_round, record_gate
from graphscene.engine.transitions import WalkDraft, arrive, follow_edge
from graphscene.model.flow_graph import (
    BindingEdge,
    DispatchNode,
    FlowGraph,
    InterruptBinding,
    RoundNode,
)
from graphscene.model.walk_actions import Dispatch, GateRecord, Interrupt, Refused, Step
from graphscene.model.walk_state import PredicateHost, RoundResume, StateStore, WalkState


class Walker:
    def __init__(self, graph: FlowGraph, store: StateStore, host: PredicateHost) -> None:
        self.graph = graph
        self.store = store
        self.host = host

    def start(self, entry: str | None = None, *, resume: RoundResume | None = None) -> Step:
        graph = self.graph
        e = entry or graph.start
        with self.store.lock():
            if e not in graph.entries:
                return Refused(f"'{e}' is not an entry of flow '{graph.flow}'")
            for node in graph.nodes.values():
                if isinstance(node, RoundNode) and e in node.gates:
                    return Refused(f"'{e}' is a gate of round '{node.id}': enter at the round")
            if resume is not None:
                refused = self._unplaceable(e, resume)
                if refused is not None:
                    return refused
            draft = WalkDraft.fresh(graph)
            if resume is not None:
                draft.round_numbers[resume.round] = resume.number
            if resume is not None and e == resume.round:
                step = enter_round(graph, self.host, draft, e, resume.records)
            else:
                step = arrive(graph, self.host, draft, e)
            if not isinstance(step, Refused):
                self.store.write(draft.freeze())
            return step

    def next(self, outcome: str, node: str | None = None, detail: str | None = None) -> Step:
        with self.store.lock():
            state = self.store.read()
            refused = self._foreign(state)
            if refused is not None:
                return refused
            assert state is not None
            draft = WalkDraft.from_state(state)
            step = self._step(state, draft, outcome, node, detail)
            if not isinstance(step, Refused):
                self.store.write(draft.freeze())
            return step

    def current(self) -> Step:
        state = self.store.read()
        refused = self._foreign(state)
        if refused is not None:
            return refused
        assert state is not None
        return state.pending

    def _unplaceable(self, e: str, resume: RoundResume) -> Refused | None:
        graph = self.graph
        r, n = resume.round, resume.number
        round_node = graph.nodes.get(r)
        if not isinstance(round_node, RoundNode):
            return Refused(f"'{r}' is not a round of flow '{graph.flow}'")
        if n < 0:
            return Refused(f"round number {n} of round '{r}' is below 0")
        if resume.records and e != r:
            return Refused(f"records of round '{r}' are given, but the walk enters at '{e}'")
        for record in resume.records:
            if record.gate not in round_node.gates:
                return Refused(f"'{record.gate}' is not a gate of round '{r}'")
        seen: set[str] = set()
        for record in resume.records:
            if record.gate in seen:
                return Refused(f"a second record for '{record.gate}' in round '{r}'")
            seen.add(record.gate)
        return None

    def _foreign(self, state: WalkState | None) -> Refused | None:
        if state is None:
            return Refused("no walk has started")
        if state.flow != self.graph.flow:
            return Refused(f"the saved walk is of flow '{state.flow}', not '{self.graph.flow}'")
        return None

    def _step(
        self,
        state: WalkState,
        draft: WalkDraft,
        outcome: str,
        node: str | None,
        detail: str | None,
    ) -> Step:
        graph, host = self.graph, self.host
        if state.awaiting == "done":
            return Refused("the walk has finished")
        if state.awaiting == "set":
            if node is None:
                return Refused(
                    f"a round's set is pending at '{state.node}': name the gate with node"
                )
            return record_gate(graph, host, draft, node, outcome, detail)
        if node is not None and node != state.node:
            return Refused(f"'{node}' is not the pending node '{state.node}'")
        if detail is not None:
            return Refused("detail is recorded only for a gate of an open round")
        pending = state.pending
        if isinstance(pending, Interrupt):
            # The resume outcome is consumed by the interrupt, never looked up in the vocabulary.
            if outcome != pending.resume_outcome:
                return Refused(
                    f"the walk is interrupted at '{state.node}': "
                    f"resume with outcome '{pending.resume_outcome}'"
                )
            return arrive(graph, host, draft, pending.resume, closed_round=pending.closed_round)
        dispatch_node = graph.nodes[state.node]
        assert isinstance(dispatch_node, DispatchNode)
        edge = dispatch_node.outcomes.get(outcome)
        if edge is None:
            return Refused(f"outcome '{outcome}' is not declared by node '{state.node}'")
        carried: tuple[GateRecord, ...] = ()
        if (
            isinstance(edge, BindingEdge)
            and isinstance(graph.vocabulary.bindings[edge.binding], InterruptBinding)
            and isinstance(pending, Dispatch)
        ):
            carried = pending.closed_round
        return follow_edge(graph, host, draft, state.node, edge, closed_round=carried)
