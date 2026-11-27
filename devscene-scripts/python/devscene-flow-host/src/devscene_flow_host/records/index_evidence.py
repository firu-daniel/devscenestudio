"""Reads the escalation evidence a story index carries: whether it has a `## Rejected findings`
section, the entries there still open, and whether it has a `## Scope register` section.

The rule: `read_index_evidence` reads as the bash walker's `fw_index_evidence` does
(`cli/templates/scripts/lib/flow-walker-gates.sh`). A heading is compared with trailing spaces,
tabs and `\\r` removed; under `## Rejected findings`, every `- ` line not containing
`call stands` is open and kept as read, `\\r` included, as `awk` prints `$0`. A repeated
`## Rejected findings` heading adds no entry of its own, and its open entries join the rest in
file order, as `fw_index_evidence` prints one `evidence:` line for any number of such headings.
An absent index is `None`; text that is not UTF-8 is a `RecordError`. It returns the evidence
and decides nothing with it.

Deliberately not covered:
- Which `## Scope register` rows are in dispute: that is judgement and stays with the
  orchestrator; only the heading's presence is read.
- Rendering the `evidence:` / `evidence.open:` lines, which is the `commands` layer's.
- An `OSError` other than a missing file: it propagates.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devscene_flow_host.records.errors import RecordError

REJECTED_FINDINGS_HEADING: Final = "## Rejected findings"
SCOPE_REGISTER_HEADING: Final = "## Scope register"
CALL_STANDS: Final = "call stands"

_HEADING_PREFIX: Final = "## "
_ENTRY_PREFIX: Final = "- "
_TRAILING: Final = " \t\r"


@dataclass(frozen=True)
class IndexEvidence:
    rejected_findings: bool
    open_rejections: tuple[str, ...]
    scope_register: bool


def read_index_evidence(path: Path) -> IndexEvidence | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None
    rejected_findings = False
    scope_register = False
    in_rejected = False
    open_rejections: list[str] = []
    for line in text.split("\n"):
        if line.startswith(_HEADING_PREFIX):
            heading = line.rstrip(_TRAILING)
            in_rejected = heading == REJECTED_FINDINGS_HEADING
            if in_rejected:
                rejected_findings = True
            elif heading == SCOPE_REGISTER_HEADING:
                scope_register = True
            continue
        if in_rejected and line.startswith(_ENTRY_PREFIX) and CALL_STANDS not in line:
            open_rejections.append(line)
    return IndexEvidence(rejected_findings, tuple(open_rejections), scope_register)
