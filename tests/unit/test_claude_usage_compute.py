"""Tests for tools/claude_usage_compute.py (#1111)."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "claude_usage_compute", TOOLS_DIR / "claude_usage_compute.py",
)
ledger = importlib.util.module_from_spec(_spec)
sys.modules["claude_usage_compute"] = ledger
_spec.loader.exec_module(ledger)


# ---- detect_family ----


class TestDetectFamily:
    def test_opus(self):
        assert ledger.detect_family("claude-opus-4-7") == "opus"

    def test_sonnet(self):
        assert ledger.detect_family("claude-sonnet-4-6") == "sonnet"

    def test_haiku(self):
        assert ledger.detect_family("claude-haiku-4-5-20251001") == "haiku"

    def test_unknown(self):
        assert ledger.detect_family("claude-3-mystery") == "unknown"

    def test_empty(self):
        assert ledger.detect_family("") == "unknown"

    def test_case_insensitive(self):
        assert ledger.detect_family("CLAUDE-OPUS-4-7") == "opus"


# ---- parse_timestamp ----


class TestParseTimestamp:
    def test_z_suffix(self):
        ts = ledger.parse_timestamp("2026-04-19T14:53:54.033Z")
        assert ts is not None
        assert ts.tzinfo is not None

    def test_offset(self):
        ts = ledger.parse_timestamp("2026-04-19T14:53:54+00:00")
        assert ts is not None

    def test_garbage_returns_none(self):
        assert ledger.parse_timestamp("not a timestamp") is None

    def test_none_returns_none(self):
        assert ledger.parse_timestamp(None) is None

    def test_int_returns_none(self):
        assert ledger.parse_timestamp(1234567890) is None


# ---- extract_record ----


def _assistant_event(
    ts: str = "2026-04-19T14:53:54.033Z",
    session: str = "sess-abc",
    model: str = "claude-opus-4-7",
    input_tokens: int = 100,
    output_tokens: int = 200,
    cache_read: int = 1000,
    cache_create: int = 500,
) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": session,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            },
        },
    }


class TestExtractRecord:
    def test_full_extraction(self):
        rec = ledger.extract_record(_assistant_event())
        assert rec is not None
        assert rec.session_id == "sess-abc"
        assert rec.model == "claude-opus-4-7"
        assert rec.family == "opus"
        assert rec.input_tokens == 100
        assert rec.output_tokens == 200
        assert rec.cache_read_input_tokens == 1000
        assert rec.cache_creation_input_tokens == 500
        assert rec.total_tokens == 1800

    def test_user_message_skipped(self):
        evt = {"type": "user", "message": {"content": "hi"}}
        assert ledger.extract_record(evt) is None

    def test_missing_usage_block(self):
        evt = _assistant_event()
        del evt["message"]["usage"]
        assert ledger.extract_record(evt) is None

    def test_missing_message(self):
        assert ledger.extract_record({"type": "assistant"}) is None

    def test_missing_timestamp_returns_none(self):
        evt = _assistant_event()
        del evt["timestamp"]
        assert ledger.extract_record(evt) is None

    def test_missing_token_fields_default_to_zero(self):
        """Tolerance: partial usage blocks don't crash."""
        evt = _assistant_event()
        evt["message"]["usage"] = {"input_tokens": 50}  # only one field
        rec = ledger.extract_record(evt)
        assert rec is not None
        assert rec.input_tokens == 50
        assert rec.output_tokens == 0
        assert rec.cache_read_input_tokens == 0
        assert rec.cache_creation_input_tokens == 0


# ---- iter_session_jsonls ----


class TestIterSessionJsonls:
    def test_picks_up_top_level_jsonls(self, tmp_path):
        proj_a = tmp_path / "proj-a"
        proj_a.mkdir()
        (proj_a / "session1.jsonl").write_text("")
        (proj_a / "session2.jsonl").write_text("")
        # Non-jsonl ignored
        (proj_a / "notes.txt").write_text("")
        files = ledger.iter_session_jsonls(tmp_path)
        names = sorted(p.name for p in files)
        assert names == ["session1.jsonl", "session2.jsonl"]

    def test_skips_subagent_subdir(self, tmp_path):
        """#1111 explicitly excludes subagent jsonls -- they double-count
        tokens already attributed to the parent session."""
        proj = tmp_path / "proj-x"
        proj.mkdir()
        (proj / "parent.jsonl").write_text("")
        subagents = proj / "subagents"
        subagents.mkdir()
        (subagents / "agent-1.jsonl").write_text("")
        (subagents / "agent-2.jsonl").write_text("")
        files = ledger.iter_session_jsonls(tmp_path)
        names = sorted(p.name for p in files)
        assert names == ["parent.jsonl"]

    def test_missing_root_returns_empty(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        assert ledger.iter_session_jsonls(nonexistent) == []

    def test_handles_multiple_projects(self, tmp_path):
        for name in ("proj-1", "proj-2", "proj-3"):
            p = tmp_path / name
            p.mkdir()
            (p / "session.jsonl").write_text("")
        files = ledger.iter_session_jsonls(tmp_path)
        assert len(files) == 3


# ---- iter_records (jsonl parsing) ----


class TestIterRecords:
    def test_parses_assistant_events(self, tmp_path):
        jsonl = tmp_path / "session.jsonl"
        lines = [
            json.dumps(_assistant_event(ts="2026-04-19T14:00:00Z", model="claude-opus-4-7")),
            json.dumps({"type": "user", "message": {"content": "hi"}}),  # skipped
            json.dumps(_assistant_event(ts="2026-04-19T14:05:00Z", model="claude-sonnet-4-6")),
        ]
        jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
        records = ledger.iter_records(jsonl)
        assert len(records) == 2
        assert records[0].family == "opus"
        assert records[1].family == "sonnet"

    def test_skips_corrupt_lines(self, tmp_path):
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text(
            json.dumps(_assistant_event()) + "\n"
            "THIS IS NOT JSON\n"
            + json.dumps(_assistant_event(session="sess-2")) + "\n",
            encoding="utf-8",
        )
        records = ledger.iter_records(jsonl)
        assert len(records) == 2

    def test_skips_blank_lines(self, tmp_path):
        jsonl = tmp_path / "session.jsonl"
        jsonl.write_text(
            "\n\n" + json.dumps(_assistant_event()) + "\n\n",
            encoding="utf-8",
        )
        records = ledger.iter_records(jsonl)
        assert len(records) == 1

    def test_missing_file_returns_empty(self, tmp_path):
        records = ledger.iter_records(tmp_path / "nonexistent.jsonl")
        assert records == []


# ---- most_recent_sunday ----


class TestMostRecentSunday:
    def test_sunday_returns_same_day_midnight(self):
        # 2026-04-12 was a Sunday
        ref = datetime(2026, 4, 12, 14, 30, tzinfo=timezone.utc)
        sun = ledger.most_recent_sunday(ref)
        assert sun.weekday() == 6  # Sunday
        assert sun.hour == 0
        assert sun.day == 12

    def test_monday_returns_previous_sunday(self):
        # 2026-04-13 was a Monday
        ref = datetime(2026, 4, 13, 9, 0, tzinfo=timezone.utc)
        sun = ledger.most_recent_sunday(ref)
        assert sun.weekday() == 6
        assert sun.day == 12  # Sunday before

    def test_saturday_returns_previous_sunday(self):
        # 2026-04-18 was a Saturday
        ref = datetime(2026, 4, 18, 23, 59, tzinfo=timezone.utc)
        sun = ledger.most_recent_sunday(ref)
        assert sun.weekday() == 6
        assert sun.day == 12

    def test_non_utc_reference_normalized(self):
        # Local timezone reference -- function should normalize to UTC first
        ref = datetime(2026, 4, 13, 1, 0, tzinfo=timezone(timedelta(hours=5)))  # Mon 01:00 +05:00 = Sun 20:00 UTC
        sun = ledger.most_recent_sunday(ref)
        # ref in UTC is 2026-04-12 20:00 (still Sunday)
        assert sun.day == 12


# ---- aggregation ----


def _mk_record(family: str = "opus", session: str = "s1", tokens: int = 100,
               ts: datetime | None = None) -> ledger.UsageRecord:
    return ledger.UsageRecord(
        timestamp=ts or datetime(2026, 4, 19, tzinfo=timezone.utc),
        session_id=session,
        model=f"claude-{family}-4-7",
        family=family,
        input_tokens=tokens // 4,
        output_tokens=tokens // 4,
        cache_read_input_tokens=tokens // 4,
        cache_creation_input_tokens=tokens // 4,
    )


class TestByFamily:
    def test_aggregates_per_family(self):
        records = [
            _mk_record("opus", tokens=400),
            _mk_record("opus", tokens=800),
            _mk_record("sonnet", tokens=200),
        ]
        totals = ledger.by_family(records)
        assert totals["opus"].total_tokens == 1200
        assert totals["opus"].message_count == 2
        assert totals["sonnet"].total_tokens == 200
        assert totals["sonnet"].message_count == 1

    def test_empty_returns_empty(self):
        assert ledger.by_family([]) == {}


class TestBySession:
    def test_aggregates_per_session(self):
        records = [
            _mk_record(session="s1", tokens=100,
                       ts=datetime(2026, 4, 19, 14, tzinfo=timezone.utc)),
            _mk_record(session="s1", tokens=200,
                       ts=datetime(2026, 4, 19, 15, tzinfo=timezone.utc)),
            _mk_record(session="s2", tokens=300,
                       ts=datetime(2026, 4, 20, 10, tzinfo=timezone.utc)),
        ]
        totals = ledger.by_session(records)
        assert totals["s1"].total_tokens == 300
        assert totals["s1"].message_count == 2
        assert totals["s1"].first_message.hour == 14
        assert totals["s1"].last_message.hour == 15
        assert totals["s2"].total_tokens == 300


class TestCurrentSessionRecord:
    def test_picks_most_recent_session(self):
        records = [
            _mk_record(session="old", tokens=100,
                       ts=datetime(2026, 4, 19, tzinfo=timezone.utc)),
            _mk_record(session="new", tokens=200,
                       ts=datetime(2026, 4, 20, tzinfo=timezone.utc)),
        ]
        current = ledger.current_session_record(records)
        assert current is not None
        assert current.session_id == "new"

    def test_empty_records_returns_none(self):
        assert ledger.current_session_record([]) is None


# ---- caps + payload ----


class TestComputeCapsPayload:
    def test_no_cap_omits_pct(self):
        totals = {"opus": ledger.FamilyTotals(family="opus", total_tokens=500, message_count=1)}
        payload = ledger.compute_caps_payload(totals, caps={})
        assert "pct_used" not in payload["opus"]

    def test_with_cap_computes_pct(self):
        totals = {"opus": ledger.FamilyTotals(family="opus", total_tokens=500, message_count=1)}
        payload = ledger.compute_caps_payload(totals, caps={"opus": 1000})
        assert payload["opus"]["pct_used"] == 50.0
        assert payload["opus"]["cap"] == 1000

    def test_zero_cap_omits_pct(self):
        totals = {"opus": ledger.FamilyTotals(family="opus", total_tokens=500, message_count=1)}
        payload = ledger.compute_caps_payload(totals, caps={"opus": 0})
        assert "pct_used" not in payload["opus"]


class TestBuildPayload:
    def test_records_outside_week_are_filtered(self):
        now = datetime(2026, 4, 15, 12, tzinfo=timezone.utc)  # Wednesday
        # week_start = Sunday 2026-04-12
        records = [
            _mk_record(family="opus", tokens=400,
                       ts=datetime(2026, 4, 14, tzinfo=timezone.utc)),  # in-week
            _mk_record(family="opus", tokens=800,
                       ts=datetime(2026, 4, 1, tzinfo=timezone.utc)),  # too old
        ]
        payload = ledger.build_payload(records, caps={}, now=now)
        assert payload["week_records"] == 1
        assert payload["by_family_week"]["opus"]["total_tokens"] == 400

    def test_current_session_uses_full_history_not_filtered_week(self):
        """current_session picks across ALL records (most recent message),
        not just the week. A user who hasn't run claude in 30 days should
        still see their last session."""
        now = datetime(2026, 4, 15, tzinfo=timezone.utc)
        records = [
            _mk_record(session="old", tokens=400,
                       ts=datetime(2026, 4, 1, tzinfo=timezone.utc)),  # outside week
        ]
        payload = ledger.build_payload(records, caps={}, now=now)
        assert payload["current_session"] is not None
        assert payload["current_session"]["session_id"] == "old"

    def test_empty_records_safe(self):
        now = datetime(2026, 4, 15, tzinfo=timezone.utc)
        payload = ledger.build_payload([], caps={}, now=now)
        assert payload["total_records"] == 0
        assert payload["week_records"] == 0
        assert payload["by_family_week"] == {}
        assert payload["current_session"] is None

    def test_divergence_placeholder_present(self):
        """The divergence field is a placeholder per the #1111 plan -- it
        documents the intent until calibration data exists."""
        now = datetime(2026, 4, 15, tzinfo=timezone.utc)
        payload = ledger.build_payload([], caps={}, now=now)
        assert "divergence_placeholder" in payload


# ---- main() integration ----


class TestMainIntegration:
    def test_main_writes_to_output_file(self, tmp_path, capsys):
        # Build a fake projects root
        projects = tmp_path / "projects"
        proj = projects / "test-proj"
        proj.mkdir(parents=True)
        jsonl = proj / "session.jsonl"
        jsonl.write_text(
            json.dumps(_assistant_event()) + "\n",
            encoding="utf-8",
        )
        out_file = tmp_path / "ledger.jsonl"
        rc = ledger.main([
            "--projects-root", str(projects),
            "--output", str(out_file),
        ])
        assert rc == 0
        assert out_file.exists()
        # One line of valid JSON
        lines = out_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["total_records"] == 1

    def test_main_prints_to_stdout_when_no_output(self, tmp_path, capsys):
        projects = tmp_path / "projects"
        projects.mkdir()
        rc = ledger.main(["--projects-root", str(projects)])
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["total_records"] == 0

    def test_main_with_caps_computes_pct(self, tmp_path, capsys):
        projects = tmp_path / "projects"
        proj = projects / "p"
        proj.mkdir(parents=True)
        # 1800 total tokens (100+200+1000+500) on opus
        (proj / "s.jsonl").write_text(
            json.dumps(_assistant_event(
                ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )) + "\n",
            encoding="utf-8",
        )
        rc = ledger.main([
            "--projects-root", str(projects),
            "--cap-opus", "10000",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        family = parsed["by_family_week"]["opus"]
        assert family["cap"] == 10000
        assert family["pct_used"] == 18.0
