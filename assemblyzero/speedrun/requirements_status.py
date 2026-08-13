"""Whether the requirements gate actually ran, recorded where the roll can see it (#2290).

The requirements-consistency gate fails open by design: a provider storm must not
brick a launch (#1899). That policy is right and is unchanged here. What was wrong
is that failing open was *silent* -- it printed one warning line mid-run and the
roll then reported exactly like a roll whose requirements had been checked and
found clean. Those are materially different outcomes and looked identical from
the outside.

Measured on boostgauge #7, 2026-08-12/13: the same call timed out at 300s on one
attempt and returned a real CONFLICT verdict in 294s on the next. Inside a roll,
the first outcome would have carried the issue past a conflict the gate
demonstrably finds -- and the operator would have read "ROLL SUCCEEDED".

This module is the crossing point. The gate runs inside the LLD sub-workflow,
which the launcher spawns as a child process, so a state flag cannot reach the
verdict block. A small append-only ledger can, and it is the same shape the
launcher already reads for filed questions and heals.

Lives under ``data/speedrun/telemetry/``, structurally exempt from every janitor
per standard 0027. Recording never raises: a ledger problem must never cost a
roll, and least of all this one -- the record exists precisely because the run is
already degraded.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

UNVERIFIED_FILENAME = "requirements-unverified.jsonl"

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def unverified_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / "data" / "speedrun" / "telemetry" / UNVERIFIED_FILENAME


def record_unverified(
    repo_root: Path | str,
    *,
    issue: int | None,
    reason: str,
    run_id: str = "",
    ts: str | None = None,
) -> bool:
    """Record that a run proceeded WITHOUT a requirements verdict.

    `reason` is the operator-facing explanation, not a stack trace: it is
    printed verbatim under the banner, so it must say what did not happen.
    """
    try:
        path = unverified_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": ts or datetime.now().strftime(_TS_FMT),
                "issue": int(issue) if issue else None,
                "reason": reason or "",
                "run_id": run_id or "",
            }) + "\n")
        return True
    except (OSError, ValueError):
        return False


def read_unverified(repo_root: Path | str, since: str = "") -> list[dict]:
    """Every record, or only those at/after `since` (a "%Y-%m-%d %H:%M:%S" stamp).

    Corrupt lines are skipped rather than fatal, for the same reason the heal
    ledger skips them: one bad line must cost one entry, not the file.

    The `since` comparison is lexicographic, which is exact for this fixed-width
    format and avoids a parse that could raise inside a reporting path.
    """
    path = unverified_path(repo_root)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if since and str(record.get("ts", "")) < since:
            continue
        out.append(record)
    return out


def format_banner(records: list[dict]) -> list[str]:
    """The operator-facing banner, as lines. Empty list when nothing to say.

    Deliberately loud and deliberately first-person about what was NOT done.
    "Requirements were not checked on this run" is the sentence that has to
    survive being skimmed at 3am.
    """
    if not records:
        return []
    lines = [
        "",
        "  !! REQUIREMENTS UNVERIFIED -- the consistency gate did not return a "
        "verdict.",
        "     The run proceeded anyway (the gate fails open so a provider storm "
        "cannot brick a launch),",
        "     so this is NOT the same as a clean requirements check. Nothing "
        "about the issue text was verified.",
    ]
    for r in records:
        issue = f"#{r['issue']}" if r.get("issue") else "(issue unknown)"
        lines.append(f"       - {issue}: {r.get('reason', '') or 'no reason recorded'}")
    lines.append(
        "     Next step: re-run `tools/check_requirements.py --repo <repo> "
        "--issue <N>` before trusting this roll."
    )
    return lines
