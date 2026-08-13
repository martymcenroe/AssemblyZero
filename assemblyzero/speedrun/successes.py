"""The success ledger: what this arc has already finished (#2191).

The 2026-08-10 overnight batch rolled `--issue 1 --issue 4 --issue 7`. Issue #4
completed end to end -- rc=0, its LLD PR and implementation PR both merged into
`hardening-run-17`, the campaign's first fully successful roll on these issues.
The operator's next launch command, by habit, again included `--issue 4`, and
nothing in the machinery would have objected: the launcher would have reset #4's
branches and redrawn an issue whose implementation was already merged into the
arc. An agent reading the log caught it, not the launcher.

Operator ruling: redrawing something that already succeeded must require
explicit, deliberate confirmation.

## Arc scoping is the load-bearing part

An entry records the base branch it succeeded on. Success on `hardening-run-17`
must not nag a deliberate wipe-and-re-run campaign on a future arc -- a new base
branch starts with an empty slate, and a gate that fires there would be exactly
the kind of false alarm operators learn to wave through. The guard fires only
when the same arc would redo its own finished work.

## This is a cache, not the record of truth

`EXIT rc=0` in the per-roll events log is the authoritative local outcome, and
the merged PRs on the arc are the record that survives a wiped machine. This
file is a queryable cache of the first, written where the launcher can read it
in the second before anything is spent. A missing or unreadable ledger therefore
degrades to "no opinion" -- it must never refuse a launch on its own absence.

Lives under ``data/speedrun/``, already structurally exempt from dirt
classification and every janitor (standard 0027).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

SUCCESSES_REL = Path("data") / "speedrun" / "successes.json"

_TS_FMT = "%Y-%m-%d %H:%M:%S"


def successes_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / SUCCESSES_REL


def read_successes(repo_root: Path | str) -> list[dict]:
    """Every recorded success, oldest first. Never raises.

    A malformed or absent ledger reads as empty: this gate exists to stop a
    redraw, and refusing a launch because a cache could not be parsed would
    make the cache load-bearing in the one direction it must never be.
    """
    try:
        raw = successes_path(repo_root).read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict) and e.get("issue") is not None]


def record_success(
    repo_root: Path | str,
    *,
    issue: int,
    base_branch: str,
    run_tag: str = "",
    prs: list[str] | None = None,
    ts: str | None = None,
) -> bool:
    """Append one rc=0 outcome. Returns False (never raises) on failure.

    The roll has already succeeded by the time this is called; a ledger problem
    must not turn that into a failure.
    """
    if not issue or not base_branch:
        # An entry with no arc cannot be scoped, and an unscoped entry would
        # fire the gate on every future arc. Better to record nothing.
        return False
    try:
        entries = read_successes(repo_root)
        entries.append({
            "issue": int(issue),
            "base_branch": base_branch,
            "run_tag": run_tag or "",
            "ts": ts or datetime.now().strftime(_TS_FMT),
            "prs": list(prs or []),
        })
        path = successes_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(entries, indent=2) + "\n", encoding="utf-8"
        )
        return True
    except (OSError, TypeError, ValueError):
        return False


def completed_on(
    repo_root: Path | str, issue: int, base_branch: str
) -> dict | None:
    """The most recent success for this issue ON THIS ARC, or None.

    Most recent rather than first: if an issue somehow succeeded twice on one
    arc, the evidence the operator needs is the latest.
    """
    if not base_branch:
        return None
    matches = [
        e for e in read_successes(repo_root)
        if e.get("issue") == issue and e.get("base_branch") == base_branch
    ]
    return matches[-1] if matches else None


def describe(entry: dict) -> str:
    """The evidence line, naming what makes this a refusal rather than a guess."""
    prs = ", ".join(str(p) for p in entry.get("prs") or []) or "none recorded"
    return (
        f"#{entry.get('issue')} already rolled to success on "
        f"'{entry.get('base_branch')}' at {entry.get('ts')} "
        f"(run {entry.get('run_tag') or 'unrecorded'}; merged PRs: {prs})"
    )


def redraw_phrase(issue: int) -> str:
    """The typed confirmation, per the standard 0017 Danger-Zone convention.

    A phrase, never y/n: a single keypress is exactly what an auto-answering
    wrapper blows through, which is why the banned-menu rule exists.
    """
    return f"REDRAW {issue}"
