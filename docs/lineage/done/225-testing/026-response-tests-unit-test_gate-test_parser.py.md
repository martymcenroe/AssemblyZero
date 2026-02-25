

```python
"""Unit tests for tools/test_gate/parser.py.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.test_gate.models import SkippedTest
from tools.test_gate.parser import (
    CRITICAL_KEYWORDS,
    detect_critical_tests,
    ensure_verbose_flag,
    parse_skipped_tests,
    run_pytest,
)


# --- T025: test_auto_add_verbose_flag ---


class TestEnsureVerboseFlag:
    """Tests for ensure_verbose_flag()."""

    def test_adds_v_when_missing(self) -> None:
        """T025: -v is added when no verbose flag is present."""
        result = ensure_verbose_flag(["tests/unit/", "--tb=short"])
        assert "-v" in result
        assert result == ["tests/unit/", "--tb=short", "-v"]

    def test_does_not_add_when_v_present(self) -> None:
        """Verbose flag already present as -v."""
        result = ensure_verbose_flag(["tests/", "-v"])
        assert result == ["tests/", "-v"]
        assert result.count("-v") == 1

    def test_does_not_add_when_vv_present(self) -> None:
        """Verbose flag already present as -vv."""
        result = ensure_verbose_flag(["-vv", "tests/"])
        assert result == ["-vv", "tests/"]
        assert "-v" not in [a for a in result if a == "-v"]

    def test_does_not_add_when_verbose_present(self) -> None:
        """Verbose flag already present as --verbose."""
        result = ensure_verbose_flag(["--verbose", "tests/"])
        assert result == ["--verbose", "tests/"]

    def test_empty_list_adds_v(self) -> None:
        """Empty args list gets -v added."""
        result = ensure_verbose_flag([])
        assert result == ["-v"]

    def test_does_not_mutate_input(self) -> None:
        """Input list is not mutated."""
        original = ["tests/", "--tb=short"]
        original_copy = list(original)
        ensure_verbose_flag(original)
        assert original == original_copy


# --- T030, T040: test_parse_skipped ---


class TestParseSkippedTests:
    """Tests for parse_skipped_tests()."""

    def test_parse_inline_skip_format(self) -> None:
        """T030: Parse 'test_name SKIPPED (reason)' format."""
        output = "tests/unit/test_auth.py::test_oauth SKIPPED (Requires provider)\n"
        result = parse_skipped_tests(output)
        assert len(result) == 1
        assert result[0]["name"] == "tests/unit/test_auth.py::test_oauth"
        assert result[0]["reason"] == "Requires provider"
        assert result[0]["file_path"] == "tests/unit/test_auth.py"
        assert result[0]["line_number"] == 0
        assert result[0]["is_critical"] is False

    def test_parse_block_skip_format(self) -> None:
        """T030: Parse 'SKIPPED [N] file:line: reason' format."""
        output = "SKIPPED [1] tests/unit/test_payment.py:55: Gateway unavailable\n"
        result = parse_skipped_tests(output)
        assert len(result) == 1
        assert result[0]["file_path"] == "tests/unit/test_payment.py"
        assert result[0]["line_number"] == 55
        assert result[0]["reason"] == "Gateway unavailable"

    def test_parse_multiple_skips(self) -> None:
        """T040: Multiple skipped tests are all captured."""
        output = (
            "tests/test_a.py::test_one SKIPPED (reason one)\n"
            "tests/test_b.py::test_two SKIPPED (reason two)\n"
            "SKIPPED [1] tests/test_c.py:10: reason three\n"
        )
        result = parse_skipped_tests(output)
        assert len(result) == 3

    def test_parse_no_skips(self) -> None:
        """T150: No SKIPPED lines returns empty list."""
        output = "tests/test_a.py::test_one PASSED\n===== 1 passed =====\n"
        result = parse_skipped_tests(output)
        assert result == []

    def test_parse_empty_output(self) -> None:
        """Edge case: empty string returns empty list."""
        assert parse_skipped_tests("") == []

    def test_parse_mixed_output(self) -> None:
        """Mixed passing and skipped output."""
        output = (
            "tests/test_a.py::test_pass PASSED\n"
            "tests/test_a.py::test_skip SKIPPED (some reason)\n"
            "tests/test_a.py::test_fail FAILED\n"
        )
        result = parse_skipped_tests(output)
        assert len(result) == 1
        assert result[0]["name"] == "tests/test_a.py::test_skip"


# --- T050, T060: test_detect_critical ---


class TestDetectCriticalTests:
    """Tests for detect_critical_tests()."""

    def test_detect_by_auth_keyword(self) -> None:
        """T060: 'auth' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_auth.py::test_oauth",
                reason="r",
                line_number=0,
                file_path="tests/test_auth.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_detect_by_security_keyword(self) -> None:
        """T060: 'security' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_security.py::test_xss",
                reason="r",
                line_number=0,
                file_path="tests/test_security.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_detect_by_payment_keyword(self) -> None:
        """T060: 'payment' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_payment.py::test_charge",
                reason="r",
                line_number=0,
                file_path="tests/test_payment.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_detect_by_critical_keyword(self) -> None:
        """T050: 'critical' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_core.py::test_critical_path",
                reason="r",
                line_number=0,
                file_path="tests/test_core.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_non_critical_unchanged(self) -> None:
        """Non-critical test stays non-critical."""
        tests = [
            SkippedTest(
                name="tests/test_utils.py::test_format",
                reason="r",
                line_number=0,
                file_path="tests/test_utils.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is False

    def test_already_critical_stays_critical(self) -> None:
        """Test already marked critical is not downgraded."""
        tests = [
            SkippedTest(
                name="tests/test_utils.py::test_format",
                reason="r",
                line_number=0,
                file_path="tests/test_utils.py",
                is_critical=True,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        assert detect_critical_tests([]) == []

    def test_does_not_mutate_input(self) -> None:
        """Input list is not mutated."""
        tests = [
            SkippedTest(
                name="tests/test_auth.py::test_x",
                reason="r",
                line_number=0,
                file_path="tests/test_auth.py",
                is_critical=False,
            )
        ]
        detect_critical_tests(tests)
        assert tests[0]["is_critical"] is False


# --- T010: test_wrapper_passes_through_args ---


class TestRunPytest:
    """Tests for run_pytest()."""

    @patch("tools.test_gate.parser.subprocess.Popen")
    def test_passes_through_args(self, mock_popen: MagicMock) -> None:
        """T010: All pytest args forwarded unchanged to subprocess."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("output", "")
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        run_pytest(["tests/unit/", "-v", "-x"])

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        # cmd should be [sys.executable, "-m", "pytest", "tests/unit/", "-v", "-x"]
        assert cmd[2] == "pytest"
        assert "tests/unit/" in cmd
        assert "-v" in cmd
        assert "-x" in cmd

    @patch("tools.test_gate.parser.subprocess.Popen")
    def test_preserves_exit_code(self, mock_popen: MagicMock) -> None:
        """T020: Exit code from pytest is preserved."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 1
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc

        exit_code, _, _ = run_pytest(["tests/"])
        assert exit_code == 1

    @patch("tools.test_gate.parser.subprocess.Popen")
    def test_timeout_returns_error(self, mock_popen: MagicMock) -> None:
        """Timeout produces exit code 1 and error message."""
        import subprocess as sp

        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = sp.TimeoutExpired(cmd="pytest", timeout=5)
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        exit_code, stdout, stderr = run_pytest(["tests/"], timeout=5)
        assert exit_code == 1
        assert "timed out" in stderr

    @patch(
        "tools.test_gate.parser.subprocess.Popen",
        side_effect=FileNotFoundError("not found"),
    )
    def test_file_not_found_returns_error(self, mock_popen: MagicMock) -> None:
        """Missing pytest returns error."""
        exit_code, stdout, stderr = run_pytest(["tests/"])
        assert exit_code == 1
        assert "not found" in stderr
```
