"""The requirements-ambiguity gate (N0c) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). The gate
has three outcomes and no fourth: verified consistent proceeds, a reproduced
conflict halts for a ruling, and anything else halts as REQUIREMENTS
UNVERIFIED. The last fail-open path, a verdict whose every conflict the model
could not articulate, now halts unverified rather than proceeding; an empty
issue body and a bad escalation seat halt the same way. A failed telemetry
record or must-resolve filing alerts the operator on its own, since the halt
it rides with does not name it.
"""
from __future__ import annotations

import importlib
import inspect
import json

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.graph import route_after_analyze_requirements

ar = importlib.import_module("assemblyzero.workflows.requirements.nodes.analyze_requirements")

GOOD = {
    "criterion_a": "floor = highest value still in the window",
    "criterion_b": "floor drifts toward the most recent value",
    "diverging_situation": "when the window maximum is not the latest sample",
}
CONFLICT = json.dumps({"is_consistent": False, "conflicts": [GOOD]})
CLEAN = json.dumps({"is_consistent": True, "conflicts": []})
UNARTICULATED = json.dumps({"is_consistent": False, "conflicts": [
    {"criterion_a": GOOD["criterion_a"], "criterion_b": GOOD["criterion_b"],
     "diverging_situation": "?"},
]})


def _result(response: str = "", success: bool = True, error: str | None = None):
    return LLMCallResult(
        success=success, response=response, raw_response=response,
        error_message=error, provider="fake", model_used="fake-model",
        duration_ms=1, attempts=1,
    )


class _Provider:
    def __init__(self, *results):
        self._results = list(results)
        self.calls = 0

    def invoke(self, **kwargs):
        self.calls += 1
        return self._results.pop(0)


@pytest.fixture
def gate(monkeypatch, tmp_path):
    """The live node with its outward calls recorded instead of made."""
    seen = {"filed": [], "telemetry": []}
    monkeypatch.setattr(
        "assemblyzero.speedrun.must_resolve.file_all_conflicts",
        lambda repo, issue, conflicts, **k: seen["filed"].extend(conflicts),
    )
    monkeypatch.setattr(
        "assemblyzero.speedrun.prompt_telemetry.record_failures",
        lambda *a, **k: seen["telemetry"].append(a),
    )
    monkeypatch.setattr("assemblyzero.speedrun.must_resolve.run_context", lambda: ("run-1", None))
    monkeypatch.setattr(ar, "_sleep", lambda seconds: None)

    def run(*results, **overrides):
        provider = _Provider(*results)
        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", lambda spec, *a, **k: provider,
        )
        state = {
            "issue_title": "t", "issue_body": "some requirement text",
            "issue_number": 332, "target_repo": str(tmp_path),
        }
        state.update(overrides)
        out = ar.analyze_requirements(state)
        seen["calls"] = provider.calls
        return out

    seen["run"] = run
    return seen


def _halts_unverified(out: dict) -> bool:
    return (
        bool(out.get("requirements_unverified"))
        and ar.REQUIREMENTS_UNVERIFIED_MARKER in out.get("error_message", "")
        and route_after_analyze_requirements(out) == "HALT"
    )


class TestParse:
    @pytest.mark.parametrize("finding", ["a bare string", 7, None, ["a", "b"]])
    def test_333_a_finding_that_is_not_an_object_is_no_verdict(self, finding):
        raw = json.dumps({"is_consistent": True, "conflicts": [GOOD, finding]})
        assert ar._parse_analysis(raw) is None

    def test_333_such_a_verdict_is_retried_then_halts_unverified(self, gate):
        bad = json.dumps({"is_consistent": True, "conflicts": ["x"]})
        out = gate["run"](_result(bad), _result(bad), _result(bad))

        assert _halts_unverified(out)
        assert gate["calls"] == 3

    def test_333_kept_an_empty_findings_list_is_a_clean_verdict(self):
        assert ar._parse_analysis(CLEAN)["conflicts"] == []


class TestStormProbe:
    def test_371_a_probe_that_raises_is_said_and_raised(self, monkeypatch, capsys):
        def broken():
            raise RuntimeError("storm counter unreadable")

        monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", broken)
        with pytest.raises(RuntimeError, match="storm counter unreadable"):
            ar._provider_storm_active()
        assert "ERROR" in capsys.readouterr().err

    def test_371_kept_a_calm_provider_reads_false(self, monkeypatch):
        monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: False)
        assert ar._provider_storm_active() is False


class TestUnverifiedRecord:
    def test_399_and_407_the_record_that_swallowed_its_failures_is_gone(self):
        """Nothing proceeds without a verdict any more (727), so nothing writes
        the 'proceeded anyway' record, and the helper that swallowed a failed
        run_context (399) and a failed write (407) is deleted."""
        assert not hasattr(ar, "_record_unverified")


class TestEmptyBody:
    @pytest.mark.parametrize("body", ["", "   \n\t"])
    def test_561_an_empty_issue_body_halts_unverified(self, gate, body):
        out = gate["run"](issue_body=body)

        assert _halts_unverified(out)
        assert gate["calls"] == 0
        assert "# fail-open:" not in inspect.getsource(ar.analyze_requirements)

    def test_561_kept_a_mock_run_reads_nothing(self, gate):
        assert gate["run"](issue_body="", config_mock_mode=True) == {}


class TestEscalation:
    def test_643_a_bad_escalation_seat_halts_unverified_naming_it(self, gate, monkeypatch):
        from assemblyzero.core import seats

        real_resolve = seats.resolve

        class _Seat:
            def __init__(self, spec):
                self.spec = spec
                self.effort = ""

        calls = {"n": 0}

        def resolve(state, seat):
            if seat == "requirements.analyze.escalation":
                calls["n"] += 1
                if calls["n"] > 1:
                    raise ValueError("no provider named bogus")
                return _Seat("bogus:model")
            return real_resolve(state, seat)

        monkeypatch.setattr(seats, "resolve", resolve)
        monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: False)
        out = gate["run"](_result(success=False, error="claude -p timed out after 600s"))

        assert _halts_unverified(out)
        assert "bogus:model" in out["error_message"]
        assert "no provider named bogus" in out["error_message"]
        assert gate["calls"] == 1


class TestUnarticulated:
    def test_727_every_conflict_unarticulated_halts_unverified(self, gate):
        out = gate["run"](_result(UNARTICULATED))

        assert _halts_unverified(out)
        assert gate["filed"] == []
        assert GOOD["criterion_a"] in out["error_message"]


class TestConfirmingAsk:
    def test_763_a_confirming_ask_that_fails_names_its_cause(self, gate):
        out = gate["run"](_result(CONFLICT), _result(success=False, error="HTTP 529 overloaded"))

        assert ar.REQUIREMENTS_CONFLICT_MARKER in out["error_message"]
        assert "HTTP 529 overloaded" in out["error_message"]

    def test_779_kept_a_conflict_that_does_not_reproduce_proceeds(self, gate):
        """Fixed in #3767: not a failure path; both asks answered."""
        assert gate["run"](_result(CONFLICT), _result(CLEAN)) == {}


class TestRecordsBesideTheHalt:
    def test_814_a_failed_telemetry_record_alerts_and_the_halt_stands(
        self, gate, monkeypatch, operator_alerts
    ):
        def broken(*a, **k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr("assemblyzero.speedrun.prompt_telemetry.record_failures", broken)
        out = gate["run"](_result(CONFLICT), _result(CONFLICT))

        assert ar.REQUIREMENTS_CONFLICT_MARKER in out["error_message"]
        assert len(operator_alerts) == 1
        assert "No space left on device" in operator_alerts[0]["cause"]
        assert len(gate["filed"]) == 1

    def test_825_a_failed_filing_alerts_naming_the_repo_and_issue(
        self, gate, monkeypatch, operator_alerts, tmp_path
    ):
        def broken(*a, **k):
            raise RuntimeError("gh issue create: HTTP 403")

        monkeypatch.setattr("assemblyzero.speedrun.must_resolve.file_all_conflicts", broken)
        out = gate["run"](_result(CONFLICT), _result(CONFLICT))

        assert ar.REQUIREMENTS_CONFLICT_MARKER in out["error_message"]
        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert "HTTP 403" in alert["cause"]
        assert "#332" in alert["what"]
        assert str(tmp_path) in alert["what"]


def test_no_fail_open_tag_remains_in_analyze_requirements():
    assert "# fail-open:" not in inspect.getsource(ar)
