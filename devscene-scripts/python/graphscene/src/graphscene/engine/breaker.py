"""The run-level undelivered breaker: `UndeliveredBreaker`, tripped by consecutive undelivered sets.

The rule: the breaker counts consecutive sets, not sessions. `observe(True)` adds one strike for
a set that had an `undelivered` result, and `observe(False)` resets the strikes to 0 for a
delivered set; it is tripped once its strikes reach its limit. It is independent of every node's
attempts. Its limit is set at construction and nowhere else (`ExecutionLimits` carries none);
`3` is GraphScene's default, equal to the pilot's three undelivered sets
(`docs/flow-graph-walker.md` → `pd_undelivered`), and a limit below 1 is refused with
`ValueError`.

Deliberately not covered:

- Persisting the count across processes: the host's.
- Deciding whether a set had an `undelivered` result, and what a host does once the breaker
  trips: `execute_set`'s and the host's.
"""


class UndeliveredBreaker:
    def __init__(self, limit: int = 3) -> None:
        if not limit >= 1:
            raise ValueError(f"UndeliveredBreaker: limit must be >= 1, got {limit}")
        self._limit = limit
        self._strikes = 0

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def strikes(self) -> int:
        return self._strikes

    @property
    def tripped(self) -> bool:
        return self._strikes >= self._limit

    def observe(self, undelivered: bool) -> int:
        self._strikes = self._strikes + 1 if undelivered else 0
        return self._strikes

    def reset(self) -> None:
        self._strikes = 0
