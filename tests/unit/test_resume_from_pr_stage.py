"""A pr-stage failure resumes instead of redrawing the pipeline (#2194).

#2193 shipped resume for `spec` and `impl` and deferred `pr`/`cleanup`, naming
the evidence it wanted first: "the first observed relaunch-after-pr-failure
that redraws an expensive impl is the evidence to build from".

`run-issue7-231606` is that observation, and it is the only one in the corpus
(21 pr passes, 1 pr failure, 0 cleanup failures across 21 passes):

    lld     passed    281.9s
    spec    passed    699.0s
    impl    passed    363.6s
    pr      failed      0.7s   ! [rejected] issue-7 -> issue-7 (non-fast-forward)

1344.5 seconds of paid work discarded to retry a git push that failed in under
a second, on a branch-state rejection rather than anything about the content.

`cleanup` is deliberately still excluded: zero observed failures means no shape
to design its integrity checks against, which is the same standard that kept
`pr` out until now.
"""

from __future__ import annotations

import json
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
        self.lines: list[str] = []

    def write(self, message):
        self.lines.append(message)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


def _state(tmp_path, repo, worktree: str | None, **overrides):
    """The measured run-issue7-231606 shape: everything passed but pr."""
    data = {
        "issue_number": 7,
        "current_stage": "pr",
        "target_repo": str(repo),
        "base_branch": "hardening-run-17",
        "lld_path": str(repo / "docs" / "lld" / "LLD-007.md"),
        "spec_path": str(repo / "docs" / "lld" / "spec-0007.md"),
        "worktree_path": worktree if worktree is not None else "",
        "stage_results": {
            "triage": {"status": "skipped", "error_message": ""},
            "lld": {"status": "passed", "error_message": ""},
            "spec": {"status": "passed", "error_message": ""},
            "impl": {"status": "passed", "error_message": ""},
            "pr": {
                "status": "failed",
                "error_message": (
                    "PR creation error: ! [rejected] issue-7 -> issue-7 "
                    "(non-fast-forward)"
                ),
            },
        },
        "started_at": "2026-08-14T04:00:00+00:00",
        "completed_at": "",
    }
    data.update(overrides)
    path = tmp_path / "7.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _plan(repo, state_path):
    log = _Log()
    with patch.object(sr, "_orchestrator_state_path", return_value=state_path), \
         patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
         patch.object(sr, "_open_lld_pr_exists", return_value=True), \
         patch.object(sr, "draft_is_stale", return_value=False), \
         patch.object(sr, "_restore_artifact", return_value=True):
        return sr.resume_plan(Path("."), repo, 7, log), log


class TestTheMeasuredRunResumes:
    def test_a_pr_failure_resumes_from_pr(self, tmp_path, repo):
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        stage, _log = _plan(repo, _state(tmp_path, repo, str(worktree)))
        assert stage == "pr"

    def test_pr_is_in_the_resumable_set(self):
        assert "pr" in sr.RESUMABLE_STAGES

    def test_the_spec_artifact_is_required_for_pr_too(self):
        """The pr stage reads the impl worktree, which exists only because
        spec produced what impl built from."""
        assert "pr" in sr._STAGES_NEEDING_SPEC
        assert "impl" in sr._STAGES_NEEDING_SPEC


class TestTheWorktreeGuard:
    """`run_pr_stage` fails immediately with "No worktree path available for
    PR creation" without one, so resuming into a missing worktree costs more
    than the redraw it saves."""

    def test_a_missing_worktree_declines(self, tmp_path, repo):
        stage, log = _plan(repo, _state(tmp_path, repo, str(tmp_path / "gone")))
        assert stage is None
        assert any("worktree" in line for line in log.lines)

    def test_an_unset_worktree_declines(self, tmp_path, repo):
        stage, log = _plan(repo, _state(tmp_path, repo, ""))
        assert stage is None
        assert any("worktree" in line for line in log.lines)

    def test_a_whitespace_worktree_declines(self, tmp_path, repo):
        stage, _log = _plan(repo, _state(tmp_path, repo, "   "))
        assert stage is None

    def test_the_decline_names_what_is_missing(self, tmp_path, repo):
        _stage, log = _plan(repo, _state(tmp_path, repo, ""))
        assert any("pr stage needs the impl worktree" in line for line in log.lines)

    def test_a_spec_failure_does_not_demand_a_worktree(self, tmp_path, repo):
        """The guard must be scoped to pr. A spec-stage resume has no
        worktree yet and must not start requiring one."""
        state = _state(
            tmp_path, repo, "",
            current_stage="spec",
            stage_results={
                "triage": {"status": "skipped", "error_message": ""},
                "lld": {"status": "passed", "error_message": ""},
                "spec": {"status": "failed", "error_message": "cap"},
            },
        )
        stage, _log = _plan(repo, state)
        assert stage == "spec"


class TestCleanupIsStillExcluded:
    """Zero observed failures means no shape to design against -- the same
    standard that kept `pr` out until its evidence arrived."""

    def test_cleanup_is_not_resumable(self):
        assert "cleanup" not in sr.RESUMABLE_STAGES

    def test_a_cleanup_failure_declines(self, tmp_path, repo):
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        state = _state(
            tmp_path, repo, str(worktree),
            current_stage="cleanup",
            stage_results={
                "triage": {"status": "skipped", "error_message": ""},
                "lld": {"status": "passed", "error_message": ""},
                "spec": {"status": "passed", "error_message": ""},
                "impl": {"status": "passed", "error_message": ""},
                "pr": {"status": "passed", "error_message": ""},
                "cleanup": {"status": "failed", "error_message": "boom"},
            },
        )
        stage, _log = _plan(repo, state)
        assert stage is None


class TestTheExistingGuardsStillApply:
    """#2193's guards are not weakened by adding a stage."""

    def test_a_requirements_conflict_still_declines(self, tmp_path, repo):
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        state = _state(
            tmp_path, repo, str(worktree),
            stage_results={
                "triage": {"status": "skipped", "error_message": ""},
                "lld": {"status": "passed", "error_message": ""},
                "spec": {"status": "passed", "error_message": ""},
                "impl": {"status": "passed", "error_message": ""},
                "pr": {
                    "status": "failed",
                    "error_message": "REQUIREMENTS CONFLICT: two readings",
                },
            },
        )
        stage, _log = _plan(repo, state)
        assert stage is None

    def test_a_closed_lld_pr_still_declines(self, tmp_path, repo):
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        state_path = _state(tmp_path, repo, str(worktree))
        log = _Log()
        with patch.object(sr, "_orchestrator_state_path", return_value=state_path), \
             patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
             patch.object(sr, "_open_lld_pr_exists", return_value=False), \
             patch.object(sr, "draft_is_stale", return_value=False), \
             patch.object(sr, "_restore_artifact", return_value=True):
            assert sr.resume_plan(Path("."), repo, 7, log) is None

    def test_a_stale_draft_still_declines(self, tmp_path, repo):
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        state_path = _state(tmp_path, repo, str(worktree))
        log = _Log()
        with patch.object(sr, "_orchestrator_state_path", return_value=state_path), \
             patch.object(sr, "resolve_attempt_branch", return_value="hardening-run-17"), \
             patch.object(sr, "_open_lld_pr_exists", return_value=True), \
             patch.object(sr, "draft_is_stale", return_value=True), \
             patch.object(sr, "_restore_artifact", return_value=True):
            assert sr.resume_plan(Path("."), repo, 7, log) is None
