"""The per-set safety contract: `clear_set`, checked before anything of a dispatch set goes out.

The rule: `clear_set` asks `stop_requested` once per dispatch before anything else, then
`pause_requested` once, then checks the whole set against `ExecutionLimits.dispatch_cap`,
halting when `counter.total()` plus the set's size would pass it; the first check that fails
returns its `Halt`, and `None` means the set may go out. This is the order of
`docs/flow-graph-walker.md` → `### Item 4` → **On the script-driven path.** No halt ever sends
part of a set. `clear_set` only checks and never calls `DispatchCounter.increment`. A STOP or
PAUSE raised while a set is out is honoured by the next `clear_set`, so a running set is never
cancelled. A retry pass is a set like any other. An empty set is refused with `ValueError`.

Deliberately not covered:

- Counting each launch and taking its number as the `Launch.seq`: `execute_set`'s.
- Where STOP and PAUSE live and where the counter is kept: the host's, through `RunSignals` and
  `DispatchCounter`.
"""

from collections.abc import Sequence

from graphscene.model.run_control import DispatchCounter, ExecutionLimits, Halt, RunSignals
from graphscene.model.walk_actions import Dispatch


def clear_set(
    dispatches: Sequence[Dispatch],
    signals: RunSignals,
    counter: DispatchCounter,
    limits: ExecutionLimits,
) -> Halt | None:
    n = len(dispatches)
    if n == 0:
        raise ValueError("clear_set: a set holds at least one dispatch")
    stop = False
    for _ in dispatches:
        if signals.stop_requested():
            stop = True
    if stop:
        return Halt("stop", f"stop requested before a set of {n}")
    if signals.pause_requested():
        return Halt("pause", f"pause requested before a set of {n}")
    cap = limits.dispatch_cap
    if cap is not None:
        total = counter.total()
        if total + n > cap:
            nodes = ", ".join(d.node for d in dispatches)
            return Halt(
                "cap",
                f"{total} dispatched; a set of {n} ({nodes}) would pass the cap {cap}",
            )
    return None
