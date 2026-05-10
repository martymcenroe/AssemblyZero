"""Speed-run instrumentation for the boostgauge YouTube demo (#1076).

Three concerns in one module:

1. **Lap splits.** A `LapSplitWriter` emits timestamped beats during a
   workflow run to `data/speedrun/{issue}-{attempt}.json`. Beats are
   recorded as wall-clock elapsed seconds since `started_at`. Hooked
   from the entry-point scripts (`tools/run_requirements_workflow.py`,
   `tools/run_implement_from_lld.py`); finer-grained per-node beats
   are deferred to follow-ups so this PR doesn't touch every node.

2. **Failure-mode classifier.** `classify_halt(state, error_message)`
   inspects the workflow state at HALT and returns one of eight labels
   (gemini-503, gemini-quota, stagnation, mech-validation-loop,
   test-plan-blocked, completeness-gate-failed, coverage-target-missed,
   unknown). Used by the run logger to track which improvements help.

3. **Run log.** `RunLogger.complete_run(...)` appends one JSONL entry
   per attempt to `data/speedrun/run-log.jsonl`. The companion CLI
   `tools/speedrun_summarize.py` aggregates this into a human-readable
   table for cross-attempt review.

The module is OPT-IN: workflows that don't pass `--speedrun` (or the
equivalent state field) skip all of this. Existing operators who never
run the speed-run see no change.

Design notes:

- Files are written immediately on each beat — robust to crashes, no
  buffer to flush. `data/speedrun/{issue}-{attempt}.json` is rewritten
  in full each time (idempotent; small files).
- `RunLogger` appends only — never rewrites. The log is the durable
  cross-attempt record. Crash safety: `tail -1` always shows the
  current run state.
- `classify_halt` is pure (no side effects) so tests can trivially
  inject state dicts.
- Wall-clock uses `time.time()` (UTC seconds since epoch). All beats
  are deltas from `started_at`, so timezone is irrelevant.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lap splits
# ---------------------------------------------------------------------------


@dataclass
class LapSplitWriter:
    """Appends timestamped beats to data/speedrun/{issue}-{attempt}.json.

    Lifetime spans one workflow attempt. Construct at workflow start with
    `LapSplitWriter.start(...)`, call `.beat(name)` at known points, then
    `.finalize(outcome=...)` at end.

    Attributes:
        issue: GitHub issue number being worked.
        attempt: Sequential attempt number for this issue (1, 2, ...).
        started_at: Wall-clock time of run start (UTC seconds since epoch).
        output_path: Where the JSON file is written.
        splits: List of {beat, t} dicts; t is seconds since started_at.
    """
    issue: int
    attempt: int
    started_at: float
    output_path: Path
    splits: list[dict[str, Any]] = field(default_factory=list)
    started_at_iso: str = ""

    @classmethod
    def start(
        cls,
        repo_root: Path,
        issue: int,
        attempt: Optional[int] = None,
    ) -> "LapSplitWriter":
        """Create a writer for issue+attempt; write initial state.

        If attempt is None, auto-increments from existing files for the
        same issue.
        """
        speedrun_dir = repo_root / "data" / "speedrun"
        speedrun_dir.mkdir(parents=True, exist_ok=True)
        if attempt is None:
            attempt = _next_attempt_number(speedrun_dir, issue)
        started_at = time.time()
        # ISO-format started_at separately so consumers don't have to
        # do epoch math just to display the run timestamp.
        started_at_iso = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at),
        )
        writer = cls(
            issue=issue,
            attempt=attempt,
            started_at=started_at,
            output_path=speedrun_dir / f"{issue}-{attempt}.json",
            started_at_iso=started_at_iso,
        )
        writer._write()
        return writer

    def beat(self, name: str) -> None:
        """Record a beat at the current wall-clock time."""
        elapsed = round(time.time() - self.started_at, 2)
        self.splits.append({"beat": name, "t": elapsed})
        self._write()

    def finalize(self, outcome: str, failure_mode: Optional[str] = None) -> None:
        """Write the terminal beat with outcome metadata.

        Outcome is one of "success", "fail", "halt". `failure_mode` is
        the classifier label from `classify_halt()` when outcome is
        "fail" or "halt".
        """
        elapsed = round(time.time() - self.started_at, 2)
        self.splits.append({
            "beat": f"completed_{outcome}",
            "t": elapsed,
            **({"failure_mode": failure_mode} if failure_mode else {}),
        })
        self._write()

    def _write(self) -> None:
        """Rewrite the JSON file with current state."""
        payload = {
            "issue": self.issue,
            "attempt": self.attempt,
            "started_at": self.started_at_iso,
            "splits": self.splits,
        }
        try:
            self.output_path.write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Failed to write lap splits: %s", e)


def _next_attempt_number(speedrun_dir: Path, issue: int) -> int:
    """Find the next sequential attempt for this issue.

    Scans `{issue}-*.json` files in speedrun_dir and returns max+1.
    Returns 1 if no prior attempts exist.
    """
    if not speedrun_dir.exists():
        return 1
    max_attempt = 0
    for f in speedrun_dir.glob(f"{issue}-*.json"):
        # Extract the attempt number from the filename stem.
        # Format: {issue}-{attempt}.json
        stem = f.stem
        parts = stem.rsplit("-", 1)
        if len(parts) != 2:
            continue
        try:
            n = int(parts[1])
            if n > max_attempt:
                max_attempt = n
        except ValueError:
            continue
    return max_attempt + 1


# ---------------------------------------------------------------------------
# Failure-mode classifier
# ---------------------------------------------------------------------------


# Eight known halt classifications. `unknown` is the fallback.
HALT_CLASSIFICATIONS = (
    "gemini-503",
    "gemini-quota",
    "stagnation",
    "mech-validation-loop",
    "test-plan-blocked",
    "completeness-gate-failed",
    "coverage-target-missed",
    "unknown",
)


def classify_halt(
    state: dict[str, Any],
    error_message: str = "",
) -> str:
    """Return a label naming the cause of a workflow halt.

    Pure function — no side effects. Inspects state fields and the
    error message string to match against known patterns. The classifier
    is intentionally generous on string matching: speed-run telemetry
    is more useful when a halt is at least categorized than when an
    unknown bucket dominates.

    Args:
        state: Workflow state dict at the moment of halt.
        error_message: Optional explicit error string to scan.

    Returns:
        One of HALT_CLASSIFICATIONS.
    """
    msg = (error_message or state.get("error_message", "") or "").lower()

    # Explicit state signals first — most reliable.
    if state.get("test_plan_status") == "BLOCKED":
        return "test-plan-blocked"

    if state.get("validation_iteration_count", 0) >= state.get("max_iterations", 20):
        # If mechanical validation looped to its limit, that's the cause.
        # Use validation_errors as a secondary signal.
        if state.get("validation_errors"):
            return "mech-validation-loop"

    if state.get("completeness_iteration_count", 0) >= state.get(
        "max_completeness_iterations", 3
    ):
        if state.get("completeness_errors") or "completeness" in msg:
            return "completeness-gate-failed"

    coverage_pct = state.get("coverage_percentage")
    coverage_target = state.get("coverage_target")
    if (
        coverage_pct is not None
        and coverage_target is not None
        and coverage_pct < coverage_target
    ):
        return "coverage-target-missed"

    # Stagnation: two consecutive REVISE verdicts, similar bodies. The
    # workflow code already detects this and sets a flag; we mirror it.
    if state.get("stagnation_detected") or "two-strike stagnation" in msg:
        return "stagnation"

    # Provider-specific transient signals from the error message.
    if "503" in msg or "service unavailable" in msg or "overloaded" in msg:
        return "gemini-503"
    if (
        "quota" in msg
        or "resource_exhausted" in msg
        or "rate limit" in msg
        or "429" in msg
    ):
        return "gemini-quota"

    return "unknown"


# ---------------------------------------------------------------------------
# Run log
# ---------------------------------------------------------------------------


@dataclass
class RunLogger:
    """Appends one JSONL entry per attempt to data/speedrun/run-log.jsonl.

    Use as a context-friendly accessor:

        logger = RunLogger(repo_root)
        ...
        logger.complete_run(
            issue=35, attempt=7, started_at_iso="...", outcome="success",
            failure_mode=None, total_seconds=542.0,
        )
    """
    repo_root: Path

    @property
    def log_path(self) -> Path:
        return self.repo_root / "data" / "speedrun" / "run-log.jsonl"

    def complete_run(
        self,
        issue: int,
        attempt: int,
        started_at_iso: str,
        outcome: str,
        total_seconds: float,
        failure_mode: Optional[str] = None,
        notes: str = "",
    ) -> None:
        """Append one run entry to the log.

        Idempotency: this function does NOT deduplicate. Calling it
        twice for the same (issue, attempt) results in two entries.
        Callers should ensure single-call discipline.
        """
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = {
            "attempt": attempt,
            "issue": issue,
            "started_at": started_at_iso,
            "ended_at": ended_at,
            "outcome": outcome,
            "failure_mode": failure_mode,
            "total_seconds": round(total_seconds, 2),
            "notes": notes,
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            logger.warning("Failed to append run-log entry: %s", e)

    def read_all(self) -> list[dict[str, Any]]:
        """Read all entries from the log. Returns [] if log doesn't exist."""
        if not self.log_path.exists():
            return []
        entries = []
        with self.log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("Skipping malformed run-log line: %s", e)
        return entries
