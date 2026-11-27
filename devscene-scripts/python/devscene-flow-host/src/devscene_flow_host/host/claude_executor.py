"""`ClaudeExecutor`, the harness's `graphscene.Executor`: one headless `claude` session per
dispatched node, its usage reported to the host's `UsageSink`.

The rule: the sink is called exactly once for every `run` that returns a result, immediately
before the return, and never for a cancelled or raising run. GraphScene writes its `Launch` row
after `run` returns, and a node runs once at a time within a set, so a node's usage record comes
just before that node's next `Launch` row: the host pairs them on `node`, with equal `result` as
the check.
A `Launch` row written by GraphScene's total-run timeout
(`graphscene/src/graphscene/engine/set_execution.py` → `_run`, its result
`Failed("infra", "timed out: no result within <run_timeout_seconds>s")`) has no usage record:
the deadline cancels `run`, which records none. The host pairs nothing with that row and does
not treat it as a pairing fault. The usage of a session killed this way is lost, unlike a
stall's.
- Every constructor input is copied, so a later change to the caller's object changes nothing.
  The host's `session_args` and `agent_args` are passed through unchanged, and may carry no
  `EXECUTOR_FLAGS` member, bare or as `<member>=`.
- Each contract's return schema is checked at construction, so an invalid one never fails mid-run.
- `dispatch.prompt_variant` is the node's prompt variant (`initial`, `revision`) or `None`, never
  the text a session is given. The agent prompt comes from the host's `AgentPromptBuilder`, called
  exactly once per `run` before the launch, with nothing kept between runs; the builder must
  return the same agent prompt for a repeated run of the same dispatch.
- A dispatch whose agent has no contract raises `LookupError`, an exception out of the builder
  propagates unchanged, and a builder that returns no non-blank string raises `ValueError`, each
  before the launch, so nothing is launched and the sink is not called.
- A launch error is `Failed("infra", …)` with every usage field empty. A stall is
  `Failed("infra", …)` with the stream's usage fields kept. Otherwise the result is
  `judge_session`'s.
- `--json-schema` is never passed: on Claude Code 2.1.332 it is not applied under `--agent`, so
  the return is read from the final `json` block.
- The usage record also carries the agent prompt it was given, the session's whole stdout
  stream, its stderr tail and its exit status, and, for a `Completed` result, the validated
  return object, so the host can write the stream and read the return's other fields, which
  `Completed` cannot carry.

Deliberately not covered:
- Building the usage-to-`Launch` pairing: the flow host's script-driven planning driver's,
  not yet merged. GraphScene's run mode (`graphscene/src/graphscene/engine/run_loop.py`)
  cannot build it.
- The per-agent MCP flags and the shared session flags: the host's input. The shared flags
  include `--add-dir <plugin_dir>`, which the executor does not add. The pilot passes it for
  every node (`cli/templates/scripts/lib/planning-node-lib.sh` → `pnl_agent_flags`) unless its
  shared vector already carries it (`PD_PLUGIN_DIR_ADDED`).
- The findings-file presence rule: `host/round_gates.py` → `record_outcome`.
- Writing the stream (from `SessionUsage.stream`) or a session manifest: the flow host's
  script-driven planning driver's, not yet merged.
- Building the agent prompt: the harness's builder is `host/agent_prompts.py` →
  `CorePromptBuilder`.
"""

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Final, Protocol

from graphscene import Dispatch, Failed, NodeResult, return_violations

from devscene_flow_host.host.session_process import run_session
from devscene_flow_host.host.session_stream import judge_session
from devscene_flow_host.records.plugin_contracts import AgentContract

# The pilot's effective `PD_NODE_STALL_SECS`: `cli/templates/scripts/autonomous-watcher.sh` →
# `planning_driver_run` computes it as `STALL_KILL_SECS` (2700) minus `POLL_INTERVAL_SECS` (15).
# The flow host's value, not a `devscene.config.json` key and not GraphScene's.
NODE_INACTIVITY_LIMIT_SECONDS: Final = 2685.0
KILL_GRACE_SECONDS: Final = 5.0
EXECUTOR_FLAGS: Final = (
    "-p",
    "--print",
    "--output-format",
    "--input-format",
    "--agent",
    "--plugin-dir",
)


@dataclass(frozen=True)
class SessionUsage:
    """`started_at` is the UTC wall clock; `duration_seconds` is monotonic."""

    node: str
    agent: str
    agent_prompt: str
    session_id: str | None
    started_at: datetime
    duration_seconds: float
    stalled: bool
    total_cost_usd: float | None
    cache_creation_input_tokens: int | None
    cache_read_input_tokens: int | None
    model_usage: Mapping[str, object]
    permission_denials: int
    withheld_tools: tuple[str, ...]
    stream: str
    stderr_tail: str
    returncode: int | None
    return_document: Mapping[str, object] | None
    result: NodeResult


class UsageSink(Protocol):
    """Receives one `SessionUsage` per `run` that returned a result."""

    def record(self, usage: SessionUsage) -> None: ...


class AgentPromptBuilder(Protocol):
    """Builds the agent prompt, the text a session is given, for one dispatch; the same
    dispatch gives the same agent prompt."""

    def __call__(self, dispatch: Dispatch) -> str: ...


class ClaudeExecutor:
    """Runs each dispatched node as one headless `claude` session, under this module's rule."""

    def __init__(
        self,
        *,
        command: Sequence[str],
        plugin_dir: Path,
        plugin_name: str,
        cwd: Path,
        contracts: Mapping[str, AgentContract],
        inactivity_limit_seconds: float,
        usage_sink: UsageSink,
        agent_prompt_builder: AgentPromptBuilder,
        session_args: Sequence[str] = (),
        agent_args: Mapping[str, Sequence[str]] | None = None,
        env: Mapping[str, str] | None = None,
        kill_grace_seconds: float = KILL_GRACE_SECONDS,
    ) -> None:
        self._command = tuple(command)
        self._plugin_dir = plugin_dir
        self._plugin_name = plugin_name
        self._cwd = cwd
        self._contracts: Mapping[str, AgentContract] = MappingProxyType(dict(contracts))
        self._inactivity_limit_seconds = inactivity_limit_seconds
        self._usage_sink = usage_sink
        self._agent_prompt_builder = agent_prompt_builder
        self._session_args = tuple(session_args)
        self._agent_args: Mapping[str, tuple[str, ...]] = MappingProxyType(
            {agent: tuple(args) for agent, args in (agent_args or {}).items()}
        )
        self._env: Mapping[str, str] | None = None if env is None else MappingProxyType(dict(env))
        self._kill_grace_seconds = kill_grace_seconds
        if not self._command:
            raise ValueError("ClaudeExecutor: command must not be empty")
        if not inactivity_limit_seconds > 0:
            raise ValueError(
                "ClaudeExecutor: inactivity_limit_seconds must be > 0, "
                f"got {inactivity_limit_seconds}"
            )
        if not kill_grace_seconds >= 0:
            raise ValueError(
                f"ClaudeExecutor: kill_grace_seconds must be >= 0, got {kill_grace_seconds}"
            )
        _refuse_executor_flags("session_args", self._session_args)
        for agent, args in self._agent_args.items():
            if agent not in self._contracts:
                raise ValueError(
                    f"ClaudeExecutor: agent_args names '{agent}', which has no contract"
                )
            _refuse_executor_flags(f"agent_args['{agent}']", args)
        for contract in self._contracts.values():
            return_violations({}, contract.return_schema)

    async def run(self, dispatch: Dispatch) -> NodeResult:
        contract = self._contracts.get(dispatch.agent)
        if contract is None:
            raise LookupError(f"{dispatch.node}: no agent contract for '{dispatch.agent}'")
        agent_prompt = self._agent_prompt_builder(dispatch)
        if not isinstance(agent_prompt, str) or not agent_prompt.strip():
            raise ValueError(f"{dispatch.node}: the agent prompt builder returned no agent prompt")
        argv = [
            *self._command,
            "-p",
            agent_prompt,
            *self._session_args,
            "--output-format",
            "stream-json",
            "--verbose",
            "--agent",
            f"{self._plugin_name}:{dispatch.agent}",
            "--plugin-dir",
            str(self._plugin_dir),
            *self._agent_args.get(dispatch.agent, ()),
        ]
        started_at = datetime.now(UTC)
        started = time.monotonic()
        session = await run_session(
            argv,
            cwd=self._cwd,
            env=self._env,
            inactivity_limit_seconds=self._inactivity_limit_seconds,
            kill_grace_seconds=self._kill_grace_seconds,
        )
        duration_seconds = time.monotonic() - started
        if session.launch_error is not None:
            result: NodeResult = Failed("infra", session.launch_error)
            usage = SessionUsage(
                node=dispatch.node,
                agent=dispatch.agent,
                agent_prompt=agent_prompt,
                session_id=None,
                started_at=started_at,
                duration_seconds=duration_seconds,
                stalled=False,
                total_cost_usd=None,
                cache_creation_input_tokens=None,
                cache_read_input_tokens=None,
                model_usage=MappingProxyType({}),
                permission_denials=0,
                withheld_tools=(),
                stream="",
                stderr_tail="",
                returncode=None,
                return_document=None,
                result=result,
            )
        else:
            reading = judge_session(session.stdout, contract, self._cwd)
            if session.stalled:
                result = Failed(
                    "infra",
                    f"stalled: the stream was silent for {self._inactivity_limit_seconds:g} s; "
                    "the session was killed",
                )
            else:
                result = reading.result
            usage = SessionUsage(
                node=dispatch.node,
                agent=dispatch.agent,
                agent_prompt=agent_prompt,
                session_id=reading.session_id,
                started_at=started_at,
                duration_seconds=duration_seconds,
                stalled=session.stalled,
                total_cost_usd=reading.total_cost_usd,
                cache_creation_input_tokens=reading.cache_creation_input_tokens,
                cache_read_input_tokens=reading.cache_read_input_tokens,
                model_usage=reading.model_usage,
                permission_denials=reading.permission_denials,
                withheld_tools=reading.withheld_tools,
                stream=session.stdout,
                stderr_tail=session.stderr_tail,
                returncode=session.returncode,
                return_document=None if session.stalled else reading.return_document,
                result=result,
            )
        self._usage_sink.record(usage)
        return result


def _refuse_executor_flags(owner: str, args: tuple[str, ...]) -> None:
    for token in args:
        if any(token == flag or token.startswith(f"{flag}=") for flag in EXECUTOR_FLAGS):
            raise ValueError(f"ClaudeExecutor: {owner} carries '{token}', a flag the executor sets")
