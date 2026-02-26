"""Unit and integration tests for completeness gate.

Issue #147: Implementation Completeness Gate (Anti-Stub Detection)

Tests cover:
- Layer 1 AST analysis functions (dead CLI flags, empty branches,
  docstring-only functions, trivial assertions, unused imports)
- Completeness gate routing (BLOCK->N4, PASS->N5, max iterations->end)
- Report generation and LLD requirement extraction
- Review materials preparation for Gemini Layer 2

Test IDs follow LLD Section 10.0 Test Plan.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.completeness.ast_analyzer import (
    CompletenessCategory,
    CompletenessIssue,
    CompletenessResult,
    analyze_dead_cli_flags,
    analyze_docstring_only_functions,
    analyze_empty_branches,
    analyze_trivial_assertions,
    analyze_unused_imports,
    run_ast_analysis,
)
from assemblyzero.workflows.testing.completeness.report_generator import (
    ReviewMaterials,
    extract_lld_requirements,
    generate_implementation_report,
    prepare_review_materials,
)
from assemblyzero.workflows.testing.nodes.completeness_gate import (
    MAX_COMPLETENESS_ITERATIONS,
    route_after_completeness_gate,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_py_file(tmp_path: Path):
    """Factory fixture to create temporary Python files with given content."""

    def _create(content: str, name: str = "module.py") -> Path:
        file_path = tmp_path / name
        file_path.write_text(textwrap.dedent(content), encoding="utf-8")
        return file_path

    return _create


@pytest.fixture
def sample_lld(tmp_path: Path) -> Path:
    """Create a sample LLD markdown file with Section 3 requirements."""
    lld_content = textwrap.dedent("""\
        # 999 - Feature: Sample Feature

        ## 1. Context & Goal

        Some context here.

        ## 2. Proposed Changes

        Some changes.

        ## 3. Requirements

        1. The system shall validate user input
        2. Error messages shall be displayed to the user
        3. The API endpoint shall return JSON responses
        4. Authentication tokens shall expire after 24 hours

        ## 4. Alternatives Considered

        None.
    """)
    lld_path = tmp_path / "999-sample-lld.md"
    lld_path.write_text(lld_content, encoding="utf-8")
    return lld_path


@pytest.fixture
def sample_implementation_file(tmp_path: Path) -> Path:
    """Create a sample implementation Python file."""
    content = textwrap.dedent("""\
        \"\"\"Sample implementation module.\"\"\"

        import json
        from pathlib import Path


        def validate_user_input(data: dict) -> bool:
            \"\"\"Validate user input data.\"\"\"
            if not isinstance(data, dict):
                raise TypeError("Input must be a dictionary")
            required_fields = ["name", "email"]
            for field in required_fields:
                if field not in data:
                    return False
            return True


        def format_error_message(error: str) -> dict:
            \"\"\"Format error messages for API responses.\"\"\"
            return {"error": error, "status": "failed"}


        def generate_json_response(data: dict, status: int = 200) -> str:
            \"\"\"Generate JSON API response.\"\"\"
            response = {"data": data, "status": status}
            return json.dumps(response)


        def create_auth_token(user_id: str, expiry_hours: int = 24) -> str:
            \"\"\"Create authentication token with expiry.\"\"\"
            return f"token_{user_id}_{expiry_hours}h"
    """)
    file_path = tmp_path / "implementation.py"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def mock_state():
    """Factory fixture to create mock TestingWorkflowState dicts."""

    def _create(**overrides) -> dict:
        base = {
            "issue_number": 999,
            "lld_path": "",
            "repo_root": "",
            "iteration_count": 0,
            "implementation_files": [],
            "test_files": [],
            "audit_dir": "",
            "completeness_verdict": "",
            "completeness_issues": [],
            "error_message": "",
        }
        base.update(overrides)
        return base

    return _create


# =============================================================================
# T010: Dead CLI Flag Detection
# =============================================================================


class TestDeadCLIFlags:
    """T010 / Scenario 010: Detect argparse add_argument with no usage."""

    def test_detect_dead_cli_flags(self) -> None:
        """T010: Returns issue for unused argparse arg."""
        source = textwrap.dedent("""\
            import argparse

            def main():
                parser = argparse.ArgumentParser()
                parser.add_argument('--foo', help='unused flag')
                parser.add_argument('--bar', help='used flag')
                args = parser.parse_args()
                print(args.bar)
        """)
        issues = analyze_dead_cli_flags(source, "cli.py")
        assert len(issues) >= 1
        foo_issues = [
            i for i in issues if "foo" in i["description"]
        ]
        assert len(foo_issues) == 1
        assert foo_issues[0]["category"] == CompletenessCategory.DEAD_CLI_FLAG
        assert foo_issues[0]["file_path"] == "cli.py"
        assert foo_issues[0]["severity"] == "ERROR"

    def test_no_dead_flags_when_all_used(self) -> None:
        """Negative: No issues when all argparse args are referenced."""
        source = textwrap.dedent("""\
            import argparse

            def main():
                parser = argparse.ArgumentParser()
                parser.add_argument('--foo', help='used flag')
                args = parser.parse_args()
                print(args.foo)
        """)
        issues = analyze_dead_cli_flags(source, "cli.py")
        assert len(issues) == 0

    def test_no_argparse_returns_empty(self) -> None:
        """No argparse code returns empty issues."""
        source = textwrap.dedent("""\
            def hello():
                return "world"
        """)
        issues = analyze_dead_cli_flags(source, "simple.py")
        assert issues == []

    def test_syntax_error_returns_empty(self) -> None:
        """Syntax errors in source return empty issues."""
        source = "def broken(:\n    pass"
        issues = analyze_dead_cli_flags(source, "broken.py")
        assert issues == []


# =============================================================================
# T020: Empty Branch (pass) Detection
# =============================================================================


class TestEmptyBranches:
    """T020 / Scenario 020: Detect empty conditional branches."""

    def test_detect_empty_branch_pass(self) -> None:
        """T020: Returns issue for `if x: pass`."""
        source = textwrap.dedent("""\
            def process(x):
                if x > 0:
                    pass
                else:
                    return x * 2
        """)
        issues = analyze_empty_branches(source, "module.py")
        assert len(issues) >= 1
        assert issues[0]["category"] == CompletenessCategory.EMPTY_BRANCH
        assert issues[0]["file_path"] == "module.py"
        assert issues[0]["severity"] == "WARNING"

    def test_detect_empty_branch_return_none(self) -> None:
        """T030: Returns issue for `if x: return None`."""
        source = textwrap.dedent("""\
            def process(value):
                if value:
                    return None
                else:
                    return value + 1
        """)
        issues = analyze_empty_branches(source, "module.py")
        assert len(issues) >= 1
        branch_issues = [
            i
            for i in issues
            if i["category"] == CompletenessCategory.EMPTY_BRANCH
        ]
        assert len(branch_issues) >= 1

    def test_no_empty_branches_in_complete_code(self) -> None:
        """No issues for branches with real logic."""
        source = textwrap.dedent("""\
            def process(x):
                if x > 0:
                    return x * 2
                else:
                    return x * -1
        """)
        issues = analyze_empty_branches(source, "module.py")
        assert issues == []

    def test_empty_else_detected(self) -> None:
        """Empty else branch also detected."""
        source = textwrap.dedent("""\
            def process(x):
                if x > 0:
                    return x * 2
                else:
                    pass
        """)
        issues = analyze_empty_branches(source, "module.py")
        assert len(issues) >= 1


# =============================================================================
# T040: Docstring-Only Function Detection
# =============================================================================


class TestDocstringOnlyFunctions:
    """T040 / Scenario 040: Detect functions with docstring + pass only."""

    def test_detect_docstring_only_function(self) -> None:
        """T040: Returns issue for func with docstring+pass."""
        source = textwrap.dedent("""\
            def placeholder():
                \"\"\"This function should do something.\"\"\"
                pass
        """)
        issues = analyze_docstring_only_functions(source, "stubs.py")
        assert len(issues) == 1
        assert issues[0]["category"] == CompletenessCategory.DOCSTRING_ONLY
        assert issues[0]["severity"] == "ERROR"
        assert "placeholder" in issues[0]["description"]
        assert issues[0]["file_path"] == "stubs.py"

    def test_docstring_return_none_detected(self) -> None:
        """Docstring + return None also detected."""
        source = textwrap.dedent("""\
            def stub_func():
                \"\"\"A stub function.\"\"\"
                return None
        """)
        issues = analyze_docstring_only_functions(source, "stubs.py")
        assert len(issues) == 1
        assert issues[0]["category"] == CompletenessCategory.DOCSTRING_ONLY

    def test_docstring_ellipsis_detected(self) -> None:
        """Docstring + ellipsis (...) also detected."""
        source = textwrap.dedent("""\
            def protocol_method():
                \"\"\"Protocol method stub.\"\"\"
                ...
        """)
        issues = analyze_docstring_only_functions(source, "proto.py")
        assert len(issues) == 1

    def test_real_function_not_flagged(self) -> None:
        """Function with real logic not flagged."""
        source = textwrap.dedent("""\
            def real_work():
                \"\"\"Does real work.\"\"\"
                result = compute()
                return result
        """)
        issues = analyze_docstring_only_functions(source, "real.py")
        assert issues == []

    def test_test_functions_skipped(self) -> None:
        """Functions starting with test_ are skipped."""
        source = textwrap.dedent("""\
            def test_something():
                \"\"\"Test placeholder.\"\"\"
                pass
        """)
        issues = analyze_docstring_only_functions(source, "tests.py")
        assert issues == []

    def test_dunder_methods_skipped(self) -> None:
        """Dunder methods are skipped."""
        source = textwrap.dedent("""\
            class MyClass:
                def __init__(self):
                    \"\"\"Init.\"\"\"
                    pass
        """)
        issues = analyze_docstring_only_functions(source, "cls.py")
        assert issues == []

    def test_abstractmethod_skipped(self) -> None:
        """Issue #477: @abstractmethod functions are not flagged."""
        source = textwrap.dedent("""\
            from abc import abstractmethod

            class Base:
                @abstractmethod
                def run(self):
                    \"\"\"Run the task.\"\"\"
                    ...
        """)
        issues = analyze_docstring_only_functions(source, "base.py")
        assert issues == []

    def test_abc_dot_abstractmethod_skipped(self) -> None:
        """Issue #477: @abc.abstractmethod functions are not flagged."""
        source = textwrap.dedent("""\
            import abc

            class Base:
                @abc.abstractmethod
                def run(self):
                    \"\"\"Run the task.\"\"\"
                    pass
        """)
        issues = analyze_docstring_only_functions(source, "base.py")
        assert issues == []


# =============================================================================
# T050: Trivial Assertion Detection
# =============================================================================


class TestTrivialAssertions:
    """T050 / Scenario 050: Detect trivial assertions in test functions."""

    def test_detect_trivial_assertion_is_not_none(self) -> None:
        """T050: Returns issue for `assert x is not None` only."""
        source = textwrap.dedent("""\
            def test_something():
                result = get_result()
                assert result is not None
        """)
        issues = analyze_trivial_assertions(source, "test_module.py")
        assert len(issues) == 1
        assert issues[0]["category"] == CompletenessCategory.TRIVIAL_ASSERTION
        assert issues[0]["severity"] == "WARNING"
        assert "test_something" in issues[0]["description"]

    def test_detect_trivial_assert_true(self) -> None:
        """assert True detected as trivial."""
        source = textwrap.dedent("""\
            def test_always_passes():
                assert True
        """)
        issues = analyze_trivial_assertions(source, "test_module.py")
        assert len(issues) == 1
        assert issues[0]["category"] == CompletenessCategory.TRIVIAL_ASSERTION

    def test_real_assertions_not_flagged(self) -> None:
        """Tests with meaningful assertions not flagged."""
        source = textwrap.dedent("""\
            def test_addition():
                result = 2 + 2
                assert result == 4
        """)
        issues = analyze_trivial_assertions(source, "test_module.py")
        assert issues == []

    def test_non_test_functions_skipped(self) -> None:
        """Non-test functions are not checked for trivial assertions."""
        source = textwrap.dedent("""\
            def helper():
                assert True
        """)
        issues = analyze_trivial_assertions(source, "test_module.py")
        assert issues == []

    def test_pytest_raises_not_trivial(self) -> None:
        """pytest.raises is not considered trivial."""
        source = textwrap.dedent("""\
            import pytest

            def test_raises():
                with pytest.raises(ValueError):
                    raise ValueError("boom")
        """)
        issues = analyze_trivial_assertions(source, "test_module.py")
        assert issues == []


# =============================================================================
# T060: Unused Import Detection
# =============================================================================


class TestUnusedImports:
    """T060 / Scenario 060: Detect unused imports."""

    def test_detect_unused_import(self) -> None:
        """T060: Returns issue for import not used in functions."""
        source = textwrap.dedent("""\
            import os
            import sys

            def main():
                print(sys.argv)
        """)
        issues = analyze_unused_imports(source, "module.py")
        os_issues = [i for i in issues if "os" in i["description"]]
        assert len(os_issues) == 1
        assert os_issues[0]["category"] == CompletenessCategory.UNUSED_IMPORT
        assert os_issues[0]["severity"] == "WARNING"

    def test_all_imports_used_no_issues(self) -> None:
        """No issues when all imports are used."""
        source = textwrap.dedent("""\
            import os
            import sys

            def main():
                print(os.getcwd())
                print(sys.argv)
        """)
        issues = analyze_unused_imports(source, "module.py")
        assert issues == []

    def test_from_import_unused(self) -> None:
        """Unused from-import detected."""
        source = textwrap.dedent("""\
            from pathlib import Path
            from os import getcwd

            def main():
                return Path(".")
        """)
        issues = analyze_unused_imports(source, "module.py")
        getcwd_issues = [i for i in issues if "getcwd" in i["description"]]
        assert len(getcwd_issues) == 1

    def test_future_imports_skipped(self) -> None:
        """__future__ imports are not flagged."""
        source = textwrap.dedent("""\
            from __future__ import annotations

            def main():
                pass
        """)
        issues = analyze_unused_imports(source, "module.py")
        future_issues = [i for i in issues if "annotations" in i["description"]]
        assert len(future_issues) == 0


# =============================================================================
# T070: Valid Code No Issues (Negative Test)
# =============================================================================


class TestValidCodeNoIssues:
    """T070 / Scenario 070: Valid implementation returns empty issues."""

    def test_valid_code_no_issues(self, tmp_py_file) -> None:
        """T070: Returns empty issues list for clean code."""
        source = """\
            import json

            def process_data(data: dict) -> str:
                \"\"\"Process and serialize data.\"\"\"
                if not data:
                    return json.dumps({"error": "empty"})
                result = {k: v.strip() for k, v in data.items()}
                return json.dumps(result)

            def validate(value: str) -> bool:
                \"\"\"Validate a string value.\"\"\"
                return bool(value and len(value) > 0)
        """
        file_path = tmp_py_file(source, "clean_module.py")
        result = run_ast_analysis([file_path])
        assert result["verdict"] == "PASS"
        assert result["issues"] == []
        assert result["ast_analysis_ms"] >= 0

    def test_valid_test_file_no_issues(self, tmp_py_file) -> None:
        """Valid test file with real assertions returns no issues."""
        source = """\
            def test_addition():
                assert 2 + 2 == 4

            def test_string_concat():
                result = "hello" + " " + "world"
                assert result == "hello world"
                assert len(result) == 11
        """
        file_path = tmp_py_file(source, "test_valid.py")
        result = run_ast_analysis([file_path])
        assert result["verdict"] == "PASS"
        assert result["issues"] == []


# =============================================================================
# T080: BLOCK Routes to N4
# =============================================================================


class TestCompletenessGateRouting:
    """T080-T100 / Scenarios 080-100: Completeness gate routing logic."""

    def test_completeness_gate_block_routing(self, mock_state) -> None:
        """T080: BLOCK verdict routes to N4_implement_code."""
        state = mock_state(
            completeness_verdict="BLOCK",
            iteration_count=1,
        )
        result = route_after_completeness_gate(state)
        assert result == "N4_implement_code"

    def test_completeness_gate_block_routing_iter_zero(self, mock_state) -> None:
        """BLOCK at iteration 0 routes to N4."""
        state = mock_state(
            completeness_verdict="BLOCK",
            iteration_count=0,
        )
        result = route_after_completeness_gate(state)
        assert result == "N4_implement_code"

    def test_completeness_gate_block_routing_iter_two(self, mock_state) -> None:
        """BLOCK at iteration 2 (below max) routes to N4."""
        state = mock_state(
            completeness_verdict="BLOCK",
            iteration_count=2,
        )
        result = route_after_completeness_gate(state)
        assert result == "N4_implement_code"

    def test_completeness_gate_pass_routing(self, mock_state) -> None:
        """T090: PASS verdict routes to N5_verify_green."""
        state = mock_state(
            completeness_verdict="PASS",
            iteration_count=0,
        )
        result = route_after_completeness_gate(state)
        assert result == "N5_verify_green"

    def test_completeness_gate_warn_routing(self, mock_state) -> None:
        """WARN verdict routes to N5_verify_green."""
        state = mock_state(
            completeness_verdict="WARN",
            iteration_count=0,
        )
        result = route_after_completeness_gate(state)
        assert result == "N5_verify_green"

    def test_max_iterations_ends(self, mock_state) -> None:
        """T100: BLOCK at max iterations (3) routes to end."""
        state = mock_state(
            completeness_verdict="BLOCK",
            iteration_count=MAX_COMPLETENESS_ITERATIONS,
        )
        result = route_after_completeness_gate(state)
        assert result == "end"

    def test_max_iterations_above_limit_ends(self, mock_state) -> None:
        """BLOCK above max iterations also routes to end."""
        state = mock_state(
            completeness_verdict="BLOCK",
            iteration_count=MAX_COMPLETENESS_ITERATIONS + 1,
        )
        result = route_after_completeness_gate(state)
        assert result == "end"

    def test_error_message_routes_to_end(self, mock_state) -> None:
        """Error message in state routes to end regardless of verdict."""
        state = mock_state(
            completeness_verdict="PASS",
            iteration_count=0,
            error_message="Something went wrong",
        )
        result = route_after_completeness_gate(state)
        assert result == "end"

    def test_max_iterations_constant_is_three(self) -> None:
        """Verify MAX_COMPLETENESS_ITERATIONS is 3 per LLD spec."""
        assert MAX_COMPLETENESS_ITERATIONS == 3


# =============================================================================
# T110: Report Generation
# =============================================================================


class TestReportGeneration:
    """T110 / Scenario 110: Implementation report file generation."""

    def test_report_generation(
        self, tmp_path: Path, sample_lld: Path, sample_implementation_file: Path
    ) -> None:
        """T110: Report file created with correct structure."""
        # Set up a fake repo root with pyproject.toml so _find_reports_dir works
        repo_root = tmp_path
        (repo_root / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")

        completeness_result = CompletenessResult(
            verdict="PASS",
            issues=[],
            ast_analysis_ms=42,
            gemini_review_ms=None,
        )
        report_path = generate_implementation_report(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[sample_implementation_file],
            completeness_result=completeness_result,
        )

        assert report_path.exists()
        assert report_path.name == "999-implementation-report.md"
        assert "reports" in str(report_path).replace("\\", "/")

        content = report_path.read_text(encoding="utf-8")
        # Check for the actual heading format used by report_generator.py
        assert "999" in content
        assert "Implementation Verification Report" in content
        assert "Requirement Verification" in content or "LLD Requirement" in content
        assert "Completeness Analysis" in content
        assert "PASS" in content

    def test_report_contains_requirement_table(
        self, tmp_path: Path, sample_lld: Path, sample_implementation_file: Path
    ) -> None:
        """Report includes LLD requirement verification table."""
        repo_root = tmp_path
        (repo_root / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")

        completeness_result = CompletenessResult(
            verdict="PASS",
            issues=[],
            ast_analysis_ms=10,
            gemini_review_ms=None,
        )
        report_path = generate_implementation_report(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[sample_implementation_file],
            completeness_result=completeness_result,
        )
        content = report_path.read_text(encoding="utf-8")
        # Should have requirement verification rows
        assert "validate" in content.lower() or "Requirement" in content

    def test_report_contains_completeness_summary(
        self, tmp_path: Path, sample_lld: Path, sample_implementation_file: Path
    ) -> None:
        """Report includes completeness analysis summary."""
        repo_root = tmp_path
        (repo_root / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")

        issues = [
            CompletenessIssue(
                category=CompletenessCategory.EMPTY_BRANCH,
                file_path="module.py",
                line_number=10,
                description="Empty if branch",
                severity="WARNING",
            )
        ]
        completeness_result = CompletenessResult(
            verdict="WARN",
            issues=issues,
            ast_analysis_ms=15,
            gemini_review_ms=None,
        )
        report_path = generate_implementation_report(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[sample_implementation_file],
            completeness_result=completeness_result,
        )
        content = report_path.read_text(encoding="utf-8")
        assert "WARN" in content
        assert "Issues Detected" in content or "empty_branch" in content.lower() or "Empty Branch" in content

    def test_report_with_block_issues(
        self, tmp_path: Path, sample_lld: Path, sample_implementation_file: Path
    ) -> None:
        """Report generated correctly with BLOCK-level issues."""
        repo_root = tmp_path
        (repo_root / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")

        issues = [
            CompletenessIssue(
                category=CompletenessCategory.DOCSTRING_ONLY,
                file_path="stubs.py",
                line_number=5,
                description="Function 'stub' has docstring but no implementation",
                severity="ERROR",
            )
        ]
        completeness_result = CompletenessResult(
            verdict="BLOCK",
            issues=issues,
            ast_analysis_ms=8,
            gemini_review_ms=None,
        )
        report_path = generate_implementation_report(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[sample_implementation_file],
            completeness_result=completeness_result,
        )
        content = report_path.read_text(encoding="utf-8")
        assert "BLOCK" in content
        assert "ERROR" in content


# =============================================================================
# T120: LLD Requirement Extraction
# =============================================================================


class TestLLDRequirementExtraction:
    """T120 / Scenario 120: Requirements parsed from LLD Section 3."""

    def test_lld_requirement_extraction(self, sample_lld: Path) -> None:
        """T120: Requirements parsed from Section 3."""
        requirements = extract_lld_requirements(sample_lld)
        assert len(requirements) == 4
        assert requirements[0] == (1, "The system shall validate user input")
        assert requirements[1] == (
            2,
            "Error messages shall be displayed to the user",
        )
        assert requirements[2] == (
            3,
            "The API endpoint shall return JSON responses",
        )
        assert requirements[3] == (
            4,
            "Authentication tokens shall expire after 24 hours",
        )

    def test_extraction_returns_tuples(self, sample_lld: Path) -> None:
        """Each requirement is a (int, str) tuple."""
        requirements = extract_lld_requirements(sample_lld)
        for req_id, req_text in requirements:
            assert isinstance(req_id, int)
            assert isinstance(req_text, str)
            assert len(req_text) > 0

    def test_extraction_no_section_3_returns_empty(self, tmp_path: Path) -> None:
        """LLD without Section 3 returns empty list."""
        lld_path = tmp_path / "no-reqs.md"
        lld_path.write_text(
            "# Feature\n\n## 1. Context\n\nSome text.\n\n## 2. Changes\n\nStuff.\n"
        )
        requirements = extract_lld_requirements(lld_path)
        assert requirements == []

    def test_extraction_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Non-existent LLD file returns empty list."""
        lld_path = tmp_path / "nonexistent.md"
        requirements = extract_lld_requirements(lld_path)
        assert requirements == []

    def test_extraction_empty_section_3(self, tmp_path: Path) -> None:
        """Section 3 with no numbered items returns empty list."""
        lld_path = tmp_path / "empty-reqs.md"
        lld_path.write_text(
            "# Feature\n\n## 3. Requirements\n\nNo requirements listed.\n\n## 4. Alternatives\n"
        )
        requirements = extract_lld_requirements(lld_path)
        assert requirements == []


# =============================================================================
# T130: Review Materials Preparation
# =============================================================================


class TestPrepareReviewMaterials:
    """T130 / Scenario 130: ReviewMaterials correctly populated."""

    def test_prepare_review_materials(
        self, sample_lld: Path, sample_implementation_file: Path
    ) -> None:
        """T130: ReviewMaterials correctly populated with LLD requirements and code snippets."""
        materials = prepare_review_materials(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[sample_implementation_file],
        )

        assert materials["issue_number"] == 999
        assert len(materials["lld_requirements"]) == 4
        assert len(materials["code_snippets"]) == 1

        # Check requirements are (int, str) tuples
        for req_id, req_text in materials["lld_requirements"]:
            assert isinstance(req_id, int)
            assert isinstance(req_text, str)

        # Check code snippets contain actual code
        for file_path, code in materials["code_snippets"].items():
            assert len(code) > 0
            assert "def " in code  # Should contain function definitions

    def test_review_materials_with_multiple_files(
        self, tmp_path: Path, sample_lld: Path
    ) -> None:
        """ReviewMaterials handles multiple implementation files."""
        file1 = tmp_path / "module_a.py"
        file1.write_text('def func_a():\n    return "a"\n')
        file2 = tmp_path / "module_b.py"
        file2.write_text('def func_b():\n    return "b"\n')

        materials = prepare_review_materials(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[file1, file2],
        )
        assert len(materials["code_snippets"]) == 2

    def test_review_materials_skips_missing_files(
        self, tmp_path: Path, sample_lld: Path
    ) -> None:
        """Non-existent files are skipped in review materials."""
        existing = tmp_path / "exists.py"
        existing.write_text('def hello():\n    return "hi"\n')
        missing = tmp_path / "missing.py"

        materials = prepare_review_materials(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[existing, missing],
        )
        assert len(materials["code_snippets"]) == 1

    def test_review_materials_skips_non_python_files(
        self, tmp_path: Path, sample_lld: Path
    ) -> None:
        """Non-Python files are skipped in review materials."""
        py_file = tmp_path / "module.py"
        py_file.write_text('def func():\n    pass\n')
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("Not a Python file.")

        materials = prepare_review_materials(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[py_file, txt_file],
        )
        assert len(materials["code_snippets"]) == 1

    def test_review_materials_type_structure(
        self, sample_lld: Path, sample_implementation_file: Path
    ) -> None:
        """ReviewMaterials has correct TypedDict structure."""
        materials = prepare_review_materials(
            issue_number=999,
            lld_path=sample_lld,
            implementation_files=[sample_implementation_file],
        )
        assert "lld_requirements" in materials
        assert "code_snippets" in materials
        assert "issue_number" in materials
        assert isinstance(materials["lld_requirements"], list)
        assert isinstance(materials["code_snippets"], dict)
        assert isinstance(materials["issue_number"], int)


# =============================================================================
# run_ast_analysis Integration Tests
# =============================================================================


class TestRunASTAnalysis:
    """Integration tests for run_ast_analysis orchestrator."""

    def test_run_ast_analysis_with_issues(self, tmp_py_file) -> None:
        """run_ast_analysis detects issues across files."""
        stub_source = """\
            def stub_function():
                \"\"\"This is a stub.\"\"\"
                pass
        """
        file_path = tmp_py_file(stub_source, "stubby.py")
        result = run_ast_analysis([file_path])
        assert result["verdict"] == "BLOCK"
        assert len(result["issues"]) >= 1
        assert result["ast_analysis_ms"] >= 0

    def test_run_ast_analysis_empty_file_list(self) -> None:
        """Empty file list returns PASS with no issues."""
        result = run_ast_analysis([])
        assert result["verdict"] == "PASS"
        assert result["issues"] == []

    def test_run_ast_analysis_skips_large_files(self, tmp_py_file) -> None:
        """Files exceeding max_file_size_bytes are skipped."""
        # Create a file that would have issues if analyzed
        source = """\
            def stub():
                \"\"\"Stub.\"\"\"
                pass
        """
        file_path = tmp_py_file(source, "big_module.py")
        # Set max_file_size_bytes to 1 byte so the file is skipped
        result = run_ast_analysis([file_path], max_file_size_bytes=1)
        assert result["verdict"] == "PASS"
        assert result["issues"] == []

    def test_run_ast_analysis_skips_non_python(self, tmp_path: Path) -> None:
        """Non-Python files are skipped."""
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("Not python code.")
        result = run_ast_analysis([txt_file])
        assert result["verdict"] == "PASS"
        assert result["issues"] == []

    def test_run_ast_analysis_test_file_checks_assertions(
        self, tmp_py_file
    ) -> None:
        """Test files are checked for trivial assertions, not other patterns."""
        source = """\
            def test_trivial():
                result = get_thing()
                assert result is not None
        """
        file_path = tmp_py_file(source, "test_something.py")
        result = run_ast_analysis([file_path])
        assert result["verdict"] == "WARN"
        assert any(
            i["category"] == CompletenessCategory.TRIVIAL_ASSERTION
            for i in result["issues"]
        )

    def test_run_ast_analysis_mixed_files(self, tmp_py_file, tmp_path: Path) -> None:
        """Mix of clean and problematic files produces correct verdict."""
        clean_source = """\
            import json

            def process(data):
                return json.dumps(data)
        """
        stub_source = """\
            def broken():
                \"\"\"Broken.\"\"\"
                pass
        """
        clean_file = tmp_py_file(clean_source, "clean.py")
        stub_file = tmp_path / "stub.py"
        stub_file.write_text(textwrap.dedent(stub_source), encoding="utf-8")

        result = run_ast_analysis([clean_file, stub_file])
        assert result["verdict"] == "BLOCK"
        assert len(result["issues"]) >= 1

    def test_run_ast_analysis_warns_only_produces_warn_verdict(
        self, tmp_py_file
    ) -> None:
        """Only WARNING-level issues produce WARN verdict."""
        source = """\
            def process(x):
                if x > 0:
                    pass
                else:
                    return x
        """
        file_path = tmp_py_file(source, "warnings_only.py")
        result = run_ast_analysis([file_path])
        # Empty branches are WARNING severity
        assert result["verdict"] == "WARN"
        assert all(i["severity"] == "WARNING" for i in result["issues"])


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestDataStructures:
    """Verify data structure enums and types."""

    def test_completeness_category_values(self) -> None:
        """All expected category values exist."""
        assert CompletenessCategory.DEAD_CLI_FLAG.value == "dead_cli_flag"
        assert CompletenessCategory.EMPTY_BRANCH.value == "empty_branch"
        assert CompletenessCategory.DOCSTRING_ONLY.value == "docstring_only"
        assert CompletenessCategory.TRIVIAL_ASSERTION.value == "trivial_assertion"
        assert CompletenessCategory.UNUSED_IMPORT.value == "unused_import"

    def test_completeness_category_count(self) -> None:
        """Exactly 5 categories defined."""
        assert len(CompletenessCategory) == 5