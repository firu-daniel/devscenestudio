"""A node's round, and a reviewer's next index outside a round.

The rule: reads as `flow-walker.sh`'s `round_of_gate`, `round_of_writer` and `render_block`'s
`findingsFolder` branch. A node's round is the first round in `graph.nodes` order that lists the
node — in its `gates` for `round_of_gate`, as its `writer` for `round_of_writer`. A reviewer's
index outside a round is read only from `DispatchNode.findings_folder`, rendered and resolved
against the repository root: the next free `review_<n>.md` index there.

Deliberately not covered:
- A round gate's iteration: it is the round number GraphScene's `Dispatch` already carries, so
  `review_iteration` answers `None` for it.
"""

from pathlib import Path

from graphscene import DispatchNode, FlowGraph, RoundNode

from devscene_flow_host.host.paths import render_path
from devscene_flow_host.records.round_files import next_review_index


def round_of_gate(graph: FlowGraph, node: str) -> RoundNode | None:
    for candidate in graph.nodes.values():
        if isinstance(candidate, RoundNode) and node in candidate.gates:
            return candidate
    return None


def round_of_writer(graph: FlowGraph, node: str) -> RoundNode | None:
    for candidate in graph.nodes.values():
        if isinstance(candidate, RoundNode) and candidate.writer == node:
            return candidate
    return None


def review_iteration(
    graph: FlowGraph, repo_root: Path, state_dir: str, branch: str, node: str
) -> int | None:
    found = graph.nodes.get(node)
    if not isinstance(found, DispatchNode) or round_of_gate(graph, node) is not None:
        return None
    if found.findings_folder is None:
        return None
    return next_review_index(repo_root / render_path(found.findings_folder, state_dir, branch))
