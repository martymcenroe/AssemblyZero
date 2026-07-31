"""One process-wide default so no child opens a console window (#2040).

Whether a child shows a console depends on the PARENT. Under an interactive
shell it inherits one and nothing appears; under Task Scheduler (#2015) there
is none to inherit, so every console application allocates its own window on
the operator's desktop.

#2037 added CREATE_NO_WINDOW to the two spawn sites that were known about. The
pipeline has 27, spawning git, gh, poetry, pytest and claude, and a poetry.exe
window appeared minutes after that fix merged. There is no reason to think 27
is the final number, new spawns get added, and libraries spawn children this
repo will never edit.

So the default is installed once, at the entry point, rather than remembered at
every call site. `subprocess.run` builds a `Popen`, so wrapping the constructor
covers every form of spawn in the process.

The failure this prevents is invisible in logs: only a human watching the
desktop sees a window appear, which is exactly how it shipped twice.
"""

from __future__ import annotations

import subprocess
import sys

# Deliberate console requests. A caller asking for one of these has made a
# decision, and quietly overriding it would be a different bug.
_CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
_DETACHED_PROCESS = 0x00000008

_installed = False


def install() -> None:
    """Make CREATE_NO_WINDOW the default for every child of this process.

    Idempotent, and a no-op off Windows -- creation flags do not exist there
    and wrapping the constructor would only add a layer that can break.
    """
    global _installed
    if _installed or sys.platform != "win32":
        return

    original_init = subprocess.Popen.__init__

    def _init(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        flags = kwargs.get("creationflags", 0)
        if not flags & (_CREATE_NEW_CONSOLE | _DETACHED_PROCESS):
            kwargs["creationflags"] = flags | subprocess.CREATE_NO_WINDOW
        return original_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _init
    _installed = True


def is_installed() -> bool:
    return _installed
