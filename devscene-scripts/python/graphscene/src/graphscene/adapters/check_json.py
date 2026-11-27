"""The check document: the JSON form the result of loading a graph is reported in, built from the
`GraphError` loading raised, or from its absence (`check_document`).

The rule: the document is `{"stage", "violations"}`, in that key order; a graph that loaded is
`{"stage": null, "violations": []}`. Each violation is `{"path", "check", "reason"}`, in that key
order and in the `GraphError`'s own violation order. `path` is `Violation.path` verbatim, `""` for
the root — never the `(root)` that `Violation.__str__` renders. `check` is set only for stage
`static`, from the check id before the reason's first `": "`, and `reason` is then the text after
it; a static reason with no `": "`, and every reason of another stage, keeps `check` `null` and
`reason` verbatim.

Deliberately not covered:
- Serializing the document to text: the caller's, with `json.dumps`.
- Validating that a static check id is one `graphscene.engine.static_check` defines.
"""

from graphscene.model.errors import GraphError


def check_document(error: GraphError | None) -> dict[str, object]:
    """Return the JSON-ready check document for `error`, or for a clean load when it is `None`."""
    if error is None:
        return {"stage": None, "violations": []}
    violations: list[object] = []
    for violation in error.violations:
        check: str | None = None
        reason = violation.reason
        if error.stage == "static":
            head, separator, tail = reason.partition(": ")
            if separator:
                check, reason = head, tail
        violations.append({"path": violation.path, "check": check, "reason": reason})
    return {"stage": error.stage, "violations": violations}
