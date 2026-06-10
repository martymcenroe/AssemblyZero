"""Tests for tools/fix_requires_python.py (#1574) -- pure logic only.

The clone/PR/merge orchestration is operator-run (gh CLI + network) and mirrors
the flow proven in AZ PR #1576; it is not unit-tested here. These cover the
detection + normalization helpers that decide what gets changed, and that
dry-run never touches the network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from fix_requires_python import (  # noqa: E402
    fix_repo,
    is_invalid_caret,
    normalized_spec,
)


class TestDetection:
    def test_caret_is_invalid(self):
        assert is_invalid_caret("^3.10")
        assert is_invalid_caret("^3.12")

    def test_tilde_is_invalid(self):
        assert is_invalid_caret("~3.10")

    def test_valid_specifiers_ok(self):
        assert not is_invalid_caret(">=3.10,<4.0")
        assert not is_invalid_caret(">=3.11")

    def test_none_is_not_invalid(self):
        assert not is_invalid_caret(None)


class TestNormalizedSpec:
    def test_caret_floors_preserved(self):
        assert normalized_spec("^3.10") == ">=3.10,<4.0"
        assert normalized_spec("^3.11") == ">=3.11,<4.0"
        assert normalized_spec("^3.12") == ">=3.12,<4.0"

    def test_result_is_valid_pep440(self):
        from packaging.specifiers import SpecifierSet
        SpecifierSet(normalized_spec("^3.10"))  # raises InvalidSpecifier if wrong


class TestDryRun:
    def test_dry_run_reports_without_mutating(self):
        # apply=False must short-circuit before any gh/network call.
        line = fix_repo("SomeRepo", "^3.11", token="unused", apply=False)
        assert "WOULD fix" in line
        assert "^3.11" in line and ">=3.11,<4.0" in line
