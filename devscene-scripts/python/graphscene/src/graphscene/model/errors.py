"""The one error shape every stage of loading a flow graph reports in.

A `Violation` names where a declared graph is wrong and why; a `GraphError` carries the stage
that rejected the graph and every violation it found.

The rule: a violation's path names the node and the field, dotted from the graph root — object
keys joined with ".", array indices as "[i]", and "" for the root itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(frozen=True)
class Violation:
    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path or '(root)'}: {self.reason}"


Stage: TypeAlias = Literal["parse", "schema", "vocabulary", "static"]


class GraphError(ValueError):
    stage: Stage
    violations: tuple[Violation, ...]

    def __init__(self, stage: Stage, violations: Sequence[Violation]) -> None:
        if not violations:
            raise ValueError("a GraphError carries at least one violation")
        self.stage = stage
        self.violations = tuple(violations)
        lines = [f"flow graph failed the {stage} check:", *(str(v) for v in self.violations)]
        super().__init__("\n".join(lines))
