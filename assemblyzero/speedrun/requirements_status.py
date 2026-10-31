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
per standard 0027.

A ledger that cannot be written or read is the very misreading this module
exists to prevent: the UNVERIFIED banner never prints, and an unchecked roll
looks clean. So both are failures under ADR 0236: each alerts the operator with
the path and the cause, and raises (#3585). An absent ledger is the one quiet
answer, because it means no run has proceeded without a verdict.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from assemblyzero.core import alert

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

    Returns True once the record is on disk. A record that cannot be written
    alerts the operator and raises the cause: the banner would otherwise never
    print, and the roll would read as one whose requirements were checked.
    """
    path = unverified_path(repo_root)
    try:
        line = json.dumps({
            "ts": ts or datetime.now().strftime(_TS_FMT),
            "issue": int(issue) if issue else None,
            "reason": reason or "",
            "run_id": run_id or "",
        }) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except (OSError, ValueError) as exc:
        alert.alert_operator(
            what="write the requirements-unverified record",
            where="assemblyzero/speedrun/requirements_status.py record_unverified",
            cause=f"{type(exc).__name__}: {exc} (ledger {path})",
            consequence=(
                "the REQUIREMENTS UNVERIFIED banner cannot print for this run, "
                "so the record is raised and the run stops rather than reading "
                "as a verified roll"
            ),
            repo=str(repo_root),
            issue=issue if isinstance(issue, int) and issue else None,
        )
        raise
    return True


def _corrupt(path: Path, lineno: int, problem: str) -> ValueError:
    """Alert on one unreadable ledger line and return the error to raise."""
    message = f"{path}:{lineno}: {problem}"
    alert.alert_operator(
        what="read the requirements-unverified ledger",
        where="assemblyzero/speedrun/requirements_status.py read_unverified",
        cause=message,
        consequence=(
            "the ledger cannot say which runs proceeded without a requirements "
            "verdict, so no UNVERIFIED banner can be trusted until the line is "
            "repaired"
        ),
    )
    return ValueError(message)


def read_unverified(repo_root: Path | str, since: str = "") -> list[dict]:
    """Every record, or only those at/after `since` (a "%Y-%m-%d %H:%M:%S" stamp).

    An absent ledger returns ``[]``: no run has proceeded without a verdict. A
    line that is not JSON, or is JSON but not an object, alerts the operator and
    raises ``ValueError`` naming the file and line: a skipped line could be the
    one marker that says this roll was never checked.

    The `since` comparison is lexicographic, which is exact for this fixed-width
    format and avoids a parse that could raise inside a reporting path.
    """
    path = unverified_path(repo_root)
    if not path.exists():
        return []
    out: list[dict] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise _corrupt(path, lineno, f"not JSON ({exc})") from exc
        if not isinstance(record, dict):
            raise _corrupt(path, lineno, "not a JSON object")
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
