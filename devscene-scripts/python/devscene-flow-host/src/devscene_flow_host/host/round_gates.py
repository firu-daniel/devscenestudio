"""Records a gate's outcome under the reviewer-file rules: the host's `next`.

The rule: `record_outcome` reads as `flow-walker.sh`'s `next` (*"outcome FAIL requires
--findings"*), `record_in_set`, `refuse_round_file` and `close_round`'s clearing of
`round.refused.*` (its `A REFUSED ROUND FILE` paragraph):
- An outcome whose verdict is `fail` requires a findings file, and so does any verdict outcome at
  a gate of the open round.
- A round gate's file must pass `round_file_problem` before its verdict is recorded.
- A refused file records nothing in the walk: its gate is left out of a `wait`'s pending list,
  and once no other gate is out, every refused gate is re-dispatched as one set in the same round.
- A held gate at a join whose only gates out are refused ones does not escalate there: the
  refused gates are re-dispatched as one set in the same round, and the held gate escalates at
  the round's next join, once every re-dispatched gate has a verdict or is held, so the
  escalation carries the whole round's verdicts. `flow-walker.sh` → `record_in_set` escalates at
  once instead ("With none out: a held gate escalates"); this order is the host's, chosen in
  #472, and GraphScene is not changed for it.
- The third refusal of one gate in a round records the held outcome `error`.
- A findings file given outside an open set (a non-round reviewer's `FAIL`, or `answered`) is
  kept in `RevisionFindingsStore`, as `next` keeps `revision_findings`; a held outcome at a gate
  of an open set keeps nothing; a result whose `passed` carries a `RoundPassage` clears the
  record, as `close_round` overwrites the key. `HostStep.revision_findings` is the record as it
  stands after the call.
- The returned step's printed reads (`read_printed`; `PrintedReads()` for a `RefusedWait`) are
  kept in `PrintedReadsStore`, as bash's `next` saves `out=`. `HostStep.printed` is that record.
Every call that records takes the `RefusalStore` lock before the walk's lock and releases it
after. The refusal, kept-findings and printed-reads records are written under that lock, and
only when the returned action is not `Refused`.

Deliberately not covered:
- Rendering a step or a `refused:` line: the `commands` layer's. `start`, and filtering refused
  gates out of `current`: `devscene_flow_host.host.re_entry`'s.
"""

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from graphscene import (
    DispatchNode,
    DispatchSet,
    FlowGraph,
    OpenRound,
    Refused,
    RoundNode,
    RoundPassage,
    Step,
    Wait,
    Walker,
    WalkState,
)

from devscene_flow_host.host.printed_reads import PrintedReads, PrintedReadsStore, read_printed
from devscene_flow_host.host.refusals import (
    ROUND_FILE_ATTEMPTS,
    GateRefusals,
    Refusal,
    RefusalStore,
    RoundRefusals,
)
from devscene_flow_host.host.reviewers import round_of_gate
from devscene_flow_host.host.revision_findings import RevisionFindingsStore
from devscene_flow_host.records.config import read_config
from devscene_flow_host.records.round_files import round_file_path, round_file_problem

REFUSAL_HELD_OUTCOME: Final = "error"


@dataclass(frozen=True)
class RefusedWait:
    """Bash's `wait` whose `refused:` line stands where `recorded:` would."""

    round: str
    refusal: Refusal
    pending: tuple[str, ...]


@dataclass(frozen=True)
class HostStep:
    """`refusals` holds the `refused:` lines `action` carries: one per gate of a re-dispatched
    set, or one per gate whose attempts reached `ROUND_FILE_ATTEMPTS` at an escalating join.
    `revision_findings` holds the kept findings files (`RevisionFindingsStore`) as they stand
    after the call; it is `()` on a `Refused` action. `printed` holds the values the step read
    from disk when `start` or `next` returned it, as kept in `PrintedReadsStore`; it is
    `PrintedReads()` on a `Refused` action."""

    action: Step | RefusedWait
    refusals: tuple[Refusal, ...] = ()
    revision_findings: tuple[str, ...] = ()
    printed: PrintedReads = PrintedReads()


def record_outcome(
    walker: Walker,
    repo_root: Path,
    branch: str,
    outcome: str,
    *,
    node: str | None = None,
    findings: str | None = None,
) -> HostStep:
    graph = walker.graph
    declared = graph.vocabulary.outcomes.get(outcome)
    if declared is not None and declared.verdict == "fail" and not findings:
        return HostStep(
            Refused(f"outcome {outcome} requires --findings with the reviewer's findings_file")
        )
    state_dir = read_config(repo_root).state_dir
    store = RefusalStore(repo_root, state_dir, branch)
    kept = RevisionFindingsStore(repo_root, state_dir, branch)
    with store.lock():
        opened = _open_set(graph, walker.store.read())
        result = _record(walker, store, repo_root, outcome, node, findings, opened)
        if isinstance(result.action, Refused):
            return result
        if opened is None and findings:
            kept.write((findings,))
        if _closed_a_round(result.action):
            kept.clear()
        printed_store = PrintedReadsStore(repo_root, state_dir, branch)
        try:
            printed = (
                PrintedReads()
                if isinstance(result.action, RefusedWait)
                else read_printed(graph, repo_root, state_dir, branch, result.action)
            )
        except BaseException:
            printed_store.clear()
            raise
        printed_store.write(printed)
        return dataclasses.replace(result, revision_findings=kept.read(), printed=printed)


def _record(
    walker: Walker,
    store: RefusalStore,
    repo_root: Path,
    outcome: str,
    node: str | None,
    findings: str | None,
    opened: OpenRound | None,
) -> HostStep:
    graph = walker.graph
    round_node = None if node is None else _verdict_gate(graph, opened, node, outcome)
    if opened is None or round_node is None or node is None:
        step = walker.next(outcome, node, None)
        if isinstance(step, Refused):
            return HostStep(step)
        if opened is None:
            store.clear()
            return HostStep(step)
        in_round = graph.nodes[opened.round]
        assert isinstance(in_round, RoundNode)
        return _settle(
            walker, store, in_round, store.read(opened.round, opened.number), node, step, None
        )
    if not findings:
        return HostStep(
            Refused(
                f"outcome {outcome} at round gate '{node}' requires --findings with the "
                "reviewer's findings_file"
            )
        )
    refusals = store.read(opened.round, opened.number)
    reason = round_file_problem(round_file_path(repo_root, findings))
    if reason is None:
        step = walker.next(outcome, node, findings)
        return _settle(walker, store, round_node, refusals, node, step, None)
    prior = refusals.gates.get(node)
    attempts = (0 if prior is None else prior.attempts) + 1
    refusal = Refusal(gate=node, attempt=attempts, reason=reason)
    if attempts >= ROUND_FILE_ATTEMPTS:
        refusals = _with_gate(refusals, node, GateRefusals(attempts, reason, redo=False))
        step = walker.next(REFUSAL_HELD_OUTCOME, node, None)
        return _settle(walker, store, round_node, refusals, node, step, refusal)
    refusals = _with_gate(refusals, node, GateRefusals(attempts, reason, redo=True))
    out = tuple(
        gate
        for gate in round_node.gates
        if gate in opened.due and gate not in opened.records and not _marked(refusals, gate)
    )
    if out:
        store.write(dataclasses.replace(refusals, announced=()))
        return HostStep(RefusedWait(opened.round, refusal, out))
    return _redispatch(walker, store, round_node, refusals)


def _closed_a_round(action: Step | RefusedWait) -> bool:
    if isinstance(action, (Wait, RefusedWait, Refused)):
        return False
    return any(isinstance(passage, RoundPassage) for passage in action.passed)


def _open_set(graph: FlowGraph, state: WalkState | None) -> OpenRound | None:
    if state is None or state.flow != graph.flow or state.awaiting != "set":
        return None
    return state.open_round


def _verdict_gate(
    graph: FlowGraph, opened: OpenRound | None, node: str, outcome: str
) -> RoundNode | None:
    if opened is None or node not in opened.due or node in opened.records:
        return None
    found = graph.nodes.get(node)
    if not isinstance(found, DispatchNode) or outcome not in found.outcomes:
        return None
    declared = graph.vocabulary.outcomes.get(outcome)
    if declared is None or declared.verdict is None:
        return None
    round_node = round_of_gate(graph, node)
    if round_node is None or round_node.id != opened.round:
        return None
    return round_node


def _marked(refusals: RoundRefusals, gate: str) -> bool:
    entry = refusals.gates.get(gate)
    return entry is not None and entry.redo


def _with_gate(refusals: RoundRefusals, gate: str, entry: GateRefusals) -> RoundRefusals:
    return dataclasses.replace(refusals, gates={**refusals.gates, gate: entry})


def _unmarked(refusals: RoundRefusals, gates: tuple[str, ...]) -> RoundRefusals:
    return dataclasses.replace(
        refusals,
        gates={
            gate: dataclasses.replace(entry, redo=False) if gate in gates else entry
            for gate, entry in refusals.gates.items()
        },
    )


def _settle(
    walker: Walker,
    store: RefusalStore,
    round_node: RoundNode,
    refusals: RoundRefusals,
    node: str | None,
    step: Step,
    spent: Refusal | None,
) -> HostStep:
    if isinstance(step, Refused):
        return HostStep(step)
    if node is not None:
        refusals = _unmarked(refusals, (node,))
    if isinstance(step, Wait):
        pending = tuple(gate for gate in step.pending if not _marked(refusals, gate))
        if not pending:
            return _redispatch(walker, store, round_node, refusals)
        store.write(dataclasses.replace(refusals, announced=()))
        if spent is not None:
            return HostStep(RefusedWait(step.round, spent, pending))
        return HostStep(Wait(step.round, step.recorded, pending))
    spent_refusals = tuple(
        refusals.refusal(gate)
        for gate in round_node.gates
        if gate in refusals.gates and refusals.gates[gate].attempts >= ROUND_FILE_ATTEMPTS
    )
    if spent_refusals:
        store.write(dataclasses.replace(refusals, announced=spent_refusals))
    else:
        store.clear()
    return HostStep(step, spent_refusals)


def _redispatch(
    walker: Walker, store: RefusalStore, round_node: RoundNode, refusals: RoundRefusals
) -> HostStep:
    current = walker.current()
    assert isinstance(current, DispatchSet), current
    marked = tuple(gate for gate in round_node.gates if _marked(refusals, gate))
    lines = tuple(refusals.refusal(gate) for gate in marked)
    store.write(dataclasses.replace(_unmarked(refusals, marked), announced=lines))
    dispatches = tuple(dispatch for dispatch in current.dispatches if dispatch.node in marked)
    return HostStep(DispatchSet(current.round, current.number, dispatches, current.passed), lines)
