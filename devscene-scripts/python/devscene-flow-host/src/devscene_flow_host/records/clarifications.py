"""Reads a branch's top-level answered clarification pairs, each with its question's origin.

The rule: `read_answered_pairs` reads `<stateDir>/clarifications/<branch>/` as
`hr_top_level_answered_pairs` does (`cli/templates/scripts/lib/harness-run-lib.sh`): a pair is a
top-level `question_<n>.md`, `<n>` all digits, with a sibling `answer_<n>.md` that is a regular
file, in ascending numeric `<n>`; no subdirectory is read. Each question's origin is read as
`pd_raised_by` reads it (`cli/templates/scripts/lib/planning-driver-lib.sh`): the text after
`Raised by: ` on the first such line before the first `## ` line, a trailing CR stripped, else
`None`. `read_answered_pairs` opens no answer file: an origin is told from the question alone.
`read_pair_text` reads one pair file's text as `pd_pairs_text` `cat`s it (the same library), and is
called only for pairs the caller has kept, so a `Phase G` answer is never opened before Phase D. It
reads values and decides nothing with them.

Deliberately not covered:
- Which origins reach a writer, and which writer: `host/planning_entry.py`'s.
- Rendering the pairs between the untrusted-data markers into a prompt: `host/agent_prompts.py`'s.
"""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from devscene_flow_host.records.errors import RecordError

CLARIFICATIONS_DIRECTORY: Final = "clarifications"
RAISED_BY_PREFIX: Final = "Raised by: "
_HEADING_PREFIX: Final = "## "
_QUESTION_NAME: Final = re.compile(r"question_([0-9]+)\.md")


@dataclass(frozen=True)
class AnsweredPair:
    """`question` and `answer` are repo-relative paths; `raised_by` is the question's origin."""

    index: int
    question: str
    answer: str
    raised_by: str | None


def read_answered_pairs(repo_root: Path, state_dir: str, branch: str) -> tuple[AnsweredPair, ...]:
    rel_dir = PurePosixPath(state_dir, CLARIFICATIONS_DIRECTORY, branch)
    directory = repo_root / rel_dir
    try:
        names = [entry.name for entry in directory.iterdir()]
    except FileNotFoundError:
        return ()

    found: list[tuple[int, str]] = []
    for name in names:
        match = _QUESTION_NAME.fullmatch(name)
        if match and (directory / f"answer_{match.group(1)}.md").is_file():
            found.append((int(match.group(1)), match.group(1)))
    found.sort(key=lambda item: item[0])

    pairs: list[AnsweredPair] = []
    for index, n in found:
        question = directory / f"question_{n}.md"
        if question.is_file():
            try:
                raw = question.read_bytes()
            except FileNotFoundError:
                continue
            raised_by = _raised_by(raw, question)
        elif question.exists():
            raised_by = None
        else:
            continue
        pairs.append(
            AnsweredPair(
                index=index,
                question=(rel_dir / f"question_{n}.md").as_posix(),
                answer=(rel_dir / f"answer_{n}.md").as_posix(),
                raised_by=raised_by,
            )
        )
    return tuple(pairs)


def read_pair_text(repo_root: Path, rel: str) -> str:
    path = repo_root / rel
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"the clarification file '{rel}' cannot be read") from None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None


def _raised_by(raw: bytes, path: Path) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise RecordError(f"{path}: not UTF-8 text") from None
    for raw_line in text.split("\n"):
        line = raw_line.removesuffix("\r")
        if line.startswith(_HEADING_PREFIX):
            return None
        if line.startswith(RAISED_BY_PREFIX):
            return line[len(RAISED_BY_PREFIX) :]
    return None
