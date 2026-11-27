"""Parses a `flow-walker` command line into an `Invocation`, or refuses it with a `UsageError`.

The rule: a command line reads as `flow-walker.sh` → `# --- Arguments` reads it — the same four
verbs, each verb's flags, the same value checks in the same order and the same refusal texts — so
an input bash refuses is refused here with the same words. A repeated flag keeps its last value,
and a required flag given an empty value is missing, as bash's `[ -n … ]` reads it. One flag is
added to `start`, `next` and `current`: `--flows <dir>`, the graph directory, required because bash
finds its graph beside itself and this command cannot.

Deliberately not covered:
- Resolving `--flows` or `--findings` against the repository root, finding that root, and the exit
  status a `UsageError` becomes: `commands/flow_walker.py`'s.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast

Command = Literal["start", "next", "current", "check-round-file"]

FLAGS: Final[Mapping[str, tuple[str, ...]]] = {
    "start": ("--flow", "--branch", "--flows", "--entry", "--skipped"),
    "next": ("--flow", "--branch", "--flows", "--outcome", "--node", "--findings", "--skipped"),
    "current": ("--flow", "--branch", "--flows"),
    "check-round-file": ("--findings",),
}

_NODE_CHARACTERS: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")
_OUTCOME_CHARACTERS: Final = _NODE_CHARACTERS | frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class UsageError(Exception):
    """A refused command line; its message is bash's text without the `flow-walker: ` prefix."""


@dataclass(frozen=True)
class Invocation:
    command: Command
    flow: str | None = None
    branch: str | None = None
    entry: str | None = None
    skipped: str | None = None
    outcome: str | None = None
    findings: str | None = None
    node: str | None = None
    flows: str | None = None


def parse(argv: Sequence[str]) -> Invocation:
    if not argv:
        raise UsageError("missing subcommand: start, next, current or check-round-file")
    command = argv[0]
    if command not in FLAGS:
        raise UsageError(
            f"unknown subcommand '{command}': expected start, next, current or check-round-file"
        )
    values: dict[str, str] = {}
    rest = list(argv[1:])
    while rest:
        flag = rest[0]
        if flag not in FLAGS[command]:
            raise UsageError(f"'{flag}' is not a flag of '{command}'")
        if len(rest) < 2:
            raise UsageError(f"{flag} requires a value")
        value = rest[1]
        del rest[:2]
        if "\n" in value:
            raise UsageError(f"the value of {flag} carries a newline")
        if flag == "--findings" and "\t" in value:
            raise UsageError(f"the value of {flag} carries a tab")
        if flag == "--node" and (not value or not set(value) <= _NODE_CHARACTERS):
            raise UsageError(f"'{value}' is not a node name")
        values[flag] = value

    if command == "check-round-file":
        if not values.get("--findings"):
            raise UsageError("missing required flag --findings")
    else:
        for required in ("--flow", "--branch", "--flows"):
            if not values.get(required):
                raise UsageError(f"missing required flag {required}")
        if command == "next":
            outcome = values.get("--outcome")
            if not outcome:
                raise UsageError("missing required flag --outcome")
            if not set(outcome) <= _OUTCOME_CHARACTERS:
                raise UsageError(f"outcome '{outcome}' is not an outcome name")
            if outcome == "FAIL" and not values.get("--findings"):
                raise UsageError(
                    "outcome FAIL requires --findings with the reviewer's findings_file"
                )
        flow = values["--flow"]
        if not set(flow) <= _NODE_CHARACTERS:
            raise UsageError(f"unknown flow '{flow}'")

    return Invocation(
        command=cast(Command, command),
        flow=values.get("--flow"),
        branch=values.get("--branch"),
        entry=values.get("--entry"),
        skipped=values.get("--skipped"),
        outcome=values.get("--outcome"),
        findings=values.get("--findings"),
        node=values.get("--node"),
        flows=values.get("--flows"),
    )
