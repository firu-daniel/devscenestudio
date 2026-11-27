"""The calls a node hook is run with and the `HookHost` protocol a host implements to run them: the
five call types `BeforeDispatch`, `AfterDispatch`, `BeforeRound`, `AfterRound` and `BeforeEnd`, and
their union `HookCall`.

The rule:

- A dispatch node takes `before` (`BeforeDispatch`) and `after` (`AfterDispatch`); a round node
  takes `before` (`BeforeRound`) and `after` (`AfterRound`); a terminal node takes `before`
  (`BeforeEnd`).
- The hooks are run mode's, called from `graphscene.engine.set_execution` and
  `graphscene.engine.run_loop`. `Walker` runs none.
- A hook may run more than once for the same node, round or end — a retry, or a `current` that
  returns the same step again — so its side effects must be repeatable, as an executor's are.
- An exception from `run` propagates out of run mode unchanged.
- `provides` is asked once per declared hook name before the walk is touched.
- Each variant carries its discriminator as a `ClassVar[Literal[...]]` named `kind`, as
  `graphscene.model.walk_actions` does.

Deliberately not covered:

- What a hook does: the host's.
- Offloading a blocking hook: the host wraps its work in `asyncio.to_thread`, as for an executor.
- Any hook outside run mode.
"""

from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, TypeAlias

from graphscene.model.run_control import NodeRecord
from graphscene.model.walk_actions import Action, Dispatch, DispatchSet, End, RoundPassage


@dataclass(frozen=True)
class BeforeDispatch:
    """`seq` is the `Launch.seq` this attempt took; `attempt` the number `AttemptBook` gave it."""

    kind: ClassVar[Literal["before_dispatch"]] = "before_dispatch"
    dispatch: Dispatch
    seq: int
    attempt: int


@dataclass(frozen=True)
class AfterDispatch:
    """`step` is what `Walker.next` returned for `record`."""

    kind: ClassVar[Literal["after_dispatch"]] = "after_dispatch"
    record: NodeRecord
    step: Action


@dataclass(frozen=True)
class BeforeRound:
    kind: ClassVar[Literal["before_round"]] = "before_round"
    dispatch_set: DispatchSet


@dataclass(frozen=True)
class AfterRound:
    """`step` is the step whose `passed` carries `passage`."""

    kind: ClassVar[Literal["after_round"]] = "after_round"
    passage: RoundPassage
    step: Action


@dataclass(frozen=True)
class BeforeEnd:
    kind: ClassVar[Literal["before_end"]] = "before_end"
    end: End


HookCall: TypeAlias = BeforeDispatch | AfterDispatch | BeforeRound | AfterRound | BeforeEnd


class HookHost(Protocol):
    """Runs the hooks a graph names, under this module's rule."""

    def provides(self, hook: str) -> bool: ...

    async def run(self, hook: str, call: HookCall) -> None: ...
