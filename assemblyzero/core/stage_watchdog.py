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

#3796 (ADR 0236): since nothing here can stop a stalled stage, the first
STALLED tick alerts the operator, once per stage run, with the stage, the
elapsed time and the ratio. An alert that cannot be delivered is raised when
the stage ends, unless the stage is already raising its own error.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from assemblyzero.core import alert, operator_wait

# Derived, not typed. Each value is the p90 duration of PASSED runs of that
# stage across the boostgauge speedrun corpus, produced by
# `tools/derive_stage_nominals.py` and re-derivable with one command:
#
#   poetry run python tools/derive_stage_nominals.py --runs <repo>/data/speedrun/runs
#
# Re-derived 2026-08-15 (#2410). Sample sizes: lld 74, spec 56, impl 22, pr 21,
# cleanup 21. These are starting points for the ratio, not SLAs -- a stage
# legitimately slower than its nominal only earns a louder log line.
#
# #2323 replaced a hand-typed table with a derived one and fixed impl, whose
# nominal sat 3x BELOW its own median. #2410 corrects the STATISTIC, which that
# derivation inherited unexamined: the median describes "typical" only when the
# distribution has one mode, and this one does not.
#
#     stage    n     p50     p75     p90     max
#     lld     74    79.9   332.9   409.0   741.1
#
# LLD passes cluster near 60s AND near 400s, both genuine -- the corpus carries
# no `skipped` verdict and the fast mode is 50-80s of real passes. The median
# lands inside the fast mode and describes neither, so on run-issue1-114223 a
# healthy LLD stage printed `running 300s (nominal ~75s) - SLOW, 3x nominal`
# while its three prior passes on that repo had taken 380.1s and 409.0s. Every
# ordinary LLD run crossed the SLOW threshold, which is the same
# warnings-mean-least failure #2323 fixed for impl, arriving by a different
# route.
#
# The label answers "is this longer than this stage plausibly takes?", not "is
# this longer than typical?". p90 answers the first, and 3x p90 clears every
# recorded healthy run of every stage -- asserted against the corpus in
# `tests/unit/test_stage_watchdog.py` rather than asserted here.
#
# `triage` has no passed samples in the corpus (it is skipped on these runs).
# It is now OMITTED rather than carried forward unmeasured: a nominal the fleet
# cannot compute honestly should produce no verdict, and 20.0 was a guess that
# would have labelled a 61-second triage STALLED.
STAGE_NOMINAL_SECONDS: dict[str, float] = {
    "lld": 409.0,
    "spec": 406.7,
    "impl": 2122.2,
    "pr": 3.2,
    "cleanup": 82.7,
}

#: A stage with fewer passing samples than this gets no nominal at all, and the
#: watchdog reports elapsed time without a verdict (#2410). Mirrors
#: `derive_stage_nominals.MIN_SAMPLES_FOR_NOMINAL`; a test pins the two
#: together so the table cannot acquire an under-sampled entry.
MIN_SAMPLES_FOR_NOMINAL = 5

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
        self._alerted = False
        self._undelivered: alert.AlertDeliveryError | None = None

    def _verdict(self, elapsed: float) -> str:
        """``"STALLED"``, ``"SLOW"`` or ``""``, against the nominal alone."""
        if not self.nominal:
            return ""
        ratio = elapsed / self.nominal
        if ratio >= STALLED_RATIO:
            return "STALLED"
        if ratio >= SLOW_RATIO:
            return "SLOW"
        return ""

    def status_line(self, elapsed: float) -> str:
        """The line printed at `elapsed` seconds — reads only declared state,
        so tests can drive it with begin()/end() and a number."""
        line = f"    [STAGE] {self.stage} running {int(elapsed)}s"
        # #2527: the one state where the MACHINE waits on the HUMAN must not
        # impersonate a slow model. While a gate has declared an operator
        # wait, the tick says whose turn it is — and no SLOW/STALLED verdict
        # is issued, because elapsed time here measures the operator's
        # attention, not the stage's health.
        if operator_wait.active() is not None:
            return line + " - awaiting OPERATOR (this wait is yours)"
        if not self.nominal:
            return line
        line += f" (nominal ~{int(self.nominal)}s)"
        verdict = self._verdict(elapsed)
        if verdict:
            line += f" - {verdict}, {int(elapsed / self.nominal)}x nominal"
        return line

    def _alert_stall(self, elapsed: float) -> None:
        """Tell the operator the stage has stalled (#3796).

        Nothing here can stop the stage, so the alert is the whole response.
        It used to be a stdout line, seen only by someone at the terminal.
        """
        ratio = elapsed / self.nominal
        alert.alert_operator(
            what=(
                f"stage {self.stage} is STALLED: running {int(elapsed)}s, "
                f"{int(ratio)}x its nominal"
            ),
            where="assemblyzero.core.stage_watchdog.StageWatchdog",
            cause=(
                f"no result after {int(elapsed)}s against a nominal of "
                f"~{int(self.nominal)}s, the p90 of its passing runs; STALLED "
                f"is {STALLED_RATIO:g}x"
            ),
            consequence=(
                "the stage keeps running: the watchdog never kills it, so "
                "look at it now"
            ),
        )

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            elapsed = time.monotonic() - self._start
            line = self.status_line(elapsed)
            # #2527: amber on a TTY while awaiting the operator; paint() is a
            # no-op into files, so logs stay free of escape codes.
            waiting = operator_wait.active() is not None
            if waiting:
                line = operator_wait.paint(line)
            print(line, flush=True)
            # #3796: the first STALLED tick alerts; later ticks only print.
            if not waiting and not self._alerted and self._verdict(elapsed) == "STALLED":
                self._alerted = True
                try:
                    self._alert_stall(elapsed)
                except alert.AlertDeliveryError as exc:
                    # alert_operator has already written the undelivered
                    # record to stderr. The error ends this thread (Python
                    # prints its traceback), and __exit__ raises it in the
                    # stage's own thread when the stage ends.
                    self._undelivered = exc
                    raise

    def __enter__(self) -> "StageWatchdog":
        self._start = time.monotonic()
        self._stop.clear()
        self._alerted = False
        self._undelivered = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        # #3796: an alert that could not be delivered is a failure of its own.
        # When the stage is already raising, its error propagates, and the
        # undelivered record is on stderr.
        if self._undelivered is not None and exc[0] is None:
            raise self._undelivered
