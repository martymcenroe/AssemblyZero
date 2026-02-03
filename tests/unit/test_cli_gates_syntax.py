"""TDD tests for CLI --gates syntax standardization.

Issue #122: Reconcile --auto vs --gates syntax across workflows.

These tests verify:
1. --gates argument works with all valid choices
2. --auto is deprecated but still works (maps to --gates none)
3. Deprecation warning is printed when --auto is used
"""

import argparse
import io
import sys
from contextlib import redirect_stderr
from unittest.mock import patch

import pytest


class TestImplementFromLLDGatesSyntax:
    """Tests for run_implement_from_lld.py --gates argument."""

    def test_gates_none_sets_auto_mode(self):
        """--gates none should set auto_mode=True (same as old --auto)."""
        # Import the module's argument parser
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "none"])

        # Apply gates configuration
        apply_gates_config(args)

        assert args.gates == "none"
        assert args.auto_mode is True

    def test_gates_all_disables_auto_mode(self):
        """--gates all should set auto_mode=False (interactive mode)."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "all"])

        apply_gates_config(args)

        assert args.gates == "all"
        assert args.auto_mode is False

    def test_gates_default_is_all(self):
        """Default --gates value should be 'all' (interactive)."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42"])

        apply_gates_config(args)

        assert args.gates == "all"
        assert args.auto_mode is False

    def test_auto_flag_deprecated_but_works(self):
        """--auto should work but print deprecation warning."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--auto"])

        # Capture stderr for deprecation warning
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            apply_gates_config(args)

        # Should map to gates=none
        assert args.gates == "none"
        assert args.auto_mode is True

        # Should print deprecation warning
        warning = stderr.getvalue()
        assert "deprecated" in warning.lower()
        assert "--gates none" in warning

    def test_gates_choices_are_valid(self):
        """--gates should only accept valid choices."""
        from tools.run_implement_from_lld import create_argument_parser

        parser = create_argument_parser()

        # Valid choices should work
        for choice in ["none", "draft", "verdict", "all"]:
            args = parser.parse_args(["--issue", "42", "--gates", choice])
            assert args.gates == choice

        # Invalid choice should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["--issue", "42", "--gates", "invalid"])


class TestIssueWorkflowGatesSyntax:
    """Tests for run_issue_workflow.py --gates argument."""

    def test_gates_none_sets_auto_mode(self):
        """--gates none should set AGENTOS_AUTO_MODE=1."""
        from tools.run_issue_workflow import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--select", "--gates", "none"])

        # Apply gates configuration
        with patch.dict("os.environ", {}, clear=False):
            import os
            apply_gates_config(args)
            assert os.environ.get("AGENTOS_AUTO_MODE") == "1"

    def test_gates_all_disables_auto_mode(self):
        """--gates all should not set AGENTOS_AUTO_MODE."""
        from tools.run_issue_workflow import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--select", "--gates", "all"])

        with patch.dict("os.environ", {"AGENTOS_AUTO_MODE": ""}, clear=False):
            import os
            os.environ.pop("AGENTOS_AUTO_MODE", None)
            apply_gates_config(args)
            assert os.environ.get("AGENTOS_AUTO_MODE") != "1"

    def test_auto_flag_deprecated_but_works(self):
        """--auto should work but print deprecation warning."""
        from tools.run_issue_workflow import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--select", "--auto"])

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with patch.dict("os.environ", {}, clear=False):
                import os
                apply_gates_config(args)
                assert os.environ.get("AGENTOS_AUTO_MODE") == "1"

        # Should print deprecation warning
        warning = stderr.getvalue()
        assert "deprecated" in warning.lower()


class TestGatesConfigIntegration:
    """Integration tests for gates configuration across workflows."""

    def test_gates_draft_enables_only_draft_gate(self):
        """--gates draft should enable draft gate only."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "draft"])

        apply_gates_config(args)

        assert args.gates_draft is True
        assert args.gates_verdict is False

    def test_gates_verdict_enables_only_verdict_gate(self):
        """--gates verdict should enable verdict gate only."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "verdict"])

        apply_gates_config(args)

        assert args.gates_draft is False
        assert args.gates_verdict is True

    def test_gates_all_enables_all_gates(self):
        """--gates all should enable both gates."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "all"])

        apply_gates_config(args)

        assert args.gates_draft is True
        assert args.gates_verdict is True

    def test_gates_none_disables_all_gates(self):
        """--gates none should disable all gates."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        args = parser.parse_args(["--issue", "42", "--gates", "none"])

        apply_gates_config(args)

        assert args.gates_draft is False
        assert args.gates_verdict is False


class TestBackwardsCompatibility:
    """Tests ensuring backwards compatibility with --auto flag."""

    def test_auto_and_gates_mutual_exclusion_warning(self):
        """Using both --auto and --gates should warn and prefer --gates."""
        from tools.run_implement_from_lld import create_argument_parser, apply_gates_config

        parser = create_argument_parser()
        # Both flags specified - --gates should take precedence
        args = parser.parse_args(["--issue", "42", "--auto", "--gates", "all"])

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            apply_gates_config(args)

        # --gates should win over --auto
        assert args.gates == "all"
        assert args.auto_mode is False

        # Should warn about conflicting flags
        warning = stderr.getvalue()
        assert "conflict" in warning.lower() or "ignoring" in warning.lower() or "deprecated" in warning.lower()
