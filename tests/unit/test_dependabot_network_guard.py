"""The dependabot tests' network guard refuses `gh` and remote git, and allows local git (#4743).

`tests/network_command_guard.py` wraps `subprocess.Popen.__init__` for every
test file that loads `tools/dependabot_review.py`. These tests drive it
directly, through `install`, rather than through the `no_network_commands`
fixture, so a refusal they provoke on purpose is not reported again at
teardown.

Where a refused command must be shown not to start, the constructor under the
guard is replaced first with a recorder that starts nothing: if the guard let
the command through, the recorder would see it.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from tests.network_command_guard import (
    NetworkCommandInUnitTest,
    fail_if_caught,
    install,
    network_reason,
)

TESTS_DIR = Path(__file__).resolve().parents[1]

#: The files that loaded the tool when #4743 was written. The coverage check
#: below must find at least these, or its detector has gone blind.
KNOWN_LOADERS = frozenset({
    "tests/unit/test_dependabot_review.py",
    "tests/unit/test_dependabot_outcomes.py",
    "tests/unit/test_dependabot_public_only.py",
    "tests/unit/test_dependabot_fake_root_guard.py",
    "tests/unit/test_npm_manifest.py",
    "tests/tools/test_dependabot_review.py",
    "tests/tools/test_dependabot_worktree_guard.py",
})


@pytest.fixture
def unstarted(monkeypatch):
    """A constructor that records every command it is handed and starts none."""
    reached: list[object] = []

    def _record(self, args, *rest, **kwargs):
        reached.append(args)
        raise RuntimeError("the recorder never starts a process")

    monkeypatch.setattr(subprocess.Popen, "__init__", _record)
    return reached


@pytest.fixture
def git_env(tmp_path, monkeypatch):
    """git with the machine's config shut out, and no repository above tmp_path."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false",
         *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


# ---- Test 1: a real gh start, and git against a network remote, are refused ----


def test_guard_refuses_a_real_gh_start(monkeypatch, unstarted):
    caught = install(monkeypatch, "probe")
    with pytest.raises(NetworkCommandInUnitTest) as excinfo:
        subprocess.run(["gh", "pr", "diff", "42", "--repo", "owner/repo",
                        "--name-only"], capture_output=True, check=False)
    assert "'gh', 'pr', 'diff', '42'" in str(excinfo.value)
    assert unstarted == [], "the guard let gh reach the constructor"
    assert len(caught) == 1


def test_guard_refuses_git_fetch_from_an_https_url(monkeypatch, unstarted):
    caught = install(monkeypatch, "probe")
    with pytest.raises(NetworkCommandInUnitTest) as excinfo:
        subprocess.run(["git", "fetch", "https://github.com/martymcenroe/AssemblyZero.git",
                        "main"], capture_output=True, check=False)
    assert "https://github.com/martymcenroe/AssemblyZero.git" in str(excinfo.value)
    assert unstarted == [], "the guard let a network fetch reach the constructor"
    assert len(caught) == 1


def test_guard_refuses_git_against_a_remote_configured_with_a_network_url(
        tmp_path, git_env, monkeypatch):
    repo = tmp_path / "repo"
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "remote", "add", "origin", "https://example.invalid/o/r.git")
    _git(repo, "remote", "add", "scp", "git@example.invalid:o/r.git")
    caught = install(monkeypatch, "probe")

    for cmd, cwd in (
        (["git", "fetch", "origin", "main"], repo),           # remote named
        (["git", "-C", str(repo), "fetch", "origin"], tmp_path),  # via -C
        (["git", "fetch"], repo),                              # default remote
        (["git", "pull", "scp", "main"], repo),                # git@ remote
        (["git", "push", "origin", "HEAD:main"], repo),
        (["git", "ls-remote", "origin"], repo),
    ):
        with pytest.raises(NetworkCommandInUnitTest):
            subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=False)
    assert len(caught) == 6


def test_guard_allows_local_git_against_a_tmp_path_repository(
        tmp_path, git_env, monkeypatch):
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    caught = install(monkeypatch, "probe")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    (clone / "f.txt").write_text("x", encoding="utf-8")
    _git(clone, "add", "f.txt")
    _git(clone, "commit", "-q", "-m", "c")
    _git(clone, "push", "-q", "origin", "HEAD:main")
    _git(clone, "fetch", "-q", "origin", "main")
    _git(clone, "fetch", "-q")
    _git(clone, "pull", "-q", "origin", "main")
    listed = _git(clone, "ls-remote", "origin")
    _git(clone, "fetch", "-q", origin.as_uri(), "main")

    assert "refs/heads/main" in listed.stdout
    assert caught == []


def test_a_swallowed_refusal_still_fails_the_test(monkeypatch, unstarted):
    """The tool may catch the refusal in a broad `except`; the record outlives it."""
    caught = install(monkeypatch, "probe")
    swallowed: list[Exception] = []
    try:
        subprocess.run(["gh", "api", "user"], capture_output=True, check=False)
    except Exception as exc:  # noqa: BLE001 -- standing in for code under test
        swallowed.append(exc)
    assert len(swallowed) == 1
    assert unstarted == []
    with pytest.raises(NetworkCommandInUnitTest) as excinfo:
        fail_if_caught(caught, "probe")
    assert "'gh', 'api', 'user'" in str(excinfo.value)
    fail_if_caught([], "probe")  # nothing recorded: no failure


@pytest.mark.parametrize("cmd", [
    ["/usr/bin/gh", "api", "user"],
    [r"C:\Program Files\GitHub CLI\gh.exe", "pr", "list"],
    "gh pr list --repo o/r",
    ["git", "-C", "x", "fetch", "--depth", "1", "https://h.invalid/r.git"],
    ["git", "push", "--repo=https://h.invalid/r.git"],
    ["git", "clone", "git@h.invalid:o/r.git", "dest"],
    ["git", "clone", "ssh://h.invalid/o/r.git"],
    ["git", "ls-remote", "http://h.invalid/r.git"],
])
def test_network_reason_names_each_network_form(cmd):
    assert network_reason(cmd) != ""


@pytest.mark.parametrize("cmd", [
    ["git", "status", "--porcelain"],
    ["git", "-C", "x", "worktree", "remove", "y"],
    ["git", "branch", "-d", "https://not-a-url-here"],
    ["ghost", "run"],
    ["poetry", "run", "pytest"],
    [],
])
def test_network_reason_passes_what_stays_local(cmd):
    assert network_reason(cmd) == ""


# ---- AC1: every file that loads the tool runs under the guard ----


def _loads_the_tool(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
                a.name == "dependabot_review" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "dependabot_review":
            return True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "spec_from_file_location":
                continue
            for arg in ast.walk(node):
                if isinstance(arg, ast.Constant) and arg.value == "dependabot_review.py":
                    return True
    return False


def _opts_in(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            return "no_network_commands" in ast.unparse(node.value)
    return False


def test_every_test_file_that_loads_the_tool_runs_under_the_guard():
    loaders: set[str] = set()
    missing: list[str] = []
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "dependabot_review" not in text:
            continue
        tree = ast.parse(text)
        if not _loads_the_tool(tree):
            continue
        rel = path.relative_to(TESTS_DIR.parent).as_posix()
        loaders.add(rel)
        if not _opts_in(tree):
            missing.append(rel)
    assert KNOWN_LOADERS <= loaders, (
        f"the loader detector missed {sorted(KNOWN_LOADERS - loaders)}")
    assert missing == [], (
        "these files load tools/dependabot_review.py but do not opt into the "
        "network guard; add `pytestmark = pytest.mark.usefixtures("
        "\"no_network_commands\")` (#4743): " + ", ".join(missing))
