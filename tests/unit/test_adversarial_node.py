"""Unit tests for adversarial node logic.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import json
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
    adversarial_summary,
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
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# Feature\n## Requirements\n1. Handles all inputs",
            "test_files": [],
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
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
    )
    def test_output_dir_rooted_in_repo_root(
        self, mock_validate, mock_write, mock_client_cls, tmp_path
    ):
        """#1757: when state carries repo_root (the worktree), generated
        tests are written under it — NOT under the process CWD, which is
        the AssemblyZero checkout when workflows run from AZ."""
        import os

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = (
            _make_valid_analysis_json()
        )
        mock_write.return_value = {}
        mock_validate.return_value = {
            "valid": True, "errors": [], "warnings": [], "mock_violations": [],
        }

        worktree = str(tmp_path / "boostgauge-7")
        state = {
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# Feature",
            "test_files": [],
            "issue_id": 7,
            "repo_root": worktree,
        }

        run_adversarial_node(state)

        assert mock_write.call_args.kwargs["output_dir"] == os.path.join(
            worktree, "tests", "adversarial"
        )

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.write_adversarial_tests"
    )
    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.validate_adversarial_tests"
    )
    def test_output_dir_cwd_relative_without_repo_root(
        self, mock_validate, mock_write, mock_client_cls
    ):
        """Backward compatibility: states without repo_root keep the old
        CWD-relative behavior (#1757)."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.return_value = (
            _make_valid_analysis_json()
        )
        mock_write.return_value = {}
        mock_validate.return_value = {
            "valid": True, "errors": [], "warnings": [], "mock_violations": [],
        }

        state = {
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# Feature",
            "test_files": [],
            "issue_id": 7,
        }

        run_adversarial_node(state)

        assert mock_write.call_args.kwargs["output_dir"] == "tests/adversarial"

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_quota_skip(self, mock_client_cls):
        """T020: On GeminiQuotaExhaustedError, sets skipped_reason and the
        skipped verdict (#2926: a review that did not run is not an error)."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = (
            GeminiQuotaExhaustedError("quota")
        )

        state = {
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "skipped"
        assert "quota" in result["adversarial_skipped_reason"].lower()
        assert result["adversarial_test_count"] == 0

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_no_client_available_skips(self, mock_client_cls):
        """#1602 / #2926: if the client cannot be built -- get_provider refuses
        the spec, or the alias is forbidden -- the non-blocking node records
        the reason and continues instead of halting the workflow. It used to
        record this as verdict "success"."""
        mock_client_cls.side_effect = ValueError(
            "Unknown provider 'gemini'. Supported: claude, anthropic, gemini, mock, scripted"
        )

        state = {
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 352,
        }

        # Must NOT raise — the construction failure is caught and skipped.
        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "skipped"
        assert result["adversarial_skipped_reason"].startswith("no adversarial client")
        assert "Unknown provider" in result["adversarial_skipped_reason"]
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
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "skipped"
        assert "Flash" in result["adversarial_skipped_reason"]

    def test_empty_implementation_skip(self):
        """T040: With no implementation files, skips gracefully."""
        state = {
            "implementation_files": [],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "skipped"
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
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "error"
        assert "Malformed Gemini response" in result["adversarial_error"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_a_reported_failure_is_recorded_once_and_not_retried(self, mock_client_cls):
        """#2926: the transport has already retried and rotated before it
        reports a failure (#1907). The node used to take a second lap with a
        longer timeout, which doubled the gauntlet and printed "timeout --
        retrying" on every run whose real cause was a dead API key. One
        call, and the transport's own message is the recorded reason."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = GeminiTimeoutError(
            "Gemini API error (status=400): API key not valid. Please pass a valid API key."
        )

        state = {
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 352,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "skipped"
        assert "API key not valid" in result["adversarial_skipped_reason"]
        assert "retry" not in result["adversarial_skipped_reason"].lower()
        assert mock_client.generate_adversarial_tests.call_count == 1

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
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
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

    def test_token_budget_trimming(self, tmp_path):
        """T190: With oversized input, output fits within 60KB."""
        big_file = tmp_path / "big_file.py"
        big_file.write_text("x" * 200_000, encoding="utf-8")
        test_file = tmp_path / "test.py"
        test_file.write_text("z" * 50_000, encoding="utf-8")

        state = {
            "implementation_files": [str(big_file)],
            "lld_content": "y" * 100_000,
            "test_files": [str(test_file)],
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
            "implementation_files": [],
            "lld_content": "",
            "test_files": [],
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)
        assert impl == ""
        assert lld == ""
        assert tests == ""

    def test_small_input_not_truncated(self, tmp_path):
        """Small inputs are returned without truncation."""
        small_file = tmp_path / "small.py"
        small_file.write_text("def foo():\n    return 42\n", encoding="utf-8")
        test_file = tmp_path / "test_small.py"
        test_file.write_text("def test_foo():\n    assert foo() == 42\n", encoding="utf-8")

        state = {
            "implementation_files": [str(small_file)],
            "lld_content": "# Small LLD\n## Requirements\n1. foo returns 42",
            "test_files": [str(test_file)],
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

    def test_multiple_impl_files_concatenated(self, tmp_path):
        """Multiple implementation files are concatenated with headers."""
        file1 = tmp_path / "file1.py"
        file1.write_text("def foo(): pass", encoding="utf-8")
        file2 = tmp_path / "file2.py"
        file2.write_text("def bar(): pass", encoding="utf-8")

        state = {
            "implementation_files": [str(file1), str(file2)],
            "lld_content": "",
            "test_files": [],
            "issue_id": 352,
        }

        impl, lld, tests = _collect_context(state)

        assert "file1.py" in impl
        assert "file2.py" in impl
        assert "def foo():" in impl
        assert "def bar():" in impl

    def test_oversized_impl_truncated_with_marker(self, tmp_path):
        """Implementation exceeding budget gets truncation marker."""
        big_file = tmp_path / "big.py"
        big_file.write_text("x" * 200_000, encoding="utf-8")

        state = {
            "implementation_files": [str(big_file)],
            "lld_content": "",
            "test_files": [],
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

class TestARefusedModelDoesNotHaltThePipeline:
    """#2286 added a pre-request model check, and this node is non-blocking.

    The handlers around the generate call name specific Gemini errors rather
    than catching broadly, which is deliberate -- but it means a NEW exception
    type escapes and halts a pipeline that is meant to continue without
    adversarial coverage. The check and its handler ship together for that
    reason.
    """

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_it_skips_rather_than_raising(self, mock_client_cls):
        from assemblyzero.workflows.testing.adversarial_gemini import (
            ForbiddenModelError,
        )

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = ForbiddenModelError(
            "alias '3.1-flash-preview' resolves to a flash tier"
        )

        state = {
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 2286,
        }

        result = run_adversarial_node(state)

        assert result["adversarial_verdict"] == "skipped"
        assert result["adversarial_test_count"] == 0
        assert "not permitted" in result["adversarial_skipped_reason"]

    @patch(
        "assemblyzero.workflows.testing.nodes.adversarial_node.AdversarialGeminiClient"
    )
    def test_the_reason_is_distinct_from_a_downgrade(self, mock_client_cls):
        """A refused REQUEST and a downgraded RESPONSE are different failures
        and must not be reported with each other's wording."""
        from assemblyzero.workflows.testing.adversarial_gemini import (
            ForbiddenModelError,
        )

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.generate_adversarial_tests.side_effect = ForbiddenModelError(
            "nope"
        )

        result = run_adversarial_node(
            {
                "implementation_files": ["/fake/module.py"],
                "lld_content": "# LLD",
                "test_files": [],
                "issue_id": 2286,
            }
        )

        assert "downgraded to Flash" not in result["adversarial_skipped_reason"]


def _refuse_network(monkeypatch) -> list:
    """Patch the two socket entry points so any connect attempt is recorded
    and fails loudly."""
    import socket

    connects: list = []

    def refuse(*args, **kwargs):
        connects.append(args)
        raise AssertionError("network call during a mock run")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    return connects


class TestMockRunsMakeNoNetworkCall:
    """#3546. A --mock rehearsal reached N7.5 and called the paid Gemini API,
    because LangGraph filtered mock_mode out of the node's input and the
    node decided by whether a client could be built."""

    def test_the_flag_is_in_the_node_schema(self):
        from assemblyzero.workflows.testing.adversarial_state import (
            AdversarialNodeState,
        )

        assert "mock_mode" in AdversarialNodeState.__annotations__

    def test_a_mock_run_skips_with_the_reason_and_opens_no_socket(self, monkeypatch):
        """The client is NOT patched here: the node must decide from the
        flag before it reaches for a transport."""
        connects = _refuse_network(monkeypatch)

        result = run_adversarial_node({
            "implementation_files": ["/fake/module.py"],
            "lld_content": "# LLD",
            "test_files": [],
            "issue_id": 3546,
            "mock_mode": True,
        })

        assert connects == []
        assert result["adversarial_verdict"] == "skipped"
        assert "mock run" in result["adversarial_skipped_reason"]
        assert result["adversarial_test_count"] == 0

    def test_the_flag_crosses_the_langgraph_boundary(self, monkeypatch):
        """The node is added to a graph typed on the full testing state, as
        build_testing_workflow adds it, and invoked with mock_mode. Before
        #3546 the key was dropped at the boundary and the node reached for a
        client; before #2926 the node's own outputs were dropped on the way
        back, so nothing downstream could say what it did."""
        from langgraph.graph import END, StateGraph

        from assemblyzero.workflows.testing.state import TestingWorkflowState

        _refuse_network(monkeypatch)
        graph = StateGraph(TestingWorkflowState)
        graph.add_node("N7_5_adversarial", run_adversarial_node)
        graph.set_entry_point("N7_5_adversarial")
        graph.add_edge("N7_5_adversarial", END)

        out = graph.compile().invoke({
            "issue_number": 3546,
            "implementation_files": ["/fake/module.py"],
            "mock_mode": True,
        })

        assert out["adversarial_verdict"] == "skipped"
        assert "mock run" in out["adversarial_skipped_reason"]
        assert adversarial_summary(out) == (
            "Adversarial review (N7.5): did not run: "
            "mock run, no adversarial review is made"
        )


class TestAdversarialSummary:
    """#2926: one line for the run report and the PR body, in every shape the
    node can leave behind."""

    def test_a_skip_names_the_reason(self):
        line = adversarial_summary({
            "adversarial_verdict": "skipped",
            "adversarial_skipped_reason": "Gemini quota exhausted: 429",
        })
        assert line == "Adversarial review (N7.5): did not run: Gemini quota exhausted: 429"

    def test_a_run_names_the_count_and_the_verdict(self):
        line = adversarial_summary({
            "adversarial_verdict": "pass",
            "adversarial_test_count": 4,
            "adversarial_skipped_reason": None,
        })
        assert line == (
            "Adversarial review (N7.5): ran; 4 adversarial test(s) written; verdict pass"
        )

    def test_an_error_names_the_error(self):
        line = adversarial_summary({
            "adversarial_verdict": "error",
            "adversarial_error": "Malformed Gemini response: Expecting value",
            "adversarial_skipped_reason": None,
        })
        assert line == (
            "Adversarial review (N7.5): errored: Malformed Gemini response: Expecting value"
        )

    def test_a_state_that_never_reached_the_node_says_so(self):
        assert adversarial_summary({}) == (
            "Adversarial review (N7.5): did not reach this step"
        )
