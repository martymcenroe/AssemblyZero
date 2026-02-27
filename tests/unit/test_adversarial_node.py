"""Unit tests for adversarial node logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.adversarial_gemini import (
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.nodes.adversarial_node import (
    _collect_context,
    _parse_gemini_response,
    run_adversarial_node,
)


def _make_valid_analysis_json(**overrides):
    """Helper to build valid AdversarialAnalysis JSON."""
    base = {
        "uncovered_edge_cases": ["empty input not tested"],
        "false_claims": ["claims Unicode support but uses ASCII regex"],
        "missing_error_handling": ["FileNotFoundError uncaught at line 42"],
        "implicit_assumptions": ["assumes UTF-8 encoding"],
        "test_cases": [
            {
                "test_id": "ADV_001",
                "target_function": "module.function",
                "category": "boundary",
                "description": "Test with empty string",
                "test_code": "def test_empty_input():\n    assert module.function('') is None",
                "claim_challenged": "handles all inputs",
                "severity": "high",
            }
        ],
    }
    base.update(overrides)
    return json.dumps(base)


class TestRunAdversarialNode:
    """Tests for run_adversarial_node (T010, T020, T030, T040)."""

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
    )
    def test_happy_path_generates_tests(
        self, mock_validate, mock_write, mock_client_cls, tmp_path
    ):
        """T010: Given valid impl + LLD, generates test files and returns pass."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = (
            _make_valid_analysis_json()
        )

        mock_write.return_value = {
            "tests/adversarial/test_352_boundary.py": (
                "def test_empty_input():\n    assert True\n"
            )
        }

        mock_validate.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "mock_violations": [],
        }

        state = {
            "implementation_files": {
                "module.py": "def function(x):\n    return x"
            },
            "lld_content": "# Feature\n## Requirements\n1. Handles all inputs",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "pass"
        assert result["adversarial_test_count"] > 0
        assert result["adversarial_skipped_reason"] is None
        assert result["generated_test_files"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_quota_skip(self, mock_client_cls):
        """T020: On GeminiQuotaExhaustedError, sets skipped_reason and error verdict."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = (
            GeminiQuotaExhaustedError("quota")
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "quota" in result["adversarial_skipped_reason"].lower()
        assert result["adversarial_test_count"] == 0

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_downgrade_skip(self, mock_client_cls):
        """T030: On GeminiModelDowngradeError, sets skipped_reason with Flash."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = (
            GeminiModelDowngradeError("Expected Pro but received gemini-2.0-flash")
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "Flash" in result["adversarial_skipped_reason"]

    def test_empty_implementation_skip(self):
        """T040: With no implementation files, skips gracefully."""
        state = {
            "implementation_files": {},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "No implementation files" in result["adversarial_skipped_reason"]
        assert result["adversarial_test_count"] == 0

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_malformed_response_error(self, mock_client_cls):
        """On malformed Gemini response, sets adversarial_error."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = "{broken json"

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "Malformed Gemini response" in result["adversarial_error"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_timeout_triggers_retry(self, mock_client_cls):
        """On first timeout, retries once then skips if retry also fails."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = GeminiTimeoutError(
            "Gemini API response exceeded 120s timeout"
        )

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "timeout" in result["adversarial_skipped_reason"].lower()
        # Should have been called twice (initial + retry)
        assert mock_client.generate_adversarial_tests.call_count == 2

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
    )
    def test_mock_violations_rejected(
        self, mock_validate, mock_write, mock_client_cls
    ):
        """Files with mock violations are excluded from clean_files."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = (
            _make_valid_analysis_json()
        )

        mock_write.return_value = {
            "tests/adversarial/test_352_boundary.py": (
                "from unittest.mock import patch\n\n"
                "def test_bad():\n    assert True\n"
            ),
            "tests/adversarial/test_352_contract.py": (
                "def test_good():\n    assert True\n"
            ),
        }

        mock_validate.return_value = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "mock_violations": [
                "tests/adversarial/test_352_boundary.py:1: Mock import detected"
            ],
        }

        state = {
            "implementation_files": {"module.py": "def f(): pass"},
            "lld_content": "# LLD",
            "existing_tests": {},
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        # Only clean file should remain
        assert "tests/adversarial/test_352_contract.py" in result["generated_test_files"]
        assert (
            "tests/adversarial/test_352_boundary.py"
            not in result["generated_test_files"]
        )


class TestParseGeminiResponse:
    """Tests for _parse_gemini_response (T050, T060, T260, T270)."""

    def test_valid_json_parsed(self):
        """T050: Parses well-formed AdversarialAnalysis JSON correctly."""
        raw = _make_valid_analysis_json()
        result = _parse_gemini_response(raw)

        assert isinstance(result["uncovered_edge_cases"], list)
        assert len(result["uncovered_edge_cases"]) > 0
        assert isinstance(result["false_claims"], list)
        assert isinstance(result["missing_error_handling"], list)
        assert isinstance(result["implicit_assumptions"], list)
        assert isinstance(result["test_cases"], list)
        assert len(result["test_cases"]) == 1
        assert result["test_cases"][0]["test_id"] == "ADV_001"

    def test_malformed_json_raises(self):
        """T060: Raises ValueError on invalid JSON."""
        with pytest.raises(ValueError, match="Malformed JSON"):
            _parse_gemini_response("{broken")

    def test_all_four_categories_present(self):
        """T260: Validates all four analysis categories are present."""
        raw = _make_valid_analysis_json()
        result = _parse_gemini_response(raw)

        assert "uncovered_edge_cases" in result
        assert "false_claims" in result
        assert "missing_error_handling" in result
        assert "implicit_assumptions" in result
        assert isinstance(result["uncovered_edge_cases"], list)
        assert isinstance(result["false_claims"], list)
        assert isinstance(result["missing_error_handling"], list)
        assert isinstance(result["implicit_assumptions"], list)

    def test_missing_category_raises(self):
        """T270: JSON missing false_claims field causes ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="false_claims"):
            _parse_gemini_response(raw)

    def test_markdown_code_block_stripped(self):
        """Handles JSON wrapped in markdown code blocks."""
        inner = _make_valid_analysis_json()
        raw = f"```json\n{inner}\n```"
        result = _parse_gemini_response(raw)
        assert isinstance(result["test_cases"], list)

    def test_empty_response_raises(self):
        """Raises ValueError on empty response."""
        with pytest.raises(ValueError, match="Empty response"):
            _parse_gemini_response("")

    def test_whitespace_only_response_raises(self):
        """Raises ValueError on whitespace-only response."""
        with pytest.raises(ValueError, match="Empty response"):
            _parse_gemini_response("   \n  ")

    def test_missing_test_cases_raises(self):
        """Raises ValueError when test_cases field is missing."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="test_cases"):
            _parse_gemini_response(raw)

    def test_test_cases_not_list_raises(self):
        """Raises ValueError when test_cases is not a list."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": "not a list",
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="test_cases must be a list"):
            _parse_gemini_response(raw)

    def test_empty_test_cases_valid(self):
        """Empty test_cases list is valid."""
        raw = _make_valid_analysis_json(test_cases=[])
        result = _parse_gemini_response(raw)
        assert result["test_cases"] == []

    def test_test_case_missing_field_raises(self):
        """Raises ValueError when a test case is missing required fields."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                {
                    "test_id": "ADV_001",
                    # missing target_function, category, etc.
                }
            ],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="missing required field"):
            _parse_gemini_response(raw)

    def test_non_dict_response_raises(self):
        """Raises ValueError when JSON is a list instead of object."""
        raw = json.dumps([1, 2, 3])
        with pytest.raises(ValueError, match="Expected JSON object"):
            _parse_gemini_response(raw)

    def test_multiple_test_cases_parsed(self):
        """Parses multiple test cases correctly."""
        test_cases = [
            {
                "test_id": f"ADV_{i:03d}",
                "target_function": f"module.func_{i}",
                "category": "boundary",
                "description": f"Test case {i}",
                "test_code": f"def test_case_{i}():\n    assert True",
                "claim_challenged": f"claim {i}",
                "severity": "medium",
            }
            for i in range(5)
        ]
        raw = _make_valid_analysis_json(test_cases=test_cases)
        result = _parse_gemini_response(raw)
        assert len(result["test_cases"]) == 5

    def test_missing_uncovered_edge_cases_raises(self):
        """Missing uncovered_edge_cases raises ValueError."""
        data = {
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="uncovered_edge_cases"):
            _parse_gemini_response(raw)

    def test_missing_missing_error_handling_raises(self):
        """Missing missing_error_handling raises ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="missing_error_handling"):
            _parse_gemini_response(raw)

    def test_missing_implicit_assumptions_raises(self):
        """Missing implicit_assumptions raises ValueError."""
        data = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "test_cases": [],
        }
        raw = json.dumps(data)
        with pytest.raises(ValueError, match="implicit_assumptions"):
            _parse_gemini_response(raw)


class TestCollectContext:
    """Tests for _collect_context (T190)."""

    def test_token_budget_trimming(self):
        """T190: With oversized input, output fits within 60KB."""
        state = {
            "implementation_files": {
                "big_file.py": "x" * 200_000,
            },
            "lld_content": "y" * 100_000,
            "existing_tests": {
                "test.py": "z" * 50_000,
            },
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        total = (
            len(impl.encode("utf-8"))
            + len(lld.encode("utf-8"))
            + len(tests.encode("utf-8"))
        )

        # Allow some margin for truncation markers
        assert total <= 65_000  # 60KB + some margin for markers

    def test_empty_state(self):
        """Handles empty state gracefully."""
        state = {
            "implementation_files": {},
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        assert impl == ""
        assert lld == ""
        assert tests == ""

    def test_small_input_not_truncated(self):
        """Small inputs are returned without truncation."""
        state = {
            "implementation_files": {
                "small.py": "def foo():\n    return 42\n",
            },
            "lld_content": "# Small LLD\n## Requirements\n1. foo returns 42",
            "existing_tests": {
                "test_small.py": "def test_foo():\n    assert foo() == 42\n",
            },
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "def foo():" in impl
        assert "Small LLD" in lld
        assert "def test_foo():" in tests
        # No truncation marker
        assert "TRUNCATED" not in impl
        assert "TRUNCATED" not in lld
        assert "TRUNCATED" not in tests

    def test_multiple_impl_files_concatenated(self):
        """Multiple implementation files are concatenated with headers."""
        state = {
            "implementation_files": {
                "file1.py": "def foo(): pass",
                "file2.py": "def bar(): pass",
            },
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "file1.py" in impl
        assert "file2.py" in impl
        assert "def foo():" in impl
        assert "def bar():" in impl

    def test_oversized_impl_truncated_with_marker(self):
        """Implementation exceeding budget gets truncation marker."""
        state = {
            "implementation_files": {
                "big.py": "x" * 200_000,
            },
            "lld_content": "",
            "existing_tests": {},
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "TRUNCATED" in impl
        assert len(impl.encode("utf-8")) < 200_000

    def test_missing_keys_handled(self):
        """Handles state with missing optional keys."""
        state = {
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        assert impl == ""
        assert lld == ""
        assert tests == ""