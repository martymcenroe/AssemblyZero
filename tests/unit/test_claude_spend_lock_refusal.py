"""While ~/.claude/claude-spend.lock exists, no seat runs on an Anthropic model (#3615).

Operator ruling, 2026-09-25: when he works on projects using AssemblyZero, no
Anthropic token is used by the workflow while the lock is on. The lock is a
switch he throws week by week (tools/claude_spend_lock.py). The refusal is in
three places so no path spends: the profile loader at run start, each
Anthropic provider before it spawns or sends, and speedrun_roll before
--fresh resets anything. T1 to T5 are the issue's tests.

It covers `anthropic:` seats as well as `claude:`: both spend Anthropic tokens.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core import seats
from assemblyzero.core.llm_provider import AnthropicProvider, ClaudeCLIProvider

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


@pytest.fixture
def locked(tmp_path, monkeypatch):
    lock = tmp_path / "claude-spend.lock"
    lock.write_text("on\n", encoding="utf-8")
    monkeypatch.setattr(seats, "CLAUDE_SPEND_LOCK", lock)
    return lock


# --- T1 and T2: the loader, at run start ---------------------------------------

def test_t1_claude_profile_is_refused_naming_every_seat_and_the_file(locked):
    with pytest.raises(seats.ClaudeSpendLocked) as exc:
        seats.load_run_profile("claude")
    msg = str(exc.value)
    claude_seats = seats.anthropic_seats(seats.load_profile(seats.builtin_path("claude")))
    assert len(claude_seats) == 13
    assert f"seats {len(claude_seats)} on Anthropic" in msg
    assert all(name in msg for name in claude_seats)
    assert str(locked) in msg


def test_t1_gemini_profile_loads_under_the_lock(locked):
    assert seats.load_run_profile("gemini")["name"] == "gemini"


def test_t1_claude_profile_loads_with_the_lock_absent():
    assert seats.load_run_profile("claude")["name"] == "claude"


def test_t2_a_claude_seat_override_is_refused(locked):
    base = seats.load_profile(seats.builtin_path("gemini"))
    with pytest.raises(seats.ClaudeSpendLocked) as exc:
        seats.apply_overrides(base, {"requirements.review": "claude:opus"})
    assert "requirements.review" in str(exc.value)


def test_t2_an_anthropic_api_seat_override_is_refused(locked):
    base = seats.load_profile(seats.builtin_path("gemini"))
    with pytest.raises(seats.ClaudeSpendLocked):
        seats.apply_overrides(base, {"requirements.review": "anthropic:opus"})


def test_t2_the_override_applies_with_the_lock_absent():
    base = seats.load_profile(seats.builtin_path("gemini"))
    out = seats.apply_overrides(base, {"requirements.review": "claude:opus"})
    assert out["seats"]["requirements.review"]["spec"] == "claude:opus"


def test_the_refusal_is_a_profile_error():
    """Every caller that already halts on a bad profile halts on this too."""
    assert issubclass(seats.ClaudeSpendLocked, seats.ProfileError)


# --- T3: the providers, before anything is spawned or sent ---------------------

def test_t3_the_claude_cli_provider_refuses_without_spawning(locked):
    provider = ClaudeCLIProvider("opus")
    with patch("assemblyzero.core.llm_provider.subprocess.Popen") as popen, \
         patch.object(ClaudeCLIProvider, "_find_cli") as find:
        result = provider.invoke("sys", "content")
    popen.assert_not_called()
    find.assert_not_called()
    assert result.success is False and result.retryable is False
    assert result.failure_class == "permanent"
    assert str(locked) in result.error_message


def test_t3_the_anthropic_api_provider_refuses_without_a_client(locked):
    provider = AnthropicProvider(model="opus")
    with patch.object(AnthropicProvider, "_get_client") as get_client:
        result = provider.invoke("sys", "content")
    get_client.assert_not_called()
    assert result.success is False and result.retryable is False
    assert str(locked) in result.error_message


# --- T4: no other path can spend ------------------------------------------------

SPAWNERS = {"run", "call", "check_call", "check_output", "Popen", "spawn", "system", "popen"}

#: Every place, today, that starts `claude` from a literal argv or imports the
#: Anthropic SDK, with why it is not a spend path the lock must stop. A new
#: site fails T4 until it is reviewed and added here. The issue expected a
#: baseline of zero; the tree held these three on the day it landed.
ALLOWED = {
    ("spawn", "tools/claude-usage-scraper.py"):
        "starts interactive claude to read /usage; it sends no prompt to a model",
    ("import", "assemblyzero/core/errors.py"):
        "imports the SDK only to classify an exception already raised; spends nothing",
    ("import", "assemblyzero/nodes/anthropic_provider.py"):
        "the SDK wrapper behind AnthropicProvider, which refuses under the lock (T3)",
}


def _first_word(node: ast.expr) -> str | None:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        head = node.elts[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.split():
        return node.value.split()[0]
    return None


def spend_sites(source: str) -> set[str]:
    """`spawn` if the source starts claude from a literal argv, `import` if it imports anthropic."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            word = _first_word(node.args[0]) if name in SPAWNERS else None
            if word and word.replace("\\", "/").rsplit("/", 1)[-1].lower() in {"claude", "claude.exe"}:
                found.add("spawn")
        elif isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == "anthropic" for a in node.names):
                found.add("import")
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "anthropic":
            found.add("import")
    return found


def test_t4_the_tree_has_no_unreviewed_spend_site():
    seen = set()
    for base in ("assemblyzero", "tools"):
        for path in sorted((ROOT / base).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == "assemblyzero/core/llm_provider.py":
                continue  # the providers themselves, which carry the T3 refusal
            try:
                source = path.read_text(encoding="utf-8")
                kinds = spend_sites(source)
            except (SyntaxError, UnicodeDecodeError):
                continue
            seen.update((kind, rel) for kind in kinds)
    assert seen - set(ALLOWED) == set(), "new spend site(s): review, then add to ALLOWED with a reason"
    assert set(ALLOWED) - seen == set(), "an ALLOWED site no longer exists: remove it"


def test_t4_the_scan_catches_a_literal_claude_spawn():
    assert spend_sites('import subprocess\nsubprocess.run(["claude", "--print", "x"])\n') == {"spawn"}
    assert spend_sites('import subprocess\nsubprocess.run("claude -p hi", shell=True)\n') == {"spawn"}
    assert spend_sites("from anthropic import Anthropic\n") == {"import"}
    assert spend_sites('import subprocess\nsubprocess.run(["git", "status"])\n') == set()


# --- T5: speedrun_roll refuses before --fresh resets anything -------------------

def test_t5_a_claude_roll_exits_before_the_reset(locked, tmp_path, capsys):
    import speedrun_roll

    repo = tmp_path / "target"
    (repo / ".git").mkdir(parents=True)
    before = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*"))

    code = speedrun_roll.main(["--repo", str(repo), "--issue", "1", "--models", "claude", "--fresh"])

    assert code == 91
    assert "claude-spend.lock" in capsys.readouterr().out
    assert sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*")) == before


def test_t5_a_forwarded_claude_seat_is_refused_too(locked, tmp_path, capsys):
    import speedrun_roll

    repo = tmp_path / "target"
    (repo / ".git").mkdir(parents=True)
    code = speedrun_roll.main(
        ["--repo", str(repo), "--issue", "1", "--fresh", "--seat", "requirements.review=claude:opus"]
    )
    assert code == 91
    assert "requirements.review" in capsys.readouterr().out
