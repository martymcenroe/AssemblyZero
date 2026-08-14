"""The record of what the pipeline preserved, so the archiver can find it (#2355).

Measured 2026-08-14, archiving hardening-run-17: the campaign held **64**
graveyard branches, the entire evidence record the preserve-not-delete
discipline had built all week, and the archiver's dry run reported
``graveyard 0``.

The bundle rule matched ``graveyard/<run>*``. The pipeline names its preserved
branches ``graveyard/issue-7-<stamp>``, ``graveyard/7-lld-<stamp>`` and
``graveyard/leavings-<stamp>``, and not one of them carries the run prefix. An
archive built by the default rule bundled zero evidence branches and still
reported ``complete: true``: the box labelled full, holding the logs and none
of the branch record.

The workaround that day was sixty-four explicit ``--branch`` flags. It worked
and it does not survive the next operator who trusts the default.

Why a record rather than a better prefix
----------------------------------------

A naming convention is a claim about what some other code does. It was wrong
here, silently, for a week, and the next namespace the preserve step invents
would break it again the same way. So the branches the pipeline preserves are
WRITTEN DOWN as it preserves them, and the archiver reads the record. The
bundle set becomes a recorded fact.

The ledger is append-only JSONL under the target repo's gitignored
``data/speedrun/runs/``, one object per preserved branch, next to the run logs
the archiver already reads.

Recording never fails a caller
------------------------------

Every writer here is in the middle of preserving someone's work. A ledger that
could raise would turn a bookkeeping problem into lost evidence, which is the
exact inversion of what it exists to prevent. `record_preserved` swallows its
own errors and says so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LEDGER_NAME = "preserved-branches.jsonl"

_TS_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Preserved:
    """One branch the pipeline preserved, and what it knows about it."""

    branch: str
    run: str = ""
    source: str = ""
    detail: str = ""
    at: str = ""


def ledger_path(repo: Path | str) -> Path:
    """Where the record lives, beside the run logs the archiver already reads."""
    return Path(repo) / "data" / "speedrun" / "runs" / LEDGER_NAME


def record_preserved(
    repo: Path | str,
    branch: str,
    *,
    run: str = "",
    source: str = "",
    detail: str = "",
) -> bool:
    """Append one preserved branch to the ledger. Never raises.

    Returns whether the record landed, so a caller that wants to say so can,
    and a caller in the middle of saving work can ignore it.
    """
    if not branch:
        return False

    record = {
        "branch": branch,
        "run": run,
        "source": source,
        "detail": detail,
        "at": datetime.now().strftime(_TS_FMT),
    }
    try:
        path = ledger_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return True
    except OSError:
        return False


def read_ledger(repo: Path | str) -> list[Preserved]:
    """Every recorded preservation, oldest first. A bad line is skipped.

    One malformed line must not hide the other sixty-three. The archiver's
    discovery pass covers whatever a skipped line would have named, so a
    partial read degrades to the pre-ledger behaviour rather than to nothing.
    """
    path = ledger_path(repo)
    if not path.is_file():
        return []

    records: list[Preserved] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        branch = data.get("branch")
        if not isinstance(branch, str) or not branch:
            continue
        records.append(
            Preserved(
                branch=branch,
                run=str(data.get("run") or ""),
                source=str(data.get("source") or ""),
                detail=str(data.get("detail") or ""),
                at=str(data.get("at") or ""),
            )
        )
    return records


def claimed_by_other_run(repo: Path | str, run: str) -> set[str]:
    """Branches the ledger attributes to a DIFFERENT run.

    Everything else is fair game for this run's archive. Over-inclusion costs
    disk in a tool that only ever writes; under-inclusion costs the evidence
    record, which is what #2355 is about. Only a positive attribution to
    another run excludes a branch.
    """
    return {
        record.branch
        for record in read_ledger(repo)
        if record.run and record.run != run
    }


def recorded_for(repo: Path | str, run: str) -> set[str]:
    """Branches the ledger attributes to this run, or to no run at all."""
    return {
        record.branch
        for record in read_ledger(repo)
        if not record.run or record.run == run
    }
