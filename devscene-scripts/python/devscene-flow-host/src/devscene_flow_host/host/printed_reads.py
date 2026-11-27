"""The values a step read from disk when it was printed: the host's own per-branch file.

Branch `b`'s file is
`<repo_root>/<stateDir>/.flow_walker_state/printed_reads/<quote(b, safe="")>.json`.

The rule:
- The record plays the part of bash's saved `out=` lines that `render_block`
  (`fw_next_review_index`) and `take_binding` (`fw_fail_count`, `fw_index_evidence`) read from
  disk at print time: a non-round reviewer's next index, a cap's per-node FAIL counts and the
  cap's index evidence. `read_printed` does those reads for a step; the store keeps them.
- Every write happens while the caller holds `RefusalStore`'s lock; this module takes no lock of
  its own. `read` takes none, because `write` replaces the file whole.
- The store writes only its file and its temporary files, all inside `printed_reads/`.

Deliberately not covered:
- When the record is written or read: the caller's.
- Rendering the values: the `commands` layer's.
- Removing a finished branch's file.
- A crash between the walk's write and this one, which leaves the previous step's reads; an
  exception from `read_printed` after the walk's write clears the record instead (`clear`), so
  `current_step` reads the files.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import quote

from graphscene import Dispatch, DispatchNode, DispatchSet, FlowGraph, Step, Stop

from devscene_flow_host.host.paths import render_path
from devscene_flow_host.host.reviewers import review_iteration
from devscene_flow_host.host.store import STATE_DIRECTORY
from devscene_flow_host.records.index_evidence import IndexEvidence, read_index_evidence
from devscene_flow_host.records.round_files import fail_count

PRINTED_READS_DIRECTORY: Final = "printed_reads"
_VERSION: Final = 1
_DOCUMENT_KEYS: Final = ("version", "review_iterations", "round_counts", "index_evidence")
_EVIDENCE_KEYS: Final = ("rejected_findings", "open_rejections", "scope_register")
_EVIDENCE_FLAGS: Final = ("rejected_findings", "scope_register")


@dataclass(frozen=True)
class PrintedReads:
    review_iterations: tuple[tuple[str, int], ...] = ()
    round_counts: tuple[tuple[str, int], ...] = ()
    index_evidence: IndexEvidence | None = None


def read_printed(
    graph: FlowGraph, repo_root: Path, state_dir: str, branch: str, action: Step
) -> PrintedReads:
    if isinstance(action, Dispatch):
        return PrintedReads(
            review_iterations=_iterations(graph, repo_root, state_dir, branch, (action,))
        )
    if isinstance(action, DispatchSet):
        return PrintedReads(
            review_iterations=_iterations(graph, repo_root, state_dir, branch, action.dispatches)
        )
    if isinstance(action, Stop) and action.reason == "cap":
        return _cap_reads(graph, repo_root, state_dir, branch, action)
    return PrintedReads()


def _iterations(
    graph: FlowGraph,
    repo_root: Path,
    state_dir: str,
    branch: str,
    dispatches: tuple[Dispatch, ...],
) -> tuple[tuple[str, int], ...]:
    found: list[tuple[str, int]] = []
    for dispatch in dispatches:
        index = review_iteration(graph, repo_root, state_dir, branch, dispatch.node)
        if index is not None:
            found.append((dispatch.node, index))
    return tuple(found)


def _cap_reads(
    graph: FlowGraph, repo_root: Path, state_dir: str, branch: str, stop: Stop
) -> PrintedReads:
    counts: list[tuple[str, int]] = []
    for counted in stop.round_counts:
        node = graph.nodes.get(counted)
        if not isinstance(node, DispatchNode) or node.findings_folder is None:
            raise ValueError(f"graph has no 'nodes.{counted}.findingsFolder'")
        folder = repo_root / render_path(node.findings_folder, state_dir, branch)
        counts.append((counted, fail_count(folder)))
    evidence: IndexEvidence | None = None
    if stop.evidence is not None:
        template = graph.paths.get(stop.evidence)
        if template is None:
            raise ValueError(f"graph has no 'paths.{stop.evidence}'")
        evidence = read_index_evidence(repo_root / render_path(template, state_dir, branch))
    return PrintedReads(round_counts=tuple(counts), index_evidence=evidence)


def printed_reads_path(repo_root: Path, state_dir: str, branch: str) -> Path:
    if not branch:
        raise ValueError("a walk's branch is empty")
    return (
        repo_root
        / state_dir
        / STATE_DIRECTORY
        / PRINTED_READS_DIRECTORY
        / (quote(branch, safe="") + ".json")
    )


class PrintedReadsStore:
    """Branch `branch`'s printed reads."""

    def __init__(self, repo_root: Path, state_dir: str, branch: str) -> None:
        self._path = printed_reads_path(repo_root, state_dir, branch)

    def read(self) -> PrintedReads | None:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            return _decode(raw)
        except ValueError as error:
            raise ValueError(f"{self._path}: {error}") from None

    def write(self, reads: PrintedReads) -> None:
        evidence = reads.index_evidence
        document = {
            "version": _VERSION,
            "review_iterations": [list(pair) for pair in reads.review_iterations],
            "round_counts": [list(pair) for pair in reads.round_counts],
            "index_evidence": None
            if evidence is None
            else {
                "rejected_findings": evidence.rejected_findings,
                "open_rejections": list(evidence.open_rejections),
                "scope_register": evidence.scope_register,
            },
        }
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{self._path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump(document, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


def _decode(raw: bytes) -> PrintedReads:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("not valid JSON") from None
    if not isinstance(document, dict):
        raise ValueError("the document is not an object")
    _keys(document, _DOCUMENT_KEYS, "the document")
    version = document["version"]
    if type(version) is not int or version != _VERSION:
        raise ValueError(f"version {json.dumps(version)} is not {_VERSION}")
    return PrintedReads(
        review_iterations=_pairs(document["review_iterations"], "review_iterations"),
        round_counts=_pairs(document["round_counts"], "round_counts"),
        index_evidence=_evidence(document["index_evidence"]),
    )


def _keys(found: dict[str, object], expected: tuple[str, ...], owner: str) -> None:
    for key in expected:
        if key not in found:
            raise ValueError(f"{owner} has no {key}")
    for key in found:
        if key not in expected:
            raise ValueError(f"{owner} has an unexpected key {json.dumps(key)}")


def _pairs(value: object, field: str) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} is not a list")
    pairs: list[tuple[str, int]] = []
    for index, item in enumerate(value):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or type(item[1]) is not int
            or item[1] < 0
        ):
            raise ValueError(f"{field}[{index}] is not a [node, count] pair")
        pairs.append((item[0], item[1]))
    return tuple(pairs)


def _evidence(value: object) -> IndexEvidence | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("index_evidence is not an object or null")
    _keys(value, _EVIDENCE_KEYS, "index_evidence")
    for key in _EVIDENCE_FLAGS:
        if not isinstance(value[key], bool):
            raise ValueError(f"index_evidence.{key} is not a boolean")
    open_rejections = value["open_rejections"]
    if not isinstance(open_rejections, list) or not all(
        isinstance(entry, str) for entry in open_rejections
    ):
        raise ValueError("index_evidence.open_rejections is not a list of strings")
    return IndexEvidence(
        value["rejected_findings"], tuple(open_rejections), value["scope_register"]
    )
