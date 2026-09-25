"""Both seats run on agy (#3517).

Operator directive, 2026-09-24: Gemini (agy) drafts and validates, for the
LLD workflow and the implementation workflow; Claude is out of both seats.
The standalone tools' defaults now say so, matching the orchestrator's
(``orchestrator/config.py``) and the library's own (``requirements/config.py``),
and the reason recorded beside the orchestrator's defaults is no longer a
crash that does not reproduce (#3519).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGY = "gemini:3.1-pro"


class TestTheStandaloneDefaultsAreAgy:
    def test_the_lld_workflow_drafts_and_reviews_on_agy(self):
        from tools.run_requirements_workflow import parse_args

        args = parse_args(["--type", "lld", "--issue", "42"])

        assert (args.drafter, args.reviewer) == (AGY, AGY)

    def test_the_implementation_workflow_reviews_on_agy(self):
        """The implementation tool has one seat flag; the test-plan revisor
        reuses it (#1072), so the reviewer default covers both."""
        from tools.run_implement_from_lld import create_argument_parser

        args = create_argument_parser().parse_args(["--issue", "42"])

        assert args.reviewer == AGY

    def test_the_spec_workflow_drafts_and_reviews_on_agy(self):
        from tools.run_implementation_spec_workflow import parse_args

        args = parse_args(["--issue", "42"])

        assert (args.drafter, args.reviewer) == (AGY, AGY)

    def test_the_defaults_match_the_orchestrator(self):
        from assemblyzero.workflows.orchestrator.config import get_default_config

        stages = get_default_config()["stages"]
        for stage in ("lld", "spec", "impl"):
            assert stages[stage]["drafter"] == AGY, stage
            assert stages[stage]["reviewer"] == AGY, stage

    def test_the_default_resolves_to_a_permitted_pro_model(self):
        from assemblyzero.core.config import FORBIDDEN_MODELS
        from assemblyzero.core.llm_provider import GeminiProvider, parse_provider_spec

        provider, model = parse_provider_spec(AGY)
        model_id = GeminiProvider.MODEL_MAP[model]

        assert provider == "gemini"
        assert "pro" in model_id
        assert "flash" not in model_id
        assert model_id not in FORBIDDEN_MODELS

    def test_an_override_to_claude_still_parses(self):
        from tools.run_requirements_workflow import parse_args

        args = parse_args([
            "--type", "lld", "--issue", "42",
            "--drafter", "claude:sonnet", "--reviewer", "claude:opus",
        ])

        assert (args.drafter, args.reviewer) == ("claude:sonnet", "claude:opus")


class TestTheReasonOnRecord:
    """#3519: the orchestrator's Gemini defaults were justified by #1431, a
    crash that did not reproduce on haiku or opus on 2026-09-24. The comment
    no longer cites it as the standing reason, and the two ADRs the directive
    was ruled against are Accepted."""

    def test_the_orchestrator_config_no_longer_rests_on_the_crash(self):
        source = (
            ROOT / "assemblyzero" / "workflows" / "orchestrator" / "config.py"
        ).read_text(encoding="utf-8")

        assert "remains the reason" not in source
        assert "#3519" in source
        assert "#3517" in source

    def test_the_two_adrs_are_accepted(self):
        for name in (
            "0232-nested-claude-calls-load-no-user-hooks.md",
            "0233-agy-tool-execution-posture.md",
        ):
            lines = (ROOT / "docs" / "adrs" / name).read_text(encoding="utf-8").splitlines()
            status = next(line for line in lines if line.startswith("**Status:**"))
            assert status.startswith("**Status:** Accepted"), (name, status)
