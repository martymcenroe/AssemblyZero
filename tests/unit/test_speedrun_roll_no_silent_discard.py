"""A mid-arc base is not thrown away over debris (#2028).

Twice on 2026-07-31 a single local branch the reset could not delete -- one
branch, for one issue -- was met by cutting a fresh attempt from the default
branch, walking away from a base holding four finished phases. The log recorded
it as routine progress and named neither what was being abandoned nor how much
was on it. Both times the arc survived by accident: once because a human was
watching, once because creating the replacement happened to fail.

The costs are not comparable. Refusing costs one stopped run and a message.
Replacing discards every phase accumulated so far, silently, and the next roll
builds against a base that has never seen them.

Replacement stays right where nothing is lost: a base level with the default
branch, or one already carrying this issue's work.
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


class _Log:
    def __init__(self):
        self.lines = []

    def write(self, message):
        self.lines.append(message)

    def text(self):
        return "\n".join(self.lines)


@pytest.fixture
def log():
    return _Log()


class TestAMidArcBaseIsKept:
    def test_it_refuses_rather_than_discarding_accumulated_work(self, log):
        established = []
        with patch.object(sr, "commits_carried", lambda r, b: 8), \
                patch.object(sr, "establish_new_attempt",
                             lambda r, lg: established.append(b"x") or "new"):
            result = sr.replace_or_refuse(
                Path("."), "hardening-run-14", 2, ["local branch: issue-2"], log
            )

        assert result is None, "a base carrying work must not be replaced"
        assert established == [], "no fresh attempt may be cut"

    def test_it_says_what_it_is_protecting(self, log):
        """The old message named neither the cost nor the cause."""
        with patch.object(sr, "commits_carried", lambda r, b: 8):
            sr.replace_or_refuse(
                Path("."), "hardening-run-14", 2, ["local branch: issue-2"], log
            )

        text = log.text()
        assert "8 commit(s)" in text
        assert "hardening-run-14" in text

    def test_it_names_every_unresolved_finding(self, log):
        """Whoever reads this has to know what to clear."""
        with patch.object(sr, "commits_carried", lambda r, b: 4):
            sr.replace_or_refuse(
                Path("."), "hardening-run-14", 2,
                ["local branch: issue-2", "worktree: C:\\x\\boostgauge-2"], log
            )

        text = log.text()
        assert "local branch: issue-2" in text
        assert "worktree: C:\\x\\boostgauge-2" in text

    def test_it_says_how_to_clear_an_undeletable_branch(self, log):
        """A branch with commits reachable from nowhere else refuses a safe
        delete, and -D is banned. Renaming under graveyard/ is the way out, and
        an operator should not have to rediscover that."""
        with patch.object(sr, "commits_carried", lambda r, b: 4):
            sr.replace_or_refuse(Path("."), "hardening-run-14", 2, ["x"], log)

        assert "graveyard/" in log.text()


class TestReplacementStillHappensWhenNothingIsLost:
    def test_a_base_level_with_the_default_branch_is_replaced(self, log):
        """A fresh attempt carrying nothing: replacing costs nothing."""
        with patch.object(sr, "commits_carried", lambda r, b: 0), \
                patch.object(sr, "establish_new_attempt", lambda r, lg: "hardening-run-15"):
            result = sr.replace_or_refuse(Path("."), "hardening-run-14", 2, ["x"], log)

        assert result == "hardening-run-15"

    def test_a_failed_replacement_still_reports_none(self, log):
        with patch.object(sr, "commits_carried", lambda r, b: 0), \
                patch.object(sr, "establish_new_attempt", lambda r, lg: None):
            assert sr.replace_or_refuse(Path("."), "b", 2, ["x"], log) is None


class TestCountingWhatTheBaseCarries:
    def _git(self, cwd, *args):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(cwd), check=True, capture_output=True, text=True,
        )

    @pytest.fixture
    def repo(self, tmp_path):
        upstream = tmp_path / "up.git"
        upstream.mkdir()
        self._git(upstream, "init", "--bare", "-b", "main")
        r = tmp_path / "repo"
        r.mkdir()
        self._git(r, "init", "-b", "main")
        (r / "a.txt").write_text("x", encoding="utf-8")
        self._git(r, "add", "-A")
        self._git(r, "commit", "-m", "init")
        self._git(r, "remote", "add", "origin", str(upstream))
        self._git(r, "push", "-u", "origin", "main")
        return r

    def test_a_level_base_carries_nothing(self, repo):
        self._git(repo, "checkout", "-b", "hardening-run-1")
        self._git(repo, "push", "-u", "origin", "hardening-run-1")
        self._git(repo, "checkout", "main")

        assert sr.commits_carried(repo, "hardening-run-1") == 0

    def test_an_accumulating_base_carries_its_phases(self, repo):
        self._git(repo, "checkout", "-b", "hardening-run-1")
        for i in range(3):
            (repo / f"phase{i}.py").write_text("x", encoding="utf-8")
            self._git(repo, "add", "-A")
            self._git(repo, "commit", "-m", f"phase {i}")
        self._git(repo, "push", "-u", "origin", "hardening-run-1")
        self._git(repo, "checkout", "main")

        assert sr.commits_carried(repo, "hardening-run-1") == 3

    def test_an_unmeasurable_base_is_unknown_not_zero(self, repo):
        """"Could not measure" and "nothing here" lead to opposite decisions.
        Folding the first into the second fails destructively -- it authorises
        discarding an arc exactly when the tooling cannot see what is on it,
        which is how the first draft of this fix behaved."""
        assert sr.commits_carried(repo, "no-such-branch") is None


class TestUnknownFailsSafe:
    def test_an_unmeasurable_base_is_never_replaced(self, log):
        established = []
        with patch.object(sr, "commits_carried", lambda r, b: None), \
                patch.object(sr, "establish_new_attempt",
                             lambda r, lg: established.append(1) or "new"):
            result = sr.replace_or_refuse(Path("."), "b", 2, ["x"], log)

        assert result is None
        assert established == []

    def test_it_admits_it_could_not_measure(self, log):
        with patch.object(sr, "commits_carried", lambda r, b: None):
            sr.replace_or_refuse(Path("."), "b", 2, ["x"], log)
        assert "unknown amount" in log.text()
