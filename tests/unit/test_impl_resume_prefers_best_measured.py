"""A resume starts from the best MEASURED preserved attempt, not the newest (#2867).

#2845 resumes the implementation stage from the newest graveyard branch. On
2026-09-05 boostgauge #4 preserved three, one chain, each the last plus one
iteration:

    graveyard/issue-4-20260905T190647Z   a7a387e   44 of 47 passing, 91%
    graveyard/issue-4-20260905T201017Z   d49f78a   41 of 44,          89%
    graveyard/issue-4-20260905T210727Z   26b169b   37 of 41,          82%

The next resume would have taken the tail. Nothing compared them: the halt
wrote the failing count into error_message and the graves carried nothing a
resume could read.

N5 now notes its result on the checkpoint it measured (`record_measurement`,
under refs/notes/az-measure -- keyed by the commit, so it survives the #2310
rename and rides every branch that carries the commit). The resume walks every
resumable grave's commits, reads the notes, and prefers the best score; with
no notes anywhere it falls back to the newest grave, exactly as before.

Real git throughout: every claim here is about commits, notes and ancestry,
and a mock of `git notes show` would assert that the author knows what a note
is rather than that the code reads one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.orchestrator import stages
from assemblyzero.workflows.testing import checkpoints
from assemblyzero.workflows.testing.checkpoints import (
    Measurement,
    read_measurement,
    record_measurement,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"[CP:post-impl] {name}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    _git(root, "init", "-q", "-b", "hardening-run-20")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _commit(root, "base.txt")
    return root


def _measure(repo: Path, sha: str, passed: int, total: int, coverage: float):
    _git(repo, "checkout", "-q", sha)
    assert record_measurement(repo, passed, total, coverage) is True
    _git(repo, "checkout", "-q", "hardening-run-20")


@pytest.fixture
def the_three_graves(repo):
    """The 2026-09-05 chain, measured as the run logs recorded it."""
    _git(repo, "checkout", "-q", "-b", "attempt", "hardening-run-20")
    _commit(repo, "scaffold.txt")
    a7a387e = _commit(repo, "iteration1.txt")
    _git(repo, "branch", "graveyard/issue-4-20260905T190647Z", a7a387e)
    d49f78a = _commit(repo, "iteration2.txt")
    _git(repo, "branch", "graveyard/issue-4-20260905T201017Z", d49f78a)
    b26b169 = _commit(repo, "iteration3.txt")
    _git(repo, "checkout", "-q", "hardening-run-20")
    # The #2310 disposal: the attempt branch is renamed, never deleted.
    _git(repo, "branch", "-m", "attempt", "graveyard/issue-4-20260905T210727Z")
    _measure(repo, a7a387e, 44, 47, 91.0)
    _measure(repo, d49f78a, 41, 44, 89.0)
    _measure(repo, b26b169, 37, 41, 82.0)
    return {"best": a7a387e, "middle": d49f78a, "tail": b26b169}


# =============================================================================
# Recording and reading
# =============================================================================


class TestTheNote:
    def test_a_measurement_is_noted_on_head_and_read_back(self, repo):
        sha = _commit(repo, "work.txt")

        assert record_measurement(repo, 44, 47, 91.0) is True

        assert read_measurement(repo, sha) == Measurement(44, 47, 91.0)

    def test_the_note_survives_a_branch_rename(self, repo):
        """#2310 renames the attempt to graveyard/; the note is on the commit."""
        _git(repo, "checkout", "-q", "-b", "issue-4")
        sha = _commit(repo, "work.txt")
        record_measurement(repo, 10, 12, 80.0)
        _git(repo, "checkout", "-q", "hardening-run-20")

        _git(repo, "branch", "-m", "issue-4", "graveyard/issue-4-20260905T190647Z")

        assert read_measurement(repo, sha) == Measurement(10, 12, 80.0)

    def test_a_second_measurement_of_the_same_commit_replaces_the_first(self, repo):
        sha = _commit(repo, "work.txt")
        record_measurement(repo, 10, 12, 80.0)

        record_measurement(repo, 11, 12, 85.0)

        assert read_measurement(repo, sha) == Measurement(11, 12, 85.0)

    def test_an_unmeasured_commit_reads_as_none(self, repo):
        sha = _commit(repo, "work.txt")

        assert read_measurement(repo, sha) is None

    def test_a_note_that_does_not_parse_reads_as_none(self, repo):
        sha = _commit(repo, "work.txt")
        _git(repo, "notes", f"--ref={checkpoints.MEASURE_NOTES_REF}",
             "add", "-f", "-m", "not a measurement", sha)

        assert read_measurement(repo, sha) is None

    def test_recording_outside_a_repo_is_a_non_fatal_false(self, tmp_path, capsys):
        assert record_measurement(tmp_path, 1, 1, 100.0) is False
        assert "non-fatal" in capsys.readouterr().out

    def test_recording_into_nothing_is_false(self, tmp_path):
        assert record_measurement(None, 1, 1, 100.0) is False
        assert record_measurement(tmp_path / "missing", 1, 1, 100.0) is False

    def test_the_description_is_the_operators_sentence(self):
        assert Measurement(44, 47, 91.0).describe() == "44 passing of 47 at 91%"


# =============================================================================
# Selection
# =============================================================================


class TestSelection:
    def test_the_best_measured_checkpoint_wins_over_the_newest(self, repo, the_three_graves):
        best = stages._best_measured_attempt(str(repo), 4, "hardening-run-20")

        assert best is not None
        assert best.commit == the_three_graves["best"]
        assert best.measurement == Measurement(44, 47, 91.0)

    def test_the_grave_named_is_the_one_whose_tip_it_is(self, repo, the_three_graves):
        """a7a387e sits in all three graves; the log names the one that
        ended there, and the worktree starts from that readable name."""
        best = stages._best_measured_attempt(str(repo), 4, "hardening-run-20")

        assert best.branch == "graveyard/issue-4-20260905T190647Z"
        assert best.is_tip is True
        assert best.commit_ish == "graveyard/issue-4-20260905T190647Z"
        assert best.commits == 2

    def test_the_best_is_not_the_newest_and_says_so(self, repo, the_three_graves):
        best = stages._best_measured_attempt(str(repo), 4, "hardening-run-20")

        assert best.is_newest is False

    def test_an_interior_checkpoint_is_started_from_by_commit(self, repo):
        """Only the last grave exists, and its best iteration is not its tip."""
        _git(repo, "checkout", "-q", "-b", "attempt", "hardening-run-20")
        good = _commit(repo, "good.txt")
        worse = _commit(repo, "worse.txt")
        _git(repo, "checkout", "-q", "hardening-run-20")
        _git(repo, "branch", "-m", "attempt", "graveyard/issue-4-20260905T210727Z")
        _measure(repo, good, 44, 47, 91.0)
        _measure(repo, worse, 37, 41, 82.0)

        best = stages._best_measured_attempt(str(repo), 4, "hardening-run-20")

        assert best.commit == good
        assert best.is_tip is False
        assert best.commit_ish == good
        assert best.commits == 1

    def test_coverage_breaks_a_tie_on_passing(self, repo):
        _git(repo, "checkout", "-q", "-b", "attempt", "hardening-run-20")
        low = _commit(repo, "low.txt")
        high = _commit(repo, "high.txt")
        _git(repo, "checkout", "-q", "hardening-run-20")
        _git(repo, "branch", "-m", "attempt", "graveyard/issue-4-20260905T210727Z")
        _measure(repo, low, 40, 47, 85.0)
        _measure(repo, high, 40, 47, 90.0)

        best = stages._best_measured_attempt(str(repo), 4, "hardening-run-20")

        assert best.commit == high

    def test_no_notes_anywhere_is_none_so_the_newest_rule_applies(self, repo):
        _git(repo, "checkout", "-q", "-b", "attempt", "hardening-run-20")
        _commit(repo, "work.txt")
        _git(repo, "checkout", "-q", "hardening-run-20")
        _git(repo, "branch", "-m", "attempt", "graveyard/issue-4-20260905T210727Z")

        assert stages._best_measured_attempt(str(repo), 4, "hardening-run-20") is None
        assert stages._recoverable_attempt_branch(str(repo), 4, "hardening-run-20") == (
            "graveyard/issue-4-20260905T210727Z", 1,
        )

    def test_a_measured_grave_the_base_moved_past_is_left_alone(self, repo, the_three_graves):
        _commit(repo, "base-moved-on.txt")

        assert stages._best_measured_attempt(str(repo), 4, "hardening-run-20") is None

    def test_another_issues_measured_grave_is_not_borrowed(self, repo):
        _git(repo, "checkout", "-q", "-b", "attempt", "hardening-run-20")
        sha = _commit(repo, "theirs.txt")
        _git(repo, "checkout", "-q", "hardening-run-20")
        _git(repo, "branch", "-m", "attempt", "graveyard/issue-41-20260905T210727Z")
        _measure(repo, sha, 50, 50, 100.0)

        assert stages._best_measured_attempt(str(repo), 4, "hardening-run-20") is None

    def test_an_unresolved_base_declines(self, repo, the_three_graves):
        assert stages._best_measured_attempt(str(repo), 4, "") is None

    def test_an_unreadable_repo_declines(self, tmp_path):
        assert stages._best_measured_attempt(
            str(tmp_path / "not-a-repo"), 4, "hardening-run-20",
        ) is None


# =============================================================================
# Wiring -- what reaches git and the log
# =============================================================================


def _run_impl(state, repo):
    """Drive run_impl_stage far enough to see the worktree add it issues."""
    seen: list[list[str]] = []
    real = stages.run_command

    def recording(cmd, *args, **kwargs):
        cmd = list(cmd)
        seen.append(cmd)
        if "worktree" in cmd and "add" in cmd:
            # Not actually carving: the argv is what is under test.
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        if "fetch" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        return real(cmd, *args, **kwargs)

    with patch.object(stages, "run_command", recording), \
         patch.object(Path, "is_dir", return_value=False):
        try:
            stages.run_impl_stage(state)
        except Exception:
            pass
    for cmd in seen:
        if "worktree" in cmd and "add" in cmd:
            return cmd
    return None


class TestTheWorktreeStartsFromTheBest:
    @pytest.fixture
    def state(self, repo):
        return {
            "issue_number": 4,
            "target_repo": str(repo),
            "assemblyzero_root": str(repo.parent / "az"),
            "base_branch": "hardening-run-20",
            "resumed_from": "impl",
        }

    def test_the_best_graves_tip_is_the_commit_ish(self, state, repo, the_three_graves):
        cmd = _run_impl(state, repo)

        assert cmd is not None, "no worktree add was issued"
        assert cmd[-1] == "graveyard/issue-4-20260905T190647Z", cmd
        assert cmd[cmd.index("-b") + 1] == "issue-4"

    def test_the_choice_and_its_measurement_are_in_the_log(self, state, repo, the_three_graves, capsys):
        _run_impl(state, repo)

        out = capsys.readouterr().out
        assert (
            "Resuming from preserved attempt graveyard/issue-4-20260905T190647Z at "
            f"{the_three_graves['best'][:7]} (44 passing of 47 at 91%, 2 commit(s) "
            "beyond hardening-run-20; the best measured checkpoint; newer "
            "preserved attempts did not measure higher)"
        ) in out

    def test_without_measurements_the_newest_grave_is_taken_as_before(self, state, repo, capsys):
        _git(repo, "checkout", "-q", "-b", "attempt", "hardening-run-20")
        _commit(repo, "work.txt")
        _git(repo, "checkout", "-q", "hardening-run-20")
        _git(repo, "branch", "-m", "attempt", "graveyard/issue-4-20260905T210727Z")

        cmd = _run_impl(state, repo)

        assert cmd[-1] == "graveyard/issue-4-20260905T210727Z", cmd
        assert (
            "Resuming from preserved attempt graveyard/issue-4-20260905T210727Z "
            "(1 commit(s) beyond hardening-run-20)"
        ) in capsys.readouterr().out

    def test_a_fresh_draw_still_starts_from_the_base(self, state, repo, the_three_graves):
        state["resumed_from"] = ""

        cmd = _run_impl(state, repo)

        assert cmd[-1] == "hardening-run-20", cmd
