"""The operator-wait class of output (#2527): the one state that shouts.

Every other state in the pipeline is the human waiting on the machine, and
white ticks at a steady cadence are the right voice for it. The one inversion
— the MACHINE waiting on the HUMAN — looked exactly the same, and the
operator's own words name the cost: "it wasn't clear to me from the terminal
output that my judgment was requested... it looks kinda like the counting it
is doing when an LLM is slow."

So the operator-wait class gets the strongest signal the terminal has:

* :func:`paint` renders a line in amber when stdout is a TTY, and returns it
  untouched when it is not — log files must not accumulate escape codes;
* :func:`begin` / :func:`end` mark the process-wide "a human is being waited
  on" window, so OTHER printers (the stage watchdog's tick line) can say so
  too instead of impersonating a slow model.

This module belongs to the operator-wait class generally, not to the visual
gate: any future gate that blocks on a human calls the same three functions
and inherits the whole treatment.
"""

from __future__ import annotations

import sys
import threading

_AMBER = "\x1b[33;1m"
_RESET = "\x1b[0m"

_lock = threading.Lock()
_active: dict | None = None


def wants_color(stream=None) -> bool:
    """True when ``stream`` (default stdout) is a live terminal."""
    stream = sys.stdout if stream is None else stream
    isatty = getattr(stream, "isatty", None)
    try:
        return bool(isatty and isatty())
    except (ValueError, OSError):
        # fail-open: a closed or detached stream is not a terminal, and "no
        # colour" is the correct, indistinguishable-from-real answer for it —
        # a paint decision must never crash the line it decorates.
        return False


def paint(text: str, stream=None) -> str:
    """``text`` in amber for a TTY, verbatim for anything else."""
    return f"{_AMBER}{text}{_RESET}" if wants_color(stream) else text


def begin(url: str = "", note: str = "") -> None:
    """Declare that the process is now waiting on the operator."""
    global _active
    with _lock:
        _active = {"url": url, "note": note}


def end() -> None:
    """Declare the wait over. Idempotent."""
    global _active
    with _lock:
        _active = None


def active() -> dict | None:
    """The current wait ({"url", "note"}) or None. For other printers."""
    with _lock:
        return dict(_active) if _active is not None else None
