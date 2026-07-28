"""Process-tree control shared by every subprocess-spawning provider.

Issue #526 established that a Windows ``subprocess`` timeout kills only the
root process: grandchildren keep the inherited pipe handles open, so the
drain that follows the kill blocks for as long as they live. Issue #1874
found the same hazard unfixed on the Gemini/agy transport, where it turned a
15-second-nominal review into a 17.5-minute hang.

The primitive lives here so both transports kill the same way.
"""

from __future__ import annotations

import os
import subprocess
import sys


def kill_process_tree(pid: int) -> None:
    """Kill a process and every descendant it spawned.

    On Windows this shells out to ``taskkill /T``; elsewhere it signals the
    process group. Never raises: a process that is already gone is the
    outcome the caller wanted.

    Args:
        pid: Process id of the tree root.
    """
    try:
        if sys.platform == "win32":
            env = os.environ.copy()
            env["PYTHONWARNINGS"] = "ignore"
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
                env=env,
            )
        else:
            os.killpg(os.getpgid(pid), 9)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        # Already dead — that's fine.
        pass
