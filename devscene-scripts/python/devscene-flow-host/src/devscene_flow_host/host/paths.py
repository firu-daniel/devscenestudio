"""A graph's path templates rendered to repo-relative paths.

The rule: `render_path` reads as `flow-walker.sh`'s `render_path` over its `subst`: every
occurrence of `{state_dir}` is replaced, then every `{branch}`, then — only when a round number is
given — every `{round}`; the result is otherwise returned unchanged, a trailing `/` included.

Deliberately not covered:
- Resolving a rendered path against the repository root: the caller's.
- Any placeholder other than the three named above.
"""

from typing import Final

from devscene_flow_host.records.round_evidence import ROUND_PLACEHOLDER

STATE_DIR_PLACEHOLDER: Final = "{state_dir}"
BRANCH_PLACEHOLDER: Final = "{branch}"


def render_path(template: str, state_dir: str, branch: str, round_number: int | None = None) -> str:
    rendered = template.replace(STATE_DIR_PLACEHOLDER, state_dir)
    rendered = rendered.replace(BRANCH_PLACEHOLDER, branch)
    if round_number is not None:
        rendered = rendered.replace(ROUND_PLACEHOLDER, str(round_number))
    return rendered
