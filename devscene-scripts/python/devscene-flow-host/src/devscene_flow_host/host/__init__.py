"""The `host` layer: answers GraphScene's protocols over the values `records` reads — the
`PredicateHost`, the walk's `StateStore`, the composed `Walker`, and `ClaudeExecutor`, the
harness's `Executor`, which launches one `claude` session per dispatched node — and holds the
harness's rules over its records.

The rule: this layer imports `devscene_flow_host.records`, `graphscene` through its public
surface only, and the standard library. It never imports `devscene_flow_host.commands`.
"""
