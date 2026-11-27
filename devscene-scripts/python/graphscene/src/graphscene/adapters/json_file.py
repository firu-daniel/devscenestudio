"""Reading a flow-graph file from disk into parsed JSON data.

The rule: the file must be UTF-8 and JSON. A file that is not raises a parse-stage `GraphError`
whose one root violation reads `not valid UTF-8: <reason> (byte <n>)` or
`not valid JSON: <message> (line <n>, column <n>)`; an `OSError` propagates unchanged.
"""

import json
import os

from graphscene.model.errors import GraphError, Violation


def read_json_file(path: str | os.PathLike[str]) -> object:
    """Read `path` as UTF-8 JSON and return the parsed data."""
    with open(path, "rb") as handle:
        data = handle.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        reason = f"not valid UTF-8: {error.reason} (byte {error.start})"
        raise GraphError("parse", [Violation("", reason)]) from error
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as error:
        reason = f"not valid JSON: {error.msg} (line {error.lineno}, column {error.colno})"
        raise GraphError("parse", [Violation("", reason)]) from error
    return parsed
