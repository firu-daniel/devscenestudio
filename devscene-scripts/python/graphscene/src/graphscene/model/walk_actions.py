"""The steps a walk returns and the passages it records on the way.

A walk step is an `Action` the host acts on, or `Refused` when the walk could not take the step.
A `Passage` records a node the walk went through without dispatching it: a skipped node, a closed
round or a ledger entry.

The rule: every class is a `@dataclass(frozen=True)`, sequences are `tuple`s, mappings are a
`types.MappingProxyType` over a fresh `dict`, and each variant carries its discriminator as a
`ClassVar[Literal[...]]` named `kind`, as `graphscene.model.flow_graph.DispatchNode.kind` does.

Field meanings:

- `agent` is `None` when `node` is a round node.
- `Dispatch.prompt_variant` is one of the node's declared `prompts`, or `None`; never prompt text.
- `evidence` is a `paths` key, never a resolved path.
- `round_counts` holds node ids, never counts: counting files is the host's.
- `End.reports` is `(slot, status)` pairs in the graph's `reports` order.
- A `Dispatch` inside a `DispatchSet` carries `passed=()`, and the set carries the passages.
- `SkipPassage.status` is the skipping predicate's `records`.
- `GateRecord.detail` is the host's opaque detail, such as a findings path.
- `Interrupt.closed_round` is the closed round the interrupted dispatch carried; the resume
  re-dispatches with it.

Deliberately not covered:

- Heartbeats and path templates: the host renders them.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Literal, TypeAlias

from graphscene.model.flow_graph import Verdict


@dataclass(frozen=True)
class GateRecord:
    gate: str
    outcome: str
    detail: str | None


@dataclass(frozen=True)
class SkipPassage:
    kind: ClassVar[Literal["skip"]] = "skip"
    node: str
    status: str


@dataclass(frozen=True)
class RoundPassage:
    kind: ClassVar[Literal["round"]] = "round"
    round: str
    number: int
    verdict: Verdict


@dataclass(frozen=True)
class LedgerPassage:
    kind: ClassVar[Literal["ledger"]] = "ledger"
    entry: str


Passage: TypeAlias = SkipPassage | RoundPassage | LedgerPassage


@dataclass(frozen=True)
class Dispatch:
    kind: ClassVar[Literal["dispatch"]] = "dispatch"
    node: str
    agent: str
    prompt_variant: str | None
    counters: Mapping[str, int]
    round_number: int | None
    converging: bool | None
    closed_round: tuple[GateRecord, ...]
    passed: tuple[Passage, ...]


@dataclass(frozen=True)
class DispatchSet:
    kind: ClassVar[Literal["set"]] = "set"
    round: str
    number: int
    dispatches: tuple[Dispatch, ...]
    passed: tuple[Passage, ...]


@dataclass(frozen=True)
class Wait:
    kind: ClassVar[Literal["wait"]] = "wait"
    round: str
    recorded: GateRecord
    pending: tuple[str, ...]


@dataclass(frozen=True)
class Interrupt:
    kind: ClassVar[Literal["interrupt"]] = "interrupt"
    binding: str
    node: str
    agent: str | None
    resume: str
    resume_outcome: str
    passed: tuple[Passage, ...]
    closed_round: tuple[GateRecord, ...] = ()


@dataclass(frozen=True)
class Stop:
    kind: ClassVar[Literal["stop"]] = "stop"
    binding: str
    node: str
    agent: str | None
    reason: str
    summary: str | None
    evidence: str | None
    round_counts: tuple[str, ...]
    held: tuple[GateRecord, ...]
    closed_round: tuple[GateRecord, ...]
    passed: tuple[Passage, ...]


@dataclass(frozen=True)
class End:
    kind: ClassVar[Literal["end"]] = "end"
    binding: str
    node: str
    reports: tuple[tuple[str, str], ...]
    passed: tuple[Passage, ...]


@dataclass(frozen=True)
class Refused:
    kind: ClassVar[Literal["refused"]] = "refused"
    reason: str


Action: TypeAlias = Dispatch | DispatchSet | Wait | Interrupt | Stop | End
Step: TypeAlias = Action | Refused
