"""Acceptance tests for pipeline worktree placement and the sweep (#2077).

The seven tests named in the issue body are the acceptance criteria.

Every test builds its own throwaway repo under tmp_path. The sweep is never
pointed at a real campaign repo here -- the live stranded worktrees are cleaned
by its first real run, with the operator watching, not by a test.
"""
from __future__ import annotations

import ast
import inspect
import subprocess
from pathlib import Path

import pytest

from assemblyzero.speedrun import worktrees as wt
from assemblyzero.speedrun.worktrees import (
    discover_pipeline_worktrees,
    orphaned_root,
    pipeline_worktree_path,
    sweep_pipeline_worktrees,
)
from assemblyzero.workflows.orchestrator.artifacts import worktree_path_for
from assemblyzero.workflows.requirements.git_operations import lld_worktree_path_for


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


# --- "after a complete roll, ~/Projects contains no new entries" -----------


def test_placement_is_inside_the_repo_not_a_sibling(repo):
    impl = worktree_path_for(7, str(repo))
    lld = lld_worktree_path_for(repo, 7)

    assert impl == repo / "data" / "worktrees" / "7"
    assert lld == repo / "data" / "worktrees" / "7-lld"

    # The property that matters: nothing lands beside the repo.
    for path in (impl, lld):
        assert repo in path.parents
        assert path.parent.parent == repo / "data"
        assert not str(path).startswith(str(repo.parent / (repo.name + "-")))


def test_placement_leaves_projects_dir_untouched_after_a_roll(repo, tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())

    for issue, lld in ((7, False), (7, True), (12, False)):
        path = pipeline_worktree_path(repo, issue, lld=lld)
        branch = f"{issue}-lld" if lld else f"issue-{issue}"
        _git(repo, "worktree", "add", "-q", str(path), "-b", branch)

    after = sorted(p.name for p in tmp_path.iterdir())
    assert after == before, "a roll must add nothing beside the repo"


def test_data_worktrees_is_not_visible_to_git_status(repo):
    (repo / ".gitignore").write_text("data/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore data")

    path = pipeline_worktree_path(repo, 7)
    _git(repo, "worktree", "add", "-q", str(path), "-b", "issue-7")

    status = _git(repo, "status", "--porcelain").stdout
    assert "worktrees" not in status


# --- "a killed roll's clean worktrees are gone after the next start" -------


def test_clean_worktrees_are_removed(repo):
    for issue in (7, 12):
        _git(repo, "worktree", "add", "-q",
             str(pipeline_worktree_path(repo, issue)), "-b", f"issue-{issue}")

    result = sweep_pipeline_worktrees(repo)

    assert {e.action for e in result.entries} == {"removed"}
    assert not pipeline_worktree_path(repo, 7).exists()
    assert not pipeline_worktree_path(repo, 12).exists()
    assert result.problems == []


def test_sweep_handles_issues_other_than_the_one_being_rolled(repo):
    # The old behaviour self-healed only the current issue, which is how ten
    # stranded directories accumulated in one day.
    for issue in (1, 4, 41):
        _git(repo, "worktree", "add", "-q",
             str(pipeline_worktree_path(repo, issue)), "-b", f"issue-{issue}")

    result = sweep_pipeline_worktrees(repo)

    swept = {e.path.name for e in result.entries}
    assert swept == {"1", "4", "41"}


def test_legacy_sibling_worktrees_are_swept_too(repo):
    legacy = repo.parent / f"{repo.name}-9"
    _git(repo, "worktree", "add", "-q", str(legacy), "-b", "issue-9")

    assert legacy.resolve() in [p.resolve() for p in discover_pipeline_worktrees(repo)]
    sweep_pipeline_worktrees(repo)
    assert not legacy.exists()


def test_unrelated_sibling_directories_are_never_touched(repo):
    decoy = repo.parent / f"{repo.name}-notes"
    decoy.mkdir()
    (decoy / "keep.txt").write_text("mine\n", encoding="utf-8")

    sweep_pipeline_worktrees(repo)

    assert decoy.is_dir() and (decoy / "keep.txt").is_file()


# --- "a dirty worktree is committed to graveyard/* before removal" --------


def test_dirty_worktree_is_preserved_on_a_graveyard_branch(repo):
    path = pipeline_worktree_path(repo, 5)
    _git(repo, "worktree", "add", "-q", str(path), "-b", "issue-5")
    (path / "wip.py").write_text("half_done = True\n", encoding="utf-8")
    (path / "README.md").write_text("edited\n", encoding="utf-8")

    result = sweep_pipeline_worktrees(repo)

    entry = result.entries[0]
    assert entry.state == "dirty"
    assert entry.action == "preserved-and-removed"
    assert entry.branch.startswith("graveyard/issue-5-")
    assert not path.exists()

    branches = _git(repo, "branch", "--list", "--format=%(refname:short)").stdout.split()
    assert entry.branch in branches

    # The branch's tree must match what was in the worktree.
    listing = _git(repo, "ls-tree", "-r", "--name-only", entry.branch).stdout.split()
    assert "wip.py" in listing
    blob = _git(repo, "show", f"{entry.branch}:wip.py").stdout
    assert blob.strip() == "half_done = True"
    edited = _git(repo, "show", f"{entry.branch}:README.md").stdout
    assert edited.strip() == "edited"


def test_dirty_worktree_content_survives_a_failed_push(repo):
    # No origin is configured, so the push inside the sweep fails. The content
    # is already on the local branch, so the sweep must proceed rather than
    # strand the worktree for a reason unrelated to its content.
    path = pipeline_worktree_path(repo, 6)
    _git(repo, "worktree", "add", "-q", str(path), "-b", "issue-6")
    (path / "wip.py").write_text("value = 42\n", encoding="utf-8")

    result = sweep_pipeline_worktrees(repo)

    entry = result.entries[0]
    assert entry.ok and entry.action == "preserved-and-removed"
    assert _git(repo, "show", f"{entry.branch}:wip.py").stdout.strip() == "value = 42"


# --- "an unregistered on-disk directory is relocated, never deleted" ------


def test_orphan_is_relocated_and_named_in_the_log(repo):
    # Models the verified boostgauge-2 case: on disk, absent from git worktree
    # list, branch deleted, so no ref reaches its content.
    orphan = repo.parent / f"{repo.name}-2"
    orphan.mkdir()
    (orphan / ".git").write_text("gitdir: /gone\n", encoding="utf-8")
    (orphan / "unreachable.py").write_text("only_copy = True\n", encoding="utf-8")

    lines: list[str] = []
    result = sweep_pipeline_worktrees(repo, log=lines.append)

    entry = next(e for e in result.entries if e.state == "orphan")
    assert entry.action == "relocated"
    assert not orphan.exists(), "the source directory was moved, not copied"

    relocated = list(orphaned_root(repo).iterdir())
    assert len(relocated) == 1
    assert relocated[0].name.startswith(f"{repo.name}-2-")
    assert (relocated[0] / "unreachable.py").read_text().strip() == "only_copy = True"

    assert any(f"{repo.name}-2" in line for line in lines)


def test_orphan_relocation_never_deletes_content(repo):
    orphan = pipeline_worktree_path(repo, 3)
    orphan.mkdir(parents=True)
    (orphan / ".git").write_text("gitdir: /gone\n", encoding="utf-8")
    (orphan / "a.py").write_text("a\n", encoding="utf-8")
    (orphan / "nested").mkdir()
    (orphan / "nested" / "b.py").write_text("b\n", encoding="utf-8")

    sweep_pipeline_worktrees(repo)

    moved = list(orphaned_root(repo).iterdir())[0]
    assert (moved / "a.py").read_text() == "a\n"
    assert (moved / "nested" / "b.py").read_text() == "b\n"


def test_already_orphaned_holding_area_is_not_re_swept(repo):
    holding = orphaned_root(repo) / "7-20260802-010101"
    holding.mkdir(parents=True)
    (holding / "kept.py").write_text("kept\n", encoding="utf-8")

    result = sweep_pipeline_worktrees(repo)

    assert result.entries == []
    assert (holding / "kept.py").is_file()


# --- "no code path passes --force; asserted against the source" -----------


def _string_literals_excluding_docstrings(source: str) -> list[str]:
    """Every string constant the module can actually pass to a subprocess.

    Docstrings are excluded deliberately: this module's docstring states the
    no-force prohibition in prose, and a scan that cannot tell a rule from its
    violation would force the rule to be deleted to satisfy the test.
    """
    tree = ast.parse(source)
    docstring_nodes = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_nodes.add(id(body[0].value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstring_nodes
    ]


def test_sweep_source_contains_no_force():
    literals = _string_literals_excluding_docstrings(inspect.getsource(wt))
    banned = {"--force", "-f", "--force-with-lease", "-D"}
    offending = [lit for lit in literals if lit in banned]
    assert offending == [], (
        f"{offending} reachable in the sweep. A worktree that resists a plain "
        f"remove is a fact to surface, not to overpower."
    )


def test_the_no_force_scan_would_actually_catch_a_violation():
    """The guard above is worthless if it cannot fail. This proves it can."""
    literals = _string_literals_excluding_docstrings(
        'def f():\n    """Never --force."""\n    return run(["git", "worktree", '
        '"remove", "--force", p])\n'
    )
    assert "--force" in literals


# --- "a worktree that cannot be removed is reported, roll continues" ------


def test_unremovable_worktree_is_reported_by_name_and_does_not_raise(repo, monkeypatch):
    path = pipeline_worktree_path(repo, 8)
    _git(repo, "worktree", "add", "-q", str(path), "-b", "issue-8")

    real_run = wt._run

    def fake_run(args):
        if "worktree" in args and "remove" in args:
            return subprocess.CompletedProcess(args, 1, "", "fatal: cannot remove")
        return real_run(args)

    monkeypatch.setattr(wt, "_run", fake_run)

    result = sweep_pipeline_worktrees(repo)

    assert len(result.problems) == 1
    problem = result.problems[0]
    assert problem.path.name == "8"
    assert "cannot remove" in problem.detail
    assert path.exists(), "a worktree it could not remove must be left alone"


def test_one_bad_worktree_does_not_stop_the_others(repo, monkeypatch):
    for issue in (10, 11):
        _git(repo, "worktree", "add", "-q",
             str(pipeline_worktree_path(repo, issue)), "-b", f"issue-{issue}")

    real_run = wt._run

    def fake_run(args):
        if "remove" in args and str(pipeline_worktree_path(repo, 10)) in args:
            return subprocess.CompletedProcess(args, 1, "", "fatal: locked")
        return real_run(args)

    monkeypatch.setattr(wt, "_run", fake_run)

    result = sweep_pipeline_worktrees(repo)

    assert len(result.entries) == 2
    assert len(result.problems) == 1
    assert not pipeline_worktree_path(repo, 11).exists()
