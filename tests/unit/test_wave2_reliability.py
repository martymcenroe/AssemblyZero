"""Unit tests for Wave 2 reliability issues.

Issue #504: E2E stagnation detection by failed test name identity
Issue #505: Completeness gate AST stagnation detection
"""



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

    def test_identical_issues_halt(self):
        """Same AST issues across 2 iterations: the node records why, and it routes to HALT.

        #3811: the stop used to route to END with no reason and no alert.
        """
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            _block_stop_reason,
            route_after_completeness_gate,
        )

        issue_ids = [["src/foo.py", 42, "empty_branch"]]
        reason = _block_stop_reason("BLOCK", issue_ids, issue_ids, 1, "issue #1")
        assert "stagnant" in reason and "the same 1 issue(s)" in reason

        state = {
            "error_message": reason,
            "completeness_verdict": "BLOCK",
            "iteration_count": 1,
        }
        assert route_after_completeness_gate(state) == "HALT"

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
        """The iteration cap stops the run even without stagnation, through HALT (#3811)."""
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            _block_stop_reason,
        )

        reason = _block_stop_reason(
            "BLOCK",
            [["src/new.py", 1, "trivial_assertion"]],
            [["src/old.py", 99, "unused_import"]],
            3,
            "issue #1",
        )
        assert "still BLOCK at iteration 3 (max 3)" in reason

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

        assert route_after_completeness_gate(state) == "N4_5_mechanical_hooks"

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

        assert route_after_completeness_gate(state) == "N4_5_mechanical_hooks"


class TestCompletenessGateStoresIssueIds:
    """The node and the router together, as a run uses them (#3852).

    The router-only tests above build state by hand, which is how a node that
    compared its own update with itself went unnoticed: every first BLOCK read
    as stagnant, and the N4 retry loop never ran.
    """

    def _run(self, tmp_path, **state_overrides):
        from unittest.mock import patch

        from assemblyzero.workflows.testing.completeness.ast_analyzer import (
            CompletenessCategory,
        )
        from assemblyzero.workflows.testing.nodes.completeness_gate import (
            completeness_gate,
            route_after_completeness_gate,
        )

        fake_issues = [
            {
                "category": CompletenessCategory.EMPTY_BRANCH,
                "file_path": "src/foo.py",
                "line_number": 42,
                "description": "Empty branch",
                "severity": "ERROR",
            }
        ]

        lld = tmp_path / "LLD-099.md"
        lld.write_text("# LLD\n\n## 3. Requirements\n\n1. foo exists\n")
        (tmp_path / "foo.py").write_text("pass")
        fake_result = {
            "verdict": "BLOCK",
            "issues": fake_issues,
            "ast_analysis_ms": 5,
            "gemini_review_ms": None,
        }
        state = {
            "repo_root": str(tmp_path),
            "issue_number": 99,
            "original_lld_path": str(lld),
            "implementation_files": [str(tmp_path / "foo.py")],
            "test_files": [],
            "audit_dir": "",
            "iteration_count": 1,
            # #2552: the gate refuses an empty requirement set before
            # any analysis; this test exercises the ordinary path.
            "requirements": ["REQ-1: foo exists"],
            **state_overrides,
        }
        with patch(
            "assemblyzero.workflows.testing.nodes.completeness_gate.run_ast_analysis",
            return_value=fake_result,
        ):
            result = completeness_gate(state)
        return result, route_after_completeness_gate({**state, **result})

    def test_node_stores_previous_issues(self, tmp_path):
        result, _ = self._run(tmp_path)
        assert result["previous_completeness_issues"] == [
            ["src/foo.py", 42, "empty_branch"]
        ]

    def test_a_first_block_goes_back_to_n4(self, tmp_path):
        """#3852 T1: no previous issues, so the node records no stop and N4 runs again."""
        result, route = self._run(tmp_path)
        assert result["error_message"] == ""
        assert route == "N4_implement_code"

    def test_a_repeated_block_halts(self, tmp_path):
        """#3852 T2: the previous iteration had the same issues, so it halts."""
        result, route = self._run(
            tmp_path, previous_completeness_issues=[["src/foo.py", 42, "empty_branch"]]
        )
        assert "stagnant" in result["error_message"]
        assert route == "HALT"
