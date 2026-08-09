"""The healing ledger: every self-heal leaves a record (#2164).

The factory heals itself in many places -- resets, redraws, base
replacements, the worktree sweep, the file janitor, storm backoffs,
restore reconciles -- and each heal used to be a transient line in an
events log. This module gives them a durable, structured record, the
self-heal counterpart of the prompt-failure telemetry (#2074).

One JSONL record per heal at ``data/speedrun/telemetry/heals.jsonl`` in
the TARGET repo. Partial outcomes are first-class: a half-completed heal
(today's WinError 5 lineage deletion) is exactly the record the report
exists to surface. Recording never raises -- a ledger problem must never
cost a roll -- and per standard 0027 the ledger is evidence, exempt from
every janitor.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HEALS_FILENAME = "heals.jsonl"

CATEGORIES = (
    "reset", "redraw", "base-replace", "sweep", "janitor",
    "storm-backoff", "restore-reconcile",
)

OUTCOMES = ("healed", "partial", "failed")


def heals_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / "data" / "speedrun" / "telemetry" / HEALS_FILENAME


def record_heal(
    repo_root: Path | str,
    category: str,
    target: str,
    outcome: str,
    *,
    detail: str = "",
    run_tag: str = "",
) -> bool:
    """Append one heal record. Returns False (never raises) on failure."""
    try:
        path = heals_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_tag": run_tag,
            "category": category,
            "target": target,
            "outcome": outcome,
            "detail": detail,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return True
    except Exception:  # noqa: BLE001 - the ledger must never cost a roll
        return False


def read_heals(repo_root: Path | str) -> list[dict]:
    """Every readable record, in order. Corrupt lines are skipped, counted
    by the caller via the length difference if it cares."""
    path = heals_path(repo_root)
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records
