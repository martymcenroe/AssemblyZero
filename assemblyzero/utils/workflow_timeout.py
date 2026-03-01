"""Global workflow timeout utility.

Issue #517: Prevents stuck workflows from running forever by enforcing
a wall-clock timeout across the entire workflow execution.

Usage:
    from assemblyzero.utils.workflow_timeout import WorkflowTimeout

    with WorkflowTimeout(minutes=90):
        # ... run workflow ...
        # Raises SystemExit if timeout exceeded

    # Or with 0 to disable:
    with WorkflowTimeout(minutes=0):
        # No timeout enforced
        pass
"""

import sys
import threading


class WorkflowTimeoutError(SystemExit):
    """Raised when workflow exceeds its wall-clock timeout.

    Inherits from SystemExit so it propagates through LangGraph's
    exception handling without being caught by generic Exception handlers.
    """

    def __init__(self, minutes: int):
        self.minutes = minutes
        super().__init__(
            f"\n[TIMEOUT] Workflow exceeded {minutes}-minute wall-clock limit. "
            f"Shutting down cleanly.\n"
            f"This is a safety guard to prevent stuck workflows from running forever.\n"
            f"Use --timeout to adjust (e.g., --timeout 120 for 2 hours, --timeout 0 to disable)."
        )


class WorkflowTimeout:
    """Context manager that enforces a global wall-clock timeout.

    Uses a daemon thread timer that interrupts the main thread via
    SystemExit after the specified duration. The daemon thread ensures
    cleanup even if the main thread is stuck.

    Args:
        minutes: Timeout in minutes. 0 disables the timeout.
    """

    def __init__(self, minutes: int = 30):
        self.minutes = minutes
        self._timer: threading.Timer | None = None

    def __enter__(self) -> "WorkflowTimeout":
        if self.minutes <= 0:
            return self

        seconds = self.minutes * 60

        def _timeout_handler():
            print(
                f"\n{'=' * 70}\n"
                f"[TIMEOUT] Workflow exceeded {self.minutes}-minute wall-clock limit.\n"
                f"Forcing shutdown to prevent resource waste.\n"
                f"{'=' * 70}\n",
                file=sys.stderr,
                flush=True,
            )
            # os._exit is the nuclear option — it bypasses all cleanup.
            # We use it because the main thread may be stuck in a blocking call
            # (subprocess, network I/O) that won't respond to exceptions.
            import os
            os._exit(42)

        self._timer = threading.Timer(seconds, _timeout_handler)
        self._timer.daemon = True
        self._timer.start()

        remaining = self.minutes
        print(f"    [TIMEOUT] Global workflow timeout: {remaining} minutes")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        return False  # Don't suppress exceptions


def add_timeout_argument(parser) -> None:
    """Add --timeout argument to an argparse parser.

    Issue #517: Shared helper so all workflow runners use the same flag.

    Args:
        parser: argparse.ArgumentParser instance.
    """
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        metavar="MINUTES",
        help="Global wall-clock timeout in minutes (default: 30, 0=disable)",
    )
