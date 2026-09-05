"""A resume into the impl stage starts from the preserved attempt (#2845).

RESTORE removes the implementation worktree on every exit (#2005), so the
best-iteration snapshot `verify_phases._restore_best` takes dies with it. What
survives is the attempt branch, renamed under `graveyard/` by the #2310
disposal discipline.

On boostgauge run 15 (`run-issue4-040403`, 2026-09-05) that branch held the
whole 48-of-52-passing implementation -- eight files, 1,356 lines, over a
post-scaffold and five post-impl checkpoints -- and the resume that followed
carved its worktree from the base and implemented from zero. Five iterations
at roughly thirty minutes each, repaid for nothing.

Two halves are tested here, because either alone makes things worse:

* the SELECTION -- which preserved attempt, if any, may be resumed from. Run
  against a real git repository rather than a mocked one: every condition is
  a git ancestry fact, and a mock of `merge-base` would be asserting that the
  test author knows what ancestry means rather than that the code does.
* the WIRING -- that the recovered branch reaches `git worktree add` as the
  commit-ish, and that the sub-workflow is told this is a later attempt. Without
  the second, the red phase reads the surviving implementation as green-at-red
  and halts the stage as fatal (#2337), turning a slow rebuild into a dead run.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.retry_mode import RESUMED
from assemblyzero.workflows.orchestrator import stages


# =============================================================================
# Selection -- real git, real ancestry
# =============================================================================


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"add {name}")


@pytest.fixture
def repo(tmp_path):
    """A repo on `hardening-run-20` with one commit, ready for graves."""
    root = tmp_path / "campaign"
    root.mkdir()
    _git(root, "init", "-b", "hardening-run-20")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _commit(root, "base.txt")
    return root


def _grave(repo: Path, branch: str, commits: int = 1, base: str | None = None):
    """Create `branch` off `base` (default: current HEAD) with `commits` on top."""
    start = base or "HEAD"
    _git(repo, "checkout", "-b", branch, start)
    for i in range(commits):
        _commit(repo, f"{branch.replace('/', '_')}-{i}.txt")
    _git(repo, "checkout", "hardening-run-20")


class TestSelection:
    def test_the_preserved_attempt_is_returned_with_its_commit_count(self, repo):
        _grave(repo, "graveyard/issue-4-20260905T114611Z", commits=6)

        found = stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        )

        assert found == ("graveyard/issue-4-20260905T114611Z", 6)

    def test_the_newest_stamp_wins(self, repo):
        _grave(repo, "graveyard/issue-4-20260902T010250Z", commits=2)
        _grave(repo, "graveyard/issue-4-20260905T114611Z", commits=6)

        found = stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        )

        assert found is not None
        assert found[0] == "graveyard/issue-4-20260905T114611Z"

    def test_another_issues_grave_is_not_borrowed(self, repo):
        """`--list graveyard/issue-4-*` also matches issue 41's graves. The
        captured number is compared, so #4 never resumes #41's work."""
        _grave(repo, "graveyard/issue-41-20260905T114611Z", commits=3)

        assert stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        ) is None

    @pytest.mark.parametrize(
        "name",
        [
            "graveyard/arc1-issue-4",
            "graveyard/run11-roll10-issue-4",
            "graveyard/issue-4-lld-20260905T114611Z",
            "graveyard/issue-4-notastamp",
        ],
    )
    def test_only_the_machinerys_own_disposal_names_are_read(self, repo, name):
        """A campaign repo accumulates hand-made graveyard names. None of them
        is a `dispose_pipeline_branches` attempt and none may be resumed from."""
        _grave(repo, name, commits=3)

        assert stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        ) is None

    def test_a_grave_the_base_has_moved_past_is_left_alone(self, repo):
        """The attempt was cut from an older base. Resuming it would rebuild
        on a tree the campaign has moved off, so the honest answer is None and
        the caller starts from the base."""
        _grave(repo, "graveyard/issue-4-20260905T114611Z", commits=6)
        _commit(repo, "base-moved-on.txt")

        assert stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        ) is None

    def test_a_grave_with_nothing_unique_is_not_resumed(self, repo):
        _grave(repo, "graveyard/issue-4-20260905T114611Z", commits=0)

        assert stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        ) is None

    def test_an_older_usable_grave_is_taken_when_the_newest_is_stale(self, repo):
        """Newest-first is a preference, not a rule: the loop keeps looking.

        The newest STAMP is cut before the base moves on, so it is stale; the
        older stamp is cut after, so it still descends from the base. Stamps
        are names, and the order they were created in is not the order they
        sort in -- which is exactly the case that would break a `max()`.
        """
        _grave(repo, "graveyard/issue-4-20260905T114611Z", commits=1)
        _commit(repo, "base-moved-on.txt")
        _grave(repo, "graveyard/issue-4-20260902T010250Z", commits=2)

        found = stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        )

        assert found == ("graveyard/issue-4-20260902T010250Z", 2)

    def test_no_graves_at_all(self, repo):
        assert stages._recoverable_attempt_branch(
            str(repo), 4, "hardening-run-20"
        ) is None

    def test_an_unresolved_base_declines_rather_than_guessing(self, repo):
        _grave(repo, "graveyard/issue-4-20260905T114611Z", commits=6)

        assert stages._recoverable_attempt_branch(str(repo), 4, "") is None

    def test_an_unreadable_repo_keeps_the_previous_behaviour(self, tmp_path):
        assert stages._recoverable_attempt_branch(
            str(tmp_path / "not-a-repo"), 4, "main"
        ) is None


# =============================================================================
# Wiring -- what reaches git, and what reaches the sub-workflow
# =============================================================================

_ATTEMPT = "graveyard/issue-4-20260905T114611Z"


def _completed(returncode=0, stdout="", stderr=""):
    # mock-ok: subprocess boundary, and a REAL CompletedProcess (standard 0024).
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _GitStub:
    """Answers the ancestry questions as a repo holding one usable attempt.

    Everything else succeeds silently, exactly as `_Recorder` does in
    `test_impl_worktree_base.py` -- this stub only adds answers for the three
    queries `_recoverable_attempt_branch` asks.
    """

    def __init__(self, attempt: str = _ATTEMPT, leftover_exists: bool = False):
        self.attempt = attempt
        self.leftover_exists = leftover_exists
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs):
        cmd = list(cmd) if isinstance(cmd, list) else [cmd]
        self.calls.append(cmd)
        if "branch" in cmd and "--list" in cmd:
            if any(a.startswith("graveyard/") for a in cmd):
                return _completed(stdout=f"{self.attempt}\n" if self.attempt else "")
            return _completed()
        if "merge-base" in cmd:
            return _completed()
        if "rev-list" in cmd and "--count" in cmd:
            # The grave carries six commits; a standing `issue-4` is
            # pointer-identical to the base, which is what makes #2310 adopt
            # it. Answering both from one branch would make this stub, not the
            # code, decide which path runs.
            ranged = cmd[-1]
            return _completed(stdout="6\n" if "graveyard/" in ranged else "0\n")
        if "show-ref" in cmd:
            # #2310's leftover probe: non-zero means the branch is absent.
            return _completed(returncode=1 if not self.leftover_exists else 0)
        return _completed()

    def worktree_add(self) -> list[str] | None:
        for cmd in self.calls:
            if "worktree" in cmd and "add" in cmd:
                return cmd
        return None


@pytest.fixture
def state(tmp_path):
    target = tmp_path / "targetrepo"
    target.mkdir()
    return {
        "issue_number": 4,
        "target_repo": str(target),
        "assemblyzero_root": str(tmp_path / "az"),
        "base_branch": "hardening-run-20",
    }


def _run_impl(state, git):
    with patch.object(stages, "run_command", git), \
         patch.object(Path, "is_dir", return_value=False):
        try:
            stages.run_impl_stage(state)
        except Exception:
            # Downstream stage work is not under test; the worktree add and
            # everything before it has already been recorded.
            pass
    return git.worktree_add()


class TestWorktreeIsCarvedFromTheAttempt:
    def test_resume_uses_the_preserved_attempt_as_the_commit_ish(self, state):
        state["resumed_from"] = "impl"

        cmd = _run_impl(state, _GitStub())

        assert cmd is not None, "no worktree add was issued"
        assert cmd[-1] == _ATTEMPT, cmd

    def test_the_branch_it_creates_is_still_the_issue_branch(self, state):
        """Everything downstream -- checkpoints, the pr stage's head, #2310's
        disposal -- keys off `issue-{N}`. Only the base changes."""
        state["resumed_from"] = "impl"

        cmd = _run_impl(state, _GitStub())

        assert cmd[cmd.index("-b") + 1] == "issue-4", cmd

    def test_the_recovery_is_named_in_the_log(self, state, capsys):
        state["resumed_from"] = "impl"

        _run_impl(state, _GitStub())

        out = capsys.readouterr().out
        assert f"Resuming from preserved attempt {_ATTEMPT}" in out
        assert "6 commit(s)" in out

    def test_a_fresh_draw_still_starts_from_the_base(self, state):
        """#2383 makes `resumed_from` explicit on the fresh path, so an empty
        value is a first run and must behave exactly as it did before."""
        state["resumed_from"] = ""

        cmd = _run_impl(state, _GitStub())

        assert cmd[-1] == "hardening-run-20", cmd

    def test_a_resume_into_a_different_stage_does_not_touch_the_worktree_base(
        self, state
    ):
        state["resumed_from"] = "spec"

        cmd = _run_impl(state, _GitStub())

        assert cmd[-1] == "hardening-run-20", cmd

    def test_nothing_preserved_falls_through_to_the_base(self, state, capsys):
        state["resumed_from"] = "impl"

        cmd = _run_impl(state, _GitStub(attempt=""))

        assert cmd[-1] == "hardening-run-20", cmd
        assert "No preserved attempt for #4" in capsys.readouterr().out

    def test_a_standing_leftover_branch_is_reported_not_silently_preferred(
        self, state, capsys
    ):
        """#2310 adopts a pointer-identical `issue-{N}`, which starts the
        worktree at the base after all. That is today's behaviour and stays,
        but the abandoned recovery must be legible in the log -- otherwise the
        run implements from zero and reads exactly like a successful resume."""
        state["resumed_from"] = "impl"

        cmd = _run_impl(state, _GitStub(leftover_exists=True))

        assert _ATTEMPT not in cmd, cmd
        out = capsys.readouterr().out
        assert f"preserved attempt {_ATTEMPT} NOT used" in out


class TestTheSubWorkflowIsToldItIsALaterAttempt:
    """#2337: a red phase that finds the implementation already present is
    fatal on a FIRST attempt. `_implementation_already_exists` consults only
    `retry_mode` and `iteration_count`, both empty on a sub-workflow entering
    fresh -- so without this the recovery halts the stage instead of resuming
    it, which is strictly worse than the from-zero rebuild it replaces.
    """

    def _invoked_state(self, state, git):
        seen: dict = {}

        class _App:
            def invoke(self, payload, config=None):
                seen.update(payload)
                raise RuntimeError("stop here: the payload is what is under test")

        class _Graph:
            def compile(self):
                return _App()

        with patch(
            "assemblyzero.workflows.testing.graph.build_testing_workflow",
            return_value=_Graph(),
        ):
            _run_impl(state, git)
        return seen

    def test_a_recovered_worktree_enters_as_RESUMED(self, state):
        state["resumed_from"] = "impl"

        seen = self._invoked_state(state, _GitStub())

        assert seen.get("retry_mode") == RESUMED

    def test_a_fresh_draw_carries_the_states_own_retry_mode(self, state):
        state["resumed_from"] = ""
        state["retry_mode"] = ""

        seen = self._invoked_state(state, _GitStub())

        assert seen.get("retry_mode") == ""

    def test_a_stage_retrys_own_mode_is_not_overwritten_without_a_recovery(
        self, state
    ):
        """#1941's REGENERATED must survive: a deterministic failure's next
        attempt still regenerates when no attempt was recovered."""
        state["resumed_from"] = ""
        state["retry_mode"] = "REGENERATED"

        seen = self._invoked_state(state, _GitStub())

        assert seen.get("retry_mode") == "REGENERATED"
