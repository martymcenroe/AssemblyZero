"""Detect a degraded dev box before a roll spends anything (#1920).

2026-07-29, roughly 14:30-15:15 Central: the box degraded. pytest died
mid-suite, then stopped completing at all; local verification of a PR was
impossible and CI had to be declared the authoritative gate. By 20:30 it was
healthy again (bounds suite 22/22 in 0.93s). Cause unknown.

A roll launched onto a sick box wastes hours AND poisons the evidence, because
every failure then looks like a target-repo problem.

## Design decisions

**The canary runs a real test suite in a real subprocess.** What actually broke
on 2026-07-29 was pytest failing to complete, so an in-process arithmetic
workload would have sailed through the exact episode this exists to catch. The
canary spends a subprocess spawn deliberately.

**Unknown is not healthy.** A metric that cannot be read aborts the roll. An
unreadable box is precisely the case this gate exists for, and treating a failed
read as a pass would make the gate silently absent exactly when the machine is
sickest.

**A missing baseline never blocks.** The first healthy run records a nominal and
proceeds. A gate that refuses to run until someone hand-seeds a number would be
removed within a week.

**Nominal is a rolling median, not the last value or the best value.** One lucky
run must not tighten the threshold onto a machine that cannot meet it again, and
one slow run must not loosen it forever. The median over a small window tracks
the machine.

**psutil is read directly here.** An earlier phrasing of this work said to
dogfood the boostgauge collector; that is not buildable today -- the collector
exists only on integration branches, is absent from boostgauge main, and is not
installed in this environment. Swapping to it is follow-up work for after
boostgauge ships as an installable package.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

#: A hung canary must abort rather than hang the launcher, whatever the nominal.
CANARY_CEILING_SECONDS = 120

#: "This is a fault, not patience" -- the same multiplier used by the other
#: watchdogs in this pipeline.
CANARY_MULTIPLIER = 3

MEMORY_ABORT_PERCENT = 90.0
ROLLING_WINDOW = 5
HEALTH_FILENAME = "box-health.json"

DEFAULT_CANARY = (
    "tests/canary/test_box_canary.py",
)


@dataclass
class Metric:
    name: str            # plain English, shown to the operator
    value: float | None
    nominal: float | None = None
    unit: str = ""
    ok: bool = True
    detail: str = ""


@dataclass
class BoxHealth:
    ok: bool
    metrics: list[Metric] = field(default_factory=list)
    message: str = ""

    @property
    def failures(self) -> list[Metric]:
        return [m for m in self.metrics if not m.ok]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def health_file(log_dir: Path | str) -> Path:
    return Path(log_dir) / HEALTH_FILENAME


def read_samples(log_dir: Path | str) -> list[float]:
    path = health_file(log_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    samples = data.get("canary_seconds") or []
    return [float(s) for s in samples if isinstance(s, (int, float))]


def nominal_from(samples: list[float]) -> float | None:
    return statistics.median(samples) if samples else None


def record_sample(log_dir: Path | str, seconds: float) -> float:
    """Append a passing canary time and return the refreshed nominal."""
    samples = (read_samples(log_dir) + [float(seconds)])[-ROLLING_WINDOW:]
    path = health_file(log_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"canary_seconds": samples, "nominal_seconds": nominal_from(samples)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return nominal_from(samples)


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def run_canary(
    az_root: Path | str,
    *,
    targets: tuple[str, ...] = DEFAULT_CANARY,
    ceiling: int = CANARY_CEILING_SECONDS,
) -> tuple[float | None, str]:
    """Time a micro test suite. Returns (seconds, problem).

    `seconds` is None when the canary could not be timed at all; `problem` then
    says why in plain English. A canary that exceeds the ceiling is reported as
    a timeout rather than being waited on.
    """
    cmd = [sys.executable, "-m", "pytest", *targets, "-q", "--no-header", "-p", "no:randomly"]
    started = time.monotonic()
    try:
        result = subprocess.run(
            cmd, cwd=str(az_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=ceiling,
        )
    except subprocess.TimeoutExpired:
        return None, (
            f"the quick self-check did not finish within {ceiling} seconds"
        )
    except OSError as exc:
        return None, f"the quick self-check could not be started ({exc})"

    elapsed = time.monotonic() - started
    if result.returncode != 0:
        return None, (
            "the quick self-check did not pass, so this machine cannot be "
            "trusted to judge a real run"
        )
    return elapsed, ""


def snapshot_resources() -> tuple[dict[str, float], list[str]]:
    """(metrics, unreadable metric names). Never raises."""
    metrics: dict[str, float] = {}
    unreadable: list[str] = []

    try:
        import psutil
    except ImportError:
        return {}, ["memory in use", "running programs", "console windows"]

    try:
        metrics["memory in use"] = float(psutil.virtual_memory().percent)
    except Exception:  # noqa: BLE001 - any read failure is "unreadable"
        unreadable.append("memory in use")

    try:
        names = [p.info.get("name") or "" for p in psutil.process_iter(["name"])]
    except Exception:  # noqa: BLE001
        unreadable.extend(["running programs", "console windows"])
        return metrics, unreadable

    metrics["running programs"] = float(len(names))
    console = {"conhost.exe", "openconsole.exe"}
    metrics["console windows"] = float(
        sum(1 for n in names if n.lower() in console)
    )
    return metrics, unreadable


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def _format_message(failures: list[Metric]) -> str:
    lines = ["BLOCKED: this machine is not healthy enough to run right now.", ""]
    for metric in failures:
        if metric.value is None:
            lines.append(f"  {metric.name}: {metric.detail}")
        elif metric.nominal is not None:
            lines.append(
                f"  {metric.name}: {metric.value:.1f}{metric.unit} measured, "
                f"against a normal of {metric.nominal:.1f}{metric.unit}"
            )
        else:
            lines.append(f"  {metric.name}: {metric.value:.1f}{metric.unit} — {metric.detail}")
    lines += [
        "",
        "  A run started on a machine in this state wastes hours and, worse, makes",
        "  every failure look like a problem with the code being built. Wait for the",
        "  machine to recover, or find out what is loading it, then start again.",
    ]
    return "\n".join(lines)


def check_box_health(
    az_root: Path | str,
    log_dir: Path | str,
    *,
    canary=run_canary,
    resources=snapshot_resources,
    memory_limit: float = MEMORY_ABORT_PERCENT,
    multiplier: int = CANARY_MULTIPLIER,
    ceiling: int = CANARY_CEILING_SECONDS,
) -> BoxHealth:
    """Judge the machine before anything is spent. Never raises."""
    metrics: list[Metric] = []

    # Resources first: they are cheap, so a box already out of memory is refused
    # without first spending a canary run on it.
    values, unreadable = resources()
    for name in unreadable:
        metrics.append(
            Metric(name, None, ok=False, detail="could not be read on this machine")
        )

    memory = values.get("memory in use")
    if memory is not None:
        metrics.append(
            Metric(
                "memory in use", memory, nominal=memory_limit, unit="%",
                ok=memory <= memory_limit,
                detail=f"above the {memory_limit:.0f}% ceiling",
            )
        )
    for name in ("running programs", "console windows"):
        if name in values:
            metrics.append(Metric(name, values[name]))

    if any(not m.ok for m in metrics):
        return BoxHealth(False, metrics, _format_message([m for m in metrics if not m.ok]))

    seconds, problem = canary(az_root, ceiling=ceiling)
    samples = read_samples(log_dir)
    nominal = nominal_from(samples)

    if seconds is None:
        metrics.append(Metric("quick self-check", None, ok=False, detail=problem))
        return BoxHealth(False, metrics, _format_message([metrics[-1]]))

    if nominal is not None and seconds > multiplier * nominal:
        metrics.append(
            Metric(
                "quick self-check", seconds, nominal=nominal, unit="s", ok=False,
                detail=f"more than {multiplier} times its normal time",
            )
        )
        return BoxHealth(False, metrics, _format_message([metrics[-1]]))

    # Passing: record the sample so the nominal tracks the machine. A missing
    # baseline is created here and never blocks.
    refreshed = record_sample(log_dir, seconds)
    metrics.append(Metric("quick self-check", seconds, nominal=refreshed, unit="s"))
    return BoxHealth(True, metrics, "")
