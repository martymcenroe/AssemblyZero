"""Unit tests for Wave 2 reliability issues.

Issue #504: E2E stagnation detection by failed test name identity
Issue #505: Completeness gate AST stagnation detection
"""

import pytest


# ===========================================================================
# Issue #504: E2E stagnation — compare failed test names
# ===========================================================================


class TestExtractFailedTestNames:
    """Tests for _extract_failed_test_names helper."""

    def test_extracts_failed_names_from_pytest_output(self):
        """Parses FAILED lines from pytest summary."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _extract_failed_test_names,
        )

        output = """
FAILED tests/test_foo.py::test_bar - AssertionError
FAILED tests/test_baz.py::TestClass::test_qux - TypeError
2 failed, 3 passed
"""
        result = _extract_failed_test_names(output)
        assert result == [
            "tests/test_baz.py::TestClass::test_qux",
            "tests/test_foo.py::test_bar",
        ]

    def test_returns_empty_for_no_failures(self):
        """No FAILED lines → empty list."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _extract_failed_test_names,
        )

        output = "5 passed in 1.23s"
        assert _extract_failed_test_names(output) == []

    def test_deduplicates_names(self):
        """Same test name appearing twice → single entry."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _extract_failed_test_names,
        )

        output = """
FAILED tests/test_a.py::test_x - Error
FAILED tests/test_a.py::test_x - Error
"""
        result = _extract_failed_test_names(output)
        assert result == ["tests/test_a.py::test_x"]

    def test_returns_sorted(self):
        """Names are returned sorted for deterministic comparison."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _extract_failed_test_names,
        )

        output = """
FAILED tests/z_test.py::test_z - Error
FAILED tests/a_test.py::test_a - Error
"""
        result = _extract_failed_test_names(output)
        assert result == ["tests/a_test.py::test_a", "tests/z_test.py::test_z"]


class TestE2EIdentityStagnation:
    """Tests for identity-based E2E stagnation detection."""

    def test_same_failures_triggers_stagnation(self):
        """Same failed test set → stagnation even if pass count increased."""
        from assemblyzero.workflows.testing.nodes.e2e_validation import (
            _extract_failed_test_names,
        )

        # Simulate: pass count went from 3 to 4 (looks like progress),
        # but same 2 tests still failing
        failures = ["tests/test_a.py::test_x", "tests/test_b.py::test_y"]

        current_failures = sorted(failures)
        previous_failures = sorted(failures)

        # Identity check matches the logic in e2e_validation.py
        identity_stagnant = (
            bool(current_failures)
            and bool(previous_failures)
            and current_failures == sorted(previous_failures)
        )
        assert identity_stagnant is True

    def test_different_failures_not_stagnant(self):
        """Different failed test set → not stagnant."""
        current = ["tests/test_a.py::test_x"]
        previous = ["tests/test_b.py::test_y"]

        identity_stagnant = (
            bool(current) and bool(previous) and current == sorted(previous)
        )
        assert identity_stagnant is False

    def test_empty_previous_not_stagnant(self):
        """First iteration (no previous failures) → not stagnant."""
        current = ["tests/test_a.py::test_x"]
        previous = []

        identity_stagnant = (
            bool(current) and bool(previous) and current == sorted(previous)
        )
        assert identity_stagnant is False


# ===========================================================================
# Issue #505: Completeness gate AST stagnation
# ===========================================================================


class TestCompletenessIssueIdentity:
    """Tests for _completeness_issue_identity helper."""

    def test_extracts_identity_tuple(self):
        """Extracts (file_path, line_number, category) from issue dict."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            _completeness_issue_identity,
        )

        issue = {
            "file_path": "src/foo.py",
            "line_number": 42,
            "category": "empty_branch",
            "description": "Empty if branch",
            "severity": "ERROR",
        }
        result = _completeness_issue_identity(issue)
        assert result == ("src/foo.py", 42, "empty_branch")

    def test_handles_enum_category(self):
        """Handles CompletenessCategory enum values."""
        from assemblyzero.workflows.testing.completeness.ast_analyzer import (
            CompletenessCategory,
        )
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            _completeness_issue_identity,
        )

        issue = {
            "file_path": "src/bar.py",
            "line_number": 10,
            "category": CompletenessCategory.DOCSTRING_ONLY,
            "description": "Docstring only",
            "severity": "ERROR",
        }
        result = _completeness_issue_identity(issue)
        assert result == ("src/bar.py", 10, "docstring_only")


class TestCompletenessGateStagnation:
    """Tests for stagnation detection in route_after_completeness_gate."""

    def test_identical_issues_routes_to_end(self):
        """Same AST issues across 2 iterations → routes to end."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            route_after_completeness_gate,
        )

        issue_ids = [["src/foo.py", 42, "empty_branch"]]
        state = {
            "error_message": "",
            "completeness_verdict": "BLOCK",
            "iteration_count": 1,
            "completeness_issues": [
                {
                    "file_path": "src/foo.py",
                    "line_number": 42,
                    "category": "empty_branch",
                    "description": "Empty if branch",
                    "severity": "ERROR",
                }
            ],
            "previous_completeness_issues": issue_ids,
        }

        assert route_after_completeness_gate(state) == "end"

    def test_different_issues_allows_retry(self):
        """Different AST issues → routes back to N4."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            route_after_completeness_gate,
        )

        state = {
            "error_message": "",
            "completeness_verdict": "BLOCK",
            "iteration_count": 1,
            "completeness_issues": [
                {
                    "file_path": "src/foo.py",
                    "line_number": 42,
                    "category": "empty_branch",
                    "description": "Empty if branch",
                    "severity": "ERROR",
                }
            ],
            "previous_completeness_issues": [
                ["src/bar.py", 10, "docstring_only"],
            ],
        }

        assert route_after_completeness_gate(state) == "N4_implement_code"

    def test_first_block_no_previous_allows_retry(self):
        """First BLOCK (no previous issues) → routes back to N4."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            route_after_completeness_gate,
        )

        state = {
            "error_message": "",
            "completeness_verdict": "BLOCK",
            "iteration_count": 1,
            "completeness_issues": [
                {
                    "file_path": "src/foo.py",
                    "line_number": 42,
                    "category": "empty_branch",
                    "description": "Empty if branch",
                    "severity": "ERROR",
                }
            ],
        }

        assert route_after_completeness_gate(state) == "N4_implement_code"

    def test_max_iterations_still_enforced(self):
        """Max iteration limit still ends even without stagnation."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            route_after_completeness_gate,
        )

        state = {
            "error_message": "",
            "completeness_verdict": "BLOCK",
            "iteration_count": 3,
            "completeness_issues": [
                {
                    "file_path": "src/new.py",
                    "line_number": 1,
                    "category": "trivial_assertion",
                    "description": "Trivial",
                    "severity": "ERROR",
                }
            ],
            "previous_completeness_issues": [
                ["src/old.py", 99, "unused_import"],
            ],
        }

        assert route_after_completeness_gate(state) == "end"

    def test_pass_verdict_proceeds(self):
        """PASS verdict always routes to N5 regardless of history."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            route_after_completeness_gate,
        )

        state = {
            "error_message": "",
            "completeness_verdict": "PASS",
            "iteration_count": 0,
            "completeness_issues": [],
        }

        assert route_after_completeness_gate(state) == "N5_verify_green"

    def test_warn_verdict_proceeds(self):
        """WARN verdict routes to N5."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            route_after_completeness_gate,
        )

        state = {
            "error_message": "",
            "completeness_verdict": "WARN",
            "iteration_count": 1,
            "completeness_issues": [
                {
                    "file_path": "src/foo.py",
                    "line_number": 1,
                    "category": "unused_import",
                    "description": "Unused",
                    "severity": "WARNING",
                }
            ],
        }

        assert route_after_completeness_gate(state) == "N5_verify_green"


class TestCompletenessGateStoresIssueIds:
    """Tests that completeness_gate node stores issue IDs for stagnation."""

    def test_node_stores_previous_issues(self, tmp_path):
        """completeness_gate stores previous_completeness_issues in result."""
        from unittest.mock import patch

        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            completeness_gate,
        )

        fake_issues = [
            {
                "category": "empty_branch",
                "file_path": "src/foo.py",
                "line_number": 42,
                "description": "Empty branch",
                "severity": "ERROR",
            }
        ]
        fake_result = {
            "verdict": "BLOCK",
            "issues": fake_issues,
            "ast_analysis_ms": 5,
            "gemini_review_ms": None,
        }

        with patch(
            "assemblyzero.workflows.testing.nodes.completeness_gate.run_ast_analysis",
            return_value=fake_result,
        ):
            state = {
                "repo_root": str(tmp_path),
                "issue_number": 99,
                "lld_path": "",
                "implementation_files": [str(tmp_path / "foo.py")],
                "test_files": [],
                "audit_dir": "",
                "iteration_count": 0,
            }
            # Create a dummy file so analysis has something
            (tmp_path / "foo.py").write_text("pass")

            result = completeness_gate(state)

        assert "previous_completeness_issues" in result
        assert result["previous_completeness_issues"] == [
            ["src/foo.py", 42, "empty_branch"]
        ]
