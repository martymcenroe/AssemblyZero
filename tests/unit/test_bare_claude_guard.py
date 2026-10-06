"""Drive the installed bare-claude guard with real PreToolUse JSON (#1734, #3686).

Each case pipes a JSON payload through the actual bash script via subprocess.
exit 0 = allowed, exit 2 = blocked.

WHICH COPY THIS DRIVES, AND WHY IT CHANGED (#3686)
--------------------------------------------------
It used to drive a copy of the script tracked in this repository under `.claude/hooks/`.
That copy was registered by nothing: it sat on disk, no settings file referenced it, and
it gated no tool call. These tests were the only thing still pointing at it, which is
exactly what made it look alive while it was not.

The script that actually runs is the one installed in the user's hook directory and
registered by the machine-wide managed settings file, so that is what these cases drive
now. Keeping a tracked second copy and testing that instead is how the dead file came to
exist, and would recreate it.

The consequence, stated rather than hidden: where the guard is not installed, such as a
CI runner, these cases skip. They assert a property of an installed guard, and a runner
has none to assert it about. Verifying that every registered hook across the machine
returns the right exit code is a separate program, run where the hooks actually are.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path.home() / ".claude" / "hooks" / "bare-claude-guard.sh"

pytestmark = pytest.mark.skipif(
    not HOOK.is_file(),
    reason=f"no installed guard at {HOOK}; these cases drive the installed copy (#3686)",
)


def run_hook(command: str | None) -> subprocess.CompletedProcess:
    payload = {"tool_name": "Bash"}
    if command is not None:
        payload["tool_input"] = {"command": command}
    return subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=15,
    )


BLOCKED = [
    "claude config list 2>/dev/null | head -15",  # the 2026-07-10 incident, verbatim shape
    "claude doctor",
    'claude "tell me a joke"',
    "cd /c/x && claude update",
    "cd /c/x; claude mcp list",
    "OUT=$(claude foo)",
    "CLAUDECODE= claude config list",          # env prefix stepped over
    "FOO=bar BAZ=qux claude anything",
    "true | claude subcommand",
    "exec claude repl",
    "command claude plugin",
    "claude.exe doctor",
]

ALLOWED = [
    "claude --help",
    "claude --version",
    'CLAUDECODE="" claude --print "summarize this"',
    "claude -p 'quick question'",
    "echo claude config",                       # prose, not an invocation
    'git commit -m "claude config cleanup"',
    "unleashed-claude-tool foo",                # hyphenated binary
    "grep -r claude tools/",
    "ls",
    "",
    # #1739 regression: the guard's first live block was THIS false positive —
    # quoted prose containing the incident command (with a paren anchor)
    # inside a gh argument. Quoted strings are masked before matching now.
    'gh issue close 756 --comment "text (CLAUDECODE= claude config list) more text"',
    "git commit -m 'guard blocks claude doctor probes'",
]


@pytest.mark.parametrize("cmd", BLOCKED)
def test_blocked(cmd):
    proc = run_hook(cmd)
    assert proc.returncode == 2, f"should block: {cmd!r}\nstderr={proc.stderr}"
    assert "bare-claude-guard" in proc.stderr


@pytest.mark.parametrize("cmd", ALLOWED)
def test_allowed(cmd):
    proc = run_hook(cmd)
    assert proc.returncode == 0, f"should allow: {cmd!r}\nstderr={proc.stderr}"


def test_missing_tool_input_allows():
    assert run_hook(None).returncode == 0


def test_malformed_json_allows_fail_open():
    proc = subprocess.run(
        ["bash", str(HOOK)], input="not json at all",
        capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0
