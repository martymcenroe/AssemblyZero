"""Actor detection for telemetry events.

Determines whether the current execution is driven by a human or Claude,
and identifies the GitHub user and machine.
"""

import hashlib
import os
import platform
import subprocess
import sys


def detect_actor() -> str:
    """Detect whether current execution is human or Claude.

    Returns "claude" if CLAUDECODE or UNLEASHED_VERSION env vars are set,
    otherwise returns "human".
    """
    if os.environ.get("CLAUDECODE") is not None:
        return "claude"
    if os.environ.get("UNLEASHED_VERSION"):
        return "claude"
    return "human"


def _detection_failed(cause: str) -> None:
    """The ERROR line for a detection that fell back to "unknown" (#3585).

    Never echoes gh's output. Not an alert or a raise: every telemetry event
    calls this, and the unit tier runs in CI with no gh login.
    """
    print(
        f"ERROR [TELEMETRY] GitHub user not detected ({cause}); events are "
        f"labelled 'unknown' for this process",
        file=sys.stderr,
        flush=True,
    )


def detect_github_user() -> str:
    """Detect the current GitHub user via gh CLI.

    Returns the GitHub username, or "unknown" if detection fails; "unknown" is
    the declared label, and a failed detection writes an ERROR line to stderr
    naming the cause first (#3585). Caches the result for the process
    lifetime. gh is not asked for the token: the username line does not need
    it, and a captured token is one more place for it to leak.
    """
    if not hasattr(detect_github_user, "_cached"):
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            _detection_failed(f"gh could not run: {type(exc).__name__}")
            detect_github_user._cached = "unknown"
            return detect_github_user._cached
        if result.returncode != 0:
            _detection_failed(f"gh auth status exited {result.returncode}")
            detect_github_user._cached = "unknown"
            return detect_github_user._cached
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            if "Logged in to github.com account" in line:
                # Format: "  ✓ Logged in to github.com account USERNAME ..."
                parts = line.split("account")
                if len(parts) > 1 and parts[1].strip():
                    username = parts[1].strip().split()[0].strip("()")
                    detect_github_user._cached = username
                    return username
        _detection_failed("gh auth status named no github.com account")
        detect_github_user._cached = "unknown"
    return detect_github_user._cached


def get_machine_id() -> str:
    """Generate a stable machine identifier (hashed for privacy).

    Returns a short hash based on hostname + platform, stable across sessions.
    """
    if not hasattr(get_machine_id, "_cached"):
        raw = f"{platform.node()}:{platform.system()}:{platform.machine()}"
        get_machine_id._cached = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return get_machine_id._cached
