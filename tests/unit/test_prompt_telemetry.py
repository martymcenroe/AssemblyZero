"""Acceptance tests for prompt-failure telemetry (#2074).

The seven tests named in the issue body are the acceptance criteria.

The fingerprint format is a contract #2075 consumes, so its round-trip is
guarded here rather than left to convention -- changing the normalization
silently re-buckets every historical record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from assemblyzero.speedrun.prompt_telemetry import (  # noqa: E402
    aggregate,
    cross_tab,
    fingerprint,
    normalize_detail,
    read_failures,
    record_failure,
    record_failures,
    render_report,
    telemetry_path,
)

# The message the operator observed on 2026-08-01, verbatim.
OBSERVED = "MECHANICAL VALIDATION FAILED: Section 2.1 table malformed"
EXPECTED_FINGERPRINT = "lld:mechanical:section-2-1-table-malformed"


# --- "a known mechanical failure emits exactly one record" ---------------


def test_the_observed_failure_produces_the_specified_fingerprint(tmp_path):
    record = record_failure(
        tmp_path, stage="lld", check="mechanical", detail=OBSERVED,
        issue=2, draft_number=1, drafter_model="gemini:3.1-pro",
        run_id="run-issue2-133746",
    )

    assert record is not None
    assert record.fingerprint == EXPECTED_FINGERPRINT

    rows = read_failures(tmp_path)
    assert len(rows) == 1
    assert rows[0]["fingerprint"] == EXPECTED_FINGERPRINT


def test_every_specified_field_is_present(tmp_path):
    record_failure(
        tmp_path, stage="lld", check="mechanical", detail=OBSERVED,
        issue=2, draft_number=3, drafter_model="gemini:3.1-pro",
        run_id="run-issue2-133746",
    )
    row = read_failures(tmp_path)[0]

    for field in ("ts_local", "repo", "issue", "stage", "check", "fingerprint",
                  "draft_number", "drafter_model", "run_id", "detail_raw"):
        assert field in row, f"{field} is part of the contract"

    assert row["issue"] == 2
    assert row["draft_number"] == 3
    assert row["drafter_model"] == "gemini:3.1-pro"
    assert row["run_id"] == "run-issue2-133746"


def test_timestamp_is_local_with_no_utc_marker(tmp_path):
    record_failure(tmp_path, stage="lld", check="mechanical", detail=OBSERVED)
    ts = read_failures(tmp_path)[0]["ts_local"]
    assert "Z" not in ts and "+" not in ts and "UTC" not in ts


def test_records_land_at_the_specified_path(tmp_path):
    record_failure(tmp_path, stage="lld", check="mechanical", detail=OBSERVED)
    assert telemetry_path(tmp_path) == (
        tmp_path / "data" / "speedrun" / "telemetry" / "prompt-failures.jsonl"
    )
    assert telemetry_path(tmp_path).is_file()


# --- "casing, whitespace and punctuation give the identical fingerprint" --


@pytest.mark.parametrize(
    "variant",
    [
        "MECHANICAL VALIDATION FAILED: Section 2.1 table malformed",
        "mechanical validation failed: section 2.1 table malformed",
        "MECHANICAL VALIDATION FAILED:    Section  2.1   table  malformed  ",
        "MECHANICAL VALIDATION FAILED: Section 2.1 table malformed!!!",
        "MECHANICAL VALIDATION FAILED:\n  Section 2.1 table malformed",
        "MECHANICAL VALIDATION FAILED: --Section 2.1, table malformed--",
    ],
)
def test_the_same_failure_normalizes_identically(variant):
    assert fingerprint("lld", "mechanical", variant) == EXPECTED_FINGERPRINT


def test_two_genuinely_different_failures_differ():
    a = fingerprint("lld", "mechanical", "Section 2.1 table malformed")
    b = fingerprint("lld", "mechanical", "Section 3.4 heading missing")
    assert a != b


def test_the_same_defect_at_a_different_check_is_a_different_fingerprint():
    a = fingerprint("lld", "mechanical", "table malformed")
    b = fingerprint("lld", "test-plan", "table malformed")
    assert a != b


def test_normalization_matches_the_specified_rules():
    assert normalize_detail("Section 2.1 table malformed") == "section-2-1-table-malformed"
    assert normalize_detail("---leading and trailing---") == "leading-and-trailing"
    assert normalize_detail("") == ""


def test_the_announcement_marker_is_stripped_not_fingerprinted():
    # Otherwise every mechanical failure would share one fingerprint and the
    # whole exercise would measure nothing.
    with_marker = fingerprint("lld", "mechanical", OBSERVED)
    without = fingerprint("lld", "mechanical", "Section 2.1 table malformed")
    assert with_marker == without
    assert "mechanical-validation-failed" not in with_marker.split(":")[2]


# --- "N failures in one roll produce N records -- no write-time dedupe" --


def test_no_deduplication_at_write_time(tmp_path):
    for _ in range(5):
        record_failure(tmp_path, stage="lld", check="mechanical", detail=OBSERVED)

    rows = read_failures(tmp_path)
    assert len(rows) == 5, "collapsing at write time destroys the rate"
    assert len({r["fingerprint"] for r in rows}) == 1


def test_record_failures_writes_one_per_detail(tmp_path):
    written = record_failures(
        tmp_path, ["first problem", "second problem", "third problem"],
        stage="lld", check="mechanical",
    )
    assert len(written) == 3
    assert len(read_failures(tmp_path)) == 3


def test_empty_details_are_not_recorded(tmp_path):
    assert record_failure(tmp_path, stage="lld", check="mechanical", detail="") is None
    assert record_failure(tmp_path, stage="lld", check="mechanical", detail="   ") is None
    assert read_failures(tmp_path) == []


# --- "detail_raw round-trips the original message unmodified" ------------


def test_detail_raw_round_trips_unmodified(tmp_path):
    messy = "MECHANICAL VALIDATION FAILED:\n  - Section 2.1 table malformed (row 3, 'Files Changed')"
    record_failure(tmp_path, stage="lld", check="mechanical", detail=messy)

    row = read_failures(tmp_path)[0]
    assert row["detail_raw"] == messy, (
        "a fingerprint must always be traceable back to what produced it"
    )


def test_unicode_survives_the_round_trip(tmp_path):
    detail = "Section 2.1 table malformed — em dash and ünïcode"
    record_failure(tmp_path, stage="lld", check="mechanical", detail=detail)
    assert read_failures(tmp_path)[0]["detail_raw"] == detail


# --- "the report groups by fingerprint, model and week, deterministically" ---


def _rows():
    return [
        {"fingerprint": "lld:mechanical:a", "drafter_model": "gemini:3.1-pro",
         "ts_local": "2026-08-01 10:00:00"},
        {"fingerprint": "lld:mechanical:a", "drafter_model": "gemini:3.1-pro",
         "ts_local": "2026-08-01 11:00:00"},
        {"fingerprint": "lld:mechanical:b", "drafter_model": "claude:haiku",
         "ts_local": "2026-07-20 09:00:00"},
    ]


def test_report_groups_by_each_key():
    rows = _rows()
    assert aggregate(rows, "fingerprint") == [
        ("lld:mechanical:a", 2), ("lld:mechanical:b", 1)
    ]
    assert aggregate(rows, "model") == [
        ("gemini:3.1-pro", 2), ("claude:haiku", 1)
    ]
    weeks = dict(aggregate(rows, "week"))
    assert sum(weeks.values()) == 3 and len(weeks) == 2


def test_report_is_byte_identical_for_identical_input():
    first = render_report(_rows(), "fingerprint")
    second = render_report(list(reversed(_rows())), "fingerprint")
    assert first == second, "equal counts must tie-break on key, not dict order"


def test_cross_tab_is_fingerprint_by_model_by_week():
    table = cross_tab(_rows())
    assert ("lld:mechanical:a", "gemini:3.1-pro", "2026-W31", 2) in table
    assert len(table) == 2


def test_report_handles_an_empty_record_set():
    assert render_report([], "fingerprint") == "No validation failures recorded.\n"


def test_since_filters_older_records(tmp_path):
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"ts_local": "2026-07-01 10:00:00", "fingerprint": "old"}) + "\n"
        + json.dumps({"ts_local": "2026-08-01 10:00:00", "fingerprint": "new"}) + "\n",
        encoding="utf-8",
    )

    assert [r["fingerprint"] for r in read_failures(tmp_path, since="2026-08-01")] == ["new"]
    assert len(read_failures(tmp_path)) == 2


def test_a_malformed_line_does_not_break_the_report(tmp_path):
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"ts_local": "2026-08-01 10:00:00", "fingerprint": "ok"}) + "\n"
        + "{ this is not json\n",
        encoding="utf-8",
    )
    assert len(read_failures(tmp_path)) == 1


# --- "a write failure is loud and does not change the roll's outcome" ----


def test_a_write_failure_is_logged_and_swallowed(tmp_path):
    # A file where the telemetry directory must go: mkdir raises, and the roll
    # must not care.
    blocker = tmp_path / "data" / "speedrun"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory\n", encoding="utf-8")

    logged: list[str] = []
    result = record_failure(
        tmp_path, stage="lld", check="mechanical", detail=OBSERVED, log=logged.append
    )

    assert result is None
    assert logged, "a silent telemetry failure is worse than none"
    assert "could not record" in logged[0]


def test_reading_a_missing_file_is_empty_not_an_error(tmp_path):
    assert read_failures(tmp_path) == []


# --- the report tool ------------------------------------------------------


def test_report_tool_runs_and_exits_zero(tmp_path, capsys):
    import prompt_failure_report

    record_failure(
        tmp_path, stage="lld", check="mechanical", detail=OBSERVED,
        drafter_model="gemini:3.1-pro",
    )

    code = prompt_failure_report.main(["--repo", str(tmp_path)])

    assert code == 0
    out = capsys.readouterr().out
    assert EXPECTED_FINGERPRINT in out
    assert "gemini:3.1-pro" in out


def test_report_tool_on_a_repo_with_no_telemetry_is_not_an_error(tmp_path, capsys):
    import prompt_failure_report

    assert prompt_failure_report.main(["--repo", str(tmp_path)]) == 0
    assert "No telemetry file" in capsys.readouterr().out


def test_report_tool_accepts_each_grouping(tmp_path):
    import prompt_failure_report

    record_failure(tmp_path, stage="lld", check="mechanical", detail=OBSERVED)
    for grouping in ("fingerprint", "model", "week"):
        assert prompt_failure_report.main(
            ["--repo", str(tmp_path), "--group-by", grouping]
        ) == 0


# --- wiring ---------------------------------------------------------------


def test_mechanical_validation_records_its_failures(tmp_path, monkeypatch):
    from assemblyzero.workflows.requirements.nodes import validate_mechanical as vm

    monkeypatch.setattr(
        vm, "_validate_lld_mechanical_inner",
        lambda _state: {
            "validation_errors": ["Section 2.1 table malformed"],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n  - Section 2.1 table malformed",
        },
    )

    result = vm.validate_lld_mechanical({
        "target_repo": str(tmp_path), "issue_number": 2, "draft_number": 1,
        "config_drafter": "gemini:3.1-pro",
    })

    assert result["lld_status"] == "BLOCKED", "the wrapper must not alter the verdict"
    rows = read_failures(tmp_path)
    assert len(rows) == 1
    assert rows[0]["fingerprint"] == EXPECTED_FINGERPRINT


def test_mechanical_validation_records_nothing_when_it_passes(tmp_path, monkeypatch):
    from assemblyzero.workflows.requirements.nodes import validate_mechanical as vm

    monkeypatch.setattr(
        vm, "_validate_lld_mechanical_inner",
        lambda _state: {"validation_errors": [], "lld_status": "PENDING", "error_message": ""},
    )

    vm.validate_lld_mechanical({"target_repo": str(tmp_path), "issue_number": 2})
    assert read_failures(tmp_path) == []


def test_telemetry_failure_does_not_change_the_validation_verdict(tmp_path, monkeypatch):
    from assemblyzero.speedrun import prompt_telemetry as pt
    from assemblyzero.workflows.requirements.nodes import validate_mechanical as vm

    monkeypatch.setattr(
        vm, "_validate_lld_mechanical_inner",
        lambda _state: {
            "validation_errors": ["boom"], "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n  - boom",
        },
    )

    def explode(*_a, **_kw):
        raise RuntimeError("telemetry is broken")

    monkeypatch.setattr(pt, "record_failures", explode)

    result = vm.validate_lld_mechanical({
        "target_repo": str(tmp_path), "issue_number": 2,
    })

    assert result["lld_status"] == "BLOCKED"
    assert result["validation_errors"] == ["boom"]
