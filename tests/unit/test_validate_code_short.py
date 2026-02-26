"""Unit tests for validate_code_response() short-file handling.

Issue #473: Fixture files (e.g., malformed JSON) are intentionally 1 line
but were rejected by the "code too short" validator.

Tests verify:
- __init__.py (1 line) → valid
- Fixture paths → valid (even if 1 line)
- Data file extensions (.json, .yaml, .yml, .toml, .txt, .csv) → valid
- Regular Python file with 1 line → invalid
- Regular Python file with 5+ lines → valid
"""

from __future__ import annotations

from assemblyzero.workflows.testing.nodes.implement_code import (
    validate_code_response,
)


def test_init_py_single_line_valid():
    """__init__.py with 1 line should be valid."""
    valid, msg = validate_code_response("# init\n", "src/__init__.py")
    assert valid is True, msg


def test_fixture_path_single_line_valid():
    """Fixture files should be valid even with 1 line."""
    valid, msg = validate_code_response(
        '{this is not valid JSON!!!}',
        "tests/fixtures/malformed.json",
    )
    assert valid is True, msg


def test_fixture_subdir_valid():
    """Files in nested fixture directories should be valid."""
    valid, msg = validate_code_response(
        "single line content",
        "tests/fixtures/lld_tracking/sample.txt",
    )
    assert valid is True, msg


def test_json_extension_single_line_valid():
    """JSON files should be valid even with 1 line."""
    valid, msg = validate_code_response('{"key": "value"}', "config.json")
    assert valid is True, msg


def test_yaml_extension_single_line_valid():
    """YAML files should be valid even with 1 line."""
    valid, msg = validate_code_response("key: value", "config.yaml")
    assert valid is True, msg


def test_yml_extension_single_line_valid():
    """YML files should be valid even with 1 line."""
    valid, msg = validate_code_response("key: value", "config.yml")
    assert valid is True, msg


def test_toml_extension_single_line_valid():
    """TOML files should be valid even with 1 line."""
    valid, msg = validate_code_response('key = "value"', "pyproject.toml")
    assert valid is True, msg


def test_txt_extension_single_line_valid():
    """TXT files should be valid even with 1 line."""
    valid, msg = validate_code_response("hello world", "data.txt")
    assert valid is True, msg


def test_csv_extension_single_line_valid():
    """CSV files should be valid even with 1 line."""
    valid, msg = validate_code_response("a,b,c", "data.csv")
    assert valid is True, msg


def test_regular_py_single_line_invalid():
    """Regular .py file with 1 line should be rejected."""
    valid, msg = validate_code_response("x = 1", "src/main.py")
    assert valid is False
    assert "too short" in msg.lower()


def test_regular_py_five_lines_valid():
    """Regular .py file with 5+ lines should be valid."""
    code = "\n".join([f"line_{i} = {i}" for i in range(5)])
    valid, msg = validate_code_response(code, "src/main.py")
    assert valid is True, msg


def test_windows_fixture_path_valid():
    r"""Windows-style fixture path (backslashes) should be valid."""
    valid, msg = validate_code_response(
        "data",
        r"tests\fixtures\sample.txt",
    )
    assert valid is True, msg
