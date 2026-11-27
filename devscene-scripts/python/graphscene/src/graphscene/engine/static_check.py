"""The static check: a built format-5 flow graph's references resolve, and its shape is walkable.

The rule: `static_violations` returns the reference violations
(`graphscene.engine.references.reference_violations`) alone when there are any. Otherwise it
returns the graph checks' violations: all of check 1 (`reachable-from-start`), then 2
(`reaches-terminal`), 3 (`fail-cycle-capped`), 8 (`gate-in-round`) and 9 (`round-fan-out`).
Checks 8 and 9 hold two kinds of rule: their round rules run on every round, and their
review-loop rules run only on a round `graphscene.engine.review_loop` reports as a review
loop. Check 8's graph-wide clause, that a dispatch node routing a fail verdict with no increment
is a gate of exactly one round, runs only when the graph declares a review loop. Checks 1, 2, 3
and 8 report nodes in key order;
check 9 reports round by round, rounds in key order, and within a round each gate's clauses in
`gates` order, then the writer, then the other edges and skips that target the round, by source
node in key order. Every reason opens with its check id. The walked edge set W is: a
`RouteEdge`'s `to`, a `BindingEdge`'s `resume` when it is not `None`, each `SkipEntry`'s `to`, and
a round node's fan-out to each of its `gates`. Check 3 walks F, a node's uncapped route edges and
its skips; for a fail edge that is not a gate's edge into its own round, F also walks a round
node's fan-out to its `gates`, since only that round's join breaks a cycle through its fan-out.
The checks are total: targets, bindings and outcome
declarations are looked up with `.get`, so a graph built in code that an earlier stage would
refuse never raises.

Deliberately not checked:
- Schema validity and declared names: earlier loading stages.
- Checks 4–7 and what runs a node (a dispatch node's findings folder included): harness checks,
  outside this package.
"""

from collections.abc import Callable, Iterable

from graphscene.engine.references import reference_violations
from graphscene.engine.review_loop import ReviewLoop, review_loop, review_loops
from graphscene.model.errors import Violation
from graphscene.model.flow_graph import (
    BindingEdge,
    DispatchNode,
    Edge,
    FlowGraph,
    Node,
    RoundNode,
    RouteEdge,
    StopBinding,
    TerminalNode,
    Verdict,
)


def _verdict(graph: FlowGraph, outcome: str) -> Verdict | None:
    declaration = graph.vocabulary.outcomes.get(outcome)
    return None if declaration is None else declaration.verdict


def _walked(node: Node) -> list[str]:
    if isinstance(node, TerminalNode):
        return []
    targets: list[str] = []
    for edge in node.outcomes.values():
        if isinstance(edge, RouteEdge):
            targets.append(edge.to)
        elif edge.resume is not None:
            targets.append(edge.resume)
    if isinstance(node, DispatchNode):
        targets.extend(entry.to for entry in node.skip or ())
    else:
        targets.extend(node.gates)
    return targets


def _uncapped(node: Node) -> list[str]:
    """Node's targets over F: uncapped route edges and skip edges."""
    if isinstance(node, TerminalNode):
        return []
    targets = [
        edge.to
        for edge in node.outcomes.values()
        if isinstance(edge, RouteEdge) and edge.increment is None
    ]
    if isinstance(node, DispatchNode):
        targets.extend(entry.to for entry in node.skip or ())
    return targets


def _uncapped_with_fan_out(node: Node) -> list[str]:
    """`_uncapped`, plus a round node's fan-out to each of its `gates`."""
    targets = _uncapped(node)
    if isinstance(node, RoundNode):
        targets.extend(node.gates)
    return targets


def _reached(
    graph: FlowGraph, sources: Iterable[str], successors: Callable[[Node], list[str]]
) -> set[str]:
    """Every node reached from `sources` (themselves included) over `successors`."""
    seen: set[str] = set()
    pending = [source for source in sources if source in graph.nodes]
    while pending:
        node_id = pending.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        pending.extend(t for t in successors(graph.nodes[node_id]) if t in graph.nodes)
    return seen


def _reachable_from_start(graph: FlowGraph) -> list[Violation]:
    reached = _reached(graph, [graph.start], _walked)
    return [
        Violation(
            f"nodes.{node_id}",
            f"reachable-from-start: node '{node_id}' is not reached from start '{graph.start}'",
        )
        for node_id in graph.nodes
        if node_id not in reached
    ]


def _is_stop(graph: FlowGraph, binding: str) -> bool:
    return isinstance(graph.vocabulary.bindings.get(binding), StopBinding)


def _is_sink(graph: FlowGraph, node: Node) -> bool:
    if isinstance(node, TerminalNode):
        return True
    for edge in node.outcomes.values():
        if isinstance(edge, BindingEdge) and _is_stop(graph, edge.binding):
            return True
        if isinstance(edge, RouteEdge) and edge.on_cap and _is_stop(graph, edge.on_cap.binding):
            return True
    return False


def _reaches_terminal(graph: FlowGraph) -> list[Violation]:
    predecessors: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for node_id, node in graph.nodes.items():
        for target in _walked(node):
            if target in predecessors:
                predecessors[target].append(node_id)
    sinks = [node_id for node_id, node in graph.nodes.items() if _is_sink(graph, node)]
    reaching: set[str] = set()
    pending = list(sinks)
    while pending:
        node_id = pending.pop()
        if node_id in reaching:
            continue
        reaching.add(node_id)
        pending.extend(predecessors[node_id])
    return [
        Violation(
            f"nodes.{node_id}",
            f"reaches-terminal: node '{node_id}' reaches no terminal node and no stop binding",
        )
        for node_id in graph.nodes
        if node_id not in reaching
    ]


def _fail_cycle_capped(graph: FlowGraph) -> list[Violation]:
    found: list[Violation] = []
    for node_id, node in graph.nodes.items():
        if isinstance(node, TerminalNode):
            continue
        for outcome, edge in node.outcomes.items():
            if not isinstance(edge, RouteEdge) or edge.increment is not None:
                continue
            if _verdict(graph, outcome) != "fail":
                continue
            target = graph.nodes.get(edge.to)
            own_round = isinstance(target, RoundNode) and node_id in target.gates
            successors = _uncapped if own_round else _uncapped_with_fan_out
            if node_id in _reached(graph, [edge.to], successors):
                found.append(
                    Violation(
                        f"nodes.{node_id}.outcomes.{outcome}",
                        f"fail-cycle-capped: outcome '{outcome}' routes '{node_id}' -> "
                        f"'{edge.to}' with no increment, and '{edge.to}' reaches '{node_id}' "
                        "again",
                    )
                )
    return found


def _routes_uncapped_fail(graph: FlowGraph, node: DispatchNode) -> bool:
    return any(
        isinstance(edge, RouteEdge) and edge.increment is None and _verdict(graph, o) == "fail"
        for o, edge in node.outcomes.items()
    )


def _rounds(graph: FlowGraph) -> list[RoundNode]:
    return [node for node in graph.nodes.values() if isinstance(node, RoundNode)]


def _gate_in_round(graph: FlowGraph) -> list[Violation]:
    found: list[Violation] = []
    has_loops = bool(review_loops(graph))
    for node_id, node in graph.nodes.items():
        if isinstance(node, DispatchNode):
            if not (has_loops and _routes_uncapped_fail(graph, node)):
                continue
            count = sum(1 for r in _rounds(graph) if node_id in r.gates)
            if count != 1:
                found.append(
                    Violation(
                        f"nodes.{node_id}",
                        f"gate-in-round: node '{node_id}' routes a fail verdict with no "
                        f"increment and is a gate of {count} round nodes, not exactly one",
                    )
                )
        elif isinstance(node, RoundNode):
            for index, gate in enumerate(node.gates):
                target = graph.nodes.get(gate)
                if target is not None and not isinstance(target, DispatchNode):
                    found.append(
                        Violation(
                            f"nodes.{node_id}.gates[{index}]",
                            f"gate-in-round: round '{node_id}' names '{gate}' as a gate, "
                            "which is not a dispatch node",
                        )
                    )
            loop = review_loop(node)
            if loop is None:
                continue
            writer = graph.nodes.get(loop.writer)
            if writer is not None and not isinstance(writer, DispatchNode):
                found.append(
                    Violation(
                        f"nodes.{node_id}.writer",
                        f"gate-in-round: round '{node_id}' names '{loop.writer}' as its "
                        "writer, which is not a dispatch node",
                    )
                )
    return found


def _dispatch(graph: FlowGraph, node_id: str) -> DispatchNode | None:
    node = graph.nodes.get(node_id)
    return node if isinstance(node, DispatchNode) else None


def _gate_clauses(
    graph: FlowGraph, r: RoundNode, gate: DispatchNode, loop: ReviewLoop | None
) -> list[Violation]:
    found: list[Violation] = []
    prefix = f"round-fan-out: gate '{gate.id}' of round '{r.id}'"
    for outcome, edge in gate.outcomes.items():
        if _verdict(graph, outcome) is None:
            continue
        if not (isinstance(edge, RouteEdge) and edge.to == r.id):
            found.append(
                Violation(
                    f"nodes.{gate.id}.outcomes.{outcome}",
                    f"{prefix} does not route outcome '{outcome}' to the round",
                )
            )
    if loop is not None:
        declared = {_verdict(graph, outcome) for outcome in gate.outcomes}
        verdicts: tuple[Verdict, ...] = ("pass", "fail")
        for verdict in verdicts:
            if verdict not in declared:
                found.append(
                    Violation(
                        f"nodes.{gate.id}.outcomes",
                        f"{prefix} routes no outcome declaring verdict {verdict}",
                    )
                )
    for index, entry in enumerate(gate.skip or ()):
        if entry.to != r.id:
            found.append(
                Violation(
                    f"nodes.{gate.id}.skip[{index}].to",
                    f"{prefix} skips to '{entry.to}', not to the round",
                )
            )
    return found


def _admitted(
    graph: FlowGraph, r: RoundNode, loop: ReviewLoop, node_id: str, outcome: str, edge: Edge
) -> bool:
    """Whether an edge of `node_id` targeting `r` is one clause (v) admits; a non-dispatch gate or
    writer is check 8's alone."""
    named = node_id in r.gates or node_id == loop.writer
    if named and _dispatch(graph, node_id) is None:
        return True
    if not isinstance(edge, RouteEdge):
        return False
    if node_id == loop.writer:
        return True
    return node_id in r.gates and _verdict(graph, outcome) is not None


def _stray_edges(graph: FlowGraph, r: RoundNode, loop: ReviewLoop) -> list[Violation]:
    found: list[Violation] = []
    for node_id, node in graph.nodes.items():
        if isinstance(node, TerminalNode):
            continue
        for outcome, edge in node.outcomes.items():
            target = edge.to if isinstance(edge, RouteEdge) else edge.resume
            if target == r.id and not _admitted(graph, r, loop, node_id, outcome, edge):
                found.append(
                    Violation(
                        f"nodes.{node_id}.outcomes.{outcome}",
                        f"round-fan-out: round '{r.id}' is targeted by '{node_id}' outcome "
                        f"'{outcome}', which is neither a verdict edge of one of its gates nor "
                        "an edge of its writer",
                    )
                )
        if isinstance(node, DispatchNode) and node_id not in r.gates:
            for index, entry in enumerate(node.skip or ()):
                if entry.to == r.id:
                    found.append(
                        Violation(
                            f"nodes.{node_id}.skip[{index}]",
                            f"round-fan-out: round '{r.id}' is targeted by a skip of "
                            f"'{node_id}', which is not one of its gates",
                        )
                    )
    return found


def _round_fan_out(graph: FlowGraph) -> list[Violation]:
    found: list[Violation] = []
    for r in _rounds(graph):
        loop = review_loop(r)
        for gate_id in r.gates:
            gate = _dispatch(graph, gate_id)
            if gate is not None:
                found.extend(_gate_clauses(graph, r, gate, loop))
        if loop is None:
            continue
        writer = _dispatch(graph, loop.writer)
        if writer is not None and not any(
            isinstance(edge, RouteEdge) and edge.to == r.id for edge in writer.outcomes.values()
        ):
            found.append(
                Violation(
                    f"nodes.{r.id}.writer",
                    f"round-fan-out: writer '{loop.writer}' of round '{r.id}' routes no outcome "
                    "to the round",
                )
            )
        found.extend(_stray_edges(graph, r, loop))
    return found


_CHECKS: tuple[Callable[[FlowGraph], list[Violation]], ...] = (
    _reachable_from_start,
    _reaches_terminal,
    _fail_cycle_capped,
    _gate_in_round,
    _round_fan_out,
)


def static_violations(graph: FlowGraph) -> list[Violation]:
    """Return the reference violations of `graph` when there are any, otherwise the graph checks'
    violations in check order; `[]` when the graph passes every check."""
    found = reference_violations(graph)
    if found:
        return found
    for check in _CHECKS:
        found.extend(check(graph))
    return found
