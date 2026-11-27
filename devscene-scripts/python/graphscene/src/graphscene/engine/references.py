"""The reference check: every name a built format-5 flow graph uses resolves to a declaration.

The rule: every node, counter, path, report-slot and prompt name the graph uses exists, `start`
is listed in `entries`, and each violation's reason opens with its check id (`node-known`,
`counter-known`, `path-known`, `report-slot-known`, `prompt-known`, `start-in-entries`).
`reference_violations` returns one `Violation` per unresolved name, in document order: `start`,
each `entries[i]`, the `start-in-entries` violation, then nodes in key order. Within a round node:
`gates[i]`, `writer` and `counter` when present, `plan[i]`, `revisionNote`, then its outcomes in
key order; within a dispatch node: its outcomes in key order, then its `skip` entries. Within a
route edge: `to`, `increment`, `reset`, `prompt`, `report.<slot>` in key order,
`onCap.roundCounts[i]`, `onCap.evidence`; within a binding edge: `resume`, `roundCounts[i]`,
`evidence`; within a skip entry: `to`, then `report.<slot>`. Paths use the serialized spelling
(`onCap`, `roundCounts`, `revisionNote`). An unknown `start` is reported once, as `node-known`; an
unknown route `to` carrying a `prompt` is reported as `node-known` alone.

Deliberately not checked:
- Binding, outcome and predicate names: the vocabulary check's (`graphscene.engine.vocabulary`).
- Reachability, termination, caps and round shape: `graphscene.engine.static_check`'s.
- What runs a node (an agent's existence, its return schema): a harness check, outside this
  package.
- Reading a file or a mapping: the graph arrives built.
"""

from collections.abc import Mapping

from graphscene.model.errors import Violation
from graphscene.model.flow_graph import (
    BindingEdge,
    DispatchNode,
    Edge,
    FlowGraph,
    Node,
    OnCapEdge,
    RoundNode,
    RouteEdge,
    SkipEntry,
)


def _node_known(path: str, name: str, graph: FlowGraph) -> list[Violation]:
    if name in graph.nodes:
        return []
    return [Violation(path, f"node-known: '{name}' is not a node")]


def _opt_node_known(path: str, name: str | None, graph: FlowGraph) -> list[Violation]:
    return [] if name is None else _node_known(path, name, graph)


def _counter_known(path: str, name: str | None, graph: FlowGraph) -> list[Violation]:
    if name is None or name in graph.counters:
        return []
    return [Violation(path, f"counter-known: '{name}' is not declared in counters")]


def _path_known(path: str, name: str | None, graph: FlowGraph) -> list[Violation]:
    if name is None or name in graph.paths:
        return []
    return [Violation(path, f"path-known: '{name}' is not declared in paths")]


def _report_slots(path: str, report: Mapping[str, str] | None, graph: FlowGraph) -> list[Violation]:
    if report is None:
        return []
    return [
        Violation(
            f"{path}.report.{slot}", f"report-slot-known: '{slot}' is not declared in reports"
        )
        for slot in report
        if slot not in graph.reports
    ]


def _round_counts(path: str, names: tuple[str, ...] | None, graph: FlowGraph) -> list[Violation]:
    found: list[Violation] = []
    for index, name in enumerate(names or ()):
        found.extend(_node_known(f"{path}.roundCounts[{index}]", name, graph))
    return found


def _prompt_known(path: str, edge: RouteEdge, graph: FlowGraph) -> list[Violation]:
    target: Node | None = graph.nodes.get(edge.to)
    if edge.prompt is None or target is None:
        return []
    if isinstance(target, DispatchNode) and edge.prompt in (target.prompts or ()):
        return []
    return [
        Violation(
            f"{path}.prompt",
            f"prompt-known: '{edge.prompt}' is not a prompt node '{edge.to}' declares",
        )
    ]


def _on_cap(path: str, on_cap: OnCapEdge | None, graph: FlowGraph) -> list[Violation]:
    if on_cap is None:
        return []
    return [
        *_round_counts(f"{path}.onCap", on_cap.round_counts, graph),
        *_path_known(f"{path}.onCap.evidence", on_cap.evidence, graph),
    ]


def _edge(path: str, edge: Edge, graph: FlowGraph) -> list[Violation]:
    if isinstance(edge, BindingEdge):
        resume = [] if edge.resume is None else _node_known(f"{path}.resume", edge.resume, graph)
        return [
            *resume,
            *_round_counts(path, edge.round_counts, graph),
            *_path_known(f"{path}.evidence", edge.evidence, graph),
        ]
    return [
        *_node_known(f"{path}.to", edge.to, graph),
        *_counter_known(f"{path}.increment", edge.increment, graph),
        *_counter_known(f"{path}.reset", edge.reset, graph),
        *_prompt_known(path, edge, graph),
        *_report_slots(path, edge.report, graph),
        *_on_cap(path, edge.on_cap, graph),
    ]


def _outcomes(node_path: str, outcomes: Mapping[str, Edge], graph: FlowGraph) -> list[Violation]:
    found: list[Violation] = []
    for name, edge in outcomes.items():
        found.extend(_edge(f"{node_path}.outcomes.{name}", edge, graph))
    return found


def _skip_entry(path: str, entry: SkipEntry, graph: FlowGraph) -> list[Violation]:
    return [*_node_known(f"{path}.to", entry.to, graph), *_report_slots(path, entry.report, graph)]


def _round(node_path: str, node: RoundNode, graph: FlowGraph) -> list[Violation]:
    found: list[Violation] = []
    for index, gate in enumerate(node.gates):
        found.extend(_node_known(f"{node_path}.gates[{index}]", gate, graph))
    found.extend(_opt_node_known(f"{node_path}.writer", node.writer, graph))
    found.extend(_counter_known(f"{node_path}.counter", node.counter, graph))
    for index, name in enumerate(node.plan or ()):
        found.extend(_path_known(f"{node_path}.plan[{index}]", name, graph))
    found.extend(_path_known(f"{node_path}.revisionNote", node.revision_note, graph))
    found.extend(_outcomes(node_path, node.outcomes, graph))
    return found


def _dispatch(node_path: str, node: DispatchNode, graph: FlowGraph) -> list[Violation]:
    found = _outcomes(node_path, node.outcomes, graph)
    for index, entry in enumerate(node.skip or ()):
        found.extend(_skip_entry(f"{node_path}.skip[{index}]", entry, graph))
    return found


def reference_violations(graph: FlowGraph) -> list[Violation]:
    """Return one `Violation` per unresolved name in `graph`, in document order; `[]` when every
    name resolves."""
    found = _node_known("start", graph.start, graph)
    for index, entry in enumerate(graph.entries):
        found.extend(_node_known(f"entries[{index}]", entry, graph))
    if graph.start in graph.nodes and graph.start not in graph.entries:
        found.append(
            Violation(
                "entries", f"start-in-entries: start '{graph.start}' is not listed in entries"
            )
        )
    for node_id, node in graph.nodes.items():
        node_path = f"nodes.{node_id}"
        if isinstance(node, RoundNode):
            found.extend(_round(node_path, node, graph))
        elif isinstance(node, DispatchNode):
            found.extend(_dispatch(node_path, node, graph))
    return found
