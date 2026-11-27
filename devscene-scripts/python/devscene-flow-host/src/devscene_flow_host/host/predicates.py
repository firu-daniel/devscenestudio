"""Answers the harness graph's phase and run-mode predicates: the harness's `PredicateHost`.

The rule: a predicate is answered only by two name patterns — `phase_<p>_off` from
`phases.<p>`, as `hr_phase_enabled` / `fw_phase_on` read it, and `run_mode_skips_<id>` from the
run mode, as `fw_run_mode_skipped` and `fw_id_in_list` read it. Every other name, an unresolvable
phase and an unresolved run mode are `None`, which the walk refuses rather than guesses, as
`flow-walker.sh` → `eval_skip` does. The records are re-read on every call, so a ledger written
mid-walk is seen at the next arrival. A `RecordError` propagates. `last_refusal` holds the
reason of the latest `answer` that returned `None`, and is reset by one that returned a boolean,
so after the walk's `Refused` it names the cause.

Deliberately not covered:
- Rendering a refusal for the walker's output, which stays the `commands` layer's; it reads
  `last_refusal`.
"""

import re
from pathlib import Path
from typing import Final

from devscene_flow_host.records.config import CONFIG_FILENAME, PHASES, read_config
from devscene_flow_host.records.ledger import RunModeUnresolved, read_run_mode

PHASE_PREDICATE: Final = re.compile(rf"^phase_({'|'.join(PHASES)})_off$")
RUN_MODE_PREDICATE: Final = re.compile(r"^run_mode_skips_([a-z][a-z0-9_-]*)$")


class HarnessPredicateHost:
    def __init__(self, repo_root: Path, branch: str, *, skipped: str | None = None) -> None:
        self._repo_root = repo_root
        self._branch = branch
        self._skipped = skipped
        self._last_refusal: str | None = None

    @property
    def last_refusal(self) -> str | None:
        return self._last_refusal

    def answer(self, predicate: str, node: str) -> bool | None:
        resolved = self._resolve(predicate)
        if isinstance(resolved, bool):
            self._last_refusal = None
            return resolved
        self._last_refusal = resolved
        return None

    def refusal_reason(self, predicate: str) -> str | None:
        resolved = self._resolve(predicate)
        return None if isinstance(resolved, bool) else resolved

    def _resolve(self, predicate: str) -> bool | str:
        """A boolean answer, or the reason there is none."""
        phase = PHASE_PREDICATE.match(predicate)
        if phase:
            name = phase.group(1)
            enabled = read_config(self._repo_root).phases[name]
            if enabled is None:
                return f"cannot resolve phases.{name} in {self._repo_root}/{CONFIG_FILENAME}"
            return not enabled
        run_mode_id = RUN_MODE_PREDICATE.match(predicate)
        if run_mode_id:
            config = read_config(self._repo_root)
            run_mode = read_run_mode(self._repo_root, config.state_dir, self._branch, self._skipped)
            if isinstance(run_mode, RunModeUnresolved):
                return run_mode.reason
            return run_mode_id.group(1) in run_mode.skipped
        return f"'{predicate}' is not a predicate the harness answers"
