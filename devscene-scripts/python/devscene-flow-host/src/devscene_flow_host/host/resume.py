"""A round's `RoundResume`, built from its files on disk for GraphScene's `Walker.start`.

The rule: `round_resume` reads as `flow-walker.sh`'s `start_round` and `start_record`. The entry is
a round's writer (role writer) or a round node (role set); any other entry has no resume. Then:
- no round file opens round 0's whole set;
- a round with files missing, whose evidence is consistent, records the present gates and opens
  only the missing ones;
- any other incomplete round opens the whole set at that round;
- a complete round that is unreadable or has no FAIL is reviewed again;
- a FAIL with the next revision note on disk opens the next round;
- a FAIL without the note records every verdict, so the round closes at once.
Convergence is never inferred from files. A recorded gate's file is repo-relative, as
`start_record` stores `round.findings.<gate>`.

Deliberately not covered:
- The counter, the prompt variants and the refusal count: a lost walk loses them, as in bash.
- Picking the entry: the caller's, from the ledger.
"""

from pathlib import Path

from graphscene import DispatchNode, FlowGraph, GateRecord, PredicateHost, RoundNode, RoundResume

from devscene_flow_host.host.paths import render_path
from devscene_flow_host.host.reviewers import round_of_writer
from devscene_flow_host.records.errors import RecordError
from devscene_flow_host.records.round_evidence import GateEvidence, read_round_evidence


def _skipped(graph: FlowGraph, host: PredicateHost, gate: str) -> bool:
    node = graph.nodes[gate]
    if not isinstance(node, DispatchNode):
        return False
    for entry in node.skip or ():
        answer = host.answer(entry.when, gate)
        if answer is None:
            # `Walker.start` refuses this predicate itself on arrival.
            return False
        if answer:
            return True
    return False


def _folder(graph: FlowGraph, repo_root: Path, state_dir: str, branch: str, gate: str) -> Path:
    node = graph.nodes[gate]
    if not isinstance(node, DispatchNode) or node.findings_folder is None:
        raise ValueError(f"round gate '{gate}' declares no findingsFolder")
    return repo_root / render_path(node.findings_folder, state_dir, branch).rstrip("/")


def _records(repo_root: Path, gates: tuple[GateEvidence, ...]) -> tuple[GateRecord, ...]:
    return tuple(
        GateRecord(item.gate, item.status, item.file.relative_to(repo_root).as_posix())
        for item in gates
        if item.status in ("PASS", "FAIL")
    )


def round_resume(
    graph: FlowGraph,
    host: PredicateHost,
    repo_root: Path,
    state_dir: str,
    branch: str,
    entry: str | None = None,
) -> RoundResume | None:
    e = entry or graph.start
    rn = round_of_writer(graph, e)
    writer = rn is not None
    if rn is None:
        node = graph.nodes.get(e)
        if not isinstance(node, RoundNode):
            return None
        rn = node

    note_template = (
        None
        if rn.revision_note is None
        else str(repo_root / render_path(graph.paths[rn.revision_note], state_dir, branch))
    )
    plan_paths = [repo_root / render_path(graph.paths[p], state_dir, branch) for p in rn.plan or ()]
    gates = [
        (g, _folder(graph, repo_root, state_dir, branch, g))
        for g in rn.gates
        if writer or not _skipped(graph, host, g)
    ]
    try:
        evidence = read_round_evidence(repo_root, note_template, plan_paths, gates)
    except RecordError as error:
        raise RecordError(f"cannot read the round evidence of '{rn.id}': {error}") from error

    r = evidence.round
    if r is None:
        return None
    if writer:
        return RoundResume(rn.id, r + 1)
    statuses = {item.status for item in evidence.gates}
    if "missing" in statuses:
        if "unreadable" not in statuses and evidence.plan == "not-newer":
            return RoundResume(rn.id, r, _records(repo_root, evidence.gates))
        return RoundResume(rn.id, r)
    if "unreadable" in statuses or "FAIL" not in statuses:
        return RoundResume(rn.id, r)
    if evidence.note_present:
        return RoundResume(rn.id, r + 1)
    return RoundResume(rn.id, r, _records(repo_root, evidence.gates))
