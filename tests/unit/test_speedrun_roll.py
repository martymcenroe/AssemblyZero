"""A roll makes its own decisions (#1919).

The wrapper this replaces required a human to know which branch to roll on and
pass it to two tools consistently, to notice when a finished arc had left the
base carrying the work, to name and cut the next attempt branch by hand, and to
read an ABORT saying "run speedrun_reset.py, verify clean, relaunch" and then
do it.

Each of those is a decision the repo can answer for itself, so each is tested
here as a decision the tool makes -- not as a message it prints.

Real repos against a real bare origin throughout; the only stubs are at the
network boundary (`gh`) and around the pipeline child itself (standard 0024).
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


@pytest.fixture
def repo(tmp_path):
    """Repo on attempt branch `hardening-run-11`, that branch pushed to origin."""
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")

    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(upstream))
    _git(r, "push", "-u", "origin", "main")
    _git(r, "remote", "set-head", "origin", "main")

    _git(r, "checkout", "-b", "hardening-run-11")
    _git(r, "push", "-u", "origin", "hardening-run-11")
    return r


@pytest.fixture
def log(tmp_path):
    return sr.EventLog(tmp_path / "events.log")


def _commit_lld(repo, issue=4):
    d = repo / "docs" / "lld" / "active"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"LLD-{issue:03d}.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", f"land LLD #{issue}")
    _git(repo, "push")


def _no_network():
    """gh-backed debris classes return nothing; they are not what is under test."""
    return patch.multiple(
        sr.gate,
        find_open_pr_debris=lambda *a, **k: [],
        find_remote_branch_debris=lambda *a, **k: [],
    )


class TestNamingIsDerivedNotChosen:
    def test_prefix_comes_from_the_current_attempt(self, repo):
        assert sr.attempt_prefix(repo) == "hardening-run"

    def test_prefix_falls_back_when_not_on_an_attempt(self, repo):
        _git(repo, "checkout", "main")
        assert sr.attempt_prefix(repo) == sr.DEFAULT_PREFIX

    def test_next_name_increments_past_the_highest(self, repo):
        assert sr.next_attempt_name(repo, "hardening-run") == "hardening-run-12"

    def test_graveyarded_attempts_still_count(self, repo):
        """A name freed by graveyarding must not be handed out again -- the old
        remote ref still holds it."""
        _git(repo, "branch", "-m", "hardening-run-11", "graveyard/hardening-run-11")
        assert sr.next_attempt_name(repo, "hardening-run") == "hardening-run-12"

    def test_remote_only_attempts_still_count(self, repo):
        """A push would collide even with no local branch of that name."""
        _git(repo, "push", "origin", "hardening-run-11:hardening-run-40")
        _git(repo, "fetch", "origin")
        assert sr.next_attempt_name(repo, "hardening-run") == "hardening-run-41"

    def test_first_attempt_when_none_exist(self, repo):
        assert sr.next_attempt_name(repo, "brand-new") == "brand-new-1"


class TestStructuralSoundness:
    def test_a_pushed_tracking_branch_is_sound(self, repo):
        assert sr.base_is_structurally_sound(repo, "hardening-run-11") == []

    def test_missing_on_origin_is_caught(self, repo):
        """The 2026-07-30 defect: `checkout -b X origin/main` never pushes X."""
        _git(repo, "checkout", "-b", "hardening-run-12", "origin/main")
        problems = sr.base_is_structurally_sound(repo, "hardening-run-12")
        assert any("does not exist on origin" in p for p in problems), problems
        assert any("upstream" in p for p in problems), problems

    def test_a_mid_arc_base_ahead_of_default_is_still_sound(self, repo):
        """An integration branch carrying earlier phases is the POINT; only a
        fresh attempt must be level with the default branch."""
        _commit_lld(repo, 2)
        assert sr.base_is_structurally_sound(repo, "hardening-run-11") == []


class TestEnsureBaseDecides:
    def test_sound_and_clean_base_is_reused(self, repo, log):
        with _no_network():
            assert sr.ensure_base(repo, 4, log) == "hardening-run-11"

    def test_unsound_base_triggers_a_fresh_attempt(self, repo, log):
        _git(repo, "checkout", "-b", "hardening-run-12", "origin/main")

        with _no_network():
            base = sr.ensure_base(repo, 4, log)

        assert base == "hardening-run-13"
        assert sr.base_is_structurally_sound(repo, base) == []

    def test_base_holding_this_issues_work_triggers_a_fresh_attempt(
        self, repo, log
    ):
        """No amount of debris cleanup fixes a base that already merged the
        issue -- it needs a base that predates it."""
        _commit_lld(repo, 4)

        with _no_network():
            base = sr.ensure_base(repo, 4, log)

        assert base == "hardening-run-12"
        assert sr.gate.find_committed_artifact_debris(repo, 4, base) == []

    def test_another_issues_work_does_not_trigger_a_fresh_attempt(
        self, repo, log
    ):
        """Phases accumulate on one integration branch; only THIS issue matters."""
        _commit_lld(repo, 2)

        with _no_network():
            assert sr.ensure_base(repo, 4, log) == "hardening-run-11"

    def test_recoverable_debris_is_self_healed_not_reported(self, repo, log):
        """The old wrapper printed 'run speedrun_reset.py, verify clean,
        relaunch' and quit. That instruction is now a code path."""
        _git(repo, "branch", "issue-4")
        healed = {}

        def fake_reset(repo_root, slug, issue):
            healed["called"] = issue
            _git(repo_root, "branch", "-d", "issue-4")

        with _no_network(), \
             patch.object(sr.reset, "reset_one_issue", fake_reset), \
             patch.object(sr.reset, "_gh_repo", lambda p: "o/r"):
            base = sr.ensure_base(repo, 4, log)

        assert healed["called"] == 4
        assert base == "hardening-run-11"

    def test_debris_that_survives_reset_escalates_to_a_fresh_attempt(
        self, repo, log
    ):
        _git(repo, "branch", "issue-4")

        with _no_network(), \
             patch.object(sr.reset, "reset_one_issue", lambda *a: None), \
             patch.object(sr.reset, "_gh_repo", lambda p: "o/r"):
            base = sr.ensure_base(repo, 4, log)

        assert base == "hardening-run-12"

    def test_detached_head_triggers_a_fresh_attempt(self, repo, log):
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo),
            capture_output=True, text=True,
        ).stdout.strip()
        _git(repo, "checkout", sha)

        with _no_network():
            assert sr.ensure_base(repo, 4, log) == "hardening-run-12"


class TestInstrumentationSurvives:
    def test_events_and_heartbeat_are_written(self, tmp_path):
        log = sr.EventLog(tmp_path / "e.log")
        log.write("START something")
        with sr.Heartbeat(tmp_path / "hb.log", interval=1):
            pass

        assert "START something" in (tmp_path / "e.log").read_text(encoding="utf-8")
        assert (tmp_path / "hb.log").read_text(encoding="utf-8").strip().endswith("alive")

    def test_child_env_carries_the_two_load_bearing_vars(self):
        env = sr._child_env()
        assert env["CLAUDECODE"] == ""
        assert env["PYTHONUNBUFFERED"] == "1"


class TestNoHumanInputBeyondRepoAndIssue:
    def test_roll_needs_only_repo_and_issue(self, repo, tmp_path):
        """No base, no attempt name, no apply flag -- the tool resolves all of
        it. Anything else here would be a ritual with a different name."""
        seen = {}

        def fake_roll(repo_root, issue, log_dir, az_root, extra):
            seen[issue] = (repo_root, log_dir)
            return 0

        # #2005/#2007: main() now gates on the AssemblyZero tree and
        # restores the repo in a finally. Neither is what these tests
        # measure, and both reach the real filesystem, so both are stubbed.
        stubs = {
            "check_assemblyzero_tree": lambda p: [],
            "restore_repo": lambda *a: [],
            "roll_issue": fake_roll,
        }
        with patch.multiple(sr, **stubs):
            code = sr.main(["--repo", str(repo), "--issue", "4", "--issue", "2"])

        assert code == 0
        assert sorted(seen) == [2, 4]

    def test_a_failing_issue_stops_the_sequence(self, repo):
        rolled = []

        def fake_roll(repo_root, issue, log_dir, az_root, extra):
            rolled.append(issue)
            return 91 if issue == 4 else 0

        # #2005/#2007: main() now gates on the AssemblyZero tree and
        # restores the repo in a finally. Neither is what these tests
        # measure, and both reach the real filesystem, so both are stubbed.
        stubs = {
            "check_assemblyzero_tree": lambda p: [],
            "restore_repo": lambda *a: [],
            "roll_issue": fake_roll,
        }
        with patch.multiple(sr, **stubs):
            code = sr.main(["--repo", str(repo), "--issue", "4", "--issue", "2"])

        assert code == 91
        assert rolled == [4], "later issues must not roll on a broken base"

    def test_extra_args_pass_through_to_the_pipeline(self, repo):
        captured = {}

        def fake_roll(repo_root, issue, log_dir, az_root, extra):
            captured["extra"] = extra
            return 0

        # #2005/#2007: main() now gates on the AssemblyZero tree and
        # restores the repo in a finally. Neither is what these tests
        # measure, and both reach the real filesystem, so both are stubbed.
        stubs = {
            "check_assemblyzero_tree": lambda p: [],
            "restore_repo": lambda *a: [],
            "roll_issue": fake_roll,
        }
        with patch.multiple(sr, **stubs):
            sr.main(["--repo", str(repo), "--issue", "4", "--max-iterations", "5"])

        assert captured["extra"] == ["--max-iterations", "5"]

    def test_non_repo_path_is_refused(self, tmp_path):
        assert sr.main(["--repo", str(tmp_path), "--issue", "4"]) == 91
