"""Renders the host's `HostStep` as the stdout `flow-walker.sh` prints for the same action.

The rule: every line keeps `flow-walker.sh`'s form — its header's `OUTPUT` grammar, built as its
`render_block`, `render_set`, `record_in_set`, `take_binding` and `render_terminal` build it —
in the same keys and the same order, one `\\n`-terminated line each, so a caller parsing bash's
output reads this unchanged. A dispatch's `prompt:` variant and the findings files a step
carries are `host/prompt_variants.py`'s, over `HostStep.revision_findings` and the action's
`closed_round`. An action or passage type not named here raises `ValueError`
naming it, never a block guessed from its fields; so does a fault bash reports as exit 2.
The values a step read from disk — a non-round reviewer's `arg.iteration`, a cap's `rounds:`
counts and its `evidence:` / `evidence.open:` lines — are `HostStep.printed`, read by the host
when the step was first printed, so a `current` prints what `start` or `next` printed and
`render` reads no file.

Deliberately not covered:
- A `Refused` and every exit status: `commands/flow_walker.py`'s.
"""

from pathlib import Path

from graphscene import (
    Dispatch,
    DispatchNode,
    DispatchSet,
    End,
    FlowGraph,
    Interrupt,
    LedgerPassage,
    Passage,
    RoundPassage,
    SkipPassage,
    Stop,
    Wait,
)

from devscene_flow_host.host.paths import render_path
from devscene_flow_host.host.prompt_variants import (
    REVISION_VARIANT,
    dispatch_variant,
    findings_files,
)
from devscene_flow_host.host.refusals import ROUND_FILE_ATTEMPTS, Refusal
from devscene_flow_host.host.reviewers import round_of_gate, round_of_writer
from devscene_flow_host.host.round_gates import HostStep, RefusedWait
from devscene_flow_host.records.index_evidence import (
    REJECTED_FINDINGS_HEADING,
    SCOPE_REGISTER_HEADING,
)


def render(
    step: HostStep, *, graph: FlowGraph, repo_root: Path, state_dir: str, branch: str
) -> str:
    action = step.action
    lines: list[str]
    if isinstance(action, Dispatch):
        lines = _block(
            action,
            _passed(action.passed) + _refused(step.refusals),
            step=step,
            graph=graph,
        )
    elif isinstance(action, DispatchSet):
        lines = []
        carried = _passed(action.passed) + _refused(step.refusals)
        for dispatch in action.dispatches:
            lines += _block(
                dispatch,
                carried,
                step=step,
                graph=graph,
            )
            carried = []
    elif isinstance(action, Wait):
        lines = ["action: wait", f"node: {action.round}"]
        lines.append(f"recorded: {action.recorded.gate} {action.recorded.outcome}")
        lines += [f"pending: {gate}" for gate in action.pending]
    elif isinstance(action, RefusedWait):
        lines = ["action: wait", f"node: {action.round}", _refused_line(action.refusal)]
        lines += [f"pending: {gate}" for gate in action.pending]
    elif isinstance(action, Interrupt):
        lines = _binding_head(action.binding, action.node, action.agent)
        lines.append(f"resume: {action.resume}")
        lines += _passed(action.passed)
    elif isinstance(action, Stop):
        lines = _binding_head(action.binding, action.node, action.agent)
        lines.append(f"reason: {action.reason}")
        if action.reason == "cap":
            lines += _cap_lines(
                action,
                step=step,
                graph=graph,
                repo_root=repo_root,
                state_dir=state_dir,
                branch=branch,
            )
        lines += [f"held: {record.gate} {record.outcome}" for record in action.held]
        lines += _refused(step.refusals)
        lines += _passed(action.passed)
    elif isinstance(action, End):
        lines = ["action: binding", f"binding: {action.binding}", f"node: {action.node}"]
        lines += [f"report: {slot} {status}" for slot, status in action.reports]
        lines += _passed(action.passed)
    else:
        raise ValueError(f"no rendering for the action type {type(action).__name__}")
    return "".join(line + "\n" for line in lines)


def _block(
    dispatch: Dispatch,
    carried: list[str],
    *,
    step: HostStep,
    graph: FlowGraph,
) -> list[str]:
    node = graph.nodes.get(dispatch.node)
    if not isinstance(node, DispatchNode):
        raise ValueError(f"graph has no dispatch node '{dispatch.node}'")
    lines = ["action: dispatch", f"node: {dispatch.node}", f"agent: {dispatch.agent}"]
    variant = dispatch_variant(node, dispatch)
    if variant is not None:
        lines.append(f"prompt: {variant}")
    if round_of_writer(graph, dispatch.node) is not None:
        lines.append(f"arg.iteration: {_round_number(dispatch)}")
    if variant == REVISION_VARIANT:
        files = findings_files(step.revision_findings, dispatch.closed_round)
        if not files:
            raise ValueError(
                f"a revision of '{dispatch.node}' is due and no findings file is recorded"
            )
        lines += [f"arg.findings_file: {path}" for path in files]
    if round_of_gate(graph, dispatch.node) is not None:
        lines.append(f"arg.iteration: {_round_number(dispatch)}")
        if dispatch.converging is not None:
            mode = "converging" if dispatch.converging else "full"
            lines.append(f"arg.review_mode: {mode}")
    else:
        index = dict(step.printed.review_iterations).get(dispatch.node)
        if index is not None:
            lines.append(f"arg.iteration: {index}")
    lines += carried
    iteration = dispatch.counters.get("iteration")
    heartbeat = node.heartbeat.replace("{iteration}", "" if iteration is None else str(iteration))
    lines.append(f"heartbeat: {heartbeat}  (#<total_dispatches>)")
    return lines


def _round_number(dispatch: Dispatch) -> int:
    if dispatch.round_number is None:
        raise ValueError(f"the dispatch of '{dispatch.node}' carries no round number")
    return dispatch.round_number


def _binding_head(binding: str, node: str, agent: str | None) -> list[str]:
    lines = ["action: binding", f"binding: {binding}", f"node: {node}"]
    if agent is not None:
        lines.append(f"agent: {agent}")
    return lines


def _cap_lines(
    stop: Stop,
    *,
    step: HostStep,
    graph: FlowGraph,
    repo_root: Path,
    state_dir: str,
    branch: str,
) -> list[str]:
    lines = [
        f"findings_file: {path}"
        for path in findings_files(step.revision_findings, stop.closed_round)
    ]
    counts = dict(step.printed.round_counts)
    for counted in stop.round_counts:
        if counted not in counts:
            raise ValueError(f"the printed reads carry no count for '{counted}'")
        lines.append(f"rounds: {counted} {counts[counted]}")
    if stop.evidence is not None:
        template = graph.paths.get(stop.evidence)
        if template is None:
            raise ValueError(f"graph has no 'paths.{stop.evidence}'")
        rendered = render_path(template, state_dir, branch)
        evidence = step.printed.index_evidence
        index = f"{repo_root}/{rendered}"
        if evidence is not None:
            if evidence.rejected_findings:
                lines.append(f"evidence: {index} {REJECTED_FINDINGS_HEADING}")
            lines += [f"evidence.open: {entry}" for entry in evidence.open_rejections]
            if evidence.scope_register:
                lines.append(f"evidence: {index} {SCOPE_REGISTER_HEADING}")
    if stop.summary is not None:
        lines.append(f"summary: {stop.summary}")
    return lines


def _passed(passed: tuple[Passage, ...]) -> list[str]:
    lines: list[str] = []
    for passage in passed:
        if isinstance(passage, SkipPassage):
            lines.append(f"skip: {passage.node} {passage.status}")
        elif isinstance(passage, RoundPassage):
            lines.append(f"round: {passage.number} {passage.verdict.upper()}")
        elif isinstance(passage, LedgerPassage):
            lines.append(f"ledger: {passage.entry}")
        else:
            raise ValueError(f"no rendering for the passage type {type(passage).__name__}")
    return lines


def _refused(refusals: tuple[Refusal, ...]) -> list[str]:
    return [_refused_line(refusal) for refusal in refusals]


def _refused_line(refusal: Refusal) -> str:
    return (
        f"refused: {refusal.gate} attempt {refusal.attempt} of {ROUND_FILE_ATTEMPTS}: "
        f"{refusal.reason}"
    )
