"""The vocabulary check: the part of a format-5 flow graph's validity JSON Schema cannot express.

The rule: every name a flow graph uses is one it declares, every hook name a node uses is declared
in `vocabulary.hooks` (an absent `vocabulary.hooks` declares none), and each binding is used where
its primitive allows. `vocabulary_violations` takes a built `FlowGraph` and returns one `Violation`
per violation, whose `str()` is that violation's `<path>: <reason>` line, in document order:
nodes in key order; within a node, a round's verdict violation, then its `outcomes` in key order
(each edge, then its `onCap`), then its `skip` entries, then a terminal's `binding`, then the
node's `before` hook names and then its `after` hook names, each in list order. Paths use the
serialized spelling (`onCap`). A binding that is not declared is reported as undeclared alone,
never also for how it is used.

Deliberately not checked:
- Schema validity and the build, both the caller's and both run first: the graph is validated
  against the format-5 schema this package ships as data, `schemas/flow-graph.schema.json` inside
  the `graphscene` package (`graphscene/src/graphscene/schemas/` in this repository), then built.
- Node-id references, reachability and counter caps: `graphscene.engine.static_check`'s.
- Reading any file: the graph arrives built.
"""

from collections.abc import Mapping

from graphscene.model.errors import Violation
from graphscene.model.flow_graph import (
    BindingDeclaration,
    BindingEdge,
    DispatchNode,
    Edge,
    EndBinding,
    FlowGraph,
    HookDeclaration,
    InterruptBinding,
    Node,
    OnCapEdge,
    OutcomeDeclaration,
    PredicateDeclaration,
    RoundNode,
    RouteEdge,
    StopBinding,
    TerminalNode,
)

_VERDICT_RULE = (
    "a round routes on one outcome declaring verdict pass and one declaring verdict fail"
)


def _undeclared_binding(path: str, name: str) -> Violation:
    return Violation(f"{path}.binding", f"binding '{name}' is not declared in vocabulary.bindings")


def _reason_violations(
    path: str, name: str, binding: BindingDeclaration, reason: str | None
) -> list[Violation]:
    if not isinstance(binding, StopBinding):
        if reason is None:
            return []
        return [Violation(f"{path}.reason", f"binding '{name}' is not a stop")]
    if reason is None:
        return [Violation(path, f"binding '{name}' is a stop and needs reason")]
    if reason not in binding.reasons:
        return [
            Violation(f"{path}.reason", f"'{reason}' is not a reason binding '{name}' declares")
        ]
    return []


def _binding_edge_violations(
    path: str, edge: BindingEdge, bindings: Mapping[str, BindingDeclaration]
) -> list[Violation]:
    name = edge.binding
    binding = bindings.get(name)
    if binding is None:
        return [_undeclared_binding(path, name)]
    found: list[Violation] = []
    if isinstance(binding, EndBinding):
        found.append(
            Violation(
                f"{path}.binding", f"binding '{name}' is an end; only a terminal node takes one"
            )
        )
    if isinstance(binding, InterruptBinding):
        if edge.resume is None:
            found.append(Violation(path, f"binding '{name}' is an interrupt and needs resume"))
    elif edge.resume is not None:
        found.append(Violation(f"{path}.resume", f"binding '{name}' is not an interrupt"))
    found.extend(_reason_violations(path, name, binding, edge.reason))
    return found


def _on_cap_violations(
    path: str, on_cap: OnCapEdge, bindings: Mapping[str, BindingDeclaration]
) -> list[Violation]:
    name = on_cap.binding
    binding = bindings.get(name)
    if binding is None:
        return [_undeclared_binding(path, name)]
    if not isinstance(binding, StopBinding):
        return [Violation(f"{path}.binding", f"binding '{name}' is not a stop")]
    return _reason_violations(path, name, binding, on_cap.reason)


def _round_violation(
    node_path: str, outcome_names: list[str], outcomes: Mapping[str, OutcomeDeclaration]
) -> list[Violation]:
    verdicts = sorted(str(outcomes[name].verdict) for name in outcome_names)
    if verdicts == ["fail", "pass"]:
        return []
    return [Violation(f"{node_path}.outcomes", _VERDICT_RULE)]


def _hook_violations(
    node_path: str, field: str, names: tuple[str, ...] | None, hooks: Mapping[str, HookDeclaration]
) -> list[Violation]:
    return [
        Violation(
            f"{node_path}.{field}[{index}]", f"hook '{name}' is not declared in vocabulary.hooks"
        )
        for index, name in enumerate(names or ())
        if name not in hooks
    ]


def _node_violations(
    node_id: str,
    node: Node,
    outcomes: Mapping[str, OutcomeDeclaration],
    bindings: Mapping[str, BindingDeclaration],
    predicates: Mapping[str, PredicateDeclaration],
    hooks: Mapping[str, HookDeclaration],
) -> list[Violation]:
    node_path = f"nodes.{node_id}"
    found: list[Violation] = []
    routes: Mapping[str, Edge] = {} if isinstance(node, TerminalNode) else node.outcomes
    undeclared = [name for name in routes if name not in outcomes]

    if isinstance(node, RoundNode) and not undeclared:
        found.extend(_round_violation(node_path, list(routes), outcomes))

    for name, edge in routes.items():
        path = f"{node_path}.outcomes.{name}"
        if name in undeclared:
            found.append(
                Violation(path, f"outcome '{name}' is not declared in vocabulary.outcomes")
            )
        if isinstance(edge, BindingEdge):
            found.extend(_binding_edge_violations(path, edge, bindings))
        elif isinstance(edge, RouteEdge) and edge.on_cap is not None:
            found.extend(_on_cap_violations(f"{path}.onCap", edge.on_cap, bindings))

    skip = (node.skip or ()) if isinstance(node, DispatchNode) else ()
    for index, entry in enumerate(skip):
        if entry.when not in predicates:
            found.append(
                Violation(
                    f"{node_path}.skip[{index}].when",
                    f"predicate '{entry.when}' is not declared in vocabulary.predicates",
                )
            )

    if isinstance(node, TerminalNode):
        binding = bindings.get(node.binding)
        if binding is None:
            found.append(_undeclared_binding(node_path, node.binding))
        elif not isinstance(binding, EndBinding):
            found.append(
                Violation(f"{node_path}.binding", f"binding '{node.binding}' is not an end")
            )

    found.extend(_hook_violations(node_path, "before", node.before, hooks))
    if not isinstance(node, TerminalNode):
        found.extend(_hook_violations(node_path, "after", node.after, hooks))
    return found


def vocabulary_violations(graph: FlowGraph) -> list[Violation]:
    """Return one `Violation` per vocabulary violation in `graph`, whose `str()` is its
    `<path>: <reason>` line, in document order; `[]` when it has none."""
    vocabulary = graph.vocabulary
    hooks: Mapping[str, HookDeclaration] = vocabulary.hooks or {}
    found: list[Violation] = []
    for node_id, node in graph.nodes.items():
        found.extend(
            _node_violations(
                node_id,
                node,
                vocabulary.outcomes,
                vocabulary.bindings,
                vocabulary.predicates,
                hooks,
            )
        )
    return found
