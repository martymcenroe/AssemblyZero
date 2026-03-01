"""Tests for Issue #517: Global workflow timeout utility.

Tests the WorkflowTimeout context manager and add_timeout_argument helper.
"""

import argparse
import time

from assemblyzero.utils.workflow_timeout import (
    WorkflowTimeout,
    WorkflowTimeoutError,
    add_timeout_argument,
)


class TestWorkflowTimeout:
    """Tests for WorkflowTimeout context manager."""

    def test_no_timeout_when_zero(self):
        """minutes=0 disables timeout — no timer created."""
        wt = WorkflowTimeout(minutes=0)
        with wt:
            assert wt._timer is None

    def test_timer_created_for_positive_minutes(self):
        """Positive minutes creates a daemon timer."""
        wt = WorkflowTimeout(minutes=90)
        with wt:
            assert wt._timer is not None
            assert wt._timer.daemon is True
            assert wt._timer.is_alive()
        # Timer cancelled and cleared on exit
        assert wt._timer is None

    def test_timer_cleared_on_normal_exit(self):
        """Timer ref is cleared when context exits normally."""
        wt = WorkflowTimeout(minutes=90)
        with wt:
            assert wt._timer is not None
        # Timer ref cleared on exit
        assert wt._timer is None

    def test_timer_cleared_on_exception(self):
        """Timer ref is cleared even when context exits via exception."""
        wt = WorkflowTimeout(minutes=90)
        try:
            with wt:
                assert wt._timer is not None
                raise ValueError("test error")
        except ValueError:
            pass
        assert wt._timer is None

    def test_does_not_suppress_exceptions(self):
        """Context manager does not suppress exceptions."""
        with_error = False
        try:
            with WorkflowTimeout(minutes=90):
                raise RuntimeError("should propagate")
        except RuntimeError:
            with_error = True
        assert with_error

    def test_default_minutes_is_30(self):
        """Default timeout is 30 minutes."""
        wt = WorkflowTimeout()
        assert wt.minutes == 30


class TestWorkflowTimeoutError:
    """Tests for the WorkflowTimeoutError exception."""

    def test_is_system_exit(self):
        """WorkflowTimeoutError inherits from SystemExit."""
        err = WorkflowTimeoutError(minutes=90)
        assert isinstance(err, SystemExit)

    def test_stores_minutes(self):
        """Stores the timeout value."""
        err = WorkflowTimeoutError(minutes=45)
        assert err.minutes == 45

    def test_message_includes_timeout_value(self):
        """Error message mentions the timeout duration."""
        err = WorkflowTimeoutError(minutes=90)
        assert "90" in str(err)
        assert "TIMEOUT" in str(err)


class TestAddTimeoutArgument:
    """Tests for the add_timeout_argument helper."""

    def test_adds_timeout_flag(self):
        """Adds --timeout with default 90."""
        parser = argparse.ArgumentParser()
        add_timeout_argument(parser)
        args = parser.parse_args([])
        assert args.timeout == 30

    def test_custom_timeout(self):
        """--timeout accepts custom value."""
        parser = argparse.ArgumentParser()
        add_timeout_argument(parser)
        args = parser.parse_args(["--timeout", "120"])
        assert args.timeout == 120

    def test_disable_timeout(self):
        """--timeout 0 disables."""
        parser = argparse.ArgumentParser()
        add_timeout_argument(parser)
        args = parser.parse_args(["--timeout", "0"])
        assert args.timeout == 0
