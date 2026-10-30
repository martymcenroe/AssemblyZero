"""preflight.py under standard 0034, one test per sweep site (#3786).

A failed transport check is still a failed ``PreflightResult``: both callers
(requirements N1 and spec N2) return it as ``error_message``, the graph routes
that to HALT, and HALT alerts. What was missing is the loud line at the point
of failure. A fault in the probe (a bug, not the transport) now raises instead
of reading as a failed transport, and an unknown Gemini alias raises instead
of probing a model the run will not use. Line numbers in the names are ledger
0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from assemblyzero.core import preflight


@pytest.fixture(autouse=True)
def _bypass_gemini_preflight():
    """Overrides tests/unit/conftest.py's fixture of the same name: here the
    real check_gemini_transport is the thing under test."""
    preflight._TRANSPORT_RESULT = None
    yield
    preflight._TRANSPORT_RESULT = None


class _FakeClient:
    def __init__(self, agy="/home/x/.local/bin/agy", success=True, response="pong",
                 raises=None, error_message="429 quota"):
        self.agy, self.success, self.response = agy, success, response
        self.raises, self.error_message = raises, error_message

    def _find_agy_cli(self):
        return self.agy

    def invoke(self, system_instruction, content, response_schema=None):
        if self.raises:
            raise self.raises
        return SimpleNamespace(
            success=self.success, response=self.response,
            error_message=None if self.success else self.error_message,
        )


class TestTheProbeModel:
    def test_64_an_unknown_gemini_alias_raises(self):
        with pytest.raises(ValueError, match="'something-new'"):
            preflight.gemini_model_for("claude:sonnet", "gemini:something-new")

    def test_64_an_unknown_alias_fails_the_preflight_loudly(self, monkeypatch, capsys):
        """Seat resolution lets an unknown alias through, so the run's
        preflight is where it is first met; both callers halt on the result."""
        probed: list[str] = []

        def probe(client=None, model=preflight.DEFAULT_PROBE_MODEL):
            probed.append(model)
            return preflight.PreflightResult(passed=True, available_credentials=1, total_credentials=1)

        monkeypatch.setattr(preflight, "check_gemini_transport", probe)

        result = preflight.preflight_for_specs("claude:sonnet", "gemini:something-new")

        assert result.passed is False
        assert "'something-new'" in result.warnings[0]
        assert probed == []
        assert "ERROR [PREFLIGHT]" in capsys.readouterr().err

    def test_a_known_alias_a_full_id_and_no_gemini_spec_are_answers(self):
        """Kept: an alias maps the way GeminiProvider maps it, a full id is
        itself, and a run with no gemini: spec probes the default model."""
        from assemblyzero.core.llm_provider import GeminiProvider

        assert preflight.gemini_model_for("gemini:3.1-pro") == GeminiProvider.MODEL_MAP["3.1-pro"]
        assert preflight.gemini_model_for("gemini:gemini-3.8-flash-low") == "gemini-3.8-flash-low"
        assert preflight.gemini_model_for("claude:opus") == preflight.DEFAULT_PROBE_MODEL


class TestAFailedCheckIsLoud:
    def test_83_no_agy_is_loud(self, capsys):
        result = preflight.check_gemini_transport(_FakeClient(agy=None), model="gemini-3.8-flash-high")

        assert result.passed is False
        err = capsys.readouterr().err
        assert "ERROR [PREFLIGHT]" in err
        assert "agy CLI was not found" in err
        assert "gemini-3.8-flash-high" in err

    def test_94_a_transport_that_raises_is_loud_and_a_failed_check(self, capsys):
        client = _FakeClient(raises=RuntimeError("could not run `wsl.exe --exec which agy`"))

        result = preflight.check_gemini_transport(client)

        assert result.passed is False
        assert "RuntimeError" in result.warnings[0]
        err = capsys.readouterr().err
        assert "ERROR [PREFLIGHT]" in err
        assert "could not run `wsl.exe" in err

    def test_94_a_fault_in_the_probe_raises(self):
        """A bug is not a transport failure; reading it as one made it look
        like an agy outage."""
        with pytest.raises(TypeError, match="a bug"):
            preflight.check_gemini_transport(_FakeClient(raises=TypeError("a bug")))

    def test_95_the_withdrawn_tag_is_gone(self):
        assert "fail-open" not in inspect.getsource(preflight)

    def test_102_a_failed_probe_call_is_loud(self, capsys):
        result = preflight.check_gemini_transport(_FakeClient(success=False, response=None))

        assert result.passed is False
        err = capsys.readouterr().err
        assert "ERROR [PREFLIGHT]" in err
        assert "429 quota" in err

    def test_102_an_empty_answer_is_loud(self, capsys):
        result = preflight.check_gemini_transport(_FakeClient(response="   "))

        assert result.passed is False
        err = capsys.readouterr().err
        assert "ERROR [PREFLIGHT]" in err
        assert "empty response" in err

    def test_a_passing_probe_is_quiet(self, capsys):
        """Kept: an answer is a pass, and says nothing at ERROR."""
        result = preflight.check_gemini_transport(_FakeClient())

        assert result.passed is True
        assert "ERROR" not in capsys.readouterr().err
