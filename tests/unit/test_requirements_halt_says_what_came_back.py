"""A requirements gate halt names what came back and suspects no storm it did not see (#4485).

All six recorded answers behind #4483 were valid JSON, and each was reported as
"unparseable". The halt printed `Transient: No` above a recovery text that
blamed "a transient capacity storm", gave no pointer to the recorded answers,
and waited four minutes of backoff on an answer whose shape came back the same
every time.
"""

from __future__ import annotations

import importlib
import json

import pytest

from assemblyzero.core import call_recording, provider_storm
from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.core.recovery_plan import generate_recovery_plan

ar = importlib.import_module("assemblyzero.workflows.requirements.nodes.analyze_requirements")


def _result(answer, *, success: bool = True, error: str | None = None) -> LLMCallResult:
    response = answer if isinstance(answer, str) else json.dumps(answer)
    return LLMCallResult(
        success=success, response=response, raw_response=response, error_message=error,
        provider="fake", model_used="fake-model", duration_ms=1, attempts=1,
    )


#: Valid JSON with no findings list: the shape #4483 recorded six times.
NO_FINDINGS = {"analysis": "the requirements look fine", "verdict": "ok"}


class _Provider:
    def __init__(self, result: LLMCallResult, *, storm: bool = False):
        self._result = result
        self._storm = storm
        self.calls = 0

    def invoke(self, **kwargs):
        self.calls += 1
        if self._storm:
            for _ in range(provider_storm.STORM_THRESHOLD):
                provider_storm.record_timeout(300)
        return self._result


@pytest.fixture(autouse=True)
def _clean_storm():
    provider_storm.reset()
    yield
    provider_storm.reset()
    call_recording.reset_context()


@pytest.fixture
def gate(monkeypatch, tmp_path, capsys):
    sleeps: list[float] = []
    monkeypatch.setattr(ar, "_sleep", sleeps.append)

    def run(result: LLMCallResult, *, storm: bool = False):
        provider = _Provider(result, storm=storm)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", lambda spec, *a, **k: provider,
        )
        out = ar.analyze_requirements({
            "issue_title": "t", "issue_body": "some requirement text",
            "issue_number": 332, "target_repo": str(tmp_path),
        })
        return out, sleeps, capsys.readouterr().out

    return run


class TestTheReasonSaysWhatCameBack:
    @pytest.mark.parametrize(
        ("result", "expected"),
        [
            (_result("", success=False, error="agy exited 1"), "the call failed: agy exited 1"),
            (_result("I think the requirements are fine."), "the answer is not JSON"),
            (_result(NO_FINDINGS), "valid JSON the gate cannot use"),
        ],
        ids=["failed-call", "not-json", "valid-json-unusable"],
    )
    def test_t1_three_failures_three_reasons(self, result, expected):
        """T1 (R1)."""
        assert expected in ar._no_verdict_reason(result)

    def test_t1_the_unusable_answer_names_its_keys(self):
        reason = ar._no_verdict_reason(_result(NO_FINDINGS))

        assert "analysis" in reason and "verdict" in reason
        assert "unparseable" not in reason


class TestTheRecoveryTextBlamesOnlyAStormItSaw:
    def _plan(self, out: dict):
        return generate_recovery_plan(
            issue_number=332, workflow="requirements", stage="N0c",
            error_type="requirements_unverified", error_message=out["error_message"],
            state=out,
        )

    def test_t2_no_storm_no_storm_wording(self, gate):
        """T2 (R2): the halt behind #4483 printed `Transient: No` over a storm."""
        out, _, _ = gate(_result(NO_FINDINGS))

        assert "storm" not in self._plan(out).recommendation.lower()

    def test_t2_a_storm_seen_during_the_attempts_is_named(self, gate):
        out, _, _ = gate(_result("", success=False, error="agy timed out"), storm=True)

        assert "storm" in self._plan(out).recommendation.lower()


class TestTheHaltPointsAtTheAnswers:
    def test_t3_an_armed_recording_is_named(self, gate, tmp_path):
        """T3 (R3)."""
        audit = tmp_path / "lineage"
        call_recording.set_context("lld", "N0c_analyze_requirements", str(audit))

        out, _, _ = gate(_result(NO_FINDINGS))

        assert str(call_recording.calls_path(audit)) in out["error_message"]

    def test_t3_no_recording_says_so(self, gate):
        out, _, _ = gate(_result(NO_FINDINGS))

        assert "no recording" in out["error_message"].lower()


class TestAShapeFailureIsResampledNotWaitedOut:
    def test_t4_the_retry_line_says_resampling_and_names_no_capacity_cause(self, gate):
        """T4 (R4): the same shape came back three times, four minutes apart."""
        out, sleeps, printed = gate(_result(NO_FINDINGS))

        retry_lines = [line for line in printed.splitlines() if "no verdict on" in line]
        assert retry_lines
        for line in retry_lines:
            assert "resampling" in line
            assert "capacity" not in line.lower() and "storm" not in line.lower()
        assert not any(sleeps)
        assert out["requirements_unverified"]

    def test_a_failed_call_still_waits_out_the_backoff(self, gate):
        _, sleeps, _ = gate(_result("", success=False, error="agy exited 1"))

        assert list(sleeps) == list(ar.GATE_UNAVAILABLE_RETRY_BACKOFF_SECONDS)
