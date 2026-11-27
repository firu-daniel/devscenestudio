"""Loading a declared flow graph: turning parsed or on-disk data into the typed `FlowGraph` model,
or into a `GraphError` whose violations name the node and the field.

The rule: a returned graph has passed the format-5 schema this package ships
(`schemas/flow-graph.schema.json`), been built, then passed the vocabulary check and the static
checks, in that order. A graph failing one stage never reaches the next.

Deliberately not checked:
- Duplicate JSON keys, which `json.loads` collapses to the last.
- What runs a node (an agent's existence, its return schema): a harness check, outside this
  package.
"""

import os

from graphscene.adapters.builder import build_flow_graph
from graphscene.adapters.json_file import read_json_file
from graphscene.adapters.schema import schema_violations
from graphscene.engine.static_check import static_violations
from graphscene.engine.vocabulary import vocabulary_violations
from graphscene.model.errors import GraphError
from graphscene.model.flow_graph import FlowGraph


def load_graph(graph: object) -> FlowGraph:
    """Validate `graph`, JSON-shaped data as `json.loads` returns it, and build its typed model."""
    found = schema_violations(graph)
    if found:
        raise GraphError("schema", found)
    assert isinstance(graph, dict)
    built = build_flow_graph(graph)
    found = vocabulary_violations(built)
    if found:
        raise GraphError("vocabulary", found)
    found = static_violations(built)
    if found:
        raise GraphError("static", found)
    return built


def load_graph_file(path: str | os.PathLike[str]) -> FlowGraph:
    """Read `path` as UTF-8 JSON and load it; a file that is not UTF-8 or not JSON is a parse-stage
    `GraphError`, and an `OSError` propagates unchanged."""
    return load_graph(read_json_file(path))
