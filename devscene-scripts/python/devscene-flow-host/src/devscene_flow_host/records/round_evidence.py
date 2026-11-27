"""Reads a round's evidence: its highest round number, each gate's status at that number, whether
the next revision note exists, and whether the plan changed after the round's files were committed.

The rule: `read_round_evidence` reads as the bash walker's `fw_round_evidence` does
(`cli/templates/scripts/lib/flow-walker-gates.sh`), asking `git` the same questions in the same
order through fixed argument vectors. `plan` is judged against every gate whose round file is
present, which is judging it against the earliest-committed present file, as bash's header says.
When `git` cannot answer in the repository root, that is a `RecordError`. It returns the evidence
and decides nothing with it.

Deliberately not covered:
- Deciding what the evidence means for the walk — which round a resume enters, which records it
  carries: that is `host`'s.
- Git's own stderr: it is not carried into the `RecordError` message.
- Rendering a graph path: the caller passes absolute paths and a note template still carrying
  `{round}`.
"""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from devscene_flow_host.records.errors import RecordError
from devscene_flow_host.records.round_files import (
    REVIEW_FILE_PREFIX,
    REVIEW_FILE_SUFFIX,
    next_review_index,
    review_verdict,
    round_file_problem,
)

ROUND_PLACEHOLDER: Final = "{round}"


@dataclass(frozen=True)
class GateEvidence:
    gate: str
    status: Literal["PASS", "FAIL", "missing", "unreadable"]
    file: Path


@dataclass(frozen=True)
class RoundEvidence:
    round: int | None
    gates: tuple[GateEvidence, ...]
    note_present: bool
    plan: Literal["not-newer", "newer", "unknown"]


def _gate_evidence(gate: str, file: Path) -> GateEvidence:
    if not file.exists():
        return GateEvidence(gate, "missing", file)
    verdict = review_verdict(file)
    if verdict is None or round_file_problem(file) is not None:
        return GateEvidence(gate, "unreadable", file)
    return GateEvidence(gate, verdict, file)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None


def _git_answer(repo_root: Path, *args: str) -> str:
    result = _git(repo_root, *args)
    if result is None or result.returncode != 0:
        raise RecordError(f"git cannot answer in {repo_root}")
    return result.stdout


def _plan_freshness(
    repo_root: Path, plan_paths: Sequence[Path], present: Sequence[Path]
) -> Literal["not-newer", "newer", "unknown"]:
    _git_answer(repo_root, "rev-parse", "--is-inside-work-tree")
    head = _git(repo_root, "rev-parse", "--verify", "-q", "HEAD")
    if head is None:
        raise RecordError(f"git cannot answer in {repo_root}")
    if head.returncode != 0:
        return "unknown"
    commits: list[str] = []
    for file in present:
        commit = _git_answer(repo_root, "rev-list", "-1", "HEAD", "--", str(file)).strip()
        if not commit:
            return "unknown"
        commits.append(commit)
    if not plan_paths:
        return "not-newer"
    plans = [str(path) for path in plan_paths]
    out = ""
    for commit in commits:
        out = _git_answer(repo_root, "rev-list", f"{commit}..HEAD", "--", *plans).strip()
        if out:
            break
    if not out:
        out = _git_answer(
            repo_root, "--no-optional-locks", "status", "--porcelain", "--", *plans
        ).strip()
    return "newer" if out else "not-newer"


def read_round_evidence(
    repo_root: Path,
    note_template: str | None,
    plan_paths: Sequence[Path],
    gates: Sequence[tuple[str, Path]],
) -> RoundEvidence:
    r = max((next_review_index(folder) - 1 for _, folder in gates), default=-1)
    if r < 0:
        return RoundEvidence(None, (), False, "unknown")
    evidence = tuple(
        _gate_evidence(gate, folder / f"{REVIEW_FILE_PREFIX}{r}{REVIEW_FILE_SUFFIX}")
        for gate, folder in gates
    )
    # An empty template is bash's `[ -e "" ]`, which is false; `Path("")` would be `.`.
    note_present = (
        Path(note_template.replace(ROUND_PLACEHOLDER, str(r + 1), 1)).exists()
        if note_template
        else False
    )
    present = [item.file for item in evidence if item.status != "missing"]
    if not present:
        return RoundEvidence(r, evidence, note_present, "unknown")
    return RoundEvidence(r, evidence, note_present, _plan_freshness(repo_root, plan_paths, present))
