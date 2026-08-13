"""A ReadOnly directory must not defeat the worktree sweep (Closes #2135).

First real-state execution of the sweep against boostgauge, 2026-08-09: all 8
registered clean worktrees failed plain `git worktree remove` with

    error: failed to delete 'C:/Users/mcwiz/Projects/boostgauge-1': Permission denied
    error: failed to delete '.git/worktrees/boostgauge-1': Permission denied

Every directory in each tree carried the Windows ReadOnly attribute -- the
worktree root, `src`, `.venv`, and the `logs`/`refs` dirs under the admin
directory. Windows refuses to delete a ReadOnly directory, so every plain
removal died with EACCES. That is very likely why worktrees accumulated during
the campaign at all: any earlier self-heal removal hit the same wall.

The failure is a PARTIAL delete, which is what makes it nasty. git removes what
it can before erroring, so the worktree ends up deregistered while its directory
remains on disk.

The fix clears the attribute and retries the PLAIN remove. Never `--force`,
here or anywhere in this module: clearing the attribute makes the plain path
work rather than bypassing the check that refuses a dirty tree.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

from assemblyzero.speedrun import worktrees as wt

_READONLY = 0x1


def _is_readonly(path: Path) -> bool:
    try:
        return bool(os.stat(path).st_file_attributes & _READONLY)
    except (OSError, AttributeError):
        return False


windows_only = pytest.mark.skipif(
    not hasattr(os.stat(Path(__file__)), "st_file_attributes"),
    reason="the ReadOnly attribute is a Windows filesystem concept",
)


@windows_only
class TestClearingTheAttribute:
    def test_it_clears_a_readonly_directory(self, tmp_path):
        d = tmp_path / "tree"
        d.mkdir()
        os.chmod(d, stat.S_IREAD)
        assert _is_readonly(d), "precondition"

        assert wt.clear_readonly(d) >= 1
        assert not _is_readonly(d)

    def test_it_clears_the_whole_tree(self, tmp_path):
        """The attribute was on every directory in the tree, not just the root."""
        root = tmp_path / "tree"
        (root / "src").mkdir(parents=True)
        (root / "src" / "deep").mkdir()
        (root / "src" / "f.txt").write_text("x", encoding="utf-8")
        for p in (root / "src" / "deep", root / "src", root):
            os.chmod(p, stat.S_IREAD)

        wt.clear_readonly(root)

        assert not _is_readonly(root)
        assert not _is_readonly(root / "src")
        assert not _is_readonly(root / "src" / "deep")

    def test_the_tree_is_removable_afterwards(self, tmp_path):
        """The property that matters. Without clearing, rmtree raises WinError 5."""
        import shutil

        root = tmp_path / "tree"
        (root / "src").mkdir(parents=True)
        for p in (root / "src", root):
            os.chmod(p, stat.S_IREAD)

        with pytest.raises(PermissionError):
            shutil.rmtree(root)

        wt.clear_readonly(root)
        shutil.rmtree(root)
        assert not root.exists()

    def test_an_absent_path_is_zero_not_an_error(self, tmp_path):
        assert wt.clear_readonly(tmp_path / "nope") == 0

    def test_it_never_raises_on_an_unreadable_corner(self, tmp_path):
        """This runs on the failure path of a removal that has already gone
        wrong; a crash here would replace a reported problem with a traceback."""
        d = tmp_path / "tree"
        d.mkdir()

        def _boom(*_a, **_k):
            raise OSError("nope")

        original = os.chmod
        os.chmod = _boom
        try:
            assert wt.clear_readonly(d) == 0
        finally:
            os.chmod = original


class TestTheRetry:
    """`_remove_worktree` is the single door both removal paths go through."""

    def _fake_run(self, results):
        calls = []

        def _run(args):
            calls.append(args)
            return results[min(len(calls) - 1, len(results) - 1)]

        _run.calls = calls
        return _run

    def _cp(self, code, stderr=""):
        return subprocess.CompletedProcess(["git"], code, stdout="", stderr=stderr)

    def test_a_clean_removal_is_not_retried(self, tmp_path, monkeypatch):
        run = self._fake_run([self._cp(0)])
        monkeypatch.setattr(wt, "_run", run)

        result = wt._remove_worktree(tmp_path, tmp_path / "1", lambda _m: None)

        assert result.returncode == 0
        assert len(run.calls) == 1

    def test_a_permission_failure_clears_and_retries_once(self, tmp_path, monkeypatch):
        path = tmp_path / "1"
        path.mkdir()
        if hasattr(os.stat(path), "st_file_attributes"):
            os.chmod(path, stat.S_IREAD)

        run = self._fake_run([self._cp(1, "Permission denied"), self._cp(0)])
        monkeypatch.setattr(wt, "_run", run)
        monkeypatch.setattr(wt, "clear_readonly", lambda _p: 3)

        result = wt._remove_worktree(tmp_path, path, lambda _m: None)

        assert result.returncode == 0
        assert len(run.calls) == 2, "exactly one retry, never a loop"

    def test_a_non_permission_failure_is_not_retried(self, tmp_path, monkeypatch):
        """A worktree that resists for another reason is a fact to surface, not
        to keep hammering."""
        run = self._fake_run([self._cp(1, "is dirty, use --force")])
        monkeypatch.setattr(wt, "_run", run)

        result = wt._remove_worktree(tmp_path, tmp_path / "1", lambda _m: None)

        assert result.returncode == 1
        assert len(run.calls) == 1

    def test_nothing_to_clear_means_no_retry(self, tmp_path, monkeypatch):
        """If the attribute was not the problem, retrying the identical command
        would just fail identically."""
        run = self._fake_run([self._cp(1, "Permission denied")])
        monkeypatch.setattr(wt, "_run", run)
        monkeypatch.setattr(wt, "clear_readonly", lambda _p: 0)

        result = wt._remove_worktree(tmp_path, tmp_path / "1", lambda _m: None)

        assert result.returncode == 1
        assert len(run.calls) == 1

    def test_the_admin_directory_is_cleared_too(self, tmp_path, monkeypatch):
        """`.git/worktrees/<name>` carried the attribute on its logs/refs dirs,
        and git names it in the same failure."""
        cleared = []
        monkeypatch.setattr(wt, "_run", self._fake_run(
            [self._cp(1, "Permission denied"), self._cp(0)]
        ))
        monkeypatch.setattr(
            wt, "clear_readonly", lambda p: cleared.append(Path(p)) or 1
        )

        wt._remove_worktree(tmp_path, tmp_path / "data" / "worktrees" / "1",
                            lambda _m: None)

        assert any(".git" in p.parts and "worktrees" in p.parts for p in cleared), (
            f"the admin dir was never cleared; cleared {cleared}"
        )

    def test_it_says_what_it_did(self, tmp_path, monkeypatch):
        said = []
        monkeypatch.setattr(wt, "_run", self._fake_run(
            [self._cp(1, "Permission denied"), self._cp(0)]
        ))
        monkeypatch.setattr(wt, "clear_readonly", lambda _p: 4)

        wt._remove_worktree(tmp_path, tmp_path / "1", said.append)

        assert any("cleared ReadOnly" in m for m in said)


class TestTheNoForceInvariantSurvives:
    def test_the_canonical_guard_still_exists_and_covers_this(self):
        """The invariant is pinned by `test_sweep_source_contains_no_force` in
        test_speedrun_worktrees.py, which inspects string literals excluding
        docstrings -- a duplicate here would be weaker (my first cut matched
        the module's own prose about never forcing) and would drift.

        Named rather than reimplemented, so the next reader finds the real one.
        """
        import tests.unit.test_speedrun_worktrees as canonical

        assert hasattr(canonical, "test_sweep_source_contains_no_force")
        canonical.test_sweep_source_contains_no_force()  # must still pass

    def test_both_removal_paths_go_through_the_retry(self):
        import inspect

        for fn in (wt._preserve_dirty, wt.sweep_pipeline_worktrees):
            source = inspect.getsource(fn)
            assert '"worktree", "remove"' not in source, (
                f"{fn.__name__} calls git remove directly, so a ReadOnly tree "
                "still defeats it"
            )
            assert "_remove_worktree(" in source
