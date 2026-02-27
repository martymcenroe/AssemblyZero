```python
"""Unit tests for adversarial test file writer.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import os
import tempfile

import pytest

from assemblyzero.workflows.testing.nodes.adversarial_writer import (
    _render_test_file,
    _sanitize_category,
    write_adversarial_tests,
)


def _make_test_case(**overrides):
    """Helper to create a test case dict."""
    base = {
        "test_id": "ADV_001",
        "target_function": "module.func",
        "category": "boundary",
        "description": "Test description",
        "test_code": "def test_example():\n    assert True",
        "claim_challenged": "some claim",
        "severity": "high",
    }
    base.update(overrides)
    return base


class TestWriteAdversarialTests:
    """Tests for write_adversarial_tests (T070, T080)."""

    def test_groups_by_category(self, tmp_path):
        """T070: 3 boundary + 2 contract cases → 2 files created."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_id="ADV_001", category="boundary", test_code="def test_b1():\n    assert True"),
                _make_test_case(test_id="ADV_002", category="boundary", test_code="def test_b2():\n    assert True"),
                _make_test_case(test_id="ADV_003", category="boundary", test_code="def test_b3():\n    assert True"),
                _make_test_case(test_id="ADV_004", category="contract", test_code="def test_c1():\n    assert True"),
                _make_test_case(test_id="ADV_005", category="contract", test_code="def test_c2():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        assert len(result) == 2
        filepaths = list(result.keys())
        filenames = [os.path.basename(fp) for fp in filepaths]
        assert "test_352_boundary.py" in filenames
        assert "test_352_contract.py" in filenames

    def test_file_naming_convention(self, tmp_path):
        """T080: Output file named test_{issue_id}_{category}.py."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(category="injection", test_code="def test_inj():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        filepaths = list(result.keys())
        assert len(filepaths) == 1
        assert filepaths[0].endswith("test_352_injection.py")

    def test_empty_test_cases_no_files(self, tmp_path):
        """Empty test_cases returns empty dict."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)
        assert result == {}

    def test_creates_output_dir(self, tmp_path):
        """Output directory is created if it doesn't exist."""
        output_dir = str(tmp_path / "nested" / "adversarial")
        assert not os.path.exists(output_dir)

        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_code="def test_x():\n    assert True"),
            ],
        }

        result = write_adversarial_tests(analysis, issue_id=99, output_dir=output_dir)
        assert len(result) == 1
        assert os.path.exists(output_dir)

    def test_files_written_to_disk(self, tmp_path):
        """Files are actually written to disk, not just returned."""
        output_dir = str(tmp_path / "adversarial")
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(category="boundary", test_code="def test_disk():\n    assert True"),
            ],
        }

        result = write_adversarial_tests(analysis, issue_id=352, output_dir=output_dir)

        for filepath, content in result.items():
            assert os.path.exists(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                assert f.read() == content

    def test_multiple_categories_separate_files(self, tmp_path):
        """Each category gets its own file."""
        analysis = {
            "uncovered_edge_cases": [],
            "false_claims": [],
            "missing_error_handling": [],
            "implicit_assumptions": [],
            "test_cases": [
                _make_test_case(test_id="ADV_001", category="boundary", test_code="def test_b():\n    assert True"),
                _make_test_case(test_id="ADV_002", category="injection", test_code="def test_i():\n    assert True"),
                _make_test_case(test_id="ADV_003", category="state", test_code="def test_s():\n    assert True"),
            ],
        }

        output_dir = str(tmp_path / "adversarial")
        result = write_adversarial_tests(analysis, issue_id=100, output_dir=output_dir)

        assert len(result) == 3
        filenames = [os.path.basename(fp) for fp in result.keys()]
        assert "test_100_boundary.py" in filenames
        assert "test_100_injection.py" in filenames
        assert "test_100_state.py" in filenames


class TestRenderTestFile:
    """Tests for _render_test_file (T090, T280, T290)."""

    def test_renders_valid_pytest_syntax(self):
        """T090: Generated file passes compile()."""
        cases = [
            _make_test_case(
                test_code="def test_something():\n    x = 1\n    assert x == 1"
            )
        ]
        content = _render_test_file(cases, "boundary", 352)
        compile(content, "test_352_boundary.py", "exec")  # Should not raise

    def test_adversarial_header_present(self):
        """T280: File starts with '# ADVERSARIAL TEST FILE' header."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert content.startswith("# ADVERSARIAL TEST FILE")

    def test_header_includes_issue_and_category(self):
        """T290: Header contains issue number and category."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "injection", 352)

        lines = content.split("\n")
        header = "\n".join(lines[:5])
        assert "Issue: #352" in header
        assert "Category: injection" in header

    def test_no_mock_docstring(self):
        """Rendered file includes no-mock enforcement docstring."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "NO mocks" in content

    def test_empty_cases_renders_header_only(self):
        """Empty test_cases list renders file with header/docstring only."""
        content = _render_test_file([], "boundary", 352)
        assert "# ADVERSARIAL TEST FILE" in content
        assert "NO mocks" in content
        # Should still compile
        compile(content, "test_352_boundary.py", "exec")

    def test_test_code_without_def_wrapped(self):
        """Test code without 'def test_' prefix is wrapped in a function."""
        cases = [
            _make_test_case(
                test_id="ADV_042",
                test_code="assert 1 + 1 == 2",
            )
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "def test_" in content
        # Should compile
        compile(content, "test_352_boundary.py", "exec")

    def test_severity_comment_present(self):
        """Rendered file includes severity comment for each test."""
        cases = [
            _make_test_case(severity="critical")
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "# Severity: critical" in content

    def test_claim_challenged_comment(self):
        """Rendered file includes claim challenged comment."""
        cases = [
            _make_test_case(claim_challenged="LLD claims all inputs handled")
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "# Challenges: LLD claims all inputs handled" in content

    def test_multiple_cases_all_rendered(self):
        """All test cases are rendered in the output."""
        cases = [
            _make_test_case(test_id="ADV_001", test_code="def test_one():\n    assert True"),
            _make_test_case(test_id="ADV_002", test_code="def test_two():\n    assert True"),
            _make_test_case(test_id="ADV_003", test_code="def test_three():\n    assert True"),
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "def test_one():" in content
        assert "def test_two():" in content
        assert "def test_three():" in content
        compile(content, "test_352_boundary.py", "exec")

    def test_empty_test_code_skipped(self):
        """Test cases with empty test_code are skipped."""
        cases = [
            _make_test_case(test_id="ADV_001", test_code=""),
            _make_test_case(test_id="ADV_002", test_code="def test_real():\n    assert True"),
        ]
        content = _render_test_file(cases, "boundary", 352)
        assert "def test_real():" in content
        # The empty one should not generate a broken function
        compile(content, "test_352_boundary.py", "exec")

    def test_generator_comment_in_header(self):
        """Header includes generator identification."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "Generator: assemblyzero adversarial testing node" in content

    def test_warning_comment_in_header(self):
        """Header includes regeneration warning."""
        cases = [_make_test_case()]
        content = _render_test_file(cases, "boundary", 352)
        assert "WARNING: Do not manually edit" in content


class TestSanitizeCategory:
    """Tests for _sanitize_category."""

    def test_normal_category(self):
        assert _sanitize_category("boundary") == "boundary"

    def test_uppercase(self):
        assert _sanitize_category("BOUNDARY") == "boundary"

    def test_special_chars(self):
        assert _sanitize_category("state-machine") == "state_machine"

    def test_empty(self):
        assert _sanitize_category("") == "general"

    def test_spaces(self):
        assert _sanitize_category("edge case") == "edge_case"

    def test_multiple_special_chars(self):
        """Multiple consecutive special chars collapse to single underscore."""
        result = _sanitize_category("foo--bar__baz")
        assert "__" not in result
        assert "--" not in result

    def test_leading_trailing_special_chars(self):
        """Leading/trailing special characters are stripped."""
        result = _sanitize_category("-boundary-")
        assert result == "boundary"

    def test_numbers_preserved(self):
        """Numbers in category names are preserved."""
        assert _sanitize_category("test123") == "test123"

    def test_mixed_case_with_special(self):
        """Mixed case with special characters handled correctly."""
        result = _sanitize_category("State-Machine_Test")
        assert result == "state_machine_test"
```
