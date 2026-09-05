"""A resume that finds its worktree on disk enters as a later attempt (#2860).

`run-issue4-140813`: the entry sweep could not remove the previous attempt's
worktree (Permission denied, holder unidentified), so `run_impl_stage` found
`worktree_path.is_dir()` true, skipped creation, and ran the sub-workflow
against the prior attempt's tree -- as a FIRST attempt. #2845 sent RESUMED
only when this entry had carved the worktree from a grave. The red phase read
the surviving implementation as green-at-red and halted in three seconds.

Same harness as `test_impl_resume_from_preserved_attempt.py`: the payload
`run_impl_stage` hands `app.invoke` is what is under test.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.retry_mode import RESUMED
from assemblyzero.workflows.orchestrator import stages


def _completed(returncode=0, stdout="", stderr=""):
    # mock-ok: subprocess boundary, and a REAL CompletedProcess (standard 0024).
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _quiet_git(cmd, *args, **kwargs):
    return _completed()


@pytest.fixture
def state(tmp_path):
    target = tmp_path / "targetrepo"
    target.mkdir()
    return {
        "issue_number": 4,
        "target_repo": str(target),
        "assemblyzero_root": str(tmp_path / "az"),
        "base_branch": "hardening-run-20",
        "retry_mode": "",
    }


def _payload(state, worktree_exists: bool):
    seen: dict = {}

    class _App:
        def invoke(self, payload, config=None):
            seen.update(payload)
            raise RuntimeError("stop here: the payload is what is under test")

    class _Graph:
        def compile(self):
            return _App()

    with patch.object(stages, "run_command", _quiet_git), \
         patch.object(Path, "is_dir", return_value=worktree_exists), \
         patch.object(Path, "is_file", return_value=False), \
         patch(
             "assemblyzero.workflows.testing.graph.build_testing_workflow",
             return_value=_Graph(),
         ):
        try:
            stages.run_impl_stage(state)
        except Exception:
            pass
    assert seen, "run_impl_stage never reached app.invoke"
    return seen


class TestAnExistingWorktreeOnAResume:
    def test_enters_as_RESUMED(self, state):
        state["resumed_from"] = "impl"

        assert _payload(state, worktree_exists=True).get("retry_mode") == RESUMED

    def test_is_named_in_the_log(self, state, capsys):
        state["resumed_from"] = "impl"

        _payload(state, worktree_exists=True)

        assert "Reusing existing worktree" in capsys.readouterr().out


class TestTheSignalIsStillScopedToResumes:
    def test_a_fresh_draw_with_a_leftover_worktree_keeps_the_states_mode(self, state):
        """A first run whose worktree somehow pre-exists is not a resume, and
        #2337's green-at-red guard must still be able to fire for it."""
        state["resumed_from"] = ""

        assert _payload(state, worktree_exists=True).get("retry_mode") == ""

    def test_a_resume_into_another_stage_is_untouched(self, state):
        state["resumed_from"] = "spec"

        assert _payload(state, worktree_exists=True).get("retry_mode") == ""
