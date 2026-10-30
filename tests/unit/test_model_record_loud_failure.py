"""model_record.py under standard 0034, one test per sweep site (#3782).

The model record says which model answered every call, so that a comparison
between profiles is not a guess. A spec the seat registry refuses used to be
recorded with an empty model id, which attributes the call to nothing; it now
raises, and the call that used it stops. A run record that cannot take a
call's line alerts the operator and the call's result is kept, since nothing
the run produces reads that line. Line numbers in the names are ledger 0908's,
at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect

import pytest

from assemblyzero.core import model_record as mr
from assemblyzero.core.alert import AlertDeliveryError
from assemblyzero.core.call_recording import RecordingProvider
from assemblyzero.core.llm_provider import MockProvider
from assemblyzero.core.seats import ProfileError


def _fields(spec: str) -> dict:
    inner = MockProvider(model="review")
    result = inner.invoke("s", "c")
    return mr.call_fields(
        inner=inner, spec=spec, seat="requirements.review", effort=None,
        result=result, duration_ms=3,
    )


class _BrokenSink:
    def __init__(self, exc: BaseException):
        self.exc = exc

    def model(self, fields):
        raise self.exc


class TestTheResolvedId:
    def test_70_a_forbidden_model_raises(self):
        with pytest.raises(ProfileError, match="forbidden"):
            _fields("gemini:3-pro")

    def test_70_a_spec_with_no_provider_raises(self):
        with pytest.raises(ProfileError, match="Invalid provider spec"):
            _fields("opus")

    def test_70_the_call_that_used_it_stops(self):
        """The recording wrap builds the fields after the call returns; a
        refused spec ends the call there instead of recording it as nothing."""
        mr.open_sink(_BrokenSink(AssertionError("never reached")))
        provider = RecordingProvider(MockProvider(model="review"), spec="gemini:3-pro")

        with pytest.raises(ProfileError, match="forbidden"):
            provider.invoke("s", "c")

    def test_71_the_resolved_id_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(mr._resolved_id)

    def test_an_empty_spec_has_no_resolved_id_and_is_quiet(self, operator_alerts):
        """Kept: a provider wrapped without a spec has no id to resolve."""
        assert _fields("")["resolved_model_id"] == ""
        assert operator_alerts == []

    def test_a_scripted_or_mock_spec_resolves_to_its_model(self):
        """Kept: these were the specs the old handler named, and the registry
        resolves them; nothing about them reached the handler."""
        assert _fields("mock:review")["resolved_model_id"] == "review"
        assert _fields("scripted:draft")["resolved_model_id"] == "draft"


class TestTheSinkWrite:
    def test_123_a_run_record_that_cannot_take_the_line_alerts(self, operator_alerts):
        mr.open_sink(_BrokenSink(TypeError("Object of type bytes is not JSON serializable")))

        assert mr.record_call({"seat": "requirements.review"}) is False
        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert "TypeError" in alert["cause"]
        assert "requirements.review" in alert["consequence"]

    def test_123_the_call_still_returns_its_result(self, operator_alerts):
        mr.open_sink(_BrokenSink(TypeError("not serializable")))
        provider = RecordingProvider(MockProvider(model="review"), spec="mock:review")

        result = provider.invoke("s", "c")

        assert result.success is True and result.response
        assert len(operator_alerts) == 1

    def test_123_an_alert_that_was_not_delivered_is_raised_not_alerted_again(
        self, operator_alerts
    ):
        mr.open_sink(_BrokenSink(AlertDeliveryError("email: no sender configured")))

        with pytest.raises(AlertDeliveryError):
            mr.record_call({"seat": "requirements.review"})
        assert operator_alerts == []

    def test_124_the_sink_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(mr)

    def test_no_open_record_is_no_write_and_quiet(self, operator_alerts):
        """Kept: outside a run there is nothing to write to, which is an answer."""
        mr.close_sink()
        assert mr.record_call({"seat": "x"}) is False
        assert operator_alerts == []
