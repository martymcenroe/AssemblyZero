#!/usr/bin/env python3
"""Token-ledger: derive Claude Code usage from local session jsonls (Closes #1111).

Why this exists -- the existing `tools/claude-usage-scraper.py` drives an
interactive PTY into `claude /status` to read the TUI's quota %. That's
the only place the % surfaces. The token data underneath, though, is sitting
on disk in `~/.claude/projects/<encoded>/*.jsonl` -- every assistant message
has a `usage` block:

    {
      "input_tokens": 5,
      "output_tokens": 555,
      "cache_read_input_tokens": 16446,
      "cache_creation_input_tokens": 19382,
      "model": "claude-opus-4-7"
    }

Walking those jsonls and aggregating gives us an INDEPENDENT token ledger
that we control. We don't have to calibrate cleanly to /status's reported
percentages -- Anthropic changes the quota algorithm without notice (caps
shift; weighting changes between input/output/cache; etc.) and any
hard-coded constants drift over time.

What we DO get is parallel-signal detection: side-by-side with the existing
`~/.claude-usage-quota.jsonl` scraped data, the **divergence** between
(our derived %) and (the TUI's reported %) IS the signal that Anthropic
shifted their algorithm. We don't have to match their numbers; we just
have to track when they change relative to us.

What this tool produces:

  - Aggregate token counts by session (using sessionId from the jsonl
    events).
  - Aggregate by current week (since most recent Sunday 00:00 UTC).
  - Per-model-family breakdown (sonnet / opus / haiku).
  - Optional cap-based percentages (--cap-opus, --cap-sonnet, --cap-haiku).
  - JSON output (default to stdout; `--output file` to append a row).

Out of scope (per #1111 body):

  - Calibrating to /status's percentages. Caps are user-configurable.
  - Plan-tier auto-detection (Max vs Team vs Enterprise) -- user supplies caps.
  - Replacing the existing scraper outright. Both should run in parallel
    during a calibration window so we have ground truth to compare against.

Files walked:

  - Glob: ~/.claude/projects/*/*.jsonl   (top-level session files)
  - Excluded: ~/.claude/projects/*/subagents/*.jsonl (subset of parent session)

Issue: #1111 | Companion: tools/claude-usage-scraper.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# Model family detection -- substring match on the message.model field.
# Order matters: more specific first.
MODEL_FAMILY_PATTERNS = (
    ("opus", "opus"),
    ("sonnet", "sonnet"),
    ("haiku", "haiku"),
)
UNKNOWN_FAMILY = "unknown"


@dataclass
class UsageRecord:
    """One assistant message's accounting fields."""
    timestamp: datetime
    session_id: str
    model: str
    family: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_input_tokens
            + self.cache_creation_input_tokens
        )


@dataclass
class FamilyTotals:
    family: str
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    message_count: int = 0


@dataclass
class SessionTotals:
    session_id: str
    total_tokens: int = 0
    message_count: int = 0
    first_message: datetime | None = None
    last_message: datetime | None = None


def detect_family(model: str) -> str:
    """Return 'opus' / 'sonnet' / 'haiku' / 'unknown' from a model id."""
    if not model:
        return UNKNOWN_FAMILY
    lower = model.lower()
    for needle, family in MODEL_FAMILY_PATTERNS:
        if needle in lower:
            return family
    return UNKNOWN_FAMILY


def parse_timestamp(raw: Any) -> datetime | None:
    """Parse a Claude-Code-style timestamp (ISO 8601 with Z suffix)."""
    if not isinstance(raw, str):
        return None
    # Python's fromisoformat is permissive enough on 3.11+ but Z suffix
    # needs swap to +00:00.
    text = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def extract_record(event: dict) -> UsageRecord | None:
    """Pull a UsageRecord from one assistant-message event, or None
    if the event isn't a usage-bearing assistant message.
    """
    if event.get("type") != "assistant":
        return None
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    timestamp = parse_timestamp(event.get("timestamp"))
    if timestamp is None:
        return None
    model = str(message.get("model") or "")
    session_id = str(event.get("sessionId") or "")
    return UsageRecord(
        timestamp=timestamp,
        session_id=session_id,
        model=model,
        family=detect_family(model),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        cache_read_input_tokens=int(usage.get("cache_read_input_tokens") or 0),
        cache_creation_input_tokens=int(usage.get("cache_creation_input_tokens") or 0),
    )


def iter_session_jsonls(projects_root: Path) -> list[Path]:
    """List top-level session jsonls (skip subagents/ subdirs).

    Subagent jsonls duplicate counts already attributed to their parent
    session; including them would double-count tokens.
    """
    if not projects_root.is_dir():
        return []
    out: list[Path] = []
    for proj_dir in projects_root.iterdir():
        if not proj_dir.is_dir():
            continue
        # Only top-level .jsonl in this project's dir (NOT subagents/)
        for jsonl in proj_dir.glob("*.jsonl"):
            if jsonl.is_file():
                out.append(jsonl)
    return out


def iter_records(path: Path) -> list[UsageRecord]:
    """Stream a single jsonl, returning every usage-bearing assistant
    message as a UsageRecord. Corrupt lines are skipped silently
    (the cost-of-best-effort vs. crashing on transient I/O is bounded).
    """
    records: list[UsageRecord] = []
    try:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                rec = extract_record(event)
                if rec is not None:
                    records.append(rec)
    except OSError:
        # File disappeared mid-read or permissions changed; nothing to do.
        pass
    return records


def collect_all_records(projects_root: Path) -> list[UsageRecord]:
    out: list[UsageRecord] = []
    for jsonl in iter_session_jsonls(projects_root):
        out.extend(iter_records(jsonl))
    return out


def most_recent_sunday(reference: datetime) -> datetime:
    """Return the most recent Sunday 00:00 UTC at or before `reference`."""
    ref_utc = reference.astimezone(timezone.utc)
    # Python: Monday=0 ... Sunday=6
    weekday = ref_utc.weekday()  # 0=Mon, 6=Sun
    days_since_sunday = (weekday + 1) % 7  # 0 when ref is Sunday
    midnight = ref_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days_since_sunday)


def filter_to_window(
    records: list[UsageRecord],
    since: datetime,
) -> list[UsageRecord]:
    return [r for r in records if r.timestamp >= since]


def by_family(records: list[UsageRecord]) -> dict[str, FamilyTotals]:
    totals: dict[str, FamilyTotals] = {}
    for r in records:
        t = totals.setdefault(r.family, FamilyTotals(family=r.family))
        t.total_tokens += r.total_tokens
        t.input_tokens += r.input_tokens
        t.output_tokens += r.output_tokens
        t.cache_read_input_tokens += r.cache_read_input_tokens
        t.cache_creation_input_tokens += r.cache_creation_input_tokens
        t.message_count += 1
    return totals


def by_session(records: list[UsageRecord]) -> dict[str, SessionTotals]:
    totals: dict[str, SessionTotals] = {}
    for r in records:
        t = totals.setdefault(r.session_id, SessionTotals(session_id=r.session_id))
        t.total_tokens += r.total_tokens
        t.message_count += 1
        if t.first_message is None or r.timestamp < t.first_message:
            t.first_message = r.timestamp
        if t.last_message is None or r.timestamp > t.last_message:
            t.last_message = r.timestamp
    return totals


def current_session_record(records: list[UsageRecord]) -> SessionTotals | None:
    """Pick the session with the most recent message as 'current'."""
    sessions = by_session(records)
    if not sessions:
        return None
    return max(
        sessions.values(),
        key=lambda s: (s.last_message or datetime.min.replace(tzinfo=timezone.utc)),
    )


def compute_caps_payload(
    family_totals: dict[str, FamilyTotals],
    caps: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """For each family in the totals, attach pct_used if a cap was supplied.

    Out: { family: { total_tokens, cap, pct_used, message_count, ... } }
    """
    out: dict[str, dict[str, Any]] = {}
    for family, totals in family_totals.items():
        entry: dict[str, Any] = {
            "total_tokens": totals.total_tokens,
            "input_tokens": totals.input_tokens,
            "output_tokens": totals.output_tokens,
            "cache_read_input_tokens": totals.cache_read_input_tokens,
            "cache_creation_input_tokens": totals.cache_creation_input_tokens,
            "message_count": totals.message_count,
        }
        cap = caps.get(family)
        if cap and cap > 0:
            entry["cap"] = cap
            entry["pct_used"] = round(100.0 * totals.total_tokens / cap, 2)
        out[family] = entry
    return out


def build_payload(
    records: list[UsageRecord],
    caps: dict[str, int],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate `records` into the output JSON shape."""
    now = now or datetime.now(timezone.utc)
    week_start = most_recent_sunday(now)

    week_records = filter_to_window(records, week_start)
    week_family_totals = by_family(week_records)
    current = current_session_record(records)

    payload: dict[str, Any] = {
        "computed_at": now.isoformat().replace("+00:00", "Z"),
        "week_start": week_start.isoformat().replace("+00:00", "Z"),
        "total_records": len(records),
        "week_records": len(week_records),
        "by_family_week": compute_caps_payload(week_family_totals, caps),
        "current_session": None,
        "divergence_placeholder": (
            "TODO #1111: compare against ~/.claude-usage-quota.jsonl latest "
            "scraped row. Until calibration window completes this field is "
            "informational only."
        ),
    }

    if current is not None:
        payload["current_session"] = {
            "session_id": current.session_id,
            "total_tokens": current.total_tokens,
            "message_count": current.message_count,
            "first_message": current.first_message.isoformat().replace("+00:00", "Z")
                if current.first_message else None,
            "last_message": current.last_message.isoformat().replace("+00:00", "Z")
                if current.last_message else None,
        }

    return payload


def parse_caps_args(args: argparse.Namespace) -> dict[str, int]:
    caps: dict[str, int] = {}
    for family in ("opus", "sonnet", "haiku"):
        val = getattr(args, f"cap_{family}", None)
        if val and val > 0:
            caps[family] = val
    return caps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.strip().split("\n")[0],
    )
    parser.add_argument(
        "--projects-root", type=Path, default=PROJECTS_ROOT,
        help=f"Override the Claude projects root (default: {PROJECTS_ROOT})",
    )
    parser.add_argument(
        "--cap-opus", type=int, default=0,
        help="Opus weekly cap (tokens). 0 = don't compute percentages.",
    )
    parser.add_argument(
        "--cap-sonnet", type=int, default=0,
        help="Sonnet weekly cap (tokens).",
    )
    parser.add_argument(
        "--cap-haiku", type=int, default=0,
        help="Haiku weekly cap (tokens).",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Append the JSON payload as one line to this file (JSONL). "
             "If omitted, prints to stdout as pretty JSON.",
    )
    args = parser.parse_args(argv)

    records = collect_all_records(args.projects_root)
    caps = parse_caps_args(args)
    payload = build_payload(records, caps)

    if args.output:
        # Append as one JSON line for ledger-style consumption.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, default=str) + "\n")
        print(f"Appended ledger row to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(payload, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
