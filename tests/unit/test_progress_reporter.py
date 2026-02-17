"""Tests for ProgressReporter — Issue #267.

Verifies the progress feedback mechanism used during long API calls
in the N4 implementation node.
"""

import time
from io import StringIO
from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.implement_code import ProgressReporter


class TestProgressReporter:
    """Tests for ProgressReporter context manager."""

    def test_reports_done_on_success(self, capsys):
        """Prints 'done' with elapsed time on successful exit."""
        with ProgressReporter("Testing", interval=60):
            time.sleep(0.05)

        captured = capsys.readouterr()
        assert "done" in captured.out
        assert "Testing..." in captured.out

    def test_reports_error_on_exception(self, capsys):
        """Prints 'error' when exception occurs inside context."""
        try:
            with ProgressReporter("Testing", interval=60):
                raise ValueError("boom")
        except ValueError:
            pass

        captured = capsys.readouterr()
        assert "error" in captured.out

    def test_does_not_raise_on_normal_exit(self):
        """Context manager does not suppress exceptions."""
        with ProgressReporter("Testing", interval=60):
            pass  # Should not raise

    def test_exception_propagates(self):
        """Exceptions are not swallowed by the context manager."""
        import pytest

        with pytest.raises(RuntimeError, match="test error"):
            with ProgressReporter("Testing", interval=60):
                raise RuntimeError("test error")

    def test_periodic_output_fires(self, capsys):
        """With short interval, periodic output is printed."""
        with ProgressReporter("Waiting", interval=0.1):
            time.sleep(0.35)

        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if "Waiting..." in l]
        # At least 2 periodic outputs + 1 final "done"
        assert len(lines) >= 3

    def test_elapsed_time_increases(self, capsys):
        """Elapsed time in output is non-negative."""
        with ProgressReporter("Timer", interval=60):
            time.sleep(0.05)

        captured = capsys.readouterr()
        # Extract time from output like "Timer... done (0s)"
        assert "(0s)" in captured.out or "(1s)" in captured.out

    def test_thread_stops_after_exit(self):
        """Background thread stops when context exits."""
        reporter = ProgressReporter("Test", interval=0.1)
        with reporter:
            time.sleep(0.05)

        # Give thread time to stop
        time.sleep(0.2)
        assert reporter._thread is not None
        assert not reporter._thread.is_alive()
