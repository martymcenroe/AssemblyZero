"""Shell utilities for cross-platform command execution.

Issue #601: Windows Shell-Aware Utility to eliminate the 'PowerShell Trap'.
"""

import sys
import shlex
import subprocess
from typing import Any

PROHIBITED_FLAGS = ["--admin", "--force", "-D", "--hard"]

def validate_command(command: str | list[str]) -> None:
    """Check command for prohibited dangerous flags.
    
    Raises ValueError if a prohibited flag is detected.
    """
    cmd_str = " ".join(command) if isinstance(command, list) else command
    for flag in PROHIBITED_FLAGS:
        if flag in cmd_str:
            raise ValueError(f"Security Block: Command contains prohibited flag '{flag}'")


def wrap_bash_if_needed(command: str) -> str:
    """Wrap command in bash -c if running on Windows and contains Bash symbols.
    
    Args:
        command: The shell command to execute.
        
    Returns:
        The original command or a bash-wrapped version for Windows.
    """
    if sys.platform != "win32":
        return command
        
    # Symbols that indicate a Bash environment is required
    bash_symbols = ["&&", "||", ">", "<", "|", "2>&1", "<<", "$"]
    
    # If any bash symbol is present, wrap it
    if any(sym in command for sym in bash_symbols):
        # Use single quotes for the inner command to prevent PowerShell interpolation
        # Escape single quotes in the command
        escaped_cmd = command.replace("'", "'\\''")
        return f"bash -c '{escaped_cmd}'"
        
    return command

def run_command(
    command: str | list[str], 
    cwd: str | None = None, 
    timeout: int = 300,
    shell: bool = False,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """Run a command safely across platforms.
    
    If command is a string and on Windows, it will be wrapped in bash -c 
    if bash symbols are detected.
    """
    validate_command(command)

    if isinstance(command, str):
        command = wrap_bash_if_needed(command)
        # On Windows, if we wrapped in bash -c, we must NOT use shell=True 
        # or PowerShell will intercept it again.
        if sys.platform == "win32" and command.startswith("bash -c"):
            shell = False
    
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        shell=shell,
        capture_output=kwargs.pop("capture_output", True),
        text=kwargs.pop("text", True),
        check=kwargs.pop("check", False),
        **kwargs
    )
