"""The per-node attempt rule: `AttemptBook`, which turns one node's `NodeResult` into its
`Settlement`.

The rule:

- A node never seen, or last settled to `Recorded`, is on attempt 1; `attempt` reports the
  attempt the node's next run is.
- `Completed(outcome, detail)` is `Recorded(NodeRecord(node, outcome, detail))`, and the node's
  count restarts.
- `Failed("agent", reason)` is `Recorded(NodeRecord(node, failure_outcome, reason))` at once,
  whatever attempts remain, and the count restarts. An agent failure is never retried.
- `Failed("undelivered", reason)` is `Redispatch(node, reason)`, and leaves the node's attempt
  number and infra reasons unchanged: it uses up no attempt.
- `Failed("infra", reason)` on attempt `k` below `max_attempts` notes the reason and is
  `Retry(node, k + 1, reason)`, retrying that node alone.
- `Failed("infra", reason)` on the last attempt is `Recorded(NodeRecord(node, failure_outcome,
  detail))`, and the count restarts. `detail` is `all <max> attempts failed for an infrastructure
  reason` followed by one `\\nattempt <i> of <max>: <reason_i>` line per attempt, in order.
- Counts are kept per node id; one node's settlements never change another's.

Deliberately not covered:

- Whether `failure_outcome` is declared and held for the node: the walk refuses an undeclared
  outcome when the caller records it.
- The backoff between attempts: `execute_set`'s.
- Persisting the book across processes: the host's.
"""

from graphscene.model.execution import Completed, NodeResult
from graphscene.model.run_control import (
    ExecutionLimits,
    NodeRecord,
    Recorded,
    Redispatch,
    Retry,
    Settlement,
)


class AttemptBook:
    def __init__(self) -> None:
        self._reasons: dict[str, tuple[str, ...]] = {}

    def attempt(self, node: str) -> int:
        return len(self._reasons.get(node, ())) + 1

    def settle(
        self, node: str, result: NodeResult, limits: ExecutionLimits, failure_outcome: str
    ) -> Settlement:
        if isinstance(result, Completed):
            self._reasons.pop(node, None)
            return Recorded(NodeRecord(node, result.outcome, result.detail))
        if result.failure == "agent":
            self._reasons.pop(node, None)
            return Recorded(NodeRecord(node, failure_outcome, result.reason))
        if result.failure == "undelivered":
            return Redispatch(node, result.reason)
        current = self.attempt(node)
        reasons = (*self._reasons.get(node, ()), result.reason)
        if current < limits.max_attempts:
            self._reasons[node] = reasons
            return Retry(node, current + 1, result.reason)
        self._reasons.pop(node, None)
        total = limits.max_attempts
        lines = "".join(
            f"\nattempt {index} of {total}: {reason}"
            for index, reason in enumerate(reasons, start=1)
        )
        detail = f"all {total} attempts failed for an infrastructure reason{lines}"
        return Recorded(NodeRecord(node, failure_outcome, detail))
