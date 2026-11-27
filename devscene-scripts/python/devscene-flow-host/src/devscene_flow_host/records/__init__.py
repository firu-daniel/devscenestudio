"""The `records` layer: reads the repository's records — `devscene.config.json`, the
flow-progress ledger, the round and reviewer files, and the plugin's manifest, agent definitions
and return schemas — into plain values.

The rule: this layer imports the standard library and `devscene_flow_host.records` only, never
`graphscene`. It answers no GraphScene protocol.
"""
