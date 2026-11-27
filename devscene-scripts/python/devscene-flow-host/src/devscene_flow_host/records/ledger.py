"""Reads the run mode's skipped ids from the flow-progress ledger, or from the ids the caller
gives, and the ledger's `P1`-`P3` planning marks.

The rule: `read_run_mode` reads as the bash walker's `fw_run_mode_skipped` does
(`cli/templates/scripts/lib/flow-walker-gates.sh`), and `parse_skipped` reads a list as
`fw_id_in_list` does. The ledger's `## Run mode` block wins whenever the ledger exists; only when
no ledger exists are the caller's skipped ids used. When neither answers, the result is a
`RunModeUnresolved` carrying the reason, never a guess. It returns the skipped-id set and decides
nothing with it. `read_planning_marks` reads the `P1`-`P3` marks as `pd_ledger_read` does
(`cli/templates/scripts/lib/planning-driver-lib.sh`): a line opening with a mark followed by
`<entry>.` sets that entry's mark, the last such line wins, and no such line is `None`. It decides
nothing about what a mark means.

Deliberately not covered:
- The ledger's other blocks.
- Whether an id is in the run mode's closed directive set, which the run-mode instructions own.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TypeAlias

from devscene_flow_host.records.errors import RecordError

LEDGER_DIRECTORY: Final = "flow_progress"
_RUN_MODE_HEADING: Final = "## Run mode"
_SKIPPED_PREFIX: Final = "- skipped: "
_TRAILING: Final = " \t\r"

PLANNING_ENTRIES: Final = ("P1", "P2", "P3")
OPEN_MARK: Final = "- [ ] "
DONE_MARK: Final = "- [x] "
SKIPPED_MARK: Final = "- [-] "
DONE_VALUE: Final = "x"
SKIPPED_VALUE: Final = "-"
RESOLVED_VALUES: Final = (DONE_VALUE, SKIPPED_VALUE)

PlanningMark: TypeAlias = Literal["x", "-", " "] | None

_MARK_VALUES: Final[tuple[tuple[str, PlanningMark], ...]] = (
    (DONE_MARK, DONE_VALUE),
    (SKIPPED_MARK, SKIPPED_VALUE),
    (OPEN_MARK, " "),
)


@dataclass(frozen=True)
class RunMode:
    skipped: frozenset[str]
    source: Literal["ledger", "argument"]


@dataclass(frozen=True)
class RunModeUnresolved:
    reason: str


@dataclass(frozen=True)
class PlanningMarks:
    p1: PlanningMark
    p2: PlanningMark
    p3: PlanningMark


def ledger_path(repo_root: Path, state_dir: str, branch: str) -> Path:
    return repo_root / state_dir / LEDGER_DIRECTORY / f"{branch}_progress.md"


def parse_skipped(value: str) -> frozenset[str]:
    members = (member.strip() for member in value.split(","))
    return frozenset(member for member in members if member and member != "none")


def read_run_mode(
    repo_root: Path, state_dir: str, branch: str, skipped: str | None
) -> RunMode | RunModeUnresolved:
    path = ledger_path(repo_root, state_dir, branch)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        if skipped:
            return RunMode(parse_skipped(skipped), "argument")
        return RunModeUnresolved(
            f"no run-mode record: no flow-progress ledger for '{branch}' and no skipped ids given"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None
    value = _ledger_skipped(text)
    if value:
        return RunMode(parse_skipped(value), "ledger")
    return RunModeUnresolved(
        f"the flow-progress ledger for '{branch}' has no '- skipped:' line under '## Run mode'"
    )


def _ledger_skipped(text: str) -> str:
    in_run_mode = False
    for line in text.split("\n"):
        if line.startswith("## "):
            in_run_mode = line.rstrip(_TRAILING) == _RUN_MODE_HEADING
            continue
        if in_run_mode and line.startswith(_SKIPPED_PREFIX):
            return line[len(_SKIPPED_PREFIX) :].rstrip(_TRAILING)
    return ""


def read_planning_marks(repo_root: Path, state_dir: str, branch: str) -> PlanningMarks:
    path = ledger_path(repo_root, state_dir, branch)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"no flow-progress ledger at {path}") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None
    marks: dict[str, PlanningMark] = dict.fromkeys(PLANNING_ENTRIES)
    for line in text.split("\n"):
        for entry in PLANNING_ENTRIES:
            for prefix, value in _MARK_VALUES:
                if line.startswith(prefix + f"{entry}."):
                    marks[entry] = value
    return PlanningMarks(p1=marks["P1"], p2=marks["P2"], p3=marks["P3"])
