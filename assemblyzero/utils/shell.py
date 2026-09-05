"""Shell utilities for cross-platform command execution.

Architectural boundary: All workflow nodes in assemblyzero/workflows/ MUST
route shell commands through ``run_command()`` instead of calling
``subprocess.run()`` directly.  This ensures uniform security validation,
bash-wrapping on Windows, and timeout handling.

Issue #601: Windows Shell-Aware Utility.
Issue #598: Permissible Command Middleware.
Issue #611: Activate middleware across workflow nodes.
"""

import sys
import subprocess
from typing import Any

from assemblyzero.core.errors import SecurityException
from assemblyzero.core.github_writes import suppress_if_inert

PROHIBITED_FLAGS: frozenset[str] = frozenset({"--admin", "--force", "-D", "--hard"})


def validate_command(command: str | list[str]) -> None:
    """Check command for prohibited dangerous flags using token-boundary matching.

    Raises:
        SecurityException: If a prohibited flag is detected.
    """
    tokens: list[str]
    if isinstance(command, list):
        tokens = command
    else:
        tokens = command.split()

    for token in tokens:
        if token in PROHIBITED_FLAGS:
            raise SecurityException(
                f"Security Block: Command contains prohibited flag '{token}'",
                command=" ".join(tokens),
                flag=token,
            )


def wrap_bash_if_needed(command: str) -> str:
    """Wrap command in bash -c if running on Windows and contains Bash symbols.

    Args:
        command: The shell command to execute.

    Returns:
        The original command or a bash-wrapped version for Windows.
    """
    if sys.platform != "win32":
        return command

    bash_symbols = ["&&", "||", ">", "<", "|", "2>&1", "<<", "$"]

    if any(sym in command for sym in bash_symbols):
        escaped_cmd = command.replace("'", "'\\''")
        return f"bash -c '{escaped_cmd}'"

    return command


def run_command(
    command: str | list[str],
    cwd: str | None = None,
    timeout: int = 300,
    shell: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a command safely across platforms.

    If command is a string and on Windows, it will be wrapped in bash -c
    if bash symbols are detected.

    Raises:
        SecurityException: If the command contains prohibited flags.
    """
    validate_command(command)

    # #2826: under a replay every GitHub write is inert. Decided here, at the
    # one runner every workflow node goes through, so a push or a PR added
    # tomorrow is covered the day it is written.
    suppressed = suppress_if_inert(command)
    if suppressed is not None:
        return suppressed

    if isinstance(command, str):
        command = wrap_bash_if_needed(command)
        if sys.platform == "win32" and command.startswith("bash -c"):
            shell = False

    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        shell=shell,
        capture_output=kwargs.pop("capture_output", True),
        text=kwargs.pop("text", True),
        # #837: Windows defaults to CP1252 for stdout decoding when text=True;
        # any UTF-8 in subprocess output (unicode file paths, tracebacks with
        # non-ASCII, emoji in test output) raises UnicodeDecodeError and
        # crashes the workflow node. Force UTF-8 with replacement chars so the
        # workflow keeps running and surfaces a readable error instead.
        encoding=kwargs.pop("encoding", "utf-8"),
        errors=kwargs.pop("errors", "replace"),
        check=kwargs.pop("check", False),
        **kwargs,
    )
