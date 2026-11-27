"""The `adapters` layer: what touches a format or the outside world — the shipped schema, the
mapping from parsed JSON to the typed model, reading a file from disk, the file a walk's state
is kept in, a built-in executor for tests, and checking an executor's return against a JSON Schema.

The rule: this layer imports `graphscene.model`, `jsonschema` and the standard library, and never
imports `graphscene.engine`.
"""
