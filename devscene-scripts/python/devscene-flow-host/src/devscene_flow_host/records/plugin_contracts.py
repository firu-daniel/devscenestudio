"""The rule: `read_plugin_name` reads `.claude-plugin/plugin.json`'s `name` as `pnl_init` does,
`read_agent_contract` reads an agent definition's `tools:` line as `pnl_agent_tools_var` does and
its return schema as `pnl_load_schemas` does (`cli/templates/scripts/lib/planning-node-lib.sh`).
Both files are re-read on every call. It reads values and decides nothing with them.

Deliberately not checked:
- Whether the return schema is valid JSON Schema: the executor's construction check, through
  `graphscene.return_violations`, does that.
- Every frontmatter key other than `tools:`.
- Every plugin manifest key other than `name`.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from devscene_flow_host.records.errors import RecordError

PLUGIN_MANIFEST: Final = ".claude-plugin/plugin.json"
AGENTS_DIRECTORY: Final = "agents"
SCHEMAS_DIRECTORY: Final = "schemas"
_AGENT_NAME: Final = re.compile(r"[a-z0-9][a-z0-9-]*")
_FENCE: Final = "---"
_TOOLS_KEY: Final = "tools:"


@dataclass(frozen=True)
class AgentContract:
    """`tools` in the `tools:` line's order; `return_schema` read-only at its top level."""

    agent: str
    tools: tuple[str, ...]
    return_schema: Mapping[str, object]


def _agent_definition_path(plugin_dir: Path, agent: str) -> Path:
    return plugin_dir / AGENTS_DIRECTORY / f"{_checked(agent)}.md"


def _return_schema_path(plugin_dir: Path, agent: str) -> Path:
    return plugin_dir / SCHEMAS_DIRECTORY / f"{_checked(agent)}.return.json"


def read_plugin_name(plugin_dir: Path) -> str:
    path = plugin_dir / PLUGIN_MANIFEST
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"no {PLUGIN_MANIFEST} under {plugin_dir}") from None
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RecordError(f"{path}: not valid JSON") from None
    if not isinstance(document, dict):
        raise RecordError(f"{path}: not a JSON object")
    name = document.get("name")
    if not isinstance(name, str) or not name:
        raise RecordError(f"{path}: carries no non-empty name")
    return name


def read_agent_contract(plugin_dir: Path, agent: str) -> AgentContract:
    definition = _agent_definition_path(plugin_dir, agent)
    schema = _return_schema_path(plugin_dir, agent)
    return AgentContract(
        agent=agent,
        tools=_tools(definition),
        return_schema=_return_schema(schema),
    )


def _checked(agent: str) -> str:
    if _AGENT_NAME.fullmatch(agent) is None:
        raise ValueError(f"not an agent name: {agent!r}")
    return agent


def _tools(path: Path) -> tuple[str, ...]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"no agent definition at {path}") from None
    # `surrogateescape` keeps every byte, as bash's `read` does, rather than refusing the file.
    lines = [line.removesuffix("\r") for line in raw.decode("utf-8", "surrogateescape").split("\n")]
    refusal = f"{path}: carries no tools: line"
    if lines[0] != _FENCE:
        raise RecordError(refusal)
    for line in lines[1:]:
        if line == _FENCE:
            break
        if line.startswith(_TOOLS_KEY):
            items = (item.strip(" \t") for item in line[len(_TOOLS_KEY) :].split(","))
            tools = tuple(item for item in items if item)
            if tools:
                return tools
            break
    raise RecordError(refusal)


def _return_schema(path: Path) -> Mapping[str, object]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"no return schema at {path}") from None
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RecordError(f"{path}: is not one JSON object") from None
    if not isinstance(document, dict):
        raise RecordError(f"{path}: is not one JSON object")
    if not isinstance(document.get("oneOf"), list):
        raise RecordError(f"{path}: carries no top-level oneOf array")
    return MappingProxyType(document)
