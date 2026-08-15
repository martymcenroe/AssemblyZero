"""Full-scale proof for the #2405 idle timeout, at the real durations.

The unit suite asserts the mechanism in seconds so it stays fast. This asserts
it at the scale the defect actually occurred at: a synthetic call that streams
for longer than the 600s ceiling boostgauge #1 died against, and a silent call
that must still be killed promptly.

Both halves are required. A mechanism that never kills anything passes the first
half trivially and is worthless; one that kills a live call passes the second and
is worse than the wall it replaced.

Run:
    poetry run python tools/prove_idle_timeout.py

Takes about 11 minutes, almost all of it the long call proving it is allowed to
finish. No model tokens are spent: the streamer is a local subprocess, because
what is under test is the transport, not the provider.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assemblyzero.core.llm_provider import (  # noqa: E402
    IDLE_TIMEOUT_SECONDS,
    _stream_with_idle_timeout,
)
from assemblyzero.workflows.testing.nodes.implementation.claude_client import (  # noqa: E402
    compute_dynamic_timeout,
)

#: The wall boostgauge #1 died against, four times, reading "timed out after 602s".
OLD_CEILING_SECONDS = 600

#: How long the synthetic call generates for. Comfortably past the old ceiling.
LONG_CALL_SECONDS = 660

_STREAMER = (
    "import sys, time\n"
    "deadline = time.monotonic() + float(sys.argv[1])\n"
    "i = 0\n"
    "while time.monotonic() < deadline:\n"
    "    print('{\"type\": \"stream_event\", \"i\": %d}' % i, flush=True)\n"
    "    i += 1\n"
    "    time.sleep(0.65)\n"  # the measured median gap from a real generation
    "print('{\"type\": \"result\", \"result\": \"generated\", \"usage\": {}}', flush=True)\n"
)

_SILENT = "import time, sys; time.sleep(float(sys.argv[1]))"


def _spawn(script: str, *args: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-u", "-c", script, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def _row(name: str, passed: bool, detail: str) -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print(f"        {detail}")
    return passed


def main() -> int:
    ceiling = compute_dynamic_timeout("x" * 2500)
    print()
    print(f"Effective ceiling for a 2.5 KB prompt : {ceiling}s")
    print(f"Idle threshold                        : {IDLE_TIMEOUT_SECONDS}s")
    print(f"The wall this replaces                : {OLD_CEILING_SECONDS}s")
    print()

    results = []

    # --- half one -----------------------------------------------------------
    print(f"[1/2] Streaming for {LONG_CALL_SECONDS}s, past the old {OLD_CEILING_SECONDS}s wall.")
    print("      Under the old transport this call died. It should now finish.")
    proc = _spawn(_STREAMER, str(LONG_CALL_SECONDS))
    started = time.monotonic()
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=IDLE_TIMEOUT_SECONDS, wall_timeout=ceiling
    )
    elapsed = time.monotonic() - started
    results.append(
        _row(
            "a call still generating past 600s completes",
            (not outcome.timed_out)
            and outcome.returncode == 0
            and elapsed > OLD_CEILING_SECONDS,
            f"ran {elapsed:.1f}s, {outcome.total_events} events, "
            f"rc={outcome.returncode}, timeout_kind={outcome.timeout_kind or 'none'}",
        )
    )

    # --- half two -----------------------------------------------------------
    idle = 10  # scaled so the proof does not take another two minutes
    print()
    print(f"[2/2] A call producing nothing, idle threshold {idle}s, backstop {ceiling}s.")
    print("      It must die at the threshold, not wait out the backstop.")
    proc = _spawn(_SILENT, str(ceiling + 120))
    started = time.monotonic()
    outcome = _stream_with_idle_timeout(
        proc, content="", idle_timeout=idle, wall_timeout=ceiling
    )
    elapsed = time.monotonic() - started
    results.append(
        _row(
            "a hung call is killed at the idle threshold",
            outcome.timed_out
            and outcome.timeout_kind == "idle"
            and elapsed < idle + 10,
            f"killed after {elapsed:.1f}s (threshold {idle}s), "
            f"silent {outcome.silent_seconds:.1f}s, kind={outcome.timeout_kind}",
        )
    )

    print()
    passed = all(results)
    print("RESULT:", "both halves pass" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
