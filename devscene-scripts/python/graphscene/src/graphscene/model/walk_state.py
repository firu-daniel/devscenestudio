"""The walk's persisted position, the input a host hands `start` to begin inside a round, and the
two protocols the engine drives and a caller implements.

`WalkState` is where a walk stands; `StateStore` is where it is saved; `PredicateHost` answers the
predicates the graph names.

The rule:

- A `WalkState` is a position, never a history.
- A `WalkState` is replaced whole and never mutated.
- `pending` is exactly what `current` returns.

Field meanings:

- `node` is the pending node; it is the round node while a set is pending.
- `OpenRound.due` is the gates dispatched in this set, in the round's `gates` order.
- `OpenRound.records` is keyed by gate and holds verdict and held outcomes alike.
- `prompts` is the prompt variant last routed to each dispatch node; an interrupt's resume
  re-dispatches with it.
- `reports` is slot → status recorded so far.
- `skipped` is node → the predicate name that skipped it on its latest arrival, so a cap's
  `round_counts` can drop a node whose predicate has `in_round_counts` false.
- `RoundResume` is a host's entry into a round at `Walker.start`: `round` is the round node,
  `number` its round number, and `records` the outcomes already recorded, in any order. It carries
  no counter, because `start` sets every counter to 0. It is never saved: a resumed walk is saved
  as an ordinary `WalkState`, so the walk-state document is unchanged.
"""

import contextlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias

from graphscene.model.walk_actions import Action, GateRecord

Awaiting: TypeAlias = Literal["dispatch", "set", "interrupt", "done"]


@dataclass(frozen=True)
class OpenRound:
    round: str
    number: int
    due: tuple[str, ...]
    records: Mapping[str, GateRecord]


@dataclass(frozen=True)
class RoundResume:
    round: str
    number: int
    records: tuple[GateRecord, ...] = ()


@dataclass(frozen=True)
class WalkState:
    flow: str
    node: str
    awaiting: Awaiting
    pending: Action
    counters: Mapping[str, int]
    round_numbers: Mapping[str, int]
    open_round: OpenRound | None
    prompts: Mapping[str, str]
    reports: Mapping[str, str]
    skipped: Mapping[str, str]


class StateStore(Protocol):
    """Where a walk is saved.

    The contract the engine relies on:

    - `read` returns `None` when no walk is saved.
    - `write` replaces the whole state atomically, so a `read` without the lock is never torn.
    - `lock` is exclusive across processes and threads, and released on every exit path.
    """

    def read(self) -> WalkState | None: ...

    def write(self, state: WalkState) -> None: ...

    def lock(self) -> contextlib.AbstractContextManager[None]: ...


class PredicateHost(Protocol):
    """Answers a named predicate for a node.

    The host decides what a predicate means; the engine never reads configuration
    (`graphscene/README.md` → `## The boundary`). `True` skips the node, `False` does not, and
    `None` means the host cannot answer, which the walk refuses rather than guesses.
    """

    def answer(self, predicate: str, node: str) -> bool | None: ...
