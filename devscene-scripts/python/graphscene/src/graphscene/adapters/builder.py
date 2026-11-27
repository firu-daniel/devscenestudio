"""`build_flow_graph`, which builds the typed, immutable form of a declared format-5 flow graph
(`graphscene.model.flow_graph`) from a parsed graph that has passed the schema check.

The mapping rules, from the schema's declaration to the model:
- Attribute names: each attribute is its schema key in snake_case — `formatVersion` →
  `format_version`, `resumeOutcome` → `resume_outcome`, `inRoundCounts` → `in_round_counts`,
  `convergingFrom` → `converging_from`, `revisionNote` → `revision_note`, `findingsFolder` →
  `findings_folder`, `onCap` → `on_cap`, `roundCounts` → `round_counts`, `promptSource` →
  `prompt_source`; every other key keeps its own name. The one addition is a node's `id`, its
  key in `nodes`.
- Containers: a JSON array becomes a `tuple`; a JSON object becomes a read-only
  `types.MappingProxyType` over a fresh `dict`, keeping the declaration's key order and never
  aliasing the caller's input.
- Absent keys: an absent optional key is `None` — `vocabulary.hooks`, a node's `promptSource`,
  `before` and `after` among them. The one exception is `held`, which the schema allows only as
  `true`: it is a `bool`, `False` when absent.
- Integers: a number the schema accepts as an integer, `3` or `3.0`, becomes an `int`.
- Which classes: an edge carrying `binding` is a `BindingEdge` and any other edge a `RouteEdge`,
  as the schema's `edge` `if`/`then` decides; a node's class follows `kind`; a binding's class
  follows `primitive`.
- Fixed words: the only fixed words are the schema's own enums, typed as `NodeKind`, `Primitive`
  and `Verdict`.

The builder does not validate. A shape the schema would have refused is a programming error here:
it raises `TypeError` naming the dotted path — object keys joined with ".", array indices as
"[i]", as `graphscene.model.errors.Violation.path` writes them — never a `GraphError`.

Deliberately not covered:
- Validation, which is the facade's: the schema check runs before the build, and the vocabulary
  and static checks run on the model it returns.
- Resolving node-id and other name references (`to`, `resume`, `gates`, `writer`, `start`,
  `entries`, `round_counts`, counter, path, report-slot, prompt and binding names): they stay
  `str` ids, and checking that they exist is `graphscene.engine.static_check`'s.
- Any harness name.
"""

from collections.abc import Mapping
from types import MappingProxyType

from graphscene.model.flow_graph import (
    BindingDeclaration,
    BindingEdge,
    CounterDeclaration,
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
    SkipEntry,
    StopBinding,
    TerminalNode,
    Verdict,
    Vocabulary,
)


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{path or '(root)'}: expected object")
    return value


def _str(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{path}: expected str")
    return value


def _int(value: object, path: str) -> int:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path}: expected int")
    return value


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{path}: expected bool")
    return value


def _strs(value: object, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{path}: expected array")
    return tuple(_str(item, f"{path}[{index}]") for index, item in enumerate(value))


def _opt_str(fields: Mapping[str, object], key: str, path: str) -> str | None:
    return _str(fields[key], _join(path, key)) if key in fields else None


def _opt_int(fields: Mapping[str, object], key: str, path: str) -> int | None:
    return _int(fields[key], _join(path, key)) if key in fields else None


def _opt_strs(fields: Mapping[str, object], key: str, path: str) -> tuple[str, ...] | None:
    return _strs(fields[key], _join(path, key)) if key in fields else None


def _str_map(value: object, path: str) -> Mapping[str, str]:
    fields = _object(value, path)
    return MappingProxyType({key: _str(child, _join(path, key)) for key, child in fields.items()})


def _opt_str_map(fields: Mapping[str, object], key: str, path: str) -> Mapping[str, str] | None:
    return _str_map(fields[key], _join(path, key)) if key in fields else None


def _outcome(value: object, path: str) -> OutcomeDeclaration:
    fields = _object(value, path)
    verdict: Verdict | None = None
    if "verdict" in fields:
        raw = fields["verdict"]
        if raw == "pass":
            verdict = "pass"
        elif raw == "fail":
            verdict = "fail"
        else:
            raise TypeError(f"{_join(path, 'verdict')}: expected 'pass' or 'fail'")
    held = _bool(fields["held"], _join(path, "held")) if "held" in fields else False
    return OutcomeDeclaration(verdict=verdict, held=held)


def _binding(value: object, path: str) -> BindingDeclaration:
    fields = _object(value, path)
    primitive = fields.get("primitive")
    if primitive == "interrupt":
        key = "resumeOutcome"
        return InterruptBinding(resume_outcome=_str(fields.get(key), _join(path, key)))
    if primitive == "stop":
        return StopBinding(reasons=_strs(fields.get("reasons"), _join(path, "reasons")))
    if primitive == "end":
        return EndBinding()
    raise TypeError(f"{_join(path, 'primitive')}: expected 'interrupt', 'stop' or 'end'")


def _predicate(value: object, path: str) -> PredicateDeclaration:
    fields = _object(value, path)
    key = "inRoundCounts"
    return PredicateDeclaration(
        records=_str(fields.get("records"), _join(path, "records")),
        in_round_counts=_bool(fields.get(key), _join(path, key)),
    )


def _hooks(value: object, path: str) -> Mapping[str, HookDeclaration]:
    fields = _object(value, path)
    hooks: dict[str, HookDeclaration] = {}
    for name, declaration in fields.items():
        _object(declaration, _join(path, name))
        hooks[name] = HookDeclaration()
    return MappingProxyType(hooks)


def _vocabulary(value: object, path: str) -> Vocabulary:
    fields = _object(value, path)
    outcomes = _object(fields.get("outcomes"), _join(path, "outcomes"))
    bindings = _object(fields.get("bindings"), _join(path, "bindings"))
    predicates = _object(fields.get("predicates"), _join(path, "predicates"))
    hooks_path = _join(path, "hooks")
    return Vocabulary(
        outcomes=MappingProxyType(
            {name: _outcome(d, _join(path, f"outcomes.{name}")) for name, d in outcomes.items()}
        ),
        bindings=MappingProxyType(
            {name: _binding(d, _join(path, f"bindings.{name}")) for name, d in bindings.items()}
        ),
        predicates=MappingProxyType(
            {
                name: _predicate(d, _join(path, f"predicates.{name}"))
                for name, d in predicates.items()
            }
        ),
        hooks=_hooks(fields["hooks"], hooks_path) if "hooks" in fields else None,
    )


def _counter(value: object, path: str) -> CounterDeclaration:
    return CounterDeclaration(cap=_int(_object(value, path).get("cap"), _join(path, "cap")))


def _on_cap(value: object, path: str) -> OnCapEdge:
    fields = _object(value, path)
    return OnCapEdge(
        binding=_str(fields.get("binding"), _join(path, "binding")),
        reason=_str(fields.get("reason"), _join(path, "reason")),
        summary=_opt_str(fields, "summary", path),
        round_counts=_opt_strs(fields, "roundCounts", path),
        evidence=_opt_str(fields, "evidence", path),
    )


def _edge(value: object, path: str) -> Edge:
    fields = _object(value, path)
    if "binding" in fields:
        return BindingEdge(
            binding=_str(fields["binding"], _join(path, "binding")),
            resume=_opt_str(fields, "resume", path),
            reason=_opt_str(fields, "reason", path),
            summary=_opt_str(fields, "summary", path),
            round_counts=_opt_strs(fields, "roundCounts", path),
            evidence=_opt_str(fields, "evidence", path),
        )
    return RouteEdge(
        to=_str(fields.get("to"), _join(path, "to")),
        increment=_opt_str(fields, "increment", path),
        reset=_opt_str(fields, "reset", path),
        prompt=_opt_str(fields, "prompt", path),
        ledger=_opt_str(fields, "ledger", path),
        report=_opt_str_map(fields, "report", path),
        on_cap=_on_cap(fields["onCap"], _join(path, "onCap")) if "onCap" in fields else None,
    )


def _edges(value: object, path: str) -> Mapping[str, Edge]:
    fields = _object(value, path)
    return MappingProxyType({name: _edge(e, _join(path, name)) for name, e in fields.items()})


def _skip_entry(value: object, path: str) -> SkipEntry:
    fields = _object(value, path)
    return SkipEntry(
        when=_str(fields.get("when"), _join(path, "when")),
        to=_str(fields.get("to"), _join(path, "to")),
        report=_opt_str_map(fields, "report", path),
    )


def _skip(value: object, path: str) -> tuple[SkipEntry, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{path}: expected array")
    return tuple(_skip_entry(item, f"{path}[{index}]") for index, item in enumerate(value))


def _node(node_id: str, value: object, path: str) -> Node:
    fields = _object(value, path)
    kind = fields.get("kind")
    if kind == "terminal":
        return TerminalNode(
            id=node_id,
            binding=_str(fields.get("binding"), _join(path, "binding")),
            before=_opt_strs(fields, "before", path),
        )
    if kind == "round":
        return RoundNode(
            id=node_id,
            parallel=_bool(fields.get("parallel"), _join(path, "parallel")),
            gates=_strs(fields.get("gates"), _join(path, "gates")),
            writer=_opt_str(fields, "writer", path),
            counter=_opt_str(fields, "counter", path),
            converging_from=_opt_int(fields, "convergingFrom", path),
            plan=_opt_strs(fields, "plan", path),
            revision_note=_opt_str(fields, "revisionNote", path),
            outcomes=_edges(fields.get("outcomes"), _join(path, "outcomes")),
            before=_opt_strs(fields, "before", path),
            after=_opt_strs(fields, "after", path),
        )
    if kind == "dispatch":
        return DispatchNode(
            id=node_id,
            agent=_str(fields.get("agent"), _join(path, "agent")),
            heartbeat=_str(fields.get("heartbeat"), _join(path, "heartbeat")),
            outcomes=_edges(fields.get("outcomes"), _join(path, "outcomes")),
            prompts=_opt_strs(fields, "prompts", path),
            findings_folder=_opt_str(fields, "findingsFolder", path),
            skip=_skip(fields["skip"], _join(path, "skip")) if "skip" in fields else None,
            prompt_source=_opt_str(fields, "promptSource", path),
            before=_opt_strs(fields, "before", path),
            after=_opt_strs(fields, "after", path),
        )
    raise TypeError(f"{_join(path, 'kind')}: expected 'dispatch', 'round' or 'terminal'")


def build_flow_graph(graph: Mapping[str, object]) -> FlowGraph:
    """Build the typed model of `graph`, a parsed format-5 flow graph that already passed the
    schema check."""
    fields = _object(graph, "")
    if fields.get("formatVersion") != 5 or isinstance(fields.get("formatVersion"), bool):
        raise TypeError("formatVersion: expected 5")
    counters = _object(fields.get("counters"), "counters")
    nodes = _object(fields.get("nodes"), "nodes")
    return FlowGraph(
        format_version=5,
        flow=_str(fields.get("flow"), "flow"),
        description=_str(fields.get("description"), "description"),
        vocabulary=_vocabulary(fields.get("vocabulary"), "vocabulary"),
        start=_str(fields.get("start"), "start"),
        entries=_strs(fields.get("entries"), "entries"),
        counters=MappingProxyType(
            {name: _counter(c, f"counters.{name}") for name, c in counters.items()}
        ),
        paths=_str_map(fields.get("paths"), "paths"),
        reports=_strs(fields.get("reports"), "reports"),
        nodes=MappingProxyType(
            {node_id: _node(node_id, n, f"nodes.{node_id}") for node_id, n in nodes.items()}
        ),
    )
