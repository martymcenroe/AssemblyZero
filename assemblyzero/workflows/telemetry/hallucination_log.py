"""Structured hallucination-event log (#1812).

Records every invented-API detection the pipeline makes, so the Tiphys fix
(see #1688) lands against a live baseline instead of remembered incidents.
Before this module, the deterministic detector's findings lived only in
console output and in-run workflow state — the evidence died at process
exit, and only unstructured review prose survived.

Two sinks, both written per event:

- A per-invocation JSON file saved through the existing ``save_audit_file``
  mechanism into the run's ``audit_dir``, so it archives into lineage
  beside the verdicts — durable, tracked, travels with the issue.
- An append-only JSONL at ``data/telemetry/hallucination-log.jsonl`` under
  the AssemblyZero root — machine-local, gitignored, the one-grep query
  index.

A sink that was asked for and cannot be written is a failure (ADR 0236,
#3585): each one alerts the operator, both sinks are still attempted, and the
first failure is raised. It used to print a WARNING to stdout and go on, so the
baseline lost events with nothing said. A run with zero detections still
records events (``passed: true``) — absence of evidence must be
distinguishable from absence of instrumentation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assemblyzero.core import alert
from assemblyzero.workflows.requirements.audit import (
    next_file_number,
    save_audit_file,
)

# Suffix for the per-invocation audit file (numbered NNN- by save_audit_file).
AUDIT_SUFFIX = "hallucination-check.json"

# Cumulative query index, relative to the AssemblyZero root. Lives under
# data/ (gitignored, machine-local) by design — the durable copy is the
# audit_dir file that lineage archival carries. data-g/ is not a dependency
# here; #1598 remains open.
JSONL_RELATIVE_PATH = Path("data") / "telemetry" / "hallucination-log.jsonl"


def build_hallucination_event(
    *,
    repo: str,
    issue: int,
    artifact: str,
    iteration: int,
    symbols_checked: int,
    flagged: dict[str, list[str]],
    skipped: bool = False,
) -> dict[str, Any]:
    """Build one detector-invocation event. Pure — no I/O.

    Args:
        repo: Target repository root path (identifies the project).
        issue: GitHub issue number the run is working.
        artifact: What the detector scanned — ``"lld"`` or ``"spec_draft"``.
        iteration: The run's review iteration (0 = first pass).
        symbols_checked: Size of the real-symbol set compared against.
        flagged: Detector output — method name -> example call sites.
            Empty when nothing was flagged.
        skipped: True when the detector could not run (no gathered
            symbols). A skipped event is NOT a clean event — it records
            that no check happened, which is the distinction the whole
            instrument exists to preserve.

    Returns:
        The event dict, ready for either sink.
    """
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "issue": issue,
        "stage": "spec",
        "artifact": artifact,
        "iteration": iteration,
        "symbols_checked": symbols_checked,
        "flagged": flagged,
        "passed": not flagged,
        "skipped": skipped,
    }


def record_hallucination_event(
    event: dict[str, Any],
    audit_dir: Path | None,
    assemblyzero_root: Path | None,
) -> None:
    """Write one event to both sinks.

    A sink given as None is not part of this run and is skipped, quietly. A
    sink that was given and cannot be written -- an audit directory that does
    not exist, or a write that fails -- alerts the operator. Both sinks are
    always attempted; the first failure is then raised.

    Args:
        event: Event from :func:`build_hallucination_event`.
        audit_dir: The run's audit directory, or None to skip that sink.
        assemblyzero_root: AssemblyZero repo root anchoring the JSONL
            sink, or None to skip it.

    Raises:
        OSError: the first sink that could not be written (FileNotFoundError
            for an audit directory that does not exist).
    """
    failures: list[OSError] = []

    if audit_dir is not None:
        if not audit_dir.exists():
            missing = FileNotFoundError(f"audit directory {audit_dir} does not exist")
            _sink_failed(event, "audit sink", audit_dir, missing)
            failures.append(missing)
        else:
            try:
                file_num = next_file_number(audit_dir)
                save_audit_file(
                    audit_dir,
                    file_num,
                    AUDIT_SUFFIX,
                    json.dumps(event, indent=2) + "\n",
                )
            except OSError as e:
                _sink_failed(event, "audit sink", audit_dir, e)
                failures.append(e)

    if assemblyzero_root is not None:
        jsonl_path = assemblyzero_root / JSONL_RELATIVE_PATH
        try:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except OSError as e:
            _sink_failed(event, "JSONL sink", jsonl_path, e)
            failures.append(e)

    if failures:
        raise failures[0]


def _sink_failed(event: dict[str, Any], sink: str, where: Path, exc: OSError) -> None:
    issue = event.get("issue")
    alert.alert_operator(
        what=f"write the hallucination-event {sink}",
        where="assemblyzero/workflows/telemetry/hallucination_log.py record_hallucination_event",
        cause=f"{type(exc).__name__}: {exc} ({where})",
        consequence=(
            f"the {event.get('artifact', '')} hallucination check of iteration "
            f"{event.get('iteration', '')} is missing from the baseline; the "
            f"write is raised"
        ),
        repo=str(event.get("repo", "")),
        issue=issue if isinstance(issue, int) and issue else None,
    )
