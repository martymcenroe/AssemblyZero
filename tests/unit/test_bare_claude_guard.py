"""Drive .claude/hooks/bare-claude-guard.sh with real PreToolUse JSON (#1734).

Each case pipes a JSON payload through the actual bash script via subprocess
(Git Bash is a hard dependency of this environment). exit 0 = allowed,
exit 2 = blocked.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "bare-claude-guard.sh"


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
