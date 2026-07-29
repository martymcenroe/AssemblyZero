"""Make a stalled stage visible while it stalls (Issue #1886).

On 2026-07-28 a test-plan review with a ~15 second nominal ran 17.5 minutes.
Nothing in the system said so. The instrumented wrapper's heartbeat reported
"alive" the entire time, because a live process is not a progressing one, and
the stall was caught only when a human compared elapsed time against what that
stage normally takes.

This prints the comparison the human was doing, while the stage is running:

    [STAGE] impl running 60s
    [STAGE] impl running 120s (nominal ~40s) - SLOW, 3x nominal
    [STAGE] impl running 180s (nominal ~40s) - STALLED, 4x nominal

It never kills anything. Bounding a call is the provider's job (#1874); this
is the observability half, so a stall is obvious in the log at the time it
happens rather than in hindsight.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

# Observed durations from the boostgauge hardening campaign run records
# (2026-07-28/29). These are starting points for the ratio, not SLAs — a
# stage legitimately slower than its nominal only earns a louder log line.
STAGE_NOMINAL_SECONDS: dict[str, float] = {
    "triage": 20.0,
    "lld": 60.0,
    "spec": 90.0,
    "impl": 240.0,
    "pr": 15.0,
    "cleanup": 90.0,
}

# Ratio at which the line changes tone. 3x is the operator's own threshold:
# "if nominal is 15 seconds, 15 minutes is a problem, not patience."
SLOW_RATIO = 3.0
STALLED_RATIO = 6.0

DEFAULT_INTERVAL_SECONDS = 60


class StageWatchdog:
    """Emit a progress line for a running stage, louder as it overruns.

    Usage:
        with StageWatchdog("impl"):
            run_the_stage()
    """

    def __init__(
        self,
        stage: str,
        nominal_seconds: Optional[float] = None,
        interval: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self.stage = stage
        self.nominal = (
            nominal_seconds
            if nominal_seconds is not None
            else STAGE_NOMINAL_SECONDS.get(stage)
        )
        self.interval = interval
        self._start = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def status_line(self, elapsed: float) -> str:
        """The line printed at `elapsed` seconds — pure, so tests can read it."""
        line = f"    [STAGE] {self.stage} running {int(elapsed)}s"
        if not self.nominal:
            return line
        line += f" (nominal ~{int(self.nominal)}s)"
        ratio = elapsed / self.nominal
        if ratio >= STALLED_RATIO:
            line += f" - STALLED, {int(ratio)}x nominal"
        elif ratio >= SLOW_RATIO:
            line += f" - SLOW, {int(ratio)}x nominal"
        return line

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            print(self.status_line(time.monotonic() - self._start), flush=True)

    def __enter__(self) -> "StageWatchdog":
        self._start = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
