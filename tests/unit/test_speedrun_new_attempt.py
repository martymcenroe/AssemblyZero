"""A new attempt branch is established and VERIFIED, not assumed (#1986).

The ritual this tool replaces was performed by hand on 2026-07-30 and got
wrong: `git checkout -b hardening-run-12 origin/main` sets the upstream to
`origin/main` and never creates `origin/hardening-run-12`. `gh pr create --base
hardening-run-12` would have failed on the run's first PR, after the LLD and
spec stages had already burned. Locally everything looked healthy -- `git
status` reports a normal tracking branch.

So the postcondition tests below are the point of the file. Every case builds a
real repo with a real bare origin, because the entire defect class lives in the
difference between local refs and remote refs, and a fixture that stubs the
remote could not express it (standard 0024).
"""

import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_new_attempt as sna  # noqa: E402


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """A repo on attempt branch `hardening-run-11`, with that branch on origin."""
    upstream = tmp_path / "upstream.git"
    upstream.mkdir()
    _git(upstream, "init", "--bare", "-b", "main")

    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-b", "main")
    (r / "README.md").write_text("x", encoding="utf-8")
    _git(r, "add", "README.md")
    _git(r, "commit", "-m", "init")
    _git(r, "remote", "add", "origin", str(upstream))
    _git(r, "push", "-u", "origin", "main")
    _git(r, "remote", "set-head", "origin", "main")

    _git(r, "checkout", "-b", "hardening-run-11")
    (r / "src.py").write_text("merged phase work", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "arc work")
    _git(r, "push", "-u", "origin", "hardening-run-11")
    return r


def _apply(repo, name="hardening-run-12"):
    return sna.main(["--repo", str(repo), "--name", name, "--apply"])


class TestTheHandRunDefect:
    """The specific breakage that motivated the tool."""

    def test_new_branch_exists_on_origin(self, repo):
        assert _apply(repo) == 0
        assert sna.remote_branch_exists(repo, "hardening-run-12")

    def test_upstream_is_its_own_counterpart_not_the_default_branch(self, repo):
        """`checkout -b X origin/main` leaves upstream=origin/main, which looks
        healthy in `git status` and breaks `gh pr create --base X`."""
        assert _apply(repo) == 0
        assert sna.upstream_of(repo, "hardening-run-12") == "origin/hardening-run-12"

    def test_the_hand_written_form_would_fail_verification(self, repo):
        """Reproduce the bad ritual, then confirm this tool's checks catch it."""
        _git(repo, "checkout", "-b", "hardening-run-99", "origin/main")

        failures = sna.verify_postconditions(repo, "hardening-run-99", "main")

        assert any("origin has no branch" in f for f in failures), failures
        assert any("upstream" in f for f in failures), failures


class TestOutcome:
    def test_the_checkout_ends_on_the_default_branch(self, repo):
        """#2012: an attempt is a REF, and the operator is never parked on one.
        The repo starts this test standing on hardening-run-11, which is also
        the branch being graveyarded -- `git branch -m` would drag the checkout
        to `graveyard/hardening-run-11`, worse than where it began."""
        assert sna.current_branch(repo) == "hardening-run-11"

        assert _apply(repo) == 0

        assert sna.current_branch(repo) == "main"

    def test_the_graveyarded_branch_is_not_where_you_land(self, repo):
        assert _apply(repo) == 0
        assert not sna.current_branch(repo).startswith("graveyard/")

    def test_the_new_attempt_exists_as_a_local_ref(self, repo):
        assert _apply(repo) == 0
        assert sna.local_branch_exists(repo, "hardening-run-12")

    def test_new_branch_is_level_with_the_default(self, repo):
        assert _apply(repo) == 0
        assert sna.commits_ahead(repo, "hardening-run-12", "origin/main") == 0

    def test_previous_attempt_is_graveyarded_not_deleted(self, repo):
        assert _apply(repo) == 0
        assert sna.local_branch_exists(repo, "graveyard/hardening-run-11")
        assert not sna.local_branch_exists(repo, "hardening-run-11")

    def test_the_old_attempts_work_is_still_reachable(self, repo):
        """The graveyard is a lab notebook, not a bin."""
        assert _apply(repo) == 0
        show = subprocess.run(
            ["git", "show", "graveyard/hardening-run-11:src.py"],
            cwd=str(repo), capture_output=True, text=True,
        )
        assert show.returncode == 0
        assert "merged phase work" in show.stdout

    def test_old_attempt_remains_on_origin_under_its_original_name(self, repo):
        """Matching the existing convention: graveyarding is a LOCAL rename."""
        assert _apply(repo) == 0
        assert sna.remote_branch_exists(repo, "hardening-run-11")

    def test_the_new_base_does_not_carry_the_old_arc_work(self, repo):
        """Checked against the REF, since the checkout is no longer moved."""
        assert _apply(repo) == 0
        shown = subprocess.run(
            ["git", "show", "hardening-run-12:src.py"],
            cwd=str(repo), capture_output=True, text=True,
        )
        assert shown.returncode != 0, "new attempt must not carry the old work"


class TestPreconditions:
    def test_dirty_tree_is_refused(self, repo, capsys):
        # #2146: refusal now classifies. An untracked file OUTSIDE the
        # pipeline-emission allowlist is operator-owned and refuses by name;
        # machinery-owned leavings are the janitor's (test_leavings_janitor).
        (repo / "uncommitted.txt").write_text("wip", encoding="utf-8")

        assert _apply(repo) == 1
        out = capsys.readouterr().out
        assert "uncommitted.txt" in out
        assert "not machinery-owned" in out
        assert sna.current_branch(repo) == "hardening-run-11", "must not mutate"

    def test_extra_worktree_is_refused(self, repo, tmp_path, capsys):
        _git(repo, "worktree", "add", str(tmp_path / "wt"), "-b", "issue-4")

        assert _apply(repo) == 1
        assert "worktree" in capsys.readouterr().out

    def test_existing_local_name_is_refused(self, repo, capsys):
        _git(repo, "branch", "hardening-run-12")

        assert _apply(repo) == 1
        assert "already exists" in capsys.readouterr().out

    def test_existing_remote_name_is_refused(self, repo, capsys):
        _git(repo, "push", "origin", "hardening-run-11:hardening-run-12")

        assert _apply(repo) == 1
        assert "origin already has a branch" in capsys.readouterr().out

    def test_detached_head_is_handled_not_refused(self, repo):
        """Nothing to graveyard is not a reason to stop. Refusing here told a
        human to check out a branch first -- an instruction the tool can carry
        out itself, which makes it a ritual rather than a safeguard (#1919)."""
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo),
            capture_output=True, text=True,
        ).stdout.strip()
        _git(repo, "checkout", sha)

        assert _apply(repo) == 0
        assert sna.local_branch_exists(repo, "hardening-run-12")
        assert sna.remote_branch_exists(repo, "hardening-run-12")
        # The old attempt keeps its own name; it was never checked out.
        assert sna.local_branch_exists(repo, "hardening-run-11")

    def test_plan_omits_the_rename_when_there_is_no_branch(self):
        flat = [" ".join(c) for c in sna.plan_steps("", "attempt-2", "main")]
        assert not any("branch -m" in c for c in flat), flat
        assert any("branch attempt-2 origin/main" in c for c in flat), flat

    def test_missing_origin_head_is_refused_with_the_remedy(self, repo, capsys):
        _git(repo, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")

        assert _apply(repo) == 1
        assert "git remote set-head" in capsys.readouterr().out


class TestDryRunIsDefault:
    def test_without_apply_nothing_changes(self, repo):
        assert sna.main(["--repo", str(repo), "--name", "hardening-run-12"]) == 0

        assert sna.current_branch(repo) == "hardening-run-11"
        assert not sna.local_branch_exists(repo, "hardening-run-12")
        assert not sna.remote_branch_exists(repo, "hardening-run-12")

    def test_dry_run_prints_the_exact_commands(self, repo, capsys):
        sna.main(["--repo", str(repo), "--name", "hardening-run-12"])
        out = capsys.readouterr().out

        assert "DRY RUN" in out
        assert "git branch -m hardening-run-11 graveyard/hardening-run-11" in out
        assert "git branch hardening-run-12 origin/main" in out
        assert "git push -u origin hardening-run-12" in out

    def test_no_banned_command_appears_in_the_plan(self, repo):
        """--apply rather than --execute is only correct if this stays true
        (standard 0017). The old branch is renamed, never deleted; the new one
        is pushed as a fresh ref, never forced."""
        flat = " ".join(
            " ".join(c) for c in sna.plan_steps("old", "new", "main")
        )
        for banned in ("--force", "-D ", "reset --hard", "clean -fd", "-f "):
            assert banned not in flat, f"{banned!r} in plan: {flat}"


class TestDefaultBranchIsReadNotAssumed:
    """Hardcoding main is the behaviour the attempt-branch model removes."""

    def test_default_branch_comes_from_origin_head(self, tmp_path):
        upstream = tmp_path / "up.git"
        upstream.mkdir()
        _git(upstream, "init", "--bare", "-b", "trunk")

        r = tmp_path / "repo"
        r.mkdir()
        _git(r, "init", "-b", "trunk")
        (r / "f.txt").write_text("x", encoding="utf-8")
        _git(r, "add", "-A")
        _git(r, "commit", "-m", "init")
        _git(r, "remote", "add", "origin", str(upstream))
        _git(r, "push", "-u", "origin", "trunk")
        _git(r, "remote", "set-head", "origin", "trunk")

        assert sna.default_branch(r) == "trunk"

    def test_new_attempt_is_cut_from_the_real_default(self, tmp_path):
        upstream = tmp_path / "up.git"
        upstream.mkdir()
        _git(upstream, "init", "--bare", "-b", "trunk")

        r = tmp_path / "repo"
        r.mkdir()
        _git(r, "init", "-b", "trunk")
        (r / "f.txt").write_text("x", encoding="utf-8")
        _git(r, "add", "-A")
        _git(r, "commit", "-m", "init")
        _git(r, "remote", "add", "origin", str(upstream))
        _git(r, "push", "-u", "origin", "trunk")
        _git(r, "remote", "set-head", "origin", "trunk")
        _git(r, "checkout", "-b", "attempt-1")
        _git(r, "push", "-u", "origin", "attempt-1")

        assert sna.main(["--repo", str(r), "--name", "attempt-2", "--apply"]) == 0
        assert sna.commits_ahead(r, "attempt-2", "origin/trunk") == 0
