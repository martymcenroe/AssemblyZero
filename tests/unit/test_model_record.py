"""Which model answered every call (#3565, under #3562).

T1 the per-call record and the fallback, T2 the run record's header and its
`model` events, T3 the profile on every telemetry row, T4 the LLD stamp.
"""

from __future__ import annotations

import json

import pytest

from assemblyzero.core import call_recording
from assemblyzero.core.llm_provider import FallbackProvider, MockProvider, get_provider
from assemblyzero.core.model_record import (
    announce_profile,
    call_fields,
    close_sink,
    model_record_is_armed,
    open_sink,
)
from assemblyzero.core.seats import (
    builtin_path,
    current_profile_name,
    load_profile,
    resolve,
    set_run_profile,
)

FIELDS = (
    "seat", "spec", "resolved_model_id", "provider_class", "fallback",
    "fallback_provider", "effort", "duration_ms", "input_tokens",
    "output_tokens", "success", "model_used",
)


class _Sink:
    def __init__(self):
        self.calls: list[dict] = []

    def model(self, fields):
        self.calls.append(fields)


def _profile(name: str) -> dict:
    return load_profile(builtin_path(name))


@pytest.fixture
def reset_call_context():
    call_recording.reset_context()
    yield
    call_recording.reset_context()


# ---------------------------------------------------------------------------
# T1: one record per call, with every field
# ---------------------------------------------------------------------------


class TestThePerCallRecord:
    def test_outside_a_run_nothing_is_wrapped(self):
        """The scripted-provider identity contract (#2731) still holds."""
        assert not model_record_is_armed()
        assert type(get_provider("mock:review")).__name__ == "MockProvider"

    def test_every_call_writes_one_record_naming_the_seat(self):
        sink = _Sink()
        open_sink(sink)
        state = {"model_profile": _profile("mock")}

        seat = resolve(state, "requirements.review")
        provider = get_provider(seat.spec, effort=seat.effort)
        provider.invoke("system", "content")
        provider.invoke("system", "content again")

        assert len(sink.calls) == 2
        record = sink.calls[0]
        assert set(FIELDS) <= set(record)
        assert record["seat"] == "requirements.review"
        assert record["spec"] == "mock:review"
        assert record["resolved_model_id"] == "review"
        assert record["provider_class"] == "MockProvider"
        assert record["fallback"] is False
        assert record["success"] is True
        assert record["duration_ms"] >= 0

    def test_a_spec_the_seat_did_not_resolve_is_recorded_without_a_seat(self):
        sink = _Sink()
        open_sink(sink)
        resolve({"model_profile": _profile("mock")}, "requirements.review")

        get_provider("mock:draft").invoke("s", "c")

        assert sink.calls[0]["seat"] == ""
        assert sink.calls[0]["spec"] == "mock:draft"

    def test_calls_jsonl_carries_the_same_fields(self, tmp_path, reset_call_context):
        sink = _Sink()
        open_sink(sink)
        call_recording.set_context("lld", "N3_review", str(tmp_path))
        seat = resolve({"model_profile": _profile("mock")}, "requirements.review")

        get_provider(seat.spec).invoke("s", "c")

        rows, unreadable = call_recording.read_calls(tmp_path)
        assert unreadable == 0 and len(rows) == len(sink.calls) == 1
        for key in ("seat", "spec", "resolved_model_id", "provider_class", "fallback", "effort"):
            assert rows[0][key] == sink.calls[0][key], key
        assert rows[0]["response"]  # the bodies are still there

    def test_a_fallback_answer_is_recorded_as_the_fallback(self):
        primary = MockProvider(model="draft", fail_on_call=1)
        fallback = MockProvider(model="review")
        wrapped = FallbackProvider(primary=primary, fallback=fallback)

        result = wrapped.invoke("s", "c")

        assert wrapped.fallback_answered is True
        assert wrapped.model == "review"
        fields = call_fields(
            inner=wrapped, spec="claude:opus", seat="requirements.review",
            effort="max", result=result, duration_ms=5,
        )
        assert fields["fallback"] is True
        assert fields["fallback_provider"] == "MockProvider"
        assert fields["resolved_model_id"] == "review"

    def test_a_primary_answer_is_not_a_fallback(self):
        wrapped = FallbackProvider(
            primary=MockProvider(model="draft"), fallback=MockProvider(model="review"),
        )
        wrapped.invoke("s", "c")
        assert wrapped.fallback_answered is False
        assert wrapped.model == "draft"


# ---------------------------------------------------------------------------
# T2: the run record opens with the profile and logs every call
# ---------------------------------------------------------------------------


class TestTheRunRecord:
    def test_the_header_and_one_model_event_per_call(self, tmp_path, reset_call_context):
        from assemblyzero.core.run_record import RunRecord

        profile = _profile("mock")
        record = RunRecord.start("impl", tmp_path, 42, argv=["test"])
        try:
            announce_profile(profile)
            call_recording.set_context("impl", "N1_review_test_plan", str(tmp_path / "audit"))
            for seat_name in ("impl.test_plan.review", "impl.code"):
                seat = resolve({"model_profile": profile}, seat_name)
                get_provider(seat.spec).invoke("s", "c")
        finally:
            record.finish("success")

        assert not model_record_is_armed()
        lines = record.events_path.read_text(encoding="utf-8").splitlines()
        header = next(line for line in lines if " profile name=" in line)
        assert "name=mock" in header and f"sha256={profile['sha256']}" in header
        seat_lines = [line for line in lines if " seat " in line and " spec=" in line]
        assert len(seat_lines) == 17

        events = [json.loads(line.split(" model ", 1)[1]) for line in lines if " model {" in line]
        calls, _ = call_recording.read_calls(tmp_path / "audit")
        assert len(events) == len(calls) == 2
        assert [e["seat"] for e in events] == ["impl.test_plan.review", "impl.code"]


# ---------------------------------------------------------------------------
# T3: the profile name on every telemetry row
# ---------------------------------------------------------------------------


class TestTheProfileOnEveryRow:
    def test_the_default_is_named_when_nothing_was_announced(self):
        assert current_profile_name() == "gemini"

    def test_convergence_rows_carry_the_run_profile(self, tmp_path):
        from assemblyzero.speedrun import convergence

        set_run_profile(_profile("claude"))
        convergence.record_stage_enter(tmp_path, "lld", 1, 5)

        rows = [
            json.loads(line)
            for line in convergence.records_path(tmp_path).read_text(encoding="utf-8").splitlines()
        ]
        assert rows and all(row["profile"] == "claude" for row in rows)

    def test_run_log_rows_carry_the_run_profile(self, tmp_path):
        from assemblyzero.utils.speedrun import RunLogger

        set_run_profile(_profile("claude"))
        logger = RunLogger(tmp_path)
        logger.complete_run(issue=1, attempt=1, started_at_iso="t", outcome="success", total_seconds=1.0)
        logger.complete_run(
            issue=1, attempt=2, started_at_iso="t", outcome="success",
            total_seconds=1.0, profile="gemini",
        )

        rows = logger.read_all()
        assert [row["profile"] for row in rows] == ["claude", "gemini"]


# ---------------------------------------------------------------------------
# T4: the LLD stamp names the reviewer that ran
# ---------------------------------------------------------------------------

LLD = "# LLD\n\n* **Status:** Draft\n\n## 1. Context\n"


class TestTheStamp:
    def test_the_resolved_reviewer_is_stamped(self):
        from assemblyzero.workflows.requirements.audit import embed_review_evidence

        out = embed_review_evidence(
            LLD, "APPROVED", "2026-09-25", 1,
            reviewer_model="gemini-3.1-pro-high", reviewer_spec="gemini:3.1-pro",
        )
        assert "Approved (gemini-3.1-pro-high, 2026-09-25)" in out
        assert "`gemini-3.1-pro-high` (`gemini:3.1-pro`)" in out

    def test_reviewer_model_in_the_environment_is_not_read(self, monkeypatch):
        from assemblyzero.core import config
        from assemblyzero.workflows.requirements.audit import embed_review_evidence

        monkeypatch.setenv("REVIEWER_MODEL", "nonsense-model")
        monkeypatch.setattr(config, "REVIEWER_MODEL", "nonsense-model")

        out = embed_review_evidence(LLD, "APPROVED", "2026-09-25", 1)

        assert "nonsense-model" not in out
        assert "Approved (gemini-3.1-pro-high, 2026-09-25)" in out

    def test_the_run_profile_decides_the_default_stamp(self):
        from assemblyzero.workflows.requirements.audit import embed_review_evidence

        set_run_profile(_profile("claude"))
        out = embed_review_evidence(LLD, "APPROVED", "2026-09-25", 1)
        assert "Approved (claude-opus-4-6, 2026-09-25)" in out


def test_close_sink_only_closes_its_own():
    first, second = _Sink(), _Sink()
    open_sink(first)
    close_sink(second)
    assert model_record_is_armed()
    close_sink(first)
    assert not model_record_is_armed()
