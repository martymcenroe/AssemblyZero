"""Process-tree control shared by every subprocess-spawning provider.

Issue #526 established that a Windows ``subprocess`` timeout kills only the
root process: grandchildren keep the inherited pipe handles open, so the
drain that follows the kill blocks for as long as they live. Issue #1874
found the same hazard unfixed on the Gemini/agy transport, where it turned a
15-second-nominal review into a 17.5-minute hang.

The primitive lives here so both transports kill the same way.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

#: ``taskkill``'s exit code when the process does not exist.
TASKKILL_NOT_FOUND = 128


class ProcessTreeKillError(RuntimeError):
    """A process tree could not be killed. Raised, never swallowed (#3585)."""


def _could_not_kill(pid: int, cause: str) -> ProcessTreeKillError:
    message = (
        f"could not kill process tree {pid}: {cause}; descendants may survive "
        f"holding the pipes (#1874)"
    )
    logger.error("[KILL] %s", message)
    print(f"ERROR [KILL] {message}", file=sys.stderr, flush=True)
    return ProcessTreeKillError(message)


def kill_process_tree(pid: int) -> None:
    """Kill a process and every descendant it spawned.

    On Windows this shells out to ``taskkill /T``; elsewhere it signals the
    process group. A process that is already gone is the outcome the caller
    wanted and is quiet: ``ProcessLookupError`` off Windows, and ``taskkill``'s
    "not found" exit (128) on Windows.

    Raises:
        ProcessTreeKillError: the kill did not happen -- ``taskkill`` exited
            with any other code or timed out, or the OS refused the signal --
            after an ERROR line naming the pid and the cause (ADR 0236, #3585).
            Treating these as "already dead" reported a surviving tree as
            killed, which is the hang #1874 describes.

    Args:
        pid: Process id of the tree root.
    """
    if sys.platform == "win32":
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        try:
            ran = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise _could_not_kill(pid, f"taskkill: {type(exc).__name__}: {exc}") from exc
        if ran.returncode not in (0, TASKKILL_NOT_FOUND):
            stderr = (ran.stderr or b"").decode("utf-8", errors="replace").strip()
            raise _could_not_kill(
                pid, f"taskkill exited {ran.returncode}: {stderr or '(no stderr)'}"
            )
        return

    try:
        os.killpg(os.getpgid(pid), 9)
    except ProcessLookupError:
        return  # already gone: the outcome the caller wanted
    except OSError as exc:
        raise _could_not_kill(pid, f"{type(exc).__name__}: {exc}") from exc
