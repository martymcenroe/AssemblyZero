"""Fingerprint and count every drafter validation failure (#2074).

Operator observation 2026-08-01: a drafter emitted a malformed Section 2.1
table (`run-issue2-133746`, lld failed 86.1s, "MECHANICAL VALIDATION FAILED:
Section 2.1 table malformed"). Nothing counted it. Each failure printed to a run
log, the retry re-rolled, and the failure mode evaporated -- while the prompts
that produce the failure rate stayed static.

The raw material already existed: lineage dirs keep every numbered draft,
rejected test-plan drafts are preserved to the audit dir, and the workflow-audit
JSONL is already written. What was missing is classification and aggregation.

## The fingerprint is a contract

`<stage>:<check>:<normalized-detail>`, where normalization lowercases, collapses
every run of non-alphanumeric characters to a single hyphen, and strips leading
and trailing hyphens. The 2026-08-01 example becomes:

    lld:mechanical:section-2-1-table-malformed

It is specified here rather than left to the implementation because #2075
consumes it. Changing the normalization silently re-buckets every historical
record, so the round-trip is guarded by tests rather than by convention.

## No deduplication at write time

Every occurrence is a record. Aggregation is the report's job. Collapsing at
write time destroys the rate this exists to measure -- and the rate is the whole
point, because "this failed twice today" and "this failed forty times today" are
different problems with the same fingerprint.

## Writing telemetry never changes a roll's outcome

A failure to append is logged loudly and swallowed. Telemetry that can break the
thing it measures is worse than no telemetry.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

TELEMETRY_REL = Path("data/speedrun/telemetry")
FAILURES_FILENAME = "prompt-failures.jsonl"

_TS_FMT = "%Y-%m-%d %H:%M:%S"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

#: Markers the pipeline prefixes onto validation messages. Stripped before
#: normalization so the fingerprint names the DEFECT, not the announcement --
#: otherwise every mechanical failure would share one fingerprint.
_MARKERS = (
    "MECHANICAL VALIDATION FAILED:",
    "REQUIREMENTS CONFLICT:",
    "TEST PLAN VALIDATION FAILED:",
    "VALIDATION FAILED:",
)


def normalize_detail(detail: str) -> str:
    """Lowercase, non-alphanumeric runs to single hyphens, ends stripped."""
    text = (detail or "").strip()
    for marker in _MARKERS:
        if text.upper().startswith(marker):
            text = text[len(marker):]
            break
    return _NON_ALNUM.sub("-", text.lower()).strip("-")


def fingerprint(stage: str, check: str, detail: str) -> str:
    """`<stage>:<check>:<normalized-detail>` -- the contract #2075 reads."""
    return f"{normalize_detail(stage)}:{normalize_detail(check)}:{normalize_detail(detail)}"


#: A fingerprint that never repeats cannot be ranked, and ranking is the whole
#: point. Mechanical details are short by nature ("Section 2.1 table
#: malformed"); a reviewer's rationale is paragraphs, and normalizing all of it
#: buckets every run separately. #2198 takes the first line, bounded.
FINGERPRINT_DETAIL_CHARS = 160


def rankable_detail(text: str, limit: int = FINGERPRINT_DETAIL_CHARS) -> str:
    """The first line of a prose finding, bounded, for use as a detail."""
    for line in (text or "").strip().splitlines():
        stripped = line.strip().lstrip("-*# ").strip()
        if stripped:
            return stripped[:limit].rstrip()
    return ""


@dataclass
class PromptFailure:
    ts_local: str
    repo: str
    issue: int | None
    stage: str
    check: str
    fingerprint: str
    draft_number: int | None
    drafter_model: str
    run_id: str
    detail_raw: str
    #: #2198: wall clock the failure cost, where the caller knows it. Optional
    #: and last, so every historical row still reads and every existing caller
    #: is unchanged.
    duration_seconds: float | None = None


def telemetry_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / TELEMETRY_REL / FAILURES_FILENAME


def record_failure(
    repo_root: Path | str,
    *,
    stage: str,
    check: str,
    detail: str,
    issue: int | None = None,
    draft_number: int | None = None,
    drafter_model: str = "",
    run_id: str = "",
    duration_seconds: float | None = None,
    log=print,
) -> PromptFailure | None:
    """Append one record. Never raises; returns None if the write failed."""
    if not (detail or "").strip():
        return None

    record = PromptFailure(
        ts_local=datetime.now().strftime(_TS_FMT),
        repo=str(repo_root),
        issue=issue,
        stage=stage,
        check=check,
        fingerprint=fingerprint(stage, check, detail),
        draft_number=draft_number,
        drafter_model=drafter_model or "",
        run_id=run_id or "",
        detail_raw=detail,
        duration_seconds=duration_seconds,
    )

    try:
        path = telemetry_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    except OSError as exc:
        log(f"  [telemetry] could not record a validation failure: {exc}")
        return None
    return record


def record_failures(
    repo_root: Path | str, details: list[str], **kwargs
) -> list[PromptFailure]:
    """One record per failure. N failures in one roll produce N records."""
    written = []
    for detail in details or []:
        entry = record_failure(repo_root, detail=detail, **kwargs)
        if entry is not None:
            written.append(entry)
    return written


# ---------------------------------------------------------------------------
# Reading and aggregation
# ---------------------------------------------------------------------------


def read_failures(repo_root: Path | str, *, since: str = "") -> list[dict]:
    """Every recorded failure, oldest first. A malformed line is skipped."""
    path = telemetry_path(repo_root)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if since and str(row.get("ts_local", "")) < since:
            continue
        rows.append(row)
    return rows


def _week_of(ts_local: str) -> str:
    try:
        parsed = datetime.strptime(ts_local, _TS_FMT)
    except (ValueError, TypeError):
        return "unknown"
    year, week, _ = parsed.isocalendar()
    return f"{year}-W{week:02d}"


def aggregate(rows: list[dict], group_by: str = "fingerprint") -> list[tuple[str, int]]:
    """Counts by one key, sorted by count descending then key ascending.

    The tie-break on key is what makes the report byte-identical for identical
    input; sorting on count alone leaves equal counts in dict order.
    """
    keyed: dict[str, int] = {}
    for row in rows:
        if group_by == "model":
            key = row.get("drafter_model") or "unknown"
        elif group_by == "week":
            key = _week_of(row.get("ts_local", ""))
        else:
            key = row.get("fingerprint") or "unknown"
        keyed[key] = keyed.get(key, 0) + 1
    return sorted(keyed.items(), key=lambda kv: (-kv[1], kv[0]))


def cross_tab(rows: list[dict]) -> list[tuple[str, str, str, int]]:
    """(fingerprint, model, week, count), deterministically ordered."""
    keyed: dict[tuple[str, str, str], int] = {}
    for row in rows:
        key = (
            row.get("fingerprint") or "unknown",
            row.get("drafter_model") or "unknown",
            _week_of(row.get("ts_local", "")),
        )
        keyed[key] = keyed.get(key, 0) + 1
    return sorted(
        ((f, m, w, c) for (f, m, w), c in keyed.items()),
        key=lambda r: (-r[3], r[0], r[1], r[2]),
    )


def render_report(rows: list[dict], group_by: str = "fingerprint") -> str:
    """Deterministic text report. Identical input yields identical bytes."""
    if not rows:
        return "No validation failures recorded.\n"

    lines = [f"{len(rows)} validation failure(s) recorded.", ""]
    width = max((len(k) for k, _ in aggregate(rows, group_by)), default=10)
    lines.append(f"By {group_by}:")
    for key, count in aggregate(rows, group_by):
        lines.append(f"  {key.ljust(width)}  {count}")

    lines += ["", "By fingerprint x model x week:"]
    for fp, model, week, count in cross_tab(rows):
        lines.append(f"  {fp} | {model} | {week} | {count}")

    return "\n".join(lines) + "\n"
