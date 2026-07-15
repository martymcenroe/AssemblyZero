"""Tests for edit-script spec revisions (Closes #1528).

Measured failure this fixes (boostgauge#96 hardening runs 4-5, data on
#1529): spec revisions were full regenerations — 1,149 → 341 → 1,407
lines across iterations. Edit blocks applied mechanically make unflagged
drift impossible by construction.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    apply_edit_blocks,
    build_edit_script_prompt,
    parse_edit_blocks,
    unchanged_ratio,
)

SPEC = """# Implementation Spec: Config

## Functions

### load_config()
Loads the config.

### validate_config()
Validates the config.

## Test Plan

- test_load_config
"""


def _block(search: str, replace: str) -> str:
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE"


class TestParseEditBlocks:
    def test_single_block(self):
        response = _block("### load_config()", "### load_config(path)")
        blocks = parse_edit_blocks(response)
        assert blocks == [("### load_config()", "### load_config(path)")]

    def test_multiple_blocks(self):
        response = (
            _block("a", "b") + "\n\n" + _block("c\nd", "c\nd\ne")
        )
        blocks = parse_edit_blocks(response)
        assert len(blocks) == 2
        assert blocks[1] == ("c\nd", "c\nd\ne")

    def test_prose_response_yields_no_blocks(self):
        assert parse_edit_blocks("Here is the revised spec:\n# Spec\n...") == []

    def test_malformed_block_ignored(self):
        # Missing the ======= divider
        response = "<<<<<<< SEARCH\nfoo\n>>>>>>> REPLACE"
        assert parse_edit_blocks(response) == []

    def test_whole_response_fence_unwrapped(self):
        response = "```\n" + _block("x", "y") + "\n```"
        assert parse_edit_blocks(response) == [("x", "y")]

    def test_empty_response(self):
        assert parse_edit_blocks("") == []


class TestApplyEditBlocks:
    def test_single_edit_applies(self):
        patched, failures = apply_edit_blocks(
            SPEC, [("Loads the config.", "Loads the config from disk.")]
        )
        assert failures == []
        assert "Loads the config from disk." in patched
        # Everything else untouched
        assert "### validate_config()" in patched

    def test_insertion_via_anchor(self):
        patched, failures = apply_edit_blocks(
            SPEC,
            [(
                "- test_load_config",
                "- test_load_config\n- test_validate_config",
            )],
        )
        assert failures == []
        assert "- test_validate_config" in patched

    def test_sequential_edits_see_prior_results(self):
        patched, failures = apply_edit_blocks(
            SPEC,
            [
                ("Loads the config.", "Loads the config quickly."),
                ("Loads the config quickly.", "Loads the config very quickly."),
            ],
        )
        assert failures == []
        assert "very quickly" in patched

    def test_search_not_found_reports_failure(self):
        patched, failures = apply_edit_blocks(SPEC, [("nonexistent text", "x")])
        assert len(failures) == 1
        assert "not found" in failures[0]

    def test_ambiguous_search_reports_failure(self):
        text = "line\nline\n"
        patched, failures = apply_edit_blocks(text, [("line", "other")])
        assert len(failures) == 1
        assert "ambiguous" in failures[0]

    def test_unchanged_content_is_byte_identical(self):
        """The core #1528 guarantee: content not named in a SEARCH block
        survives exactly — drift is structurally impossible."""
        patched, failures = apply_edit_blocks(
            SPEC, [("Validates the config.", "Validates the config strictly.")]
        )
        assert failures == []
        untouched = SPEC.replace("Validates the config.", "")
        for line in untouched.splitlines():
            if line.strip():
                assert line in patched


class TestUnchangedRatio:
    def test_identical_is_one(self):
        assert unchanged_ratio(SPEC, SPEC) == 1.0

    def test_full_rewrite_is_low(self):
        assert unchanged_ratio(SPEC, "totally different\ncontent\n") < 0.2

    def test_small_edit_is_high(self):
        patched, _ = apply_edit_blocks(
            SPEC, [("Loads the config.", "Loads it.")]
        )
        assert unchanged_ratio(SPEC, patched) > 0.85


class TestBuildEditScriptPrompt:
    def test_prompt_carries_deficiencies_and_draft(self):
        prompt = build_edit_script_prompt(
            existing_draft=SPEC,
            review_feedback="Section X is vague.",
            completeness_issues=["Functions missing input/output examples: f()"],
            prior_completeness_breakdown=[{"iteration": 1, "failures": ["y"]}],
        )
        assert "<<<<<<< SEARCH" in prompt
        assert "Functions missing input/output examples" in prompt
        assert "Section X is vague." in prompt
        assert "Iteration 1" in prompt
        assert SPEC in prompt
        assert "Touch NOTHING else" in prompt


class TestGenerateSpecEditScriptIntegration:
    """The revision path tries edit-script first and falls back safely."""

    def _base_revision_state(self, tmp_path):
        return {
            "issue_number": 7,
            "assemblyzero_root": str(tmp_path),
            "repo_root": str(tmp_path),
            "spec_draft": SPEC,
            "completeness_issues": ["Functions missing examples: f()"],
            "review_feedback": "",
            "review_iteration": 1,
            "max_iterations": 3,
            "config_mock_mode": False,
            "config_drafter": "gemini:3.1-pro",
            "lld_content": "# LLD",
            "audit_dir": "",
        }

    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.check_spec_size_or_raise", create=True)
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template")
    @patch("assemblyzero.core.preflight.check_gemini_available")
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider")
    def test_edit_blocks_patch_without_regeneration(
        self, mock_get_provider, mock_preflight, mock_template, _sz, tmp_path
    ):
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec

        mock_template.return_value = "# Template"
        mock_preflight.return_value = Mock(
            passed=True, available_credentials=4, total_credentials=4, warnings=[]
        )
        drafter = MagicMock()
        drafter.invoke.return_value = Mock(
            success=True,
            response=_block("Loads the config.", "Loads the config from disk."),
            error_message=None,
            input_tokens=10,
            output_tokens=5,
        )
        mock_get_provider.return_value = drafter

        result = generate_spec(self._base_revision_state(tmp_path))

        assert result["error_message"] == ""
        assert "Loads the config from disk." in result["spec_draft"]
        # Unflagged content preserved byte-identical
        assert "### validate_config()" in result["spec_draft"]
        # Only ONE LLM call — the edit-script call; no regeneration
        assert drafter.invoke.call_count == 1

    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template")
    @patch("assemblyzero.core.preflight.check_gemini_available")
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider")
    def test_prose_response_falls_back_to_full_revision(
        self, mock_get_provider, mock_preflight, mock_template, tmp_path
    ):
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec

        mock_template.return_value = "# Template"
        mock_preflight.return_value = Mock(
            passed=True, available_credentials=4, total_credentials=4, warnings=[]
        )
        drafter = MagicMock()
        drafter.invoke.side_effect = [
            Mock(  # edit-script attempt: prose, no blocks
                success=True, response="I rewrote the spec:\n# Spec v2\n...",
                error_message=None, input_tokens=1, output_tokens=1,
            ),
            Mock(  # classic full-revision call
                success=True, response="# Spec v2 (classic)\n\ncontent",
                error_message=None, input_tokens=1, output_tokens=1,
            ),
        ]
        mock_get_provider.return_value = drafter

        result = generate_spec(self._base_revision_state(tmp_path))

        assert result["error_message"] == ""
        assert result["spec_draft"].startswith("# Spec v2 (classic)")
        assert drafter.invoke.call_count == 2

    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.load_template")
    @patch("assemblyzero.core.preflight.check_gemini_available")
    @patch("assemblyzero.workflows.implementation_spec.nodes.generate_spec.get_provider")
    def test_unmatched_search_falls_back(
        self, mock_get_provider, mock_preflight, mock_template, tmp_path
    ):
        from assemblyzero.workflows.implementation_spec.nodes.generate_spec import generate_spec

        mock_template.return_value = "# Template"
        mock_preflight.return_value = Mock(
            passed=True, available_credentials=4, total_credentials=4, warnings=[]
        )
        drafter = MagicMock()
        drafter.invoke.side_effect = [
            Mock(  # edit-script attempt: block whose SEARCH isn't verbatim
                success=True,
                response=_block("text that is not in the spec", "replacement"),
                error_message=None, input_tokens=1, output_tokens=1,
            ),
            Mock(
                success=True, response="# Spec v3 (classic)\n\ncontent",
                error_message=None, input_tokens=1, output_tokens=1,
            ),
        ]
        mock_get_provider.return_value = drafter

        result = generate_spec(self._base_revision_state(tmp_path))

        assert result["error_message"] == ""
        assert result["spec_draft"].startswith("# Spec v3 (classic)")
        assert drafter.invoke.call_count == 2