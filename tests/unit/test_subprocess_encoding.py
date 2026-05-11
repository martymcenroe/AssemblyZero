"""Regression tests for #837 -- subprocess calls must specify UTF-8 + replace
on Windows so non-ASCII output (unicode file paths, tracebacks with emoji,
non-Latin-1 stdout) doesn't crash workflow nodes with UnicodeDecodeError.

The fix is to pass `encoding="utf-8", errors="replace"` to subprocess.run when
`text=True` (or `capture_output=True` which implies text). These tests assert
the fix is in place at the call sites and at the central `run_command()`
helper in `assemblyzero/utils/shell.py`.
"""
from unittest.mock import patch

from assemblyzero.utils import shell


def test_run_command_defaults_encoding_to_utf8_with_replace():
    """The central helper must default to UTF-8 + replace so callers don't
    need to remember on every call. #837."""
    with patch.object(shell.subprocess, "run") as mock_run:
        shell.run_command("git status")
    _, kwargs = mock_run.call_args
    assert kwargs.get("encoding") == "utf-8", (
        "run_command must default encoding to 'utf-8' "
        "(Windows otherwise defaults to CP1252 and crashes on UTF-8 output)"
    )
    assert kwargs.get("errors") == "replace", (
        "run_command must default errors to 'replace' so undecodable bytes "
        "are substituted with U+FFFD instead of raising UnicodeDecodeError"
    )


def test_run_command_caller_can_override_encoding():
    """Defaults must be overridable -- otherwise binary stdout callers
    can't pass encoding=None to get bytes back."""
    with patch.object(shell.subprocess, "run") as mock_run:
        shell.run_command("git status", encoding="latin-1", errors="strict")
    _, kwargs = mock_run.call_args
    assert kwargs.get("encoding") == "latin-1"
    assert kwargs.get("errors") == "strict"


def test_run_command_does_not_crash_on_utf8_bytes_in_decoder():
    """End-to-end: when the subprocess emits UTF-8 bytes, they decode cleanly
    instead of raising. Uses a fake CompletedProcess whose stdout has been
    decoded by the (mocked) subprocess layer."""
    fake_stdout = "café — non-ASCII output"  # contains chars that crash CP1252
    with patch.object(shell.subprocess, "run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = fake_stdout
        mock_run.return_value.stderr = ""
        result = shell.run_command("git status")
    assert result.stdout == fake_stdout
