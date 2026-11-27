"""Judges a finished `claude -p --output-format stream-json --verbose` transcript into the node's
`NodeResult` and the usage fields the session reported.

The rule: `judge_session` reads the stream as `PNL_REAP_JQ` does
(`cli/templates/scripts/lib/planning-node-lib.sh`), in its order. The lines that parse as JSON
objects are the events; `init` is the first `system`/`init` event and `result` the last `result`
event. The first clause that holds decides the result:
1. no `init` — `infra`;
2. `init` grants a tool the contract does not declare — `agent`;
3. no `result` — `undelivered`;
4. `is_error` with an overload marker in the result text — `undelivered`;
5. `is_error`, or a subtype other than `success` — `infra`;
6. no return block: the last fenced `json` block, followed by nothing but whitespace — `infra`;
7. a block that is not one JSON object — `infra`;
8. a return that fails `contract.return_schema` — `infra`;
9. a return with no non-empty string `outcome` — `infra`;
10. otherwise `Completed`, its detail the return's non-blank `findings_file` resolved against `cwd`;
    the validated return object is kept as `return_document`, which is `None` on every other
    clause.
Every reason is one line. The usage fields are read whenever their event exists, on every
classification, and a field of the wrong JSON type is `None`. A `ValueError` from
`return_violations` for an invalid schema propagates.

Departures from `PNL_REAP_JQ`:
- An outcome the node does not declare is `Completed`: refusing it is the walk's.
- A `FAIL`, or a round gate's `PASS`, with no findings file is not refused here: that is
  `devscene_flow_host.host.round_gates.record_outcome`'s.

Deliberately not covered:
- Launching the session and detecting a stall: `host/session_process.py`.
- The usage sink and the session's duration: `host/claude_executor.py`.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from graphscene import Completed, Failed, NodeResult, return_violations

from devscene_flow_host.records.plugin_contracts import AgentContract

DETAIL_FIELD: Final = "findings_file"
OVERLOAD_MARKERS: Final = ("API Error: 500", "API Error: 503", "API Error: 529", "Overloaded")
_MCP_PREFIX: Final = "mcp__"
_OPEN_FENCE: Final = "\n```json\n"
_CLOSE_FENCE: Final = "\n```"
_BLANK: Final = frozenset(" \t\r\n")
_API_ERROR_LIMIT: Final = 200


@dataclass(frozen=True)
class SessionReading:
    result: NodeResult
    session_id: str | None
    total_cost_usd: float | None
    cache_creation_input_tokens: int | None
    cache_read_input_tokens: int | None
    model_usage: Mapping[str, object]
    permission_denials: int
    withheld_tools: tuple[str, ...]
    return_document: Mapping[str, object] | None


def judge_session(stream: str, contract: AgentContract, cwd: Path) -> SessionReading:
    events = _events(stream)
    init = next(
        (e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None
    )
    result_event = next((e for e in reversed(events) if e.get("type") == "result"), None)
    init_tools = _list(init.get("tools")) if init is not None else []
    withheld: tuple[str, ...] = ()
    if init is not None:
        withheld = tuple(
            tool
            for tool in contract.tools
            if not tool.startswith(_MCP_PREFIX) and tool not in init_tools
        )
    usage = _object(result_event.get("usage")) if result_event is not None else {}
    model_usage = _object(result_event.get("modelUsage")) if result_event is not None else {}
    denials = _list(result_event.get("permission_denials")) if result_event is not None else []
    result, document = _classify(init, init_tools, result_event, contract, cwd)
    return SessionReading(
        result=result,
        session_id=_string(init.get("session_id")) if init is not None else None,
        total_cost_usd=(
            _number(result_event.get("total_cost_usd")) if result_event is not None else None
        ),
        cache_creation_input_tokens=_integer(usage.get("cache_creation_input_tokens")),
        cache_read_input_tokens=_integer(usage.get("cache_read_input_tokens")),
        model_usage=MappingProxyType(dict(model_usage)),
        permission_denials=len(denials),
        withheld_tools=withheld,
        return_document=document,
    )


def _classify(
    init: Mapping[str, object] | None,
    init_tools: list[object],
    result_event: Mapping[str, object] | None,
    contract: AgentContract,
    cwd: Path,
) -> tuple[NodeResult, Mapping[str, object] | None]:
    if init is None:
        return Failed("infra", "the agent did not resolve: no init event"), None
    extra = [tool for tool in init_tools if tool not in contract.tools]
    if extra:
        granted = ", ".join(_tostring(tool) for tool in extra)
        return Failed(
            "agent",
            _oneline(f"the init event grants tools the agent does not declare: [{granted}]"),
        ), None
    if result_event is None:
        return Failed("undelivered", "no result event"), None
    is_error = result_event.get("is_error") is True
    text = _tostring(result_event.get("result"))
    if is_error and any(marker in text for marker in OVERLOAD_MARKERS):
        return Failed("undelivered", f"API error: {_oneline(text)[:_API_ERROR_LIMIT]}"), None
    subtype = result_event.get("subtype")
    if is_error or subtype != "success":
        ended = "no subtype" if subtype is None or subtype is False else _tostring(subtype)
        suffix = " with is_error" if is_error else ""
        return Failed("infra", _oneline(f"the session ended as {ended}{suffix}")), None
    block = _return_block(result_event.get("result"))
    if block is None:
        return Failed("infra", "the result carries no return block"), None
    try:
        document: object = json.loads(block)
    except json.JSONDecodeError:
        document = None
    if not isinstance(document, dict):
        return Failed("infra", "the return block is not one JSON object"), None
    violations = return_violations(document, contract.return_schema)
    if violations:
        return Failed("infra", _oneline(f"the return fails its schema: {violations[0]}")), None
    outcome = document.get("outcome")
    if not isinstance(outcome, str) or not outcome:
        return Failed("infra", "the return carries no outcome"), None
    return Completed(outcome, _detail(document.get(DETAIL_FIELD), cwd)), MappingProxyType(document)


def _return_block(text: object) -> str | None:
    if not isinstance(text, str):
        return None
    opened = ("\n" + text.replace("\r\n", "\n")).split(_OPEN_FENCE)
    if len(opened) < 2:
        return None
    body, fence, after = ("\n" + opened[-1]).partition(_CLOSE_FENCE)
    if not fence or not _blank(after):
        return None
    return body


def _detail(value: object, cwd: Path) -> str | None:
    if not isinstance(value, str) or _blank(value):
        return None
    path = Path(value)
    return value if path.is_absolute() else str(cwd / path)


def _events(stream: str) -> list[Mapping[str, object]]:
    events: list[Mapping[str, object]] = []
    for line in stream.split("\n"):
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _blank(text: str) -> bool:
    return all(character in _BLANK for character in text)


def _oneline(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ")


def _tostring(value: object) -> str:
    # jq's `(x // "") | tostring`: null and false read as "", a string as itself, anything else as
    # its compact JSON.
    if value is None or value is False:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _object(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
