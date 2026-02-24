"""Actor detection for telemetry events.

Determines whether the current execution is driven by a human or Claude,
and identifies the GitHub user and machine.
"""

import hashlib
import os
import platform
import subprocess


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


def detect_github_user() -> str:
    """Detect the current GitHub user via gh CLI.

    Returns the GitHub username, or "unknown" if detection fails.
    Caches the result for the process lifetime.
    """
    if not hasattr(detect_github_user, "_cached"):
        try:
            result = subprocess.run(
                ["gh", "auth", "status", "--show-token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines() + result.stderr.splitlines():
                if "Logged in to github.com account" in line:
                    # Format: "  ✓ Logged in to github.com account USERNAME ..."
                    parts = line.split("account")
                    if len(parts) > 1:
                        username = parts[1].strip().split()[0].strip("()")
                        detect_github_user._cached = username
                        return username
        except Exception:
            pass
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
