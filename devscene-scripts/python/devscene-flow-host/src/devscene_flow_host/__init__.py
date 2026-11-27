"""The harness's GraphScene host.

It holds only the code that feeds GraphScene the harness's configuration, records, predicates and
hooks, the harness's executor — `ClaudeExecutor`, which runs each dispatched node as one headless
`claude` session — and the commands over it; anything useful without DevScene
belongs in GraphScene; another DevScene Python integration gets its own `devscene`-prefixed
package.

The rule: this package imports only the standard library, itself and its declared runtime
dependencies. It reaches `graphscene` through its public surface only — `import graphscene` or
`from graphscene import <name in graphscene.__all__>`, never a submodule such as
`graphscene.engine` — and GraphScene never imports it (`tests/test_boundary.py`).

The package is three layers, `commands` over `host` over `records`, and an import only ever
points downward; only `host` and `commands` import `graphscene`. The contracts in
`pyproject.toml` hold them (`tests/test_layers.py`). The package root exports nothing, because
adopters never import this package, and no module inside the package imports from the package
root: each imports the defining module of what it needs.
"""

__all__: list[str] = []
