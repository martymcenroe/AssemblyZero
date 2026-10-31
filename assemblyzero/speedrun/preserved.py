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

A lost record is a failure (ADR 0236, #3585)
--------------------------------------------

`record_preserved` used to swallow its own errors and return False, which both
writers ignored, so a branch could be preserved and never reach the archive's
record. It now raises naming the ledger. Both writers (the worktree sweep and
the file janitor) catch it after the branch already holds the work, alert the
operator, and report the entry as failed, so no evidence is lost to the raise.
`read_ledger` alerts and raises on a ledger it cannot read and on a line that
is not a record, rather than hand the archiver a shorter list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from assemblyzero.core import alert

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
    """Append one preserved branch to the ledger. True once it is on disk.

    A line that cannot be written raises `OSError` naming the ledger, and an
    empty branch raises `ValueError`: there is nothing to record. Each caller
    has already put the work on the branch, so it alerts the operator and
    reports a failed entry; the raise never costs the preserved content.
    """
    if not branch:
        raise ValueError("record_preserved needs a branch name; got an empty one")

    record = {
        "branch": branch,
        "run": run,
        "source": source,
        "detail": detail,
        "at": datetime.now().strftime(_TS_FMT),
    }
    path = ledger_path(repo)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except (OSError, ValueError) as exc:
        raise OSError(
            f"cannot append {branch} to the preserved-branch ledger {path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    return True


def _unreadable(path: Path, cause: str) -> None:
    alert.alert_operator(
        what="read the preserved-branch ledger",
        where="assemblyzero/speedrun/preserved.py read_ledger",
        cause=cause,
        consequence=(
            "the branches it records cannot be attributed, so the archive or "
            "report reading it stops rather than bundle a shorter list"
        ),
        repo=str(path.parents[3]),
    )


def _bad_line(path: Path, lineno: int, why: str) -> ValueError:
    """Alert about one ledger line that is not a record; the error to raise."""
    cause = f"{path}:{lineno} {why}"
    _unreadable(path, cause)
    return ValueError(f"the preserved-branch ledger line {cause}")


def read_ledger(repo: Path | str) -> list[Preserved]:
    """Every recorded preservation, oldest first.

    An absent ledger is the legitimate answer "nothing recorded yet" and
    returns ``[]``. A ledger that exists but cannot be read, or a line that is
    not a JSON object naming a branch, alerts the operator and raises: the
    archiver would otherwise bundle a shorter list and could not say which
    branch it lost the attribution of.
    """
    path = ledger_path(repo)
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        _unreadable(path, f"{type(exc).__name__}: {exc} ({path})")
        raise

    records: list[Preserved] = []
    for lineno, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError as exc:
            raise _bad_line(path, lineno, f"is not JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise _bad_line(path, lineno, "is not a JSON object")
        branch = data.get("branch")
        if not isinstance(branch, str) or not branch:
            raise _bad_line(path, lineno, f"names no branch: {branch!r}")
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
