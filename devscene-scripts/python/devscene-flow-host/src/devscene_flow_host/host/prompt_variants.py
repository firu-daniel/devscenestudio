"""Which prompt variant a dispatch runs, and which findings files a revision carries.

The rule: reads as `flow-walker.sh`'s `render_block` picks a dispatch's `prompt:` and its
`arg.findings_file:` lines, and is the one home of that choice for `commands/render.py`,
`host/agent_prompts.py` and `host/planning_entry.py`.
- A node that declares no `prompts` runs no variant (`None`); one that does runs the dispatch's
  `prompt_variant`, or `INITIAL_VARIANT` when the dispatch carries none (`declared_variant`).
- `dispatch_variant` answers the same and raises `ValueError` naming the node and the variant when
  the variant is not one of the node's `prompts`; `declared_variant` checks nothing.
- The findings files are the walk's recorded revision findings when there are any, otherwise the
  `detail` of each `GateRecord` of the closed round that has one, in that tuple's order
  (`findings_files`).

Deliberately not covered:
- Where the recorded revision findings come from — `HostStep.revision_findings` or
  `RevisionFindingsStore` — and what a caller does with no findings file: each caller's.
- Rendering a variant or a findings file as a line or a prompt token: `commands/render.py`'s and
  `host/agent_prompts.py`'s.
"""

from typing import Final

from graphscene import Dispatch, DispatchNode, GateRecord

INITIAL_VARIANT: Final = "initial"
REVISION_VARIANT: Final = "revision"


def declared_variant(node: DispatchNode, dispatch: Dispatch) -> str | None:
    if node.prompts is None:
        return None
    return dispatch.prompt_variant if dispatch.prompt_variant is not None else INITIAL_VARIANT


def dispatch_variant(node: DispatchNode, dispatch: Dispatch) -> str | None:
    variant = declared_variant(node, dispatch)
    if variant is not None and node.prompts is not None and variant not in node.prompts:
        raise ValueError(f"graph gives '{dispatch.node}' the unknown prompt variant '{variant}'")
    return variant


def findings_files(
    revision_findings: tuple[str, ...], closed_round: tuple[GateRecord, ...]
) -> tuple[str, ...]:
    if revision_findings:
        return revision_findings
    return tuple(record.detail for record in closed_round if record.detail is not None)
