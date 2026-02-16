"""TDD tests for CLI --review syntax standardization.

Issue #122: Reconcile --auto vs --gates syntax across workflows.
Updated for --gates → --review refactoring.

These tests verify:
1. --review argument works with all valid choices
2. --auto is deprecated but still works (maps to --review none)
3. --gates is deprecated but still works (maps to --review)
4. Deprecation warning is printed when --auto or --gates is used
"""

import argparse
import io
import sys
from contextlib import redirect_stderr
from unittest.mock import patch

import pytest


class TestImplementFromLLDReviewSyntax:
    """Tests for run_implement_from_lld.py --review argument."""

    def test_review_none_sets_auto_mode(self):
        """--review none should set auto_mode=True."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--review", "none"])

        apply_review_config(args)

        assert args.review == "none"
        assert args.auto_mode is True

    def test_review_all_disables_auto_mode(self):
        """--review all should set auto_mode=False (interactive mode)."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--review", "all"])

        apply_review_config(args)

        assert args.review == "all"
        assert args.auto_mode is False

    def test_review_default_is_none(self):
        """Default --review value should be 'none' (auto mode)."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42"])

        apply_review_config(args)

        assert args.review == "none"
        assert args.auto_mode is True

    def test_auto_flag_deprecated_but_works(self):
        """--auto should work but print deprecation warning."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--auto"])

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            apply_review_config(args)

        # Should map to review=none
        assert args.review == "none"
        assert args.auto_mode is True

        # Should print deprecation warning
        warning = stderr.getvalue()
        assert "deprecated" in warning.lower()

    def test_review_choices_are_valid(self):
        """--review should only accept valid choices."""
        from tools.run_implement_from_lld import create_argument_parser

        parser = create_argument_parser()

        # Valid choices should work
        for choice in ["none", "draft", "verdict", "all"]:
            args = parser.parse_args(["--issue", "42", "--review", choice])
            assert args.review == choice

        # Invalid choice should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["--issue", "42", "--review", "invalid"])


class TestReviewConfigIntegration:
    """Integration tests for review configuration."""

    def test_review_draft_enables_only_draft_gate(self):
        """--review draft should enable draft gate only."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--review", "draft"])

        apply_review_config(args)

        assert args.gates_draft is True
        assert args.gates_verdict is False

    def test_review_verdict_enables_only_verdict_gate(self):
        """--review verdict should enable verdict gate only."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--review", "verdict"])

        apply_review_config(args)

        assert args.gates_draft is False
        assert args.gates_verdict is True

    def test_review_all_enables_all_gates(self):
        """--review all should enable both gates."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--review", "all"])

        apply_review_config(args)

        assert args.gates_draft is True
        assert args.gates_verdict is True

    def test_review_none_disables_all_gates(self):
        """--review none should disable all gates."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--review", "none"])

        apply_review_config(args)

        assert args.gates_draft is False
        assert args.gates_verdict is False


class TestDeprecatedGatesFlag:
    """Tests for deprecated --gates flag backwards compatibility."""

    def test_gates_deprecated_maps_to_review(self):
        """--gates should work as deprecated alias for --review."""
        from tools.run_implement_from_lld import create_argument_parser, apply_review_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "all"])

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            apply_review_config(args)

        # Should map to review=all
        assert args.review == "all"
        assert args.auto_mode is False

        # Should print deprecation warning
        warning = stderr.getvalue()
        assert "deprecated" in warning.lower()
