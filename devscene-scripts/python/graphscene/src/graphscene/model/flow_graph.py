"""The typed, immutable form of a declared format-5 flow graph, built by
`graphscene.adapters.builder.build_flow_graph`.

- Absent keys: an absent optional key is `None` — `Vocabulary.hooks`, a node's `prompt_source`,
  `before` and `after` among them. The one exception is `held`, which the schema allows only as
  `true`: it is a `bool`, `False` when absent.
- Fixed words: the only fixed words are the schema's own enums, typed as `NodeKind`, `Primitive`
  and `Verdict`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Literal, TypeAlias

NodeKind: TypeAlias = Literal["dispatch", "round", "terminal"]
Primitive: TypeAlias = Literal["interrupt", "stop", "end"]
Verdict: TypeAlias = Literal["pass", "fail"]


@dataclass(frozen=True)
class OutcomeDeclaration:
    verdict: Verdict | None
    held: bool


@dataclass(frozen=True)
class InterruptBinding:
    primitive: ClassVar[Literal["interrupt"]] = "interrupt"
    resume_outcome: str


@dataclass(frozen=True)
class StopBinding:
    primitive: ClassVar[Literal["stop"]] = "stop"
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EndBinding:
    primitive: ClassVar[Literal["end"]] = "end"


BindingDeclaration: TypeAlias = InterruptBinding | StopBinding | EndBinding


@dataclass(frozen=True)
class PredicateDeclaration:
    records: str
    in_round_counts: bool


@dataclass(frozen=True)
class HookDeclaration:
    pass


@dataclass(frozen=True)
class Vocabulary:
    outcomes: Mapping[str, OutcomeDeclaration]
    bindings: Mapping[str, BindingDeclaration]
    predicates: Mapping[str, PredicateDeclaration]
    hooks: Mapping[str, HookDeclaration] | None


@dataclass(frozen=True)
class CounterDeclaration:
    cap: int


@dataclass(frozen=True)
class OnCapEdge:
    binding: str
    reason: str
    summary: str | None
    round_counts: tuple[str, ...] | None
    evidence: str | None


@dataclass(frozen=True)
class RouteEdge:
    to: str
    increment: str | None
    reset: str | None
    prompt: str | None
    ledger: str | None
    report: Mapping[str, str] | None
    on_cap: OnCapEdge | None


@dataclass(frozen=True)
class BindingEdge:
    binding: str
    resume: str | None
    reason: str | None
    summary: str | None
    round_counts: tuple[str, ...] | None
    evidence: str | None


Edge: TypeAlias = RouteEdge | BindingEdge


@dataclass(frozen=True)
class SkipEntry:
    when: str
    to: str
    report: Mapping[str, str] | None


@dataclass(frozen=True)
class DispatchNode:
    kind: ClassVar[Literal["dispatch"]] = "dispatch"
    id: str
    agent: str
    heartbeat: str
    outcomes: Mapping[str, Edge]
    prompts: tuple[str, ...] | None
    findings_folder: str | None
    skip: tuple[SkipEntry, ...] | None
    prompt_source: str | None
    before: tuple[str, ...] | None
    after: tuple[str, ...] | None


@dataclass(frozen=True)
class RoundNode:
    """`writer`, `counter` and `converging_from` are `None` together on a round that is not a
    review loop (`graphscene.engine.review_loop`)."""

    kind: ClassVar[Literal["round"]] = "round"
    id: str
    parallel: bool
    gates: tuple[str, ...]
    writer: str | None
    counter: str | None
    converging_from: int | None
    plan: tuple[str, ...] | None
    revision_note: str | None
    outcomes: Mapping[str, Edge]
    before: tuple[str, ...] | None
    after: tuple[str, ...] | None


@dataclass(frozen=True)
class TerminalNode:
    kind: ClassVar[Literal["terminal"]] = "terminal"
    id: str
    binding: str
    before: tuple[str, ...] | None


Node: TypeAlias = DispatchNode | RoundNode | TerminalNode


@dataclass(frozen=True)
class FlowGraph:
    format_version: Literal[5]
    flow: str
    description: str
    vocabulary: Vocabulary
    start: str
    entries: tuple[str, ...]
    counters: Mapping[str, CounterDeclaration]
    paths: Mapping[str, str]
    reports: tuple[str, ...]
    nodes: Mapping[str, Node]
