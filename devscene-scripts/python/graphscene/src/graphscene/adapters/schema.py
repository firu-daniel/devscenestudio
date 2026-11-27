"""The format-5 schema check: `schema_violations` validates parsed data against the schema this
package ships (`schemas/flow-graph.schema.json`) and returns every violation, sorted by path then
reason.

A schema `pattern` is matched as ECMA-262, as `ajv` matches it: its `$` only at the very end of
the string, never before a trailing newline, and its `.` against no line terminator. A `pattern`
using any construct outside the translator's supported set is refused when the validator is
built, never passed to `re` untranslated.
"""

import json
import re
from collections.abc import Iterable
from functools import cache
from importlib.resources import files

from jsonschema import Draft7Validator

from graphscene.model.errors import Violation

_ECMA_DOT = "[^\\n\\r\\u2028\\u2029]"
_ECMA_SYNTAX = frozenset("^$\\.*+?()[]{}|/")
_QUANTIFIER = re.compile(r"\{[0-9]+(?:,[0-9]*)?\}")


def _render(path: Iterable[str | int]) -> str:
    rendered = ""
    for part in path:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered = f"{rendered}.{part}" if rendered else part
    return rendered


def _ecma_pattern(pattern: str, path: tuple[str | int, ...]) -> str:
    """Rewrite `pattern` so Python's `re` reads it as ECMA-262 does: an unescaped `$` outside a
    character class matches only at the very end, and an unescaped `.` outside one matches no
    line terminator.

    Supported, and read alike by both engines once those two rewrites are made: literals, `^`,
    `$`, `.`, `|`, `*`, `+`, `?`, a digits-only quantifier `{n}` / `{n,}` / `{n,m}`, a plain or
    `(?:` group, and a non-empty character class of literals and ranges with an optional leading
    `^`; plus a backslash before one of `^ $ \\ . * + ? ( ) [ ] { } | /`, or before `-` inside a
    class. Any other construct raises `ValueError` naming the pattern's schema path, so a schema
    change forces a decision about this translator."""

    def refuse(construct: str) -> ValueError:
        return ValueError(
            f"{_render(path)}: schema pattern {pattern!r} uses {construct!r}, "
            "which _ecma_pattern does not translate to ECMA-262"
        )

    out: list[str] = []
    in_class = False
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            escaped = pattern[index + 1 : index + 2]
            if not escaped:
                raise refuse(char)
            if escaped not in _ECMA_SYNTAX and not (in_class and escaped == "-"):
                raise refuse(char + escaped)
            out.append(char + escaped)
            index += 2
            continue
        if in_class:
            if char == "[":
                raise refuse(char)
            in_class = char != "]"
            out.append(char)
        elif char == "[":
            opener = "[^" if pattern.startswith("[^", index) else "["
            # `[]` and `[^]` are an empty and an any-character class in ECMA-262; Python reads
            # that `]` as a literal and keeps the class open.
            if pattern.startswith("]", index + len(opener)):
                raise refuse(opener + "]")
            in_class = True
            out.append(opener)
            index += len(opener)
            continue
        elif char == "$":
            out.append("\\Z")
        elif char == ".":
            out.append(_ECMA_DOT)
        elif char == "{":
            quantifier = _QUANTIFIER.match(pattern, index)
            if quantifier is None:
                raise refuse(char)
            out.append(quantifier.group())
            index = quantifier.end()
            continue
        elif char in "}]":
            raise refuse(char)
        elif pattern.startswith("(?", index):
            if not pattern.startswith("(?:", index):
                raise refuse(pattern[index : index + 3])
            out.append("(?:")
            index += 3
            continue
        else:
            out.append(char)
        index += 1
    return "".join(out)


# Keywords whose value is instance data, never a schema: copied unchanged.
_DATA_KEYWORDS = frozenset({"const", "enum", "default", "examples"})
# Keywords whose value maps a name (not a keyword) to a subschema.
_NAMED_SUBSCHEMAS = frozenset(
    {"properties", "definitions", "$defs", "dependentSchemas", "dependencies"}
)


def _ecma_patterns(node: object, path: tuple[str | int, ...] = ()) -> object:
    """Return a copy of the schema `node`, found at `path`, with every `pattern` keyword and every
    `patternProperties` key rewritten by `_ecma_pattern`; instance data under `const`, `enum`,
    `default` and `examples` is copied unchanged."""
    if isinstance(node, list):
        return [_ecma_patterns(child, path + (index,)) for index, child in enumerate(node)]
    if not isinstance(node, dict):
        return node
    copied: dict[object, object] = {}
    for key, child in node.items():
        here = path + (key,)
        if key in _DATA_KEYWORDS:
            copied[key] = child
        elif key == "pattern" and isinstance(child, str):
            copied[key] = _ecma_pattern(child, here)
        elif key == "patternProperties" and isinstance(child, dict):
            copied[key] = {
                _ecma_pattern(name, here + (name,)): _ecma_patterns(sub, here + (name,))
                for name, sub in child.items()
            }
        elif key in _NAMED_SUBSCHEMAS and isinstance(child, dict):
            copied[key] = {name: _ecma_patterns(sub, here + (name,)) for name, sub in child.items()}
        else:
            copied[key] = _ecma_patterns(child, here)
    return copied


@cache
def _validator() -> Draft7Validator:
    resource = files("graphscene") / "schemas" / "flow-graph.schema.json"
    schema = _ecma_patterns(json.loads(resource.read_text(encoding="utf-8")))
    assert isinstance(schema, dict)
    return Draft7Validator(schema)


def schema_violations(graph: object) -> list[Violation]:
    """Return every schema violation in `graph`, JSON-shaped data as `json.loads` returns it,
    sorted by path then reason; `[]` for a schema-valid graph. Never raises `GraphError`."""
    return sorted(
        (
            Violation(_render(error.absolute_path), error.message)
            for error in _validator().iter_errors(graph)
        ),
        key=lambda violation: (violation.path, violation.reason),
    )
