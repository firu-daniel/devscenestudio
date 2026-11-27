"""Composes the host's parts into GraphScene's `Walker` for one branch.

The rule: the walker `open_walker` returns reads and writes the branch's own store under the
configured `stateDir`, and asks a `HarnessPredicateHost` that re-reads the records on every
arrival. The configuration is read once, for `stateDir`; a `RecordError` from it propagates.

Deliberately not covered:
- Locating and loading the graph file, and rendering a `Step`: the `commands` layer's.
"""

from pathlib import Path

from graphscene import FlowGraph, Walker

from devscene_flow_host.host.predicates import HarnessPredicateHost
from devscene_flow_host.host.store import walk_store
from devscene_flow_host.records.config import read_config


def open_walker(
    repo_root: Path, branch: str, graph: FlowGraph, *, skipped: str | None = None
) -> Walker:
    config = read_config(repo_root)
    return Walker(
        graph,
        walk_store(repo_root, config.state_dir, branch),
        HarnessPredicateHost(repo_root, branch, skipped=skipped),
    )
