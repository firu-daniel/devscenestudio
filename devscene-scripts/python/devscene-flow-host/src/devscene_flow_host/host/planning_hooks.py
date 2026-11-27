"""The planning graph's hooks, `commit_plan_round`, `flip_ledger` and `commit_convergence`, as one
GraphScene `HookHost`, `PlanningHooks`.

The rule:
- `commit_plan_round` is Override 6 of
  `plugin/instructions/task_plan_writing_instructions_autonomous.md`, as `pd_act` →
  `prl_round_commit` makes it (`cli/templates/scripts/lib/planning-driver-lib.sh`): on an
  `AfterRound`, one `plan-round` commit with the passage's round number.
- `flip_ledger` is Override 5's flips, as `pd_act` → `prl_ledger_flip` makes them: for each
  `LedgerPassage` in the call's step's `passed`, in order, an entry in `PLANNING_ENTRIES` is
  flipped, then committed as `ledger-flip` even when the flip changed nothing; any other entry is
  skipped. The step is `AfterRound.step`, `AfterDispatch.step`, `BeforeEnd.end` or
  `BeforeRound.dispatch_set`.
- `commit_convergence` is Overrides 3 and 4, then the `P3` flip, as `pd_handoff` →
  `prl_convergence_commits` then `prl_ledger_flip P3`: on a `BeforeEnd`, a `ui-test-plan` commit
  when a UI-test plan was written, then `task-plan`, then the `P3` flip and its `ledger-flip`
  commit. The `End`'s `ui_test` report decides whether the plan was written (status `passed`);
  without that slot the ledger decides: `P2` is `x` and the rendered `ui_test_index` exists.
- Every hook is repeatable: a commit with nothing new to commit is the wrapper's exit 3, and a
  resolved entry's flip leaves the ledger untouched.
- A hook run on a call kind it does not take raises `ValueError`; an unknown hook raises
  `LookupError`. `CommitPointError` and `RecordError` propagate.

Deliberately not covered:
- A pause's `plan-round-partial` commit and the `<ask>` / `<escalate>` parks: the run driver's
  (#424), because each is a `RunExit` and not a node or round event.
- `P0` and the ledger's creation: the fork's Setup acts.
- Resolving `commit_wrapper`: the caller's.
"""

import asyncio
from pathlib import Path
from typing import Final

from graphscene import (
    Action,
    AfterDispatch,
    AfterRound,
    BeforeEnd,
    BeforeRound,
    End,
    FlowGraph,
    HookCall,
    LedgerPassage,
    Passage,
    Wait,
)

from devscene_flow_host.host.commit_points import commit_artifact, flip_ledger_entry
from devscene_flow_host.host.paths import render_path
from devscene_flow_host.records.ledger import DONE_VALUE, PLANNING_ENTRIES, read_planning_marks

COMMIT_PLAN_ROUND: Final = "commit_plan_round"
FLIP_LEDGER: Final = "flip_ledger"
COMMIT_CONVERGENCE: Final = "commit_convergence"
HOOKS: Final = (COMMIT_PLAN_ROUND, FLIP_LEDGER, COMMIT_CONVERGENCE)

UI_TEST_SLOT: Final = "ui_test"
UI_TEST_WRITTEN_STATUS: Final = "passed"
UI_TEST_INDEX_PATH: Final = "ui_test_index"
_CONVERGENCE_ENTRY: Final = PLANNING_ENTRIES[2]


class PlanningHooks:
    def __init__(
        self,
        graph: FlowGraph,
        *,
        repo_root: Path,
        state_dir: str,
        branch: str,
        commit_wrapper: Path,
    ) -> None:
        self._graph = graph
        self._repo_root = repo_root
        self._state_dir = state_dir
        self._branch = branch
        self._wrapper = commit_wrapper

    def provides(self, hook: str) -> bool:
        return hook in HOOKS

    async def run(self, hook: str, call: HookCall) -> None:
        if hook not in HOOKS:
            raise LookupError(f"PlanningHooks provides no hook '{hook}'")
        if hook == COMMIT_PLAN_ROUND:
            if not isinstance(call, AfterRound):
                raise _misused(hook, call)
            await commit_artifact(
                self._wrapper, self._repo_root, "plan-round", round_number=call.passage.number
            )
        elif hook == FLIP_LEDGER:
            await self._flip_passed(_passed(hook, call))
        else:
            if not isinstance(call, BeforeEnd):
                raise _misused(hook, call)
            await self._converge(call.end)

    async def _flip_passed(self, passed: tuple[Passage, ...]) -> None:
        for passage in passed:
            if isinstance(passage, LedgerPassage) and passage.entry in PLANNING_ENTRIES:
                await self._flip(passage.entry)

    async def _flip(self, entry: str) -> None:
        await asyncio.to_thread(
            flip_ledger_entry, self._repo_root, self._state_dir, self._branch, entry
        )
        await commit_artifact(self._wrapper, self._repo_root, "ledger-flip", entry=entry)

    async def _converge(self, end: End) -> None:
        if await self._ui_test_plan_written(end):
            await commit_artifact(self._wrapper, self._repo_root, "ui-test-plan")
        await commit_artifact(self._wrapper, self._repo_root, "task-plan")
        await self._flip(_CONVERGENCE_ENTRY)

    async def _ui_test_plan_written(self, end: End) -> bool:
        reports = dict(end.reports)
        if UI_TEST_SLOT in reports:
            return reports[UI_TEST_SLOT] == UI_TEST_WRITTEN_STATUS
        marks = await asyncio.to_thread(
            read_planning_marks, self._repo_root, self._state_dir, self._branch
        )
        if marks.p2 != DONE_VALUE:
            return False
        index = render_path(self._graph.paths[UI_TEST_INDEX_PATH], self._state_dir, self._branch)
        return (self._repo_root / index).exists()


def _passed(hook: str, call: HookCall) -> tuple[Passage, ...]:
    step: Action
    if isinstance(call, AfterRound | AfterDispatch):
        step = call.step
    elif isinstance(call, BeforeEnd):
        step = call.end
    elif isinstance(call, BeforeRound):
        step = call.dispatch_set
    else:
        raise _misused(hook, call)
    return () if isinstance(step, Wait) else step.passed


def _misused(hook: str, call: HookCall) -> ValueError:
    return ValueError(f"hook '{hook}' does not run on {call.kind}")
