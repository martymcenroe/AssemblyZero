"""Every worktree a workflow cuts is recorded with relative paths (#4241).

The operator works the same checkouts from Windows and from Ubuntu (WSL). A
worktree recorded with an absolute path from one side reads as ``prunable``
from the other, so a run's worktree, still holding unlanded work, is offered
for pruning there. ``git worktree add --relative-paths`` records both links
relative, and both sides can open the worktree.

Two kinds of test:

- T1: the cutting functions, run against a real throwaway repository, leave a
  worktree whose ``.git`` file and whose admin ``gitdir`` file are relative.
- T2: an ``ast`` guard over ``assemblyzero/`` and ``tools/``. Every list or
  tuple literal that holds ``"worktree"`` followed by ``"add"`` also holds
  ``"--relative-paths"``. It is checked against a fixture that omits the flag.
"""
from __future__ import annotations

import ast
import itertools
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("assemblyzero", "tools")
FLAG = "--relative-paths"

#: Every site, by file, that cuts a worktree today. A new site is caught by
#: the guard; one that disappears is caught by the count, so the list stays
#: the truth about where worktrees come from.
EXPECTED_SITES = {
    "assemblyzero/workflows/orchestrator/stages.py": 2,
    "assemblyzero/workflows/requirements/git_operations.py": 2,
    "tools/dependabot_review.py": 1,
    "tools/run_implement_from_lld.py": 3,
    "tools/speedrun_roll.py": 1,
}


def _string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def worktree_add_literals(source: str, filename: str) -> list[tuple[int, bool]]:
    """``(line, has_flag)`` for every literal argv that runs ``worktree add``."""
    found: list[tuple[int, bool]] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        words = [_string(element) for element in node.elts]
        if any(
            first == "worktree" and second == "add"
            for first, second in itertools.pairwise(words)
        ):
            found.append((node.lineno, FLAG in words))
    return found


def _scan() -> dict[str, list[tuple[int, bool]]]:
    sites: dict[str, list[tuple[int, bool]]] = {}
    for top in SCANNED:
        for path in sorted((REPO_ROOT / top).rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            # utf-8-sig: llm_provider.py starts with a byte-order mark.
            found = worktree_add_literals(path.read_text(encoding="utf-8-sig"), rel)
            if found:
                sites[rel] = found
    return sites


# ---------------------------------------------------------------------------
# T2: the guard
# ---------------------------------------------------------------------------


def test_t2_every_worktree_add_passes_relative_paths():
    missing = [
        f"{rel}:{line}"
        for rel, found in _scan().items()
        for line, has_flag in found
        if not has_flag
    ]
    assert missing == [], (
        "these `git worktree add` calls omit --relative-paths (#4241): "
        + ", ".join(missing)
    )


def test_t2_the_sites_are_the_known_ones():
    counts = {rel: len(found) for rel, found in _scan().items()}
    assert counts == EXPECTED_SITES


def test_t2_the_guard_catches_a_call_without_the_flag():
    fixture = (
        "import subprocess\n"
        "def cut(path):\n"
        "    subprocess.run(['git', 'worktree', 'add', str(path), '-b', 'x'])\n"
        "def cut_right(path):\n"
        "    subprocess.run(['git', 'worktree', 'add', '--relative-paths', str(path)])\n"
        "def unrelated():\n"
        "    return ['git', 'worktree', 'list']\n"
    )
    assert worktree_add_literals(fixture, "fixture.py") == [(3, False), (5, True)]


# ---------------------------------------------------------------------------
# T1: the cutting functions, against a real repository
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture
def target(tmp_path, monkeypatch) -> Path:
    """A throwaway repository, with the machine's git config shut out.

    The operator's own ``~/.gitconfig`` sets ``worktree.useRelativePaths``,
    so on his machine every worktree is relative whatever the code passes. CI
    and other machines have no such setting; the flag is what makes it true
    everywhere, so the test runs git as a machine without it would.
    """
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "target"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("-c", "user.email=t@example.com", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "start", cwd=repo)
    return repo


def _assert_relative(worktree: Path) -> None:
    gitfile = (worktree / ".git").read_text(encoding="utf-8").strip()
    assert gitfile.startswith("gitdir: ")
    link = gitfile.removeprefix("gitdir: ")
    assert not Path(link).is_absolute(), gitfile
    admin = (worktree / link).resolve()
    back = (admin / "gitdir").read_text(encoding="utf-8").strip()
    assert not Path(back).is_absolute(), back


@pytest.fixture
def runner_module():
    tools = str(REPO_ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import run_implement_from_lld

    return run_implement_from_lld


def test_t1_the_implementation_worktree_is_relative(target, runner_module):
    worktree, error = runner_module.create_worktree(target, 42)
    assert error == ""
    _assert_relative(worktree)


def test_t1_the_existing_branch_retry_is_relative(target, runner_module):
    _git("branch", "42-implementation", cwd=target)
    worktree, error = runner_module.create_worktree(target, 42)
    assert error == ""
    _assert_relative(worktree)


def test_t1_the_mock_detached_worktree_is_relative(target, runner_module):
    worktree, error = runner_module.create_worktree(target, 42, detached=True)
    assert error == ""
    _assert_relative(worktree)


def test_t1_the_lld_worktree_is_relative(target):
    from assemblyzero.workflows.requirements.git_operations import (
        setup_lld_worktree,
    )

    worktree, _branch = setup_lld_worktree(target, 42)
    _assert_relative(worktree)


def test_t1_the_lld_existing_branch_retry_is_relative(target):
    from assemblyzero.workflows.requirements.git_operations import (
        setup_lld_worktree,
    )

    _git("branch", "42-lld", cwd=target)
    worktree, _branch = setup_lld_worktree(target, 42)
    _assert_relative(worktree)
