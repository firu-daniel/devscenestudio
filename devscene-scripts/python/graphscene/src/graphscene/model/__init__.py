"""The `model` layer: the typed flow-graph model, the one error shape every stage reports in, and
the walk's actions, its state, the executor that runs a node and its result, and the protocols
the engine drives.

The rule: this layer imports the standard library only. A `typing.Protocol` that an adapter
implements and the engine drives is declared here, so an adapter never imports the engine.
"""
