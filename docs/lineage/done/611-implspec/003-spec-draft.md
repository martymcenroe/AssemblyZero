# Token-safe blocklist: each entry is matched as a complete CLI token,
# never as a substring. Extend this set via BLOCKED_FLAGS.
# v1 scope: hardcoded set per Issue #611 (Q3 resolved).
# Extensible registry deferred to a future issue.
BLOCKED_FLAGS: frozenset[str] = frozenset({
    "--admin",
    "--force",
    "-D",
    "--hard",
})


def validate_command(command: str | list[str]) -> None:
    """Validate a shell command against the security blocklist.

    Tokenises the command string using shlex.split() (or accepts a pre-split
    list) so that flag matching is exact-token, not naive substring.

    Args:
        command: A shell command string or a pre-split argument list.

    Raises:
        SecurityException: If any token in the command matches BLOCKED_FLAGS.
        SecurityException: If command is a string and shlex.split() raises
            ValueError (malformed/unbalanced quoting) — fail closed.
    """
    if isinstance(command, str):
        command_str = command
        try:
            tokens = shlex.split(command)
        except ValueError:
            raise SecurityException(
                command=command_str,
                flag="",
                message=f"Malformed command (unbalanced quoting): {command_str}",
            )
    else:
        tokens = list(command)
        command_str = " ".join(command)

    for token in tokens:
        if token in BLOCKED_FLAGS:
            raise SecurityException(
                command=command_str,
                flag=token,
                message=f"Blocked flag {token!r} detected in command: {command_str}",
            )


def wrap_bash_if_needed(command: str) -> str | list[str]:
    """Wrap a command in bash -c on Windows; return unchanged on POSIX.

    Args:
        command: Raw shell command string.

    Returns:
        On Windows: ['bash', '-c', command]
        On POSIX:   command (unchanged string)
    """
    if sys.platform == "win32":
        return ["bash", "-c", command]
    return command


def _prepare_command(command: str | list[str]) -> str | list[str]:
    """Convert a command into a form safe for subprocess.run(shell=False).

    For pre-split lists: returned as-is.
    For strings on Windows: wrapped via ['bash', '-c', command].
    For strings on POSIX: split into a token list via shlex.split().

    This ensures subprocess.run() always receives either a list of arguments
    or a string that has been platform-adapted, preventing the common error
    of passing a multi-word string to subprocess.run(shell=False) which would
    interpret the entire string as an executable path.

    Args:
        command: Command string or pre-split argument list.

    Returns:
        A list[str] or platform-appropriate command representation.
    """
    if isinstance(command, list):
        return command
    if sys.platform == "win32":
        return ["bash", "-c", command]
    # POSIX: split the string into tokens so subprocess.run(shell=False)
    # can locate the executable and pass arguments correctly.
    return shlex.split(command)


def run_command(
    command: str | list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    timeout: float | None = 60.0,
    check: bool = False,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    """Run a shell command through the security middleware.

    Validates the command, converts it into a subprocess-safe form (splitting
    string commands into token lists on POSIX, wrapping in bash on Windows),
    then delegates to subprocess.run().

    Args:
        command:        Command string or pre-split argument list.
        cwd:            Working directory for the subprocess.
        env:            Environment variables (merged with os.environ if None).
        capture_output: Whether to capture stdout/stderr (default True).
        timeout:        Seconds before TimeoutExpired is raised (default 60s).
                        Pass timeout=None for commands with no upper bound
                        (e.g., full test suite runs from a node).
        check:          If True, raise CalledProcessError on non-zero exit.
        **kwargs:       Additional keyword arguments forwarded verbatim to
                        subprocess.run() (e.g., stdin=PIPE, preexec_fn=...).

    Returns:
        subprocess.CompletedProcess with returncode, stdout, stderr.

    Raises:
        SecurityException:             Command contains a blocked flag, or
                                       command string has malformed quoting.
        subprocess.TimeoutExpired:     Process exceeded timeout.
        subprocess.CalledProcessError: check=True and returncode != 0.
        FileNotFoundError:             Executable not found.
    """
    # Security gate — runs before any subprocess is spawned
    validate_command(command)

    # Platform adaptation and string-to-list conversion
    prepared = _prepare_command(command)

    return subprocess.run(
        prepared,
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        timeout=timeout,
        check=check,
        text=True,
        **kwargs,
    )
```

**Key changes from previous revision:**

1. **POSIX string splitting (BLOCKING fix):** Added `_prepare_command()` helper that replaces the previous inline `wrap_bash_if_needed()` call. On POSIX, string commands are now split via `shlex.split(command)` into a token list before being passed to `subprocess.run()`. This prevents `FileNotFoundError` when running commands like `run_command("echo hello")` on Linux/macOS, where `subprocess.run("echo hello", shell=False)` would interpret the entire string `"echo hello"` as the executable name.

2. **`wrap_bash_if_needed()` preserved:** The public function remains for backward compatibility and external callers, but `run_command()` now uses the internal `_prepare_command()` which encapsulates the complete platform-aware preparation logic (Windows bash-wrapping *and* POSIX string splitting).

3. **`_prepare_command()` logic:**
   - `list` input -> returned as-is (already tokenised)
   - `str` input on Windows -> `["bash", "-c", command]` (same as `wrap_bash_if_needed`)
   - `str` input on POSIX -> `shlex.split(command)` (e.g., `"echo hello"` -> `["echo", "hello"]`)

4. **Double-split safety:** `shlex.split()` is called twice for string commands on POSIX — once in `validate_command()` for security checking, and once in `_prepare_command()` for subprocess preparation. This is intentional: `validate_command()` must tokenise independently (it may be called standalone), and the cost of a second `shlex.split()` is negligible for CLI-length strings. Malformed strings will already have been rejected by `validate_command()` before `_prepare_command()` is reached.

5. **New test case T270** (added to Section 10, test_shell.py): Verifies that `run_command("echo hello")` on POSIX results in `subprocess.run(["echo", "hello"], ...)` being called, confirming the string-to-list conversion.