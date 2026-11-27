"""Runs one session process to its end, leaving no process of its group behind.

The rule:
- The argument vector is launched as given, under the given working directory and environment,
  with stdin closed and in a process group of its own (`start_new_session=True`). An `OSError`
  from the launch is a `SessionRun` carrying `launch_error`, never an exception.
- Stdout is read in chunks of `READ_CHUNK_BYTES`, never by line, so a line longer than the
  reader's default limit is neither refused nor cut; every byte is kept and decoded as UTF-8 with
  `errors="replace"`.
- Stderr is drained concurrently in its own task, keeping its last `STDERR_TAIL_BYTES`, so a
  chatty stderr never blocks the process.
- Each stdout read is bounded by the inactivity limit, so any chunk resets the clock. A read that
  times out is a stall: the group is killed and the run returns with `stalled=True` and the stdout
  read so far.
- At stdout EOF the process's exit is awaited, bounded by the inactivity limit; a leader still
  running past it is a stall.
- Killing the group is `SIGTERM` to the group, up to the kill grace for the process to exit, then
  `SIGKILL` to the group and its exit awaited; a `ProcessLookupError` means the group is gone.
  Once the leader has exited, a `PermissionError` from `killpg` means only zombies remain (Darwin
  answers `EPERM` for a zombie-only group) and is treated as the group being gone; while the
  leader runs, it propagates.
- On every path out — a normal exit, a stall, `asyncio.CancelledError`, any unexpected
  exception — the group is killed, whether or not the leader has exited, and the stderr drain is
  then awaited for at most `STDERR_DRAIN_SECONDS`. `CancelledError` is re-raised after the kill,
  never turned into a `SessionRun`.
- Nothing is written to a file, so repeating a run repeats nothing.
- The inactivity limit and the kill grace have no default here: the caller owns both values.

Deliberately not covered:
- A platform without `os.killpg`: POSIX only, as GraphScene's `FileStateStore` is POSIX-only
  through `fcntl`.
- Writing the stream anywhere: the flow host's script-driven planning driver's, not yet merged,
  which receives it through `ClaudeExecutor`'s `SessionUsage.stream`.
- What a stall or an exit status means for the node: `host/claude_executor.py`.
"""

import asyncio
import contextlib
import os
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

READ_CHUNK_BYTES: Final = 65536
STDERR_TAIL_BYTES: Final = 4096
STDERR_DRAIN_SECONDS: Final = 5.0


@dataclass(frozen=True)
class SessionRun:
    stdout: str
    stderr_tail: str
    returncode: int | None
    stalled: bool
    launch_error: str | None


async def run_session(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None,
    inactivity_limit_seconds: float,
    kill_grace_seconds: float,
) -> SessionRun:
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=None if env is None else dict(env),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        return SessionRun(
            stdout="",
            stderr_tail="",
            returncode=None,
            stalled=False,
            launch_error=f"cannot launch {argv[0]}: {error.strerror}",
        )
    assert process.stdout is not None and process.stderr is not None
    stdout = process.stdout
    stderr_task = asyncio.create_task(_drain_tail(process.stderr))
    chunks: list[bytes] = []
    stalled = False
    tail = b""
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    stdout.read(READ_CHUNK_BYTES), inactivity_limit_seconds
                )
            except TimeoutError:
                stalled = True
                break
            if not chunk:
                break
            chunks.append(chunk)
        if not stalled:
            try:
                await asyncio.wait_for(process.wait(), inactivity_limit_seconds)
            except TimeoutError:
                stalled = True
    finally:
        # The leader may already have exited while members of its group run on, so the group
        # is killed on every path out, never only while the leader runs.
        await _kill_group(process, kill_grace_seconds)
        tail = await _stderr_tail(stderr_task)
    return SessionRun(
        stdout=b"".join(chunks).decode("utf-8", errors="replace"),
        stderr_tail=tail.decode("utf-8", errors="replace"),
        returncode=process.returncode,
        stalled=stalled,
        launch_error=None,
    )


async def _drain_tail(stream: asyncio.StreamReader) -> bytes:
    tail = b""
    while chunk := await stream.read(READ_CHUNK_BYTES):
        tail = (tail + chunk)[-STDERR_TAIL_BYTES:]
    return tail


async def _stderr_tail(task: asyncio.Task[bytes]) -> bytes:
    done, _ = await asyncio.wait({task}, timeout=STDERR_DRAIN_SECONDS)
    if task in done:
        return task.result()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return b""


async def _kill_group(process: asyncio.subprocess.Process, kill_grace_seconds: float) -> None:
    _signal_group(process.pid, signal.SIGTERM, leader_exited=process.returncode is not None)
    try:
        await asyncio.wait_for(process.wait(), kill_grace_seconds)
    except TimeoutError:
        pass
    _signal_group(process.pid, signal.SIGKILL, leader_exited=process.returncode is not None)
    await process.wait()


def _signal_group(pid: int, signal_number: signal.Signals, *, leader_exited: bool) -> None:
    try:
        os.killpg(pid, signal_number)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin answers EPERM, not ESRCH, for a group whose only members are zombies.
        if not leader_exited:
            raise
