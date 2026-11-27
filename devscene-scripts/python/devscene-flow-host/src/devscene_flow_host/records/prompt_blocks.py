"""Reads a node's `promptSource` and the fenced blocks under that heading of a plugin document.

The rule: `parse_prompt_source` splits `<document> → ## <section> → ### <heading>`, the document
relative to the plugin directory. `read_prompt_blocks` reads the heading as `pnl_core_scan` reads it
and refuses as `pnl_init` does (`cli/templates/scripts/lib/planning-node-lib.sh`): a `##` line opens
a section; the heading is the `###` line equal to it inside the section equal to its own, and ends
at the next `##` or `###` line; a line opening with three backticks toggles a fence, and nothing
inside a fence is read as a heading; a trailing CR is stripped from every line. Each block is its
lines joined by `\\n` with trailing newlines stripped, as bash's `$(…)` strips them, in document
order. It reads values and decides nothing with them.

Deliberately not covered:
- Whether the number of blocks matches the node's `prompts`: the caller's.
- Filling a block's tokens: `host/agent_prompts.py`'s.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from devscene_flow_host.records.errors import RecordError

SOURCE_SEPARATOR: Final = " → "
SECTION_PREFIX: Final = "## "
HEADING_PREFIX: Final = "### "
FENCE_PREFIX: Final = "```"


@dataclass(frozen=True)
class PromptSource:
    """`document` is relative to the plugin directory; `section` a `## ` line, `heading` a `### `
    line."""

    document: str
    section: str
    heading: str


def parse_prompt_source(value: str) -> PromptSource:
    parts = value.split(SOURCE_SEPARATOR)
    if len(parts) == 3:
        document, section, heading = parts
        if (
            section.startswith(SECTION_PREFIX)
            and heading.startswith(HEADING_PREFIX)
            and document
            and not PurePosixPath(document).is_absolute()
            and ".." not in document.split("/")
        ):
            return PromptSource(document=document, section=section, heading=heading)
    raise ValueError(f"prompt source '{value}' is not '<document> → ## <section> → ### <heading>'")


def read_prompt_blocks(plugin_dir: Path, source: PromptSource) -> tuple[str, ...]:
    path = plugin_dir / source.document
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"the prompt document '{path}' cannot be read") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None

    lines = text.split("\n")
    # awk reads no record after a final newline.
    if lines and lines[-1] == "":
        lines.pop()

    in_section = in_heading = in_fence = False
    found_section = found_heading = False
    fences = 0
    blocks: list[list[str]] = []
    for raw_line in lines:
        line = raw_line.removesuffix("\r")
        if line.startswith(FENCE_PREFIX):
            if in_fence:
                in_fence = False
            else:
                in_fence = True
                if in_heading:
                    blocks.append([])
            if in_heading:
                fences += 1
            continue
        if in_fence:
            if in_heading:
                blocks[-1].append(line)
            continue
        if line.startswith(SECTION_PREFIX):
            in_section = line == source.section
            found_section = found_section or in_section
            in_heading = False
            continue
        if line.startswith(HEADING_PREFIX):
            in_heading = in_section and line == source.heading
            found_heading = found_heading or in_heading

    if not found_section:
        raise RecordError(f"the heading '{source.section}' is not in '{path}'")
    if not found_heading:
        raise RecordError(
            f"the heading '{source.heading}' is not under '{source.section}' in '{path}'"
        )
    if fences % 2:
        raise RecordError(
            f"the heading '{source.heading}' carries {fences} fence lines in '{path}', "
            "an unclosed block"
        )
    return tuple("\n".join(block).rstrip("\n") for block in blocks)
