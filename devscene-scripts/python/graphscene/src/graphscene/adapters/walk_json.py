"""The walk's JSON forms (`graphscene.model.walk_state`, `graphscene.model.walk_actions`): the
walk-state document a file store persists a `WalkState` with (`state_to_json`,
`state_from_json`), the step document a walk `Step` is reported as (`step_document`), and the
round-resume document a `RoundResume` is read from (`resume_from_json`).

The rule: the walk-state document's top level carries `"version": 2` beside the state's fields;
every key is the attribute's own name, with no case mapping; each action and passage object
carries its `kind` first; a `tuple` is a JSON array, an `End.reports` pair a 2-element array, a
`Mapping` a JSON object in key order, and `None` a JSON `null` under a key that is always present.
The codec reads only what it writes: a document of another version is refused. A change to the
document's shape (a key added, removed or renamed, a `kind` added or removed, or a value encoded
differently) raises `_VERSION`, and a document of an older version is refused, never migrated. The
step document of an action is that action's encoding inside the state document, as `pending`; a
refusal's is `{"kind": "refused", "reason": …}`. The round-resume document is
`{"round", "number", "records"}`, each record the state document's record object; it carries no
`version`, because it is read only and a `RoundResume` is never saved. Neither changes the state
document's shape.

Decoding rebuilds the frozen types with `tuple`s and `MappingProxyType`s over fresh `dict`s, as
`graphscene.adapters.builder` builds the graph. A malformed document raises
`ValueError("<path>: <reason>")`, the path dotted from the root as
`graphscene.model.errors.Violation.path` writes one and rendered `(root)` for the root, as
`Violation.__str__` renders it. Refused: a parse failure, a `version` other than 2, a missing or
extra key, a value of the wrong JSON type (a `bool` is never an integer, and a JSON number with a
fraction part never one either), an unknown `kind`, and an `awaiting` or `verdict` outside its
`Literal`.

Deliberately not checked:
- A duplicate object key: `json.loads` keeps the last one.
- A mapping key containing "." makes its path ambiguous; it is decoded unchanged.
- Whether the state is one a walk can reach: an `OpenRound.records` key differing from its
  record's `gate`, or a `pending` disagreeing with `awaiting`, decodes as written.
- Whether a round-resume document fits a graph: a round the graph lacks, a negative `number`, a
  record of a gate outside the round or a duplicate gate decodes as written, and `Walker.start`
  refuses it.
"""

import json
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TypeVar

from graphscene.model.flow_graph import Verdict
from graphscene.model.walk_actions import (
    Action,
    Dispatch,
    DispatchSet,
    End,
    GateRecord,
    Interrupt,
    LedgerPassage,
    Passage,
    Refused,
    RoundPassage,
    SkipPassage,
    Step,
    Stop,
    Wait,
)
from graphscene.model.walk_state import Awaiting, OpenRound, RoundResume, WalkState

_VERSION = 2

_AWAITING: Mapping[str, Awaiting] = {
    "dispatch": "dispatch",
    "set": "set",
    "interrupt": "interrupt",
    "done": "done",
}
_VERDICTS: Mapping[str, Verdict] = {"pass": "pass", "fail": "fail"}

_T = TypeVar("_T")


def _record_out(record: GateRecord) -> dict[str, object]:
    return {"gate": record.gate, "outcome": record.outcome, "detail": record.detail}


def _records_out(records: tuple[GateRecord, ...]) -> list[object]:
    return [_record_out(record) for record in records]


def _passage_out(passage: Passage) -> dict[str, object]:
    if isinstance(passage, SkipPassage):
        return {"kind": passage.kind, "node": passage.node, "status": passage.status}
    if isinstance(passage, RoundPassage):
        return {
            "kind": passage.kind,
            "round": passage.round,
            "number": passage.number,
            "verdict": passage.verdict,
        }
    return {"kind": passage.kind, "entry": passage.entry}


def _passed_out(passed: tuple[Passage, ...]) -> list[object]:
    return [_passage_out(passage) for passage in passed]


def _dispatch_out(action: Dispatch) -> dict[str, object]:
    return {
        "kind": action.kind,
        "node": action.node,
        "agent": action.agent,
        "prompt_variant": action.prompt_variant,
        "counters": dict(action.counters),
        "round_number": action.round_number,
        "converging": action.converging,
        "closed_round": _records_out(action.closed_round),
        "passed": _passed_out(action.passed),
    }


def _action_out(action: Action) -> dict[str, object]:
    if isinstance(action, Dispatch):
        return _dispatch_out(action)
    if isinstance(action, DispatchSet):
        return {
            "kind": action.kind,
            "round": action.round,
            "number": action.number,
            "dispatches": [_dispatch_out(dispatch) for dispatch in action.dispatches],
            "passed": _passed_out(action.passed),
        }
    if isinstance(action, Wait):
        return {
            "kind": action.kind,
            "round": action.round,
            "recorded": _record_out(action.recorded),
            "pending": list(action.pending),
        }
    if isinstance(action, Interrupt):
        return {
            "kind": action.kind,
            "binding": action.binding,
            "node": action.node,
            "agent": action.agent,
            "resume": action.resume,
            "resume_outcome": action.resume_outcome,
            "closed_round": _records_out(action.closed_round),
            "passed": _passed_out(action.passed),
        }
    if isinstance(action, Stop):
        return {
            "kind": action.kind,
            "binding": action.binding,
            "node": action.node,
            "agent": action.agent,
            "reason": action.reason,
            "summary": action.summary,
            "evidence": action.evidence,
            "round_counts": list(action.round_counts),
            "held": _records_out(action.held),
            "closed_round": _records_out(action.closed_round),
            "passed": _passed_out(action.passed),
        }
    return {
        "kind": action.kind,
        "binding": action.binding,
        "node": action.node,
        "reports": [[slot, status] for slot, status in action.reports],
        "passed": _passed_out(action.passed),
    }


def _open_round_out(open_round: OpenRound | None) -> dict[str, object] | None:
    if open_round is None:
        return None
    return {
        "round": open_round.round,
        "number": open_round.number,
        "due": list(open_round.due),
        "records": {gate: _record_out(r) for gate, r in open_round.records.items()},
    }


def state_to_json(state: WalkState) -> str:
    """Return `state` as the version-2 JSON document, ending in a newline."""
    document: dict[str, object] = {
        "version": _VERSION,
        "flow": state.flow,
        "node": state.node,
        "awaiting": state.awaiting,
        "pending": _action_out(state.pending),
        "counters": dict(state.counters),
        "round_numbers": dict(state.round_numbers),
        "open_round": _open_round_out(state.open_round),
        "prompts": dict(state.prompts),
        "reports": dict(state.reports),
        "skipped": dict(state.skipped),
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=False, indent=1) + "\n"


def step_document(step: Step) -> dict[str, object]:
    """Return `step` as its JSON-ready step document."""
    if isinstance(step, Refused):
        return {"kind": step.kind, "reason": step.reason}
    return _action_out(step)


def _refuse(path: str, reason: str) -> ValueError:
    return ValueError(f"{path or '(root)'}: {reason}")


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _refuse(path, "expected object")
    return value


def _fields(value: object, path: str, keys: tuple[str, ...]) -> dict[str, object]:
    fields = _object(value, path)
    for key in keys:
        if key not in fields:
            raise _refuse(_join(path, key), "missing key")
    for key in fields:
        if key not in keys:
            raise _refuse(_join(path, key), "unexpected key")
    return fields


def _str(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise _refuse(path, "expected string")
    return value


def _int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _refuse(path, "expected integer")
    return value


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise _refuse(path, "expected boolean")
    return value


def _optional(read: Callable[[object, str], _T], value: object, path: str) -> _T | None:
    return None if value is None else read(value, path)


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise _refuse(path, "expected array")
    return value


def _tuple(read: Callable[[object, str], _T], value: object, path: str) -> tuple[_T, ...]:
    return tuple(read(item, f"{path}[{index}]") for index, item in enumerate(_list(value, path)))


def _mapping(
    read: Callable[[object, str], _T], value: object, path: str
) -> MappingProxyType[str, _T]:
    fields = _object(value, path)
    return MappingProxyType({key: read(child, _join(path, key)) for key, child in fields.items()})


def _literal(choices: Mapping[str, _T], value: object, path: str) -> _T:
    if isinstance(value, str) and value in choices:
        return choices[value]
    allowed = ", ".join(repr(choice) for choice in choices)
    raise _refuse(path, f"expected one of {allowed}")


def _kind(value: object, path: str, allowed: tuple[str, ...]) -> str:
    fields = _object(value, path)
    kind_path = _join(path, "kind")
    if "kind" not in fields:
        raise _refuse(kind_path, "missing key")
    kind = _str(fields["kind"], kind_path)
    if kind not in allowed:
        raise _refuse(kind_path, f"unknown kind {kind!r}")
    return kind


def _record(value: object, path: str) -> GateRecord:
    fields = _fields(value, path, ("gate", "outcome", "detail"))
    return GateRecord(
        gate=_str(fields["gate"], _join(path, "gate")),
        outcome=_str(fields["outcome"], _join(path, "outcome")),
        detail=_optional(_str, fields["detail"], _join(path, "detail")),
    )


def _passage(value: object, path: str) -> Passage:
    kind = _kind(value, path, ("skip", "round", "ledger"))
    if kind == "skip":
        fields = _fields(value, path, ("kind", "node", "status"))
        return SkipPassage(
            node=_str(fields["node"], _join(path, "node")),
            status=_str(fields["status"], _join(path, "status")),
        )
    if kind == "round":
        fields = _fields(value, path, ("kind", "round", "number", "verdict"))
        return RoundPassage(
            round=_str(fields["round"], _join(path, "round")),
            number=_int(fields["number"], _join(path, "number")),
            verdict=_literal(_VERDICTS, fields["verdict"], _join(path, "verdict")),
        )
    fields = _fields(value, path, ("kind", "entry"))
    return LedgerPassage(entry=_str(fields["entry"], _join(path, "entry")))


def _report(value: object, path: str) -> tuple[str, str]:
    pair = _list(value, path)
    if len(pair) != 2:
        raise _refuse(path, "expected 2-element array")
    return _str(pair[0], f"{path}[0]"), _str(pair[1], f"{path}[1]")


def _dispatch(value: object, path: str) -> Dispatch:
    _kind(value, path, ("dispatch",))
    fields = _fields(
        value,
        path,
        (
            "kind",
            "node",
            "agent",
            "prompt_variant",
            "counters",
            "round_number",
            "converging",
            "closed_round",
            "passed",
        ),
    )
    return Dispatch(
        node=_str(fields["node"], _join(path, "node")),
        agent=_str(fields["agent"], _join(path, "agent")),
        prompt_variant=_optional(_str, fields["prompt_variant"], _join(path, "prompt_variant")),
        counters=_mapping(_int, fields["counters"], _join(path, "counters")),
        round_number=_optional(_int, fields["round_number"], _join(path, "round_number")),
        converging=_optional(_bool, fields["converging"], _join(path, "converging")),
        closed_round=_tuple(_record, fields["closed_round"], _join(path, "closed_round")),
        passed=_tuple(_passage, fields["passed"], _join(path, "passed")),
    )


def _action(value: object, path: str) -> Action:
    kind = _kind(value, path, ("dispatch", "set", "wait", "interrupt", "stop", "end"))
    if kind == "dispatch":
        return _dispatch(value, path)
    if kind == "set":
        fields = _fields(value, path, ("kind", "round", "number", "dispatches", "passed"))
        return DispatchSet(
            round=_str(fields["round"], _join(path, "round")),
            number=_int(fields["number"], _join(path, "number")),
            dispatches=_tuple(_dispatch, fields["dispatches"], _join(path, "dispatches")),
            passed=_tuple(_passage, fields["passed"], _join(path, "passed")),
        )
    if kind == "wait":
        fields = _fields(value, path, ("kind", "round", "recorded", "pending"))
        return Wait(
            round=_str(fields["round"], _join(path, "round")),
            recorded=_record(fields["recorded"], _join(path, "recorded")),
            pending=_tuple(_str, fields["pending"], _join(path, "pending")),
        )
    if kind == "interrupt":
        fields = _fields(
            value,
            path,
            (
                "kind",
                "binding",
                "node",
                "agent",
                "resume",
                "resume_outcome",
                "closed_round",
                "passed",
            ),
        )
        return Interrupt(
            binding=_str(fields["binding"], _join(path, "binding")),
            node=_str(fields["node"], _join(path, "node")),
            agent=_optional(_str, fields["agent"], _join(path, "agent")),
            resume=_str(fields["resume"], _join(path, "resume")),
            resume_outcome=_str(fields["resume_outcome"], _join(path, "resume_outcome")),
            closed_round=_tuple(_record, fields["closed_round"], _join(path, "closed_round")),
            passed=_tuple(_passage, fields["passed"], _join(path, "passed")),
        )
    if kind == "stop":
        fields = _fields(
            value,
            path,
            (
                "kind",
                "binding",
                "node",
                "agent",
                "reason",
                "summary",
                "evidence",
                "round_counts",
                "held",
                "closed_round",
                "passed",
            ),
        )
        return Stop(
            binding=_str(fields["binding"], _join(path, "binding")),
            node=_str(fields["node"], _join(path, "node")),
            agent=_optional(_str, fields["agent"], _join(path, "agent")),
            reason=_str(fields["reason"], _join(path, "reason")),
            summary=_optional(_str, fields["summary"], _join(path, "summary")),
            evidence=_optional(_str, fields["evidence"], _join(path, "evidence")),
            round_counts=_tuple(_str, fields["round_counts"], _join(path, "round_counts")),
            held=_tuple(_record, fields["held"], _join(path, "held")),
            closed_round=_tuple(_record, fields["closed_round"], _join(path, "closed_round")),
            passed=_tuple(_passage, fields["passed"], _join(path, "passed")),
        )
    fields = _fields(value, path, ("kind", "binding", "node", "reports", "passed"))
    return End(
        binding=_str(fields["binding"], _join(path, "binding")),
        node=_str(fields["node"], _join(path, "node")),
        reports=_tuple(_report, fields["reports"], _join(path, "reports")),
        passed=_tuple(_passage, fields["passed"], _join(path, "passed")),
    )


def _open_round(value: object, path: str) -> OpenRound:
    fields = _fields(value, path, ("round", "number", "due", "records"))
    return OpenRound(
        round=_str(fields["round"], _join(path, "round")),
        number=_int(fields["number"], _join(path, "number")),
        due=_tuple(_str, fields["due"], _join(path, "due")),
        records=_mapping(_record, fields["records"], _join(path, "records")),
    )


_STATE_KEYS = (
    "version",
    "flow",
    "node",
    "awaiting",
    "pending",
    "counters",
    "round_numbers",
    "open_round",
    "prompts",
    "reports",
    "skipped",
)


def state_from_json(text: str) -> WalkState:
    """Rebuild the `WalkState` a version-2 document written by `state_to_json` holds."""
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as error:
        reason = f"not valid JSON: {error.msg} (line {error.lineno}, column {error.colno})"
        raise _refuse("", reason) from error
    document = _object(parsed, "")
    if "version" not in document:
        raise _refuse("version", "missing key")
    version = document["version"]
    if isinstance(version, bool) or version != _VERSION or not isinstance(version, int):
        raise _refuse("version", f"unsupported version {json.dumps(version)}")
    fields = _fields(document, "", _STATE_KEYS)
    return WalkState(
        flow=_str(fields["flow"], "flow"),
        node=_str(fields["node"], "node"),
        awaiting=_literal(_AWAITING, fields["awaiting"], "awaiting"),
        pending=_action(fields["pending"], "pending"),
        counters=_mapping(_int, fields["counters"], "counters"),
        round_numbers=_mapping(_int, fields["round_numbers"], "round_numbers"),
        open_round=_optional(_open_round, fields["open_round"], "open_round"),
        prompts=_mapping(_str, fields["prompts"], "prompts"),
        reports=_mapping(_str, fields["reports"], "reports"),
        skipped=_mapping(_str, fields["skipped"], "skipped"),
    )


def resume_from_json(text: str) -> RoundResume:
    """Read the `RoundResume` a round-resume document holds."""
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as error:
        reason = f"not valid JSON: {error.msg} (line {error.lineno}, column {error.colno})"
        raise _refuse("", reason) from error
    fields = _fields(parsed, "", ("round", "number", "records"))
    return RoundResume(
        round=_str(fields["round"], "round"),
        number=_int(fields["number"], "number"),
        records=_tuple(_record, fields["records"], "records"),
    )
