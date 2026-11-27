"""Reads a reviewer's round file: its verdict, whether a round gate may use it, and the next free
`review_<n>.md` index and the `FAIL` count of a findings folder.

The rule: `review_verdict`, `round_file_problem`, `next_review_index` and `fail_count` read as the
bash walker's `fw_review_verdict`, `fw_round_file_check`, `fw_next_review_index` and
`fw_fail_count` do (`cli/templates/scripts/lib/flow-walker-gates.sh`), and `round_file_path`
resolves a path as `flow-walker.sh`'s `round_file_path` does. A file is read as bytes and split on
`\\n`, never decoded, so any file `awk` reads is read the same way. These functions return values
and decide nothing about the walk.

Deliberately not covered:
- The class name inside `**Class:**`: `plugin/instructions/finding_grades.md` owns that list.
- An `OSError` other than a missing file: it propagates, where `awk` would print nothing.
- A missing file or folder is a value (`None`, `0`), never a `RecordError`, because the walk
  routes on it.
"""

import re
from pathlib import Path
from typing import Final, Literal

REVIEW_FILE_PREFIX: Final = "review_"
REVIEW_FILE_SUFFIX: Final = ".md"
MUST_FIX_HEADING: Final = "## Must Fix"
NO_SINGLE_VERDICT_LINE: Final = "no single verdict line"

_VERDICT_PASS: Final = b"verdict: PASS"
_VERDICT_FAIL: Final = b"verdict: FAIL"
_REVIEW_NAME: Final = re.compile(
    re.escape(REVIEW_FILE_PREFIX) + "([0-9]+)" + re.escape(REVIEW_FILE_SUFFIX)
)
_ENTRY: Final = re.compile(rb"[0-9]+\. ")
_CLASS: Final = re.compile(rb"[ \t]*\*\*Class:\*\*[ \t]*[^ \t]")
_FAILURE: Final = re.compile(rb"[ \t]*\*\*Failure:\*\*[ \t]*[^ \t]")


def _lines(path: Path) -> list[bytes] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    return [line[:-1] if line.endswith(b"\r") else line for line in raw.split(b"\n")]


def _verdict(lines: list[bytes]) -> Literal["PASS", "FAIL"] | None:
    found = [line for line in lines if line in (_VERDICT_PASS, _VERDICT_FAIL)]
    if len(found) != 1:
        return None
    return "PASS" if found[0] == _VERDICT_PASS else "FAIL"


def review_verdict(path: Path) -> Literal["PASS", "FAIL"] | None:
    lines = _lines(path)
    return None if lines is None else _verdict(lines)


def round_file_problem(path: Path) -> str | None:
    lines = _lines(path)
    verdict = None if lines is None else _verdict(lines)
    if lines is None or verdict is None:
        return NO_SINGLE_VERDICT_LINE
    must_fix = MUST_FIX_HEADING.encode()
    problem: str | None = None
    entries = 0
    in_section = is_open = has_class = has_failure = False

    def settle() -> None:
        nonlocal problem, is_open
        if is_open and problem is None:
            if not has_class:
                problem = f"Must Fix entry {entries} lacks **Class:**"
            elif not has_failure:
                problem = f"Must Fix entry {entries} lacks **Failure:**"
        is_open = False

    for line in lines:
        if line.startswith(b"## "):
            settle()
            in_section = line == must_fix
            continue
        if not in_section:
            continue
        if _ENTRY.match(line):
            settle()
            entries += 1
            is_open, has_class, has_failure = True, False, False
            continue
        if is_open and _CLASS.match(line):
            has_class = True
        if is_open and _FAILURE.match(line):
            has_failure = True
    settle()
    if verdict == "FAIL" and entries == 0:
        return "verdict: FAIL with no numbered entry under ## Must Fix"
    if verdict == "PASS" and entries > 0:
        return "verdict: PASS with a numbered entry under ## Must Fix"
    return problem


def _review_entries(folder: Path) -> list[tuple[int, str]]:
    if not folder.is_dir():
        return []
    found: list[tuple[int, str]] = []
    for entry in folder.iterdir():
        match = _REVIEW_NAME.fullmatch(entry.name)
        if match is not None:
            found.append((int(match.group(1)), entry.name))
    return found


def next_review_index(folder: Path) -> int:
    return max((n for n, _ in _review_entries(folder)), default=-1) + 1


def fail_count(folder: Path) -> int:
    return sum(1 for _, name in _review_entries(folder) if review_verdict(folder / name) == "FAIL")


def round_file_path(repo_root: Path, findings: str) -> Path:
    path = Path(findings)
    return path if path.is_absolute() else repo_root / findings
