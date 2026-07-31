"""A roll returns what it borrowed, says how it died, and refuses stale code.

Three defects observed on live rolls of boostgauge on 2026-07-31:

- #2005 the repo was handed back on the attempt branch with pipeline worktrees
  still registered;
- #2006 a roll died seven minutes in leaving only START/BASE/LAUNCH, because the
  signal traps the bash wrapper had were never reimplemented in the Python
  rewrite -- so "killed by a supervisor" and "died silently" looked identical;
- #2007 a tool run from a shared checkout parked on another lane's branch
  executed pipeline code two commits behind main and failed with a TypeError
  that was already fixed and merged.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _make_repo(tmp_path, name="boostgauge", default="main"):
    upstream = tmp_path / f"{name}-up.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", default)
    r = tmp_path / name
    r.mkdir()
    _git(r, "init", "-b", default)
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(upstream))
    _git(r, "push", "-u", "origin", default)
    _git(r, "remote", "set-head", "origin", default)
    return r


@pytest.fixture
def log(tmp_path):
    return sr.EventLog(tmp_path / "events.log")


class TestRestoreHandsTheRepoBack:
    @pytest.fixture
    def repo(self, tmp_path):
        r = _make_repo(tmp_path)
        _git(r, "checkout", "-b", "hardening-run-12")
        _git(r, "push", "-u", "origin", "hardening-run-12")
        _git(r, "worktree", "add", str(tmp_path / "boostgauge-7"), "-b", "issue-7")
        return r

    def test_ends_on_the_default_branch(self, repo, log):
        assert sr.restore_repo(repo, [7], log) == []
        assert sr.attempt.current_branch(repo) == "main"

    def test_pipeline_worktrees_are_gone(self, repo, log):
        sr.restore_repo(repo, [7], log)
        worktrees = subprocess.run(
            ["git", "worktree", "list"], cwd=str(repo),
            capture_output=True, text=True,
        ).stdout.strip().splitlines()
        assert len(worktrees) == 1, worktrees

    def test_the_attempt_branch_survives(self, repo, log):
        """Restoring the checkout must not destroy the run's integration branch."""
        sr.restore_repo(repo, [7], log)
        assert sr.attempt.local_branch_exists(repo, "hardening-run-12")

    def test_default_branch_is_read_not_assumed(self, tmp_path, log):
        r = _make_repo(tmp_path, name="trunkrepo", default="trunk")
        _git(r, "checkout", "-b", "attempt-1")

        assert sr.restore_repo(r, [], log) == []
        assert sr.attempt.current_branch(r) == "trunk"

    def test_it_reports_rather_than_claims_when_it_cannot_finish(
        self, tmp_path, log
    ):
        r = tmp_path / "norigin"
        r.mkdir()
        _git(r, "init", "-b", "main")
        (r / "f.txt").write_text("x", encoding="utf-8")
        _git(r, "add", "-A")
        _git(r, "commit", "-m", "init")

        failures = sr.restore_repo(r, [], log)
        assert failures and "origin/HEAD" in failures[0]


class TestRestoreRunsOnEveryExit:
    @pytest.fixture
    def repo(self, tmp_path):
        r = _make_repo(tmp_path)
        _git(r, "checkout", "-b", "hardening-run-12")
        _git(r, "push", "-u", "origin", "hardening-run-12")
        return r

    def _main(self, repo, roll_result):
        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
             patch.object(sr, "roll_issue", roll_result):
            return sr.main(["--repo", str(repo), "--issue", "7"])

    def test_restores_after_a_successful_roll(self, repo):
        self._main(repo, lambda *a: 0)
        assert sr.attempt.current_branch(repo) == "main"

    def test_restores_after_a_failed_roll(self, repo):
        code = self._main(repo, lambda *a: 91)
        assert code == 91
        assert sr.attempt.current_branch(repo) == "main"

    def test_restores_when_the_roll_raises(self, repo):
        def boom(*a):
            raise RuntimeError("pipeline exploded")

        with pytest.raises(RuntimeError):
            self._main(repo, boom)
        assert sr.attempt.current_branch(repo) == "main"

    def test_restores_on_the_signal_exit_path(self, repo):
        """SignalExit is a SystemExit, so `finally` still fires -- that is the
        whole reason the handler raises instead of calling os._exit."""
        def killed(*a):
            raise sr.SignalExit(90)

        with pytest.raises(SystemExit):
            self._main(repo, killed)
        assert sr.attempt.current_branch(repo) == "main"


class TestSignalHandlersAreRealNotDocumented:
    def test_handlers_are_installed_for_the_catchable_signals(self, log):
        import signal

        originals = {}
        for attr in ("SIGTERM", "SIGINT"):
            sig = getattr(signal, attr)
            originals[sig] = signal.getsignal(sig)
        try:
            sr.install_signal_handlers(log)
            for sig in originals:
                assert signal.getsignal(sig) not in (
                    signal.SIG_DFL, signal.SIG_IGN, originals[sig]
                ), f"{sig} handler not installed"
        finally:
            for sig, handler in originals.items():
                signal.signal(sig, handler)

    def test_the_handler_logs_the_signal_then_exits(self, log):
        import signal

        original = signal.getsignal(signal.SIGTERM)
        try:
            sr.install_signal_handlers(log)
            handler = signal.getsignal(signal.SIGTERM)
            with pytest.raises(SystemExit):
                handler(signal.SIGTERM, None)
        finally:
            signal.signal(signal.SIGTERM, original)

        assert "SIGNAL: SIGTERM received" in log.path.read_text(encoding="utf-8")


class TestAssemblyZeroTreeGate:
    @pytest.fixture
    def az(self, tmp_path):
        return _make_repo(tmp_path, name="AssemblyZero")

    def test_a_level_tree_passes(self, az):
        assert sr.check_assemblyzero_tree(az) == []

    def test_a_tree_behind_main_is_refused(self, az):
        """The live failure: right branch name, stale code."""
        (az / "tools").mkdir()
        (az / "tools" / "x.py").write_text("new", encoding="utf-8")
        _git(az, "add", "-A")
        _git(az, "commit", "-m", "advance main")
        _git(az, "push")
        _git(az, "reset", "--soft", "HEAD~1")
        _git(az, "checkout", "--", ".")
        _git(az, "stash", "-u")

        problems = sr.check_assemblyzero_tree(az)
        assert any("behind origin/main" in p for p in problems), problems

    def test_a_detached_tree_at_origin_main_passes(self, az):
        """A pinned worktree is a legitimate way to run a roll; a branch-name
        check would have rejected it."""
        sha = subprocess.run(
            ["git", "rev-parse", "origin/main"], cwd=str(az),
            capture_output=True, text=True,
        ).stdout.strip()
        _git(az, "checkout", sha)

        assert sr.check_assemblyzero_tree(az) == []

    def test_tracked_modifications_to_pipeline_code_are_refused(self, az):
        (az / "tools").mkdir()
        (az / "tools" / "t.py").write_text("v1", encoding="utf-8")
        _git(az, "add", "-A")
        _git(az, "commit", "-m", "add tool")
        _git(az, "push")
        (az / "tools" / "t.py").write_text("locally edited", encoding="utf-8")

        problems = sr.check_assemblyzero_tree(az)
        assert any("tracked modification" in p for p in problems), problems

    def test_untracked_files_are_ignored(self, az):
        """Other lanes leave one-off scripts in tools/; they do not change the
        code being executed."""
        (az / "tools").mkdir()
        (az / "tools" / "land_something.py").write_text("x", encoding="utf-8")

        assert sr.check_assemblyzero_tree(az) == []

    def test_a_stale_tree_blocks_the_roll_before_anything_is_spent(self, tmp_path):
        repo = _make_repo(tmp_path)
        rolled = []

        with patch.object(
            sr, "check_assemblyzero_tree", lambda p: ["2 commit(s) behind origin/main"]
        ), patch.object(sr, "roll_issue", lambda *a: rolled.append(a) or 0):
            code = sr.main(["--repo", str(repo), "--issue", "7"])

        assert code == 91
        assert rolled == [], "a stale tree must block before any roll starts"
