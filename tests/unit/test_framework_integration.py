"""Integration tests for multi-framework TDD wiring.

Issue #381: Tests that framework detection is wired into the workflow nodes
(N0 load_lld, N2.5 validate_tests_mechanical, N3/N5 verify_phases).
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.framework_detector import (
    CoverageType,
    TestFramework,
    TestRunResult,
)
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _resolve_framework_enum,
    _verify_red_non_pytest,
    _verify_green_non_pytest,
)
from assemblyzero.workflows.testing.runner_registry import get_framework_config


# =============================================================================
# N0: Framework detection wired into load_lld
# =============================================================================


class TestN0FrameworkDetection:
    """Test that load_lld populates framework_config in state."""

    def test_mock_load_populates_framework_config(self):
        """_mock_load_lld returns framework_config and total_scenarios."""
        from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "issue_number": 42,
                "mock_mode": True,
                "repo_root": tmpdir,
            }
            result = _mock_load_lld(state)

        assert "framework_config" in result
        assert "total_scenarios" in result
        assert result["framework_config"] is not None
        # Mock LLD has no explicit framework → pytest default
        fw = result["framework_config"]["framework"]
        assert fw == TestFramework.PYTEST or fw == "pytest"

    def test_mock_load_total_scenarios_matches_scenarios(self):
        """total_scenarios equals len(test_scenarios) in mock load."""
        from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "issue_number": 42,
                "mock_mode": True,
                "repo_root": tmpdir,
            }
            result = _mock_load_lld(state)

        assert result["total_scenarios"] == len(result["test_scenarios"])


# =============================================================================
# get_framework_config
# =============================================================================


class TestFrameworkConfigRegistry:
    """Test that get_framework_config returns correct configs."""

    def test_pytest_config(self):
        config = get_framework_config(TestFramework.PYTEST)
        assert config["test_file_extension"] == ".py"
        assert config["coverage_type"] == CoverageType.LINE

    def test_playwright_config(self):
        config = get_framework_config(TestFramework.PLAYWRIGHT)
        assert config["test_file_extension"] == ".spec.ts"
        assert config["coverage_type"] == CoverageType.SCENARIO

    def test_jest_config(self):
        config = get_framework_config(TestFramework.JEST)
        assert config["test_file_extension"] == ".test.ts"
        assert config["coverage_type"] == CoverageType.LINE

    def test_vitest_config(self):
        config = get_framework_config(TestFramework.VITEST)
        assert config["test_file_extension"] == ".test.ts"


# =============================================================================
# _resolve_framework_enum helper
# =============================================================================


class TestResolveFrameworkEnum:
    """Test the helper that normalizes framework from config dict."""

    def test_enum_value_passthrough(self):
        assert _resolve_framework_enum({"framework": TestFramework.JEST}) == TestFramework.JEST

    def test_string_value_converted(self):
        assert _resolve_framework_enum({"framework": "playwright"}) == TestFramework.PLAYWRIGHT

    def test_invalid_string_returns_none(self):
        assert _resolve_framework_enum({"framework": "unknown_framework"}) is None

    def test_missing_key_returns_none(self):
        assert _resolve_framework_enum({}) is None

    def test_none_value_returns_none(self):
        assert _resolve_framework_enum({"framework": None}) is None


# =============================================================================
# N2.5: Framework-aware validation
# =============================================================================


class TestN25FrameworkValidation:
    """Test validate_tests_mechanical_node with non-pytest frameworks."""

    def test_pytest_path_unchanged(self):
        """When framework is pytest, use the AST path (existing behavior)."""
        state = {
            "generated_tests": "import pytest\n\ndef test_example():\n    assert True\n",
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "framework_config": {"framework": TestFramework.PYTEST},
        }
        result = validate_tests_mechanical_node(state)
        assert result["validation_result"]["is_valid"] is True

    def test_no_framework_config_uses_ast_path(self):
        """When framework_config is None, use the AST path."""
        state = {
            "generated_tests": "import pytest\n\ndef test_example():\n    assert True\n",
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
        }
        result = validate_tests_mechanical_node(state)
        assert result["validation_result"]["is_valid"] is True

    @patch("assemblyzero.workflows.testing.nodes.validate_tests_mechanical.get_runner")
    def test_playwright_uses_runner_validation(self, mock_get_runner):
        """Playwright framework triggers runner.validate_test_file()."""
        mock_runner = MagicMock()
        mock_runner.validate_test_file.return_value = []  # No errors
        mock_get_runner.return_value = mock_runner

        state = {
            "generated_tests": "import { test } from '@playwright/test';\ntest('works', async () => {});",
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "framework_config": {"framework": TestFramework.PLAYWRIGHT},
            "repo_root": ".",
            "test_files": ["tests/app.spec.ts"],
        }
        result = validate_tests_mechanical_node(state)
        assert result["validation_result"]["is_valid"] is True
        mock_runner.validate_test_file.assert_called_once()

    @patch("assemblyzero.workflows.testing.nodes.validate_tests_mechanical.get_runner")
    def test_jest_validation_errors_propagated(self, mock_get_runner):
        """Jest runner validation errors are captured in result."""
        mock_runner = MagicMock()
        mock_runner.validate_test_file.return_value = [
            "No test structure (describe/it/test) found"
        ]
        mock_get_runner.return_value = mock_runner

        state = {
            "generated_tests": "console.log('not a test');",
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "framework_config": {"framework": "jest"},
            "repo_root": ".",
            "test_files": ["tests/app.test.ts"],
        }
        result = validate_tests_mechanical_node(state)
        assert result["validation_result"]["is_valid"] is False
        assert len(result["validation_result"]["errors"]) == 1
        assert result["scaffold_attempts"] == 1

    @patch("assemblyzero.workflows.testing.nodes.validate_tests_mechanical.get_runner")
    def test_runner_unavailable_skips_validation(self, mock_get_runner):
        """If runner creation fails (e.g., npx missing), skip validation."""
        mock_get_runner.side_effect = EnvironmentError("npx not found")

        state = {
            "generated_tests": "test content",
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "framework_config": {"framework": TestFramework.PLAYWRIGHT},
            "repo_root": ".",
        }
        result = validate_tests_mechanical_node(state)
        # Should pass (skip) with a warning
        assert result["validation_result"]["is_valid"] is True
        assert len(result["validation_result"]["warnings"]) > 0


# =============================================================================
# N3: Red phase non-pytest
# =============================================================================


class TestN3RedPhaseNonPytest:
    """Test _verify_red_non_pytest."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_all_tests_fail_passes_red_phase(self, mock_get_runner):
        """Red phase passes when all tests fail."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 0,
            "failed": 3,
            "skipped": 0,
            "errors": 0,
            "total": 3,
            "coverage_percent": 0.0,
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": "3 tests failed",
            "exit_code": 1,
            "framework": TestFramework.PLAYWRIGHT,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.spec.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "audit_dir": "",
                "file_counter": 0,
            }
            result = _verify_red_non_pytest(
                state,
                {"framework": TestFramework.PLAYWRIGHT},
                TestFramework.PLAYWRIGHT,
            )

        assert result["next_node"] == "N4_implement_code"
        assert result["error_message"] == ""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_some_tests_pass_fails_red_phase(self, mock_get_runner):
        """Red phase fails when some tests pass."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 1,
            "failed": 2,
            "skipped": 0,
            "errors": 0,
            "total": 3,
            "coverage_percent": 0.0,
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": "1 passed, 2 failed",
            "exit_code": 1,
            "framework": TestFramework.PLAYWRIGHT,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.spec.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "audit_dir": "",
                "file_counter": 0,
            }
            result = _verify_red_non_pytest(
                state,
                {"framework": TestFramework.PLAYWRIGHT},
                TestFramework.PLAYWRIGHT,
            )

        assert result["next_node"] == "END"
        assert "passed unexpectedly" in result["error_message"]

    def test_no_test_files_returns_error(self):
        """Red phase returns error when no test files."""
        state = {
            "test_files": [],
            "repo_root": ".",
        }
        result = _verify_red_non_pytest(
            state,
            {"framework": TestFramework.JEST},
            TestFramework.JEST,
        )
        assert "No test files" in result["error_message"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_runner_unavailable_returns_error(self, mock_get_runner):
        """Red phase returns error if runner can't be created."""
        mock_get_runner.side_effect = EnvironmentError("npx not found")

        state = {
            "test_files": ["tests/app.spec.ts"],
            "repo_root": ".",
        }
        result = _verify_red_non_pytest(
            state,
            {"framework": TestFramework.PLAYWRIGHT},
            TestFramework.PLAYWRIGHT,
        )
        assert "Runner unavailable" in result["error_message"]


# =============================================================================
# N5: Green phase non-pytest
# =============================================================================


class TestN5GreenPhaseNonPytest:
    """Test _verify_green_non_pytest."""

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_all_pass_with_coverage_succeeds(self, mock_get_runner):
        """Green phase passes when all tests pass and coverage meets target."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 5,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "total": 5,
            "coverage_percent": 95.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": "5 passed",
            "exit_code": 0,
            "framework": TestFramework.JEST,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.test.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "coverage_target": 90,
                "iteration_count": 0,
                "max_iterations": 5,
                "total_scenarios": 5,
                "audit_dir": "",
                "file_counter": 0,
                "framework_config": {"framework": TestFramework.JEST, "coverage_type": CoverageType.LINE},
            }
            result = _verify_green_non_pytest(
                state,
                state["framework_config"],
                TestFramework.JEST,
            )

        assert result["next_node"] == "N6_e2e_validation"
        assert result["error_message"] == ""
        assert result["coverage_achieved"] == 95.0

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_playwright_scenario_coverage(self, mock_get_runner):
        """Playwright uses scenario coverage (passed/total_scenarios)."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 8,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "total": 8,
            "coverage_percent": 0.0,  # Playwright doesn't give line coverage
            "coverage_type": CoverageType.SCENARIO,
            "raw_output": "8 passed",
            "exit_code": 0,
            "framework": TestFramework.PLAYWRIGHT,
        }
        mock_runner.compute_scenario_coverage.return_value = 1.0  # 8/8
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.spec.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "coverage_target": 90,
                "iteration_count": 0,
                "max_iterations": 5,
                "total_scenarios": 8,
                "audit_dir": "",
                "file_counter": 0,
                "framework_config": {
                    "framework": TestFramework.PLAYWRIGHT,
                    "coverage_type": CoverageType.SCENARIO,
                },
            }
            result = _verify_green_non_pytest(
                state,
                state["framework_config"],
                TestFramework.PLAYWRIGHT,
            )

        assert result["next_node"] == "N6_e2e_validation"
        assert result["coverage_achieved"] == 100.0

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_failures_loop_back_to_implement(self, mock_get_runner):
        """Green phase loops back to N4 when tests fail."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 2,
            "failed": 1,
            "skipped": 0,
            "errors": 0,
            "total": 3,
            "coverage_percent": 66.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": "2 passed, 1 failed",
            "exit_code": 1,
            "framework": TestFramework.JEST,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.test.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "coverage_target": 90,
                "iteration_count": 0,
                "max_iterations": 5,
                "total_scenarios": 3,
                "audit_dir": "",
                "file_counter": 0,
                "previous_passed": -1,
                "previous_coverage": -1.0,
                "framework_config": {"framework": TestFramework.JEST, "coverage_type": CoverageType.LINE},
            }
            result = _verify_green_non_pytest(
                state,
                state["framework_config"],
                TestFramework.JEST,
            )

        assert result["next_node"] == "N4_implement_code"
        assert result["iteration_count"] == 1

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_stagnation_detection_halts(self, mock_get_runner):
        """Stagnation detection halts when passed count is unchanged."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 2,
            "failed": 1,
            "skipped": 0,
            "errors": 0,
            "total": 3,
            "coverage_percent": 66.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": "2 passed, 1 failed",
            "exit_code": 1,
            "framework": TestFramework.JEST,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.test.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "coverage_target": 90,
                "iteration_count": 1,
                "max_iterations": 5,
                "total_scenarios": 3,
                "audit_dir": "",
                "file_counter": 0,
                "previous_passed": 2,  # Same as current
                "previous_coverage": 66.0,
                "framework_config": {"framework": TestFramework.JEST, "coverage_type": CoverageType.LINE},
            }
            result = _verify_green_non_pytest(
                state,
                state["framework_config"],
                TestFramework.JEST,
            )

        assert result["next_node"] == "end"
        assert "stagnant" in result["error_message"].lower()

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_max_iterations_reached(self, mock_get_runner):
        """Green phase stops at max iterations with failures."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 1,
            "failed": 2,
            "skipped": 0,
            "errors": 0,
            "total": 3,
            "coverage_percent": 33.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": "1 passed, 2 failed",
            "exit_code": 1,
            "framework": TestFramework.JEST,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.test.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "coverage_target": 90,
                "iteration_count": 4,  # Will become 5 >= max_iterations
                "max_iterations": 5,
                "total_scenarios": 3,
                "audit_dir": "",
                "file_counter": 0,
                "framework_config": {"framework": TestFramework.JEST, "coverage_type": CoverageType.LINE},
            }
            result = _verify_green_non_pytest(
                state,
                state["framework_config"],
                TestFramework.JEST,
            )

        assert result["next_node"] == "end"
        assert "failed after" in result["error_message"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.get_runner")
    def test_skip_e2e_routes_to_finalize(self, mock_get_runner):
        """When skip_e2e is set, successful green phase routes to N7."""
        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = {
            "passed": 3,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "total": 3,
            "coverage_percent": 95.0,
            "coverage_type": CoverageType.LINE,
            "raw_output": "3 passed",
            "exit_code": 0,
            "framework": TestFramework.JEST,
        }
        mock_get_runner.return_value = mock_runner

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "test_files": ["tests/app.test.ts"],
                "repo_root": tmpdir,
                "issue_number": 42,
                "coverage_target": 90,
                "iteration_count": 0,
                "max_iterations": 5,
                "total_scenarios": 3,
                "skip_e2e": True,
                "audit_dir": "",
                "file_counter": 0,
                "framework_config": {"framework": TestFramework.JEST, "coverage_type": CoverageType.LINE},
            }
            result = _verify_green_non_pytest(
                state,
                state["framework_config"],
                TestFramework.JEST,
            )

        assert result["next_node"] == "N7_finalize"


# =============================================================================
# Pytest path untouched
# =============================================================================


class TestPytestPathUntouched:
    """Verify the existing pytest path is not affected by framework branching."""

    def test_verify_red_with_pytest_config_stays_on_pytest_path(self):
        """verify_red_phase with PYTEST framework_config uses the existing code path."""
        from assemblyzero.workflows.testing.nodes.verify_phases import verify_red_phase

        # With mock_mode, the existing mock path should work unchanged
        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "issue_number": 42,
                "mock_mode": True,
                "repo_root": tmpdir,
                "test_files": [],
                "audit_dir": "",
                "file_counter": 0,
                "framework_config": {"framework": TestFramework.PYTEST},
            }
            result = verify_red_phase(state)

        # Mock red phase returns known values
        assert result["next_node"] == "N4_implement_code"
        assert "3 failed" in result["red_phase_output"]

    def test_verify_green_with_pytest_config_stays_on_pytest_path(self):
        """verify_green_phase with PYTEST framework_config uses the existing code path."""
        from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "issue_number": 42,
                "mock_mode": True,
                "repo_root": tmpdir,
                "test_files": [],
                "audit_dir": "",
                "file_counter": 0,
                "coverage_target": 90,
                "iteration_count": 0,
                "framework_config": {"framework": TestFramework.PYTEST},
            }
            result = verify_green_phase(state)

        # Mock green phase first iteration returns known values
        assert "coverage" in result["green_phase_output"].lower() or "passed" in result["green_phase_output"].lower()
