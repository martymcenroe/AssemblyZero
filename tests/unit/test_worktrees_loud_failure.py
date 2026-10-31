"""The pipeline-worktree sweep fails loudly (ADR 0236, #3585).

The sweep runs at every launch and moves or removes the pipeline's worktrees.
A `git worktree list` that failed read as "nothing registered", so every
pipeline worktree would have been relocated as an orphan; a failed status, a
failed `git add`, a failed push, a ledger that could not record the branch,
and a removal or relocation that failed each produced at most a line in a log
nobody was shown, or nothing at all.

Now the worktree list raises before anything moves, every failed entry alerts
the operator, a failed push keeps the worktree, ReadOnly clearing raises
instead of clearing part of a tree, and an unexpected OSError alerts and stops
the sweep.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from assemblyzero.speedrun import worktrees as wt
from assemblyzero.speedrun.preserved import ledger_path, read_ledger


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
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


@pytest.fixture
def origin(repo: Path, tmp_path: Path) -> Path:
    """A bare origin, so a graveyard push succeeds."""
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    return bare


def _worktree(repo: Path, issue: int, *, dirty: bool = False) -> Path:
    path = wt.pipeline_worktree_path(repo, issue)
    _git(repo, "worktree", "add", "-q", str(path), "-b", f"issue-{issue}")
    if dirty:
        (path / "wip.py").write_text("half_done = True\n", encoding="utf-8")
    return path


def _failing(fragment: tuple[str, ...], code: int, stderr: str):
    """wt._run, except that argv containing every word of `fragment` fails."""
    real = wt._run

    def run(args):
        if all(word in args for word in fragment):
            return subprocess.CompletedProcess(args, code, "", stderr)
        return real(args)

    return run


# --- kept behaviour --------------------------------------------------------


def test_a_healthy_sweep_alerts_nobody(repo, origin, operator_alerts):
    clean = _worktree(repo, 1)
    dirty = _worktree(repo, 2, dirty=True)

    result = wt.sweep_pipeline_worktrees(repo, log=lambda _m: None)

    assert result.problems == []
    assert not clean.exists() and not dirty.exists()
    assert operator_alerts == []


# --- discovery -------------------------------------------------------------


def test_97_a_worktree_list_that_fails_alerts_and_raises_before_anything_moves(
    repo, operator_alerts, monkeypatch
):
    orphan = wt.worktrees_root(repo) / "3"
    orphan.mkdir(parents=True)
    (orphan / "keep.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        wt, "_run", _failing(("worktree", "list"), 128, "fatal: not a git repository")
    )

    with pytest.raises(RuntimeError, match="not a git repository"):
        wt.sweep_pipeline_worktrees(repo, log=lambda _m: None)

    assert (orphan / "keep.txt").exists(), "nothing may move on an unknown worktree list"
    assert len(operator_alerts) == 1
    assert "128" in operator_alerts[0]["cause"]


def test_136_a_status_that_fails_is_alerted_and_still_treated_as_dirty(
    repo, operator_alerts, monkeypatch
):
    path = _worktree(repo, 4)
    monkeypatch.setattr(wt, "_run", _failing(("status",), 128, "fatal: index corrupt"))

    assert wt.is_dirty(path) is True
    assert len(operator_alerts) == 1
    assert "index corrupt" in operator_alerts[0]["cause"]


# --- clearing ReadOnly ------------------------------------------------------


def _fake_os(*, attrs: int = 0x1, stat_fails: Path | None = None, chmod_fails: bool = False):
    """A stand-in for the `os` module worktrees uses: stat and chmod only."""
    calls: list[Path] = []

    def stat(target):
        if stat_fails is not None and Path(target) == stat_fails:
            raise PermissionError(13, "Permission denied", str(target))
        return SimpleNamespace(st_file_attributes=attrs)

    def chmod(target, _mode):
        if chmod_fails:
            raise PermissionError(13, "Permission denied", str(target))
        calls.append(Path(target))

    return SimpleNamespace(stat=stat, chmod=chmod), calls


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    (root / "src").mkdir(parents=True)
    (root / "src" / "f.txt").write_text("x", encoding="utf-8")
    return root


def test_223_a_tree_that_cannot_be_listed_raises(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    fake, _ = _fake_os()
    monkeypatch.setattr(wt, "os", fake)

    def rglob(self, _pattern):
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "rglob", rglob)

    with pytest.raises(OSError):
        wt.clear_readonly(root)


def test_229_a_path_that_cannot_be_stat_ed_raises(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    fake, _ = _fake_os(stat_fails=root / "src" / "f.txt")
    monkeypatch.setattr(wt, "os", fake)

    with pytest.raises(OSError):
        wt.clear_readonly(root)


def test_229_off_windows_there_is_no_attribute_to_clear(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    monkeypatch.setattr(
        wt, "os", SimpleNamespace(stat=lambda _t: SimpleNamespace(), chmod=None)
    )

    assert wt.clear_readonly(root) == 0


def test_236_a_chmod_that_fails_raises(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    fake, _ = _fake_os(chmod_fails=True)
    monkeypatch.setattr(wt, "os", fake)

    with pytest.raises(OSError):
        wt.clear_readonly(root)


def test_236_every_readonly_path_is_cleared(tmp_path, monkeypatch):
    root = _tree(tmp_path)
    fake, calls = _fake_os()
    monkeypatch.setattr(wt, "os", fake)

    assert wt.clear_readonly(root) == 3
    assert set(calls) == {root, root / "src", root / "src" / "f.txt"}


# --- preserving a dirty worktree ---------------------------------------------


def test_274_a_failed_git_add_is_a_failed_entry_and_alerts(repo, origin, operator_alerts, monkeypatch):
    path = _worktree(repo, 5, dirty=True)
    monkeypatch.setattr(wt, "_run", _failing(("add", "-A"), 128, "fatal: unable to index file"))

    entry = wt._preserve_dirty(repo, path.resolve(), lambda _m: None)

    assert not entry.ok
    assert "git add" in entry.detail
    assert path.exists() and (path / "wip.py").exists()
    assert len(operator_alerts) == 1
    assert "unable to index" in operator_alerts[0]["cause"]


def test_286_a_failed_push_keeps_the_worktree_and_alerts(repo, operator_alerts):
    path = _worktree(repo, 6, dirty=True)  # no origin: the push fails

    entry = wt._preserve_dirty(repo, path.resolve(), lambda _m: None)

    assert not entry.ok and entry.action == "reported"
    assert path.exists(), "a branch that is only local does not license removing the worktree"
    assert _git(repo, "show", f"{entry.branch}:wip.py").stdout.strip() == "half_done = True"
    assert [r.branch for r in read_ledger(repo)] == [entry.branch]
    assert len(operator_alerts) == 1
    assert "push" in operator_alerts[0]["what"]


def test_295_a_branch_the_ledger_cannot_record_is_a_failed_entry_and_alerts(
    repo, origin, operator_alerts
):
    path = _worktree(repo, 7, dirty=True)
    (repo / "data" / "speedrun").write_text("not a directory\n", encoding="utf-8")

    entry = wt._preserve_dirty(repo, path.resolve(), lambda _m: None)

    assert not entry.ok and entry.action == "preserved-and-removed"
    assert not path.exists(), "the content is on a pushed branch; removal still happens"
    assert len(operator_alerts) == 1
    assert str(ledger_path(repo)) in operator_alerts[0]["cause"]


def test_300_a_preserved_worktree_that_cannot_be_removed_alerts(
    repo, origin, operator_alerts, monkeypatch
):
    path = _worktree(repo, 8, dirty=True)
    monkeypatch.setattr(wt, "_run", _failing(("worktree", "remove"), 1, "fatal: locked"))

    entry = wt._preserve_dirty(repo, path.resolve(), lambda _m: None)

    assert not entry.ok and "not removed" in entry.detail
    assert len(operator_alerts) == 1
    assert "locked" in operator_alerts[0]["cause"]


# --- an orphan, a clean worktree, and the sweep itself ----------------------


def test_315_an_orphan_that_cannot_be_relocated_alerts(repo, operator_alerts, monkeypatch):
    orphan = wt.worktrees_root(repo) / "9"
    orphan.mkdir(parents=True)

    def refuse(*_a, **_k):
        raise PermissionError(13, "Permission denied", str(orphan))

    monkeypatch.setattr(wt.shutil, "move", refuse)

    entry = wt._relocate_orphan(repo, orphan)

    assert not entry.ok
    assert orphan.exists()
    assert len(operator_alerts) == 1
    assert "Permission denied" in operator_alerts[0]["cause"]


def test_330_with_no_log_a_failure_still_reaches_stderr(repo, operator_alerts, monkeypatch, capsys):
    _worktree(repo, 10)
    monkeypatch.setattr(wt, "_run", _failing(("worktree", "remove"), 1, "fatal: cannot remove"))

    wt.sweep_pipeline_worktrees(repo)

    assert "cannot remove" in capsys.readouterr().err


def test_344_a_clean_worktree_that_cannot_be_removed_alerts(
    repo, operator_alerts, monkeypatch
):
    path = _worktree(repo, 11)
    monkeypatch.setattr(wt, "_run", _failing(("worktree", "remove"), 1, "fatal: cannot remove"))

    result = wt.sweep_pipeline_worktrees(repo, log=lambda _m: None)

    assert len(result.problems) == 1 and path.exists()
    assert len(operator_alerts) == 1
    assert "cannot remove" in operator_alerts[0]["cause"]


def test_351_an_unexpected_os_error_alerts_and_raises(repo, operator_alerts, monkeypatch):
    _worktree(repo, 12)

    def explode(_path):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(wt, "is_dirty", explode)

    with pytest.raises(OSError, match="Input/output error"):
        wt.sweep_pipeline_worktrees(repo, log=lambda _m: None)

    assert len(operator_alerts) == 1
    assert "12" in operator_alerts[0]["what"]
