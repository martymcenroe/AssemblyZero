"""The gate's one retry escalates instead of re-asking the same model (#2375).

#2290 gave the requirements gate a retry for a timeout on a healthy transport,
and that retry re-asked the SAME model. Measured 2026-08-14 on boostgauge #1's
converted body: claude sonnet timed out at the 600s bound three consecutive
times (13:0x, 13:4x, 14:2x Central), and claude opus returned a CLEAN verdict
inside the same bound on its first attempt immediately afterwards. A trivial
`claude -p` round-tripped in 5.0s between attempts, so the transport was
healthy throughout, and the same sonnet call had completed boostgauge #7 -- a
comparable-size, comparably-tabled document -- in about five minutes that
morning.

The model is the variable on this content class. A same-model retry therefore
spends a second full 600s budget to reach the same wall; escalating costs the
same one retry and has a measured chance of returning a verdict.

Every precondition #2290 set on the retry is unchanged, and is re-asserted here
rather than assumed -- a fix that quietly widened when the gate retries would be
a different and worse change.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from assemblyzero.core.llm_provider import LLMCallResult  # noqa: E402
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (  # noqa: E402
    GATE_DRAFTER_ESCALATION,
    analyze_requirements,
    escalated_drafter,
)

BOOSTGAUGE_1 = ROOT / "tests" / "fixtures" / "requirements" / "boostgauge-1-body.md"

CONSISTENT = '{"is_consistent": true, "conflicts": []}'


def _result(success, response, error=None):
    return LLMCallResult(
        success=success,
        response=response,
        raw_response=response,
        error_message=error,
        provider="fake",
        model_used="fake-model",
        duration_ms=1,
        attempts=1,
    )


TIMEOUT = _result(False, None, "claude -p timed out after 600s")
OK = _result(True, CONSISTENT)
OTHER_FAILURE = _result(False, None, "400 invalid request")


class _Provider:
    """Returns a scripted sequence, one entry per call."""

    def __init__(self, *results):
        self._results = list(results)
        self.calls: list[dict] = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return self._results[min(len(self.calls) - 1, len(self._results) - 1)]


@pytest.fixture
def specs(monkeypatch):
    """Install a provider and record every spec `get_provider` is asked for.

    Recording the spec is the whole point: the retry must ask for a DIFFERENT
    model, and a factory that ignores its argument cannot show that.
    """

    def _install(*results, raises_for=()):
        provider = _Provider(*results)
        asked: list[str] = []

        def _factory(spec, *args, **kwargs):
            asked.append(spec)
            if spec in raises_for:
                raise ValueError(f"unknown provider spec: {spec}")
            return provider

        monkeypatch.setattr(
            "assemblyzero.core.llm_provider.get_provider", _factory
        )
        return asked, provider

    return _install


@pytest.fixture
def calm(monkeypatch):
    """A healthy transport: no provider storm in progress."""
    monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: False)


@pytest.fixture
def storm(monkeypatch):
    monkeypatch.setattr("assemblyzero.core.provider_storm.is_storm", lambda: True)


def _state(tmp_path, drafter):
    return {
        "issue_title": "feat: gauge rendering",
        "issue_body": "The renderer shall draw the needle at the value's angle.",
        "issue_number": 1,
        "target_repo": str(tmp_path),
        "config_drafter": drafter,
    }


class TestTheRetryEscalates:
    def test_a_sonnet_timeout_retries_on_opus(self, tmp_path, specs, calm):
        asked, provider = specs(TIMEOUT, OK)

        analyze_requirements(_state(tmp_path, "claude:sonnet"))

        assert asked == ["claude:sonnet", "claude:opus"]
        assert len(provider.calls) == 2

    def test_the_lookup_tolerates_case_and_surrounding_space(
        self, tmp_path, specs, calm
    ):
        asked, _ = specs(TIMEOUT, OK)
        analyze_requirements(_state(tmp_path, " Claude:Sonnet "))
        assert asked[1] == "claude:opus"

    def test_a_drafter_with_no_escalation_still_retries_itself(
        self, tmp_path, specs, calm
    ):
        """#2290's behaviour survives wherever no measurement replaces it.
        Inventing a ladder for every spec is the guessing #2375 forbids."""
        asked, provider = specs(TIMEOUT, OK)

        analyze_requirements(_state(tmp_path, "fake:model"))

        # The provider object is reused rather than rebuilt -- exactly what
        # #2290 did. The retry is visible in the call count, not in a second
        # trip through the factory.
        assert asked == ["fake:model"]
        assert len(provider.calls) == 2

    def test_a_broken_escalation_target_falls_back_rather_than_losing_the_retry(
        self, tmp_path, specs, calm, monkeypatch
    ):
        """A bad map entry must not cost the run the attempt #2290 gave it."""
        # The package re-exports `analyze_requirements` as a FUNCTION, so a
        # dotted setattr target resolves to it rather than to the module.
        from importlib import import_module

        module = import_module(
            "assemblyzero.workflows.requirements.nodes.analyze_requirements"
        )
        monkeypatch.setattr(
            module, "GATE_DRAFTER_ESCALATION", {"claude:sonnet": "bogus:spec"}
        )
        asked, provider = specs(TIMEOUT, OK, raises_for=("bogus:spec",))

        analyze_requirements(_state(tmp_path, "claude:sonnet"))

        assert asked == ["claude:sonnet", "bogus:spec"]
        assert len(provider.calls) == 2, "the retry must still happen"


class TestWhatEscalationDoesNotChange:
    """The retry's preconditions are #2290's and stay #2290's."""

    def test_a_storm_still_suppresses_the_retry(self, tmp_path, specs, storm):
        asked, provider = specs(TIMEOUT, OK)

        analyze_requirements(_state(tmp_path, "claude:sonnet"))

        assert asked == ["claude:sonnet"]
        assert len(provider.calls) == 1, "escalating into a storm is still wrong"

    def test_a_non_timeout_failure_is_still_not_retried(self, tmp_path, specs, calm):
        asked, provider = specs(OTHER_FAILURE, OK)

        analyze_requirements(_state(tmp_path, "claude:sonnet"))

        assert asked == ["claude:sonnet"]
        assert len(provider.calls) == 1

    def test_a_first_attempt_that_succeeds_never_escalates(
        self, tmp_path, specs, calm
    ):
        asked, provider = specs(OK)

        analyze_requirements(_state(tmp_path, "claude:sonnet"))

        assert asked == ["claude:sonnet"]
        assert len(provider.calls) == 1

    def test_the_gate_still_fails_open_when_both_attempts_die(
        self, tmp_path, specs, calm
    ):
        """Protective, not load-bearing (#1899). Escalation does not make the
        gate able to kill a roll."""
        specs(TIMEOUT, TIMEOUT)

        assert analyze_requirements(_state(tmp_path, "claude:sonnet")) == {}


class TestTheVerdictNamesItsDrafter:
    """'The gate did not answer' and 'the gate did not answer ON SONNET' are
    different facts, and only the second tells the next reader whether
    escalating is worth trying."""

    def test_a_clean_verdict_names_the_model_that_gave_it(
        self, tmp_path, specs, calm, capsys
    ):
        specs(TIMEOUT, OK)
        analyze_requirements(_state(tmp_path, "claude:sonnet"))
        assert "Verdict from claude:opus." in capsys.readouterr().out

    def test_an_unescalated_clean_verdict_names_the_original(
        self, tmp_path, specs, calm, capsys
    ):
        specs(OK)
        analyze_requirements(_state(tmp_path, "gemini:3.1-pro"))
        assert "Verdict from gemini:3.1-pro." in capsys.readouterr().out

    def test_the_clean_marker_itself_is_unchanged(
        self, tmp_path, specs, calm, capsys
    ):
        """The pre-check asserts this sentence verbatim, so the drafter goes on
        its own line rather than into it."""
        from assemblyzero.workflows.requirements.precheck import CLEAN_MARKER

        specs(OK)
        analyze_requirements(_state(tmp_path, "claude:sonnet"))
        assert CLEAN_MARKER in capsys.readouterr().out

    def test_an_unavailable_verdict_names_the_model_that_actually_ran(
        self, tmp_path, specs, calm, capsys
    ):
        specs(TIMEOUT, TIMEOUT)
        analyze_requirements(_state(tmp_path, "claude:sonnet"))
        assert "analysis unavailable on claude:opus" in capsys.readouterr().out


class TestTheEscalationMap:
    def test_it_holds_the_measured_pair_and_nothing_invented(self):
        assert GATE_DRAFTER_ESCALATION == {"claude:sonnet": "claude:opus"}

    def test_an_unmapped_spec_returns_none(self):
        assert escalated_drafter("gemini:3.1-pro") is None
        assert escalated_drafter("") is None

    def test_the_strongest_model_maps_nowhere(self):
        assert escalated_drafter("claude:opus") is None, (
            "a self-map would be an infinite ladder dressed as a fix"
        )

    def test_no_entry_points_at_itself(self):
        for source, target in GATE_DRAFTER_ESCALATION.items():
            assert source != target

    def test_no_entry_forms_a_cycle(self):
        """One escalation, not a ladder: no target may itself be escalatable."""
        for target in GATE_DRAFTER_ESCALATION.values():
            assert escalated_drafter(target) is None


class TestTheDocumentThisWasMeasuredOn:
    """#2375's acceptance: a fixture pins the change against this document."""

    def test_the_converted_body_is_captured(self):
        assert BOOSTGAUGE_1.is_file(), (
            "boostgauge #1's converted body is the document the escalation was "
            "measured on; without it this fix is pinned to nothing"
        )

    def test_it_is_the_converted_form_not_the_prose_it_replaced(self):
        body = BOOSTGAUGE_1.read_text(encoding="utf-8")
        assert "## Requirements" in body
        assert "## Acceptance Criteria" in body
        assert "## State Variables and Ownership" in body, "the ADR 0228 table"

    def test_it_is_checker_clean_under_adr_0226_and_0228(self):
        """#2375 records it as checker-clean, so the timeout is not the document
        being malformed. Free and deterministic: no model call."""
        from assemblyzero.workflows.requirements import form_check as fc

        report = fc.check_form(BOOSTGAUGE_1.read_text(encoding="utf-8"))
        assert report.ok, [v.detail for v in report.violations]

    def test_it_still_carries_the_content_class_that_timed_out(self):
        """Dense tables and a revision history -- the reasoning surface #2375
        names. If a later edit strips them the fixture stops representing the
        case, and this says so rather than passing quietly."""
        body = BOOSTGAUGE_1.read_text(encoding="utf-8")
        rows = [ln for ln in body.splitlines() if ln.strip().startswith("|")]
        assert len(rows) >= 15, f"only {len(rows)} table rows"
        assert "revision history" in body.lower()
