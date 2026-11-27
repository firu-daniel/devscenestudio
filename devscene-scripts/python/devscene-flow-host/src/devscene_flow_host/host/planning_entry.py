"""Where a planning walk enters, decided from the ledger, the answered pairs, the saved walk and
the drafts on disk.

The rule: `decide_planning_entry` reads as `cli/templates/scripts/lib/planning-driver-lib.sh` →
`pd_entry`, with `pd_pairs`, `pd_walk_usable` and `pd_block_usable`, in `pd_entry`'s order:
- `P1`, `P2` and `P3` all resolved (`x` or `-`) is `PlanningDone`;
- the writer pairs are the answered pairs minus a `Phase G` origin and a prompt-injection screen
  origin; a kept pair raised by a UI-test agent makes them UI pairs;
- a usable saved `Dispatch` or `DispatchSet` is continued with `outcome=None`, carrying the pairs
  only when its first node declares `prompts`; a usable saved `Interrupt` is continued with its
  `resume_outcome` only when there are writer pairs, so a parked writer keeps its saved variant;
  every other saved step, and no saved walk, falls through;
- otherwise the walk starts at the first entry that holds: with writer pairs `ui_writer` for UI
  pairs else `plan_writer`; `P1` `x` with `P2` resolved `convergence`; `P1` `x` with the UI-test
  index on disk `ui_review`; `P1` `x` `ui_writer`; the story index on disk `plan_round`; else
  `plan_writer`, with `round_resume`'s resume for that entry.
A step is unusable when the ledger contradicts its first node — `P1` `x` inside `P1`'s loop, `P2`
resolved inside `P2`'s loop, `P1` open inside `P2`'s loop with no `LedgerPassage("P1")` in its
`passed` — when a dispatch's required index is absent, or when a findings file a revision carries
exists neither as given nor under the repository root. A ledger entry's loop is derived from the
graph: every node with an outcome `RouteEdge` naming it, plus such a round node's gates and
writer. A `RecordError` propagates.

Deliberately not covered:
- Acting on the decision — `start_run` / `continue_run`, the prompt builder over the pairs: the
  run driver's (#424).
- Creating the ledger and its `P0`: the fork's Setup.
- Archiving consumed pairs: the watcher's.
- A flow other than the planning graph.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeAlias

from graphscene import (
    Dispatch,
    DispatchNode,
    DispatchSet,
    FlowGraph,
    Interrupt,
    LedgerPassage,
    RoundNode,
    RoundResume,
    RouteEdge,
    Walker,
)

from devscene_flow_host.host.paths import render_path
from devscene_flow_host.host.planning_hooks import UI_TEST_INDEX_PATH
from devscene_flow_host.host.prompt_variants import (
    INITIAL_VARIANT,
    REVISION_VARIANT,
    declared_variant,
    findings_files,
)
from devscene_flow_host.host.re_entry import current_step
from devscene_flow_host.host.resume import round_resume
from devscene_flow_host.records.clarifications import AnsweredPair, read_answered_pairs
from devscene_flow_host.records.ledger import (
    DONE_VALUE,
    PLANNING_ENTRIES,
    RESOLVED_VALUES,
    PlanningMark,
    PlanningMarks,
    read_planning_marks,
)

PLAN_WRITER_ENTRY: Final = "plan_writer"
PLAN_ROUND_ENTRY: Final = "plan_round"
UI_WRITER_ENTRY: Final = "ui_writer"
UI_REVIEW_ENTRY: Final = "ui_review"
CONVERGENCE_ENTRY: Final = "convergence"
STORY_INDEX_PATH: Final = "story_index"
PHASE_G_ORIGIN: Final = "Phase G"
SCREEN_ORIGIN: Final = "prompt-injection-reviewer (prompt-injection screen)"
UI_WRITER_AGENT: Final = "ui-tests-plan-writer"
UI_REVIEWER_AGENT: Final = "ui-tests-plan-reviewer"

_P1: Final = PLANNING_ENTRIES[0]
_P2: Final = PLANNING_ENTRIES[1]


@dataclass(frozen=True)
class PlanningDone:
    pass


@dataclass(frozen=True)
class ContinueWalk:
    """`outcome` is `None` for `continue_run(outcome=None)`, else the interrupt's resume
    outcome."""

    outcome: str | None
    pairs: tuple[AnsweredPair, ...]


@dataclass(frozen=True)
class StartWalk:
    entry: str
    resume: RoundResume | None
    pairs: tuple[AnsweredPair, ...]


PlanningEntry: TypeAlias = PlanningDone | ContinueWalk | StartWalk


def decide_planning_entry(
    walker: Walker, repo_root: Path, state_dir: str, branch: str
) -> PlanningEntry:
    graph = walker.graph
    marks = read_planning_marks(repo_root, state_dir, branch)
    if _resolved(marks.p1) and _resolved(marks.p2) and _resolved(marks.p3):
        return PlanningDone()
    pairs, ui_pairs = _writer_pairs(repo_root, state_dir, branch)

    saved = current_step(walker, repo_root, branch)
    action = saved.action
    if isinstance(action, (Dispatch, DispatchSet, Interrupt)) and _usable(
        graph, repo_root, state_dir, branch, marks, action, saved.revision_findings
    ):
        if isinstance(action, Interrupt):
            if pairs:
                return ContinueWalk(action.resume_outcome, pairs)
        else:
            first = _first_node(action)
            node = None if first is None else graph.nodes.get(first)
            writer = isinstance(node, DispatchNode) and node.prompts is not None
            return ContinueWalk(None, pairs if writer else ())

    entry = _start_entry(repo_root, state_dir, branch, graph, marks, pairs, ui_pairs)
    return StartWalk(
        entry, round_resume(graph, walker.host, repo_root, state_dir, branch, entry), pairs
    )


def _resolved(mark: PlanningMark) -> bool:
    return mark in RESOLVED_VALUES


def _writer_pairs(
    repo_root: Path, state_dir: str, branch: str
) -> tuple[tuple[AnsweredPair, ...], bool]:
    kept: list[AnsweredPair] = []
    ui = False
    for pair in read_answered_pairs(repo_root, state_dir, branch):
        origin = pair.raised_by or ""
        if origin.startswith(PHASE_G_ORIGIN) or origin.startswith(SCREEN_ORIGIN):
            continue
        if UI_WRITER_AGENT in origin or UI_REVIEWER_AGENT in origin:
            ui = True
        kept.append(pair)
    return tuple(kept), ui


def _start_entry(
    repo_root: Path,
    state_dir: str,
    branch: str,
    graph: FlowGraph,
    marks: PlanningMarks,
    pairs: tuple[AnsweredPair, ...],
    ui_pairs: bool,
) -> str:
    if pairs:
        return UI_WRITER_ENTRY if ui_pairs else PLAN_WRITER_ENTRY
    if marks.p1 == DONE_VALUE:
        if _resolved(marks.p2):
            return CONVERGENCE_ENTRY
        if _index(graph, repo_root, state_dir, branch, UI_TEST_INDEX_PATH).exists():
            return UI_REVIEW_ENTRY
        return UI_WRITER_ENTRY
    if _index(graph, repo_root, state_dir, branch, STORY_INDEX_PATH).exists():
        return PLAN_ROUND_ENTRY
    return PLAN_WRITER_ENTRY


def _index(graph: FlowGraph, repo_root: Path, state_dir: str, branch: str, key: str) -> Path:
    return repo_root / render_path(graph.paths[key], state_dir, branch)


def _ledger_loop(graph: FlowGraph, entry: str) -> frozenset[str]:
    loop: set[str] = set()
    for node in graph.nodes.values():
        if not isinstance(node, (DispatchNode, RoundNode)):
            continue
        if not any(
            isinstance(edge, RouteEdge) and edge.ledger == entry for edge in node.outcomes.values()
        ):
            continue
        loop.add(node.id)
        if isinstance(node, RoundNode):
            loop.update(node.gates)
            if node.writer is not None:
                loop.add(node.writer)
    return frozenset(loop)


def _first_node(action: Dispatch | DispatchSet | Interrupt) -> str | None:
    if isinstance(action, DispatchSet):
        return action.dispatches[0].node if action.dispatches else None
    return action.node


def _usable(
    graph: FlowGraph,
    repo_root: Path,
    state_dir: str,
    branch: str,
    marks: PlanningMarks,
    action: Dispatch | DispatchSet | Interrupt,
    revision_findings: tuple[str, ...],
) -> bool:
    dispatches: tuple[Dispatch, ...] = (
        (action,)
        if isinstance(action, Dispatch)
        else action.dispatches
        if isinstance(action, DispatchSet)
        else ()
    )
    for dispatch in dispatches:
        if not _dispatch_usable(graph, repo_root, state_dir, branch, dispatch, revision_findings):
            return False
    first = _first_node(action)
    if first is None:
        return True
    if marks.p1 == DONE_VALUE and first in _ledger_loop(graph, _P1):
        return False
    if first in _ledger_loop(graph, _P2):
        if _resolved(marks.p2):
            return False
        if marks.p1 != DONE_VALUE and LedgerPassage(_P1) not in action.passed:
            return False
    return True


def _dispatch_usable(
    graph: FlowGraph,
    repo_root: Path,
    state_dir: str,
    branch: str,
    dispatch: Dispatch,
    revision_findings: tuple[str, ...],
) -> bool:
    node = graph.nodes.get(dispatch.node)
    variant = declared_variant(node, dispatch) if isinstance(node, DispatchNode) else None
    required = _required_index(graph, dispatch.node, variant)
    if required is not None and not _index(graph, repo_root, state_dir, branch, required).exists():
        return False
    if variant == REVISION_VARIANT:
        files = findings_files(revision_findings, dispatch.closed_round)
        for file in files:
            if not Path(file).exists() and not (repo_root / file).exists():
                return False
    return True


def _required_index(graph: FlowGraph, node: str, variant: str | None) -> str | None:
    p1_gates = {
        gate
        for member in _ledger_loop(graph, _P1)
        if isinstance(round_node := graph.nodes[member], RoundNode)
        for gate in round_node.gates
    }
    if (
        node in p1_gates
        or (node == PLAN_WRITER_ENTRY and variant == REVISION_VARIANT)
        or (node == UI_WRITER_ENTRY and variant == INITIAL_VARIANT)
    ):
        return STORY_INDEX_PATH
    if node == UI_REVIEW_ENTRY or (node == UI_WRITER_ENTRY and variant == REVISION_VARIANT):
        return UI_TEST_INDEX_PATH
    return None
