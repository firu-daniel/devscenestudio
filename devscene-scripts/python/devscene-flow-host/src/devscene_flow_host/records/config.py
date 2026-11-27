"""Reads `devscene.config.json` into a `HarnessConfig`.

The rule: `read_config` reads two keys, `stateDir` and `phases`, and refuses a configuration with
no `defaultBranch`, as `hr_config_load` does; each key is read as the bash walker's reader reads
it in `cli/templates/scripts/lib/harness-run-lib.sh`: `stateDir` as `hr_config_dir` /
`hr_state_dir`, `phases` as `hr_phase_enabled`. It reads values and decides nothing about what
they mean to the walk.

Deliberately not checked:
- Every other key.
- Whether `stateDir` is a safe repo-relative path, which is the schema's.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from devscene_flow_host.records.errors import RecordError

CONFIG_FILENAME: Final = "devscene.config.json"
# The schema's default `devscene/`, normalised as `hr_state_dir` normalises it.
DEFAULT_STATE_DIR: Final = "devscene"
# The phases `hr_phase_enabled` accepts.
PHASES: Final = ("parity", "qa", "docs")


@dataclass(frozen=True)
class HarnessConfig:
    """`state_dir` is repo-relative with no trailing `/`. `phases` holds exactly the `PHASES`
    keys, in that order: `True` on, `False` off, `None` unresolvable."""

    state_dir: str
    phases: Mapping[str, bool | None]


def read_config(repo_root: Path) -> HarnessConfig:
    path = repo_root / CONFIG_FILENAME
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RecordError(f"no {CONFIG_FILENAME} at {repo_root}") from None
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RecordError(f"{path}: not valid JSON") from None
    if not isinstance(document, dict):
        raise RecordError(f"{path}: not a JSON object")
    # The shapes `hr_config_load` does not emit; any other value passes through its `tostring`.
    if document.get("defaultBranch") in (None, "", "null"):
        raise RecordError(f"{path}: no defaultBranch")
    return HarnessConfig(
        state_dir=_state_dir(document, path),
        phases=_phases(document),
    )


def _state_dir(document: dict[str, object], path: Path) -> str:
    value = document.get("stateDir")
    if value is None:
        return DEFAULT_STATE_DIR
    if not isinstance(value, str):
        raise RecordError(f"{path}: stateDir is not a string")
    return value.rstrip("/") or DEFAULT_STATE_DIR


def _phases(document: dict[str, object]) -> Mapping[str, bool | None]:
    # `hr_config_load` reads a `null` value as not set and a phase under a `phases` that is not an
    # object as `null`, and `hr_phase_enabled` reads not set as off; the schema defaults every
    # phase to off.
    value = document.get("phases")
    phases: dict[str, object] = value if isinstance(value, dict) else {}
    return MappingProxyType({phase: _phase(phases, phase) for phase in PHASES})


def _phase(phases: dict[str, object], phase: str) -> bool | None:
    value = phases.get(phase)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return None
