"""The review-loop pattern: which round nodes are review loops, and the pattern's own walk rule.

The rule: a round node is a review loop when it declares `writer`, `counter` and
`convergingFrom`, which the schema requires together. A review loop's writer is dispatched with
its round's number. Its gates are dispatched with `converging`, which is
`counter >= convergingFrom`. Its shape is held by the review-loop clauses of checks 8 and 9
(`graphscene.engine.static_check`). A round that does not declare `writer` is a plain fan-out
and join.

Deliberately not covered:

- The round itself, which is engine-generic for any round (`graphscene.engine.transitions`,
  `graphscene.engine.rounds`): fan-out, the join and the held join, the round number, and the
  closed round carried on an edge and on an interrupt.
- What a host does with `plan`, `revisionNote` and a dispatch node's `findingsFolder`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from graphscene.model.flow_graph import FlowGraph, RoundNode


@dataclass(frozen=True)
class ReviewLoop:
    round: str
    writer: str
    counter: str
    converging_from: int


def review_loop(node: RoundNode) -> ReviewLoop | None:
    return _loop(node.id, node.writer, node.counter, node.converging_from)


def _loop(
    round_id: str, writer: str | None, counter: str | None, converging_from: int | None
) -> ReviewLoop | None:
    if writer is None or counter is None or converging_from is None:
        return None
    return ReviewLoop(round_id, writer, counter, converging_from)


def review_loops(graph: FlowGraph) -> tuple[ReviewLoop, ...]:
    """Every round node's review loop, in `nodes` key order."""
    loops = (review_loop(node) for node in graph.nodes.values() if isinstance(node, RoundNode))
    return tuple(loop for loop in loops if loop is not None)


def is_converging(loop: ReviewLoop, counters: Mapping[str, int]) -> bool:
    return counters[loop.counter] >= loop.converging_from
