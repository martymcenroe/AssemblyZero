"""adversarial_validator.py under standard 0034, one test per open sweep site.

Ledger 0908 found the three open sites compliant: a file that does not
compile is an error and the result is invalid, and the mock and assertion
scans answer "nothing found" for source that does not parse because their
only caller runs them after ``compile`` accepted it. These tests pin that,
and that a syntax error is reported once, by the check that owns it. Lines
63 and 79 were fixed in #3725 and are tested in test_adversarial_review_halts.py.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

from assemblyzero.workflows.testing.nodes.adversarial_validator import (
    _check_assertions,
    _check_no_mocks,
    _check_syntax,
    validate_adversarial_tests,
)

BROKEN = "def test_a(:\n    assert True\n"


def test_114_the_mock_scan_of_unparseable_source_adds_nothing():
    assert _check_no_mocks(BROKEN, "t.py") == []

    result = validate_adversarial_tests({"t.py": BROKEN})
    assert result["valid"] is False
    assert result["mock_violations"] == []
    assert [e for e in result["errors"] if "SyntaxError" in e] == result["errors"]


def test_227_a_test_file_that_does_not_compile_is_an_error():
    assert _check_syntax(BROKEN, "t.py") == ["t.py: SyntaxError: invalid syntax (line 1)"]

    result = validate_adversarial_tests({"t.py": BROKEN, "u.py": "def test_b():\n    assert 1\n"})
    assert result["valid"] is False
    assert result["errors"] == ["t.py: SyntaxError: invalid syntax (line 1)"]


def test_251_the_assertion_scan_of_unparseable_source_adds_nothing():
    """The syntax error is the file's one error; it is not also reported as
    a test with no assertions."""
    assert _check_assertions(BROKEN, "t.py") == []

    result = validate_adversarial_tests({"t.py": BROKEN})
    assert len(result["errors"]) == 1
    assert "no assertions" not in result["errors"][0]


def test_the_scans_still_run_on_source_that_compiles():
    """Kept: a mock and a test without assertions are found in valid code."""
    source = (
        "from unittest.mock import MagicMock\n\n\n"
        "def test_a():\n    MagicMock()\n"
    )
    result = validate_adversarial_tests({"t.py": source})
    assert result["valid"] is False
    assert result["mock_violations"]
    assert result["errors"] == ["t.py: test_a has no assertions"]
