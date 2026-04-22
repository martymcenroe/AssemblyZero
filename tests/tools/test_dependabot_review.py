"""Unit tests for tools/dependabot_review.py.

Issue #957: Regression test for the Windows CreateProcess argv-size limit.
The tool used to pass full PR bodies via `gh pr edit --body "<string>"`,
which crashed on Windows with WinError 206 when bodies exceeded ~32KB
(common for multi-package dependabot group bumps with embedded release
notes). The fix routes large bodies through `--body-file <tempfile>`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import dependabot_review  # noqa: E402


# 30KB is well above the empirically-observed Windows CreateProcess limit
# (~32K total including the rest of the command). Real PR #953 body was ~19KB.
LARGE_BODY = "x" * 30_000


def _stub_run(captured: dict) -> mock.MagicMock:
    """Replace the module's `run` with a stub that records args and returns success."""
    stub = mock.MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    )

    def _capture(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        return stub.return_value

    stub.side_effect = _capture
    return stub


class TestRunGhWithBody:
    """Direct tests for the new helper introduced by #957."""

    def test_uses_body_file_flag_not_body(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        dependabot_review.run_gh_with_body(
            ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
            "hello world",
        )

        assert "--body-file" in captured["cmd"]
        assert "--body" not in captured["cmd"], (
            "Helper must NOT pass body via --body argv (the bug it fixes)."
        )

    def test_body_file_contents_match_body(self, monkeypatch):
        captured: dict = {}
        body_seen: dict = {}

        def _capture(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            # Read the file before the helper deletes it
            tmp_path = cmd[cmd.index("--body-file") + 1]
            body_seen["text"] = Path(tmp_path).read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        dependabot_review.run_gh_with_body(
            ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
            "exact body content",
        )
        assert body_seen["text"] == "exact body content"

    def test_tempfile_cleaned_up_after_call(self, monkeypatch):
        tmp_paths: list[str] = []

        def _capture(cmd, *args, **kwargs):
            tmp_paths.append(cmd[cmd.index("--body-file") + 1])
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        dependabot_review.run_gh_with_body(
            ["gh", "pr", "comment", "1", "--repo", "owner/repo"],
            "some comment",
        )
        assert tmp_paths, "subprocess should have been invoked"
        assert not Path(tmp_paths[0]).exists(), "tempfile should be cleaned up after call"

    def test_tempfile_cleaned_up_on_exception(self, monkeypatch):
        tmp_paths: list[str] = []

        def _capture_then_raise(cmd, *args, **kwargs):
            tmp_paths.append(cmd[cmd.index("--body-file") + 1])
            raise RuntimeError("simulated subprocess failure")

        monkeypatch.setattr(dependabot_review, "run", _capture_then_raise)

        with pytest.raises(RuntimeError):
            dependabot_review.run_gh_with_body(
                ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
                "body",
            )
        assert tmp_paths, "subprocess should have been invoked"
        assert not Path(tmp_paths[0]).exists(), (
            "tempfile must be cleaned up even when the subprocess raises."
        )

    def test_handles_30kb_body_without_winerror(self, monkeypatch):
        """REGRESSION: 30KB body must not raise FileNotFoundError (WinError 206)."""
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        result = dependabot_review.run_gh_with_body(
            ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
            LARGE_BODY,
        )
        assert result.returncode == 0


class TestInjectNoIssue:
    """Tests for inject_no_issue, the original failure site."""

    def test_inject_no_issue_does_not_use_body_argv(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        pr = dependabot_review.PRInfo(
            number=42,
            title="t",
            author_login="app/dependabot",
            body=LARGE_BODY,
            head_ref="dependabot/pip/x-1",
        )
        dependabot_review.inject_no_issue(pr, "owner/repo")

        assert "--body" not in captured["cmd"], (
            "inject_no_issue must use --body-file, never --body (#957 fix)."
        )
        assert "--body-file" in captured["cmd"]

    def test_inject_no_issue_writes_full_tagged_body(self, monkeypatch):
        body_seen: dict = {}

        def _capture(cmd, *args, **kwargs):
            tmp_path = cmd[cmd.index("--body-file") + 1]
            body_seen["text"] = Path(tmp_path).read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        pr = dependabot_review.PRInfo(
            number=42,
            title="bump foo",
            author_login="app/dependabot",
            body="Bumps `foo` from 1.0 to 2.0.",
            head_ref="dependabot/pip/foo-2",
        )
        dependabot_review.inject_no_issue(pr, "owner/repo")

        assert "Bumps `foo` from 1.0 to 2.0." in body_seen["text"]
        assert "No-Issue:" in body_seen["text"]


class TestCommentOnPr:
    """comment_on_pr also routes through run_gh_with_body for consistency."""

    def test_uses_body_file(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        dependabot_review.comment_on_pr(99, "owner/repo", "comment text")

        assert "--body-file" in captured["cmd"]
        assert "--body" not in captured["cmd"]
        assert "gh" in captured["cmd"][0]
        assert "comment" in captured["cmd"]


class TestWaitForMergeable:
    """Issue #971: accept 'unstable' in addition to 'clean', tolerate one
    cycle of 'blocked' to absorb the Cerberus-arrival race."""

    def _stub_state(self, monkeypatch, states):
        """Make `run` return a sequence of mergeable_state values."""
        it = iter(states)

        def _capture(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=next(it), stderr=""
            )

        monkeypatch.setattr(dependabot_review, "run", mock.Mock(side_effect=_capture))
        monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)

    def test_clean_returns_true(self, monkeypatch):
        self._stub_state(monkeypatch, ["clean"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_unstable_returns_true(self, monkeypatch):
        """Unstable means non-required checks failing; gh pr merge --squash
        accepts this. Was the gating bug in PR #953 + #741 today."""
        self._stub_state(monkeypatch, ["unstable"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_dirty_returns_false_immediately(self, monkeypatch):
        """Merge conflict — waiting won't help. Don't burn 15 min."""
        self._stub_state(monkeypatch, ["dirty"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is False

    def test_persistent_blocked_returns_false(self, monkeypatch):
        """After tolerating one cycle, persistent blocked gives up."""
        self._stub_state(monkeypatch, ["blocked", "blocked", "blocked"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is False

    def test_blocked_then_clean_returns_true(self, monkeypatch):
        """Race tolerance: Cerberus arrives between two of our polls."""
        self._stub_state(monkeypatch, ["blocked", "clean"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_pending_then_clean_returns_true(self, monkeypatch):
        """Normal happy path: state resolves after a few cycles."""
        self._stub_state(monkeypatch, ["unknown", "unknown", "clean"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_default_timeout_is_900s(self):
        """Issue #971: bumped from 300 -> 900 to cover Cerberus tail."""
        assert dependabot_review.MERGEABLE_TIMEOUT_S == 900


class TestIsPRBranchStale:
    """Issue #994: detect when a PR's base SHA is behind current main HEAD."""

    def _stub_api(self, monkeypatch, base_sha, main_sha):
        """Stub `run` to return base_sha for the pulls call, main_sha for branches."""
        def _capture(cmd, *args, **kwargs):
            joined = " ".join(cmd)
            if "/pulls/" in joined:
                stdout = base_sha
            elif "/branches/main" in joined:
                stdout = main_sha
            else:
                stdout = ""
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")
        monkeypatch.setattr(dependabot_review, "run", mock.Mock(side_effect=_capture))

    def test_returns_true_when_shas_differ(self, monkeypatch):
        self._stub_api(monkeypatch, "abc123", "def456")
        assert dependabot_review.is_pr_branch_stale(1, "owner/repo") is True

    def test_returns_false_when_shas_match(self, monkeypatch):
        self._stub_api(monkeypatch, "samesha", "samesha")
        assert dependabot_review.is_pr_branch_stale(1, "owner/repo") is False

    def test_returns_false_on_empty_responses(self, monkeypatch):
        """Conservative: don't trigger rebase on uncertain state."""
        self._stub_api(monkeypatch, "", "")
        assert dependabot_review.is_pr_branch_stale(1, "owner/repo") is False

    def test_strips_quotes_from_jq_output(self, monkeypatch):
        """gh api --jq returns JSON-quoted strings; helper must strip quotes."""
        self._stub_api(monkeypatch, '"abc123"', '"abc123"')
        assert dependabot_review.is_pr_branch_stale(1, "owner/repo") is False


class TestRequestDependabotRebase:
    """Issue #994: posts both an explanatory comment AND the trigger comment."""

    def test_posts_explanation_then_trigger(self, monkeypatch):
        comments: list[str] = []
        monkeypatch.setattr(
            dependabot_review,
            "comment_on_pr",
            lambda pr_number, repo, body: comments.append(body),
        )
        dependabot_review.request_dependabot_rebase(42, "owner/repo")

        assert len(comments) == 2
        assert "@dependabot rebase" in comments[1]
        explanation = comments[0].lower()
        assert "rebas" in explanation or "behind" in explanation or "main" in explanation


class TestProcessPrDeferralStaleBranchPriority:
    """Issue #994: in the deferral path, staleness check supersedes
    multi-package recreate. Both can be true simultaneously; rebase first."""

    def _stub_pipeline(self, monkeypatch, exit_code, package_count, is_stale):
        """Stub the pieces of process_pr we need to exercise the deferral branch."""
        monkeypatch.setattr(dependabot_review, "verify_author", lambda pr: True)
        monkeypatch.setattr(
            dependabot_review,
            "create_audit_worktree",
            lambda main_repo, pr_number: (Path("/tmp/fake"), "fake-branch"),
        )
        monkeypatch.setattr(
            dependabot_review,
            "checkout_pr_into_worktree",
            lambda worktree, pr_number, repo: True,
        )
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv", lambda worktree: None)
        monkeypatch.setattr(dependabot_review, "install_deps", lambda worktree: True)
        monkeypatch.setattr(dependabot_review, "run_tests", lambda worktree: exit_code)
        monkeypatch.setattr(dependabot_review, "count_packages", lambda body: package_count)
        monkeypatch.setattr(dependabot_review, "is_pr_branch_stale", lambda pr, repo: is_stale)

    def test_stale_branch_triggers_rebase_not_recreate(self, monkeypatch):
        actions: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "comment_on_pr",
            lambda pr_number, repo, body: actions.append(f"comment: {body[:40]}"),
        )
        monkeypatch.setattr(
            dependabot_review, "request_dependabot_rebase",
            lambda pr_number, repo: actions.append("REBASE"),
        )
        monkeypatch.setattr(
            dependabot_review, "request_dependabot_recreate",
            lambda pr_number, repo: actions.append("RECREATE"),
        )

        self._stub_pipeline(monkeypatch, exit_code=1, package_count=3, is_stale=True)
        pr = dependabot_review.PRInfo(
            number=42, title="t", author_login="app/dependabot",
            body="fake", head_ref="r",
        )
        result = dependabot_review.process_pr(pr, "owner/repo", Path("/tmp/main"))
        assert result == "deferred"
        assert "REBASE" in actions
        assert "RECREATE" not in actions, (
            "staleness diagnosis should preempt recreate — rebase is cheaper"
        )

    def test_current_branch_multi_package_still_recreates(self, monkeypatch):
        """Existing behavior preserved when staleness check returns False."""
        actions: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "comment_on_pr",
            lambda pr_number, repo, body: actions.append(f"comment: {body[:40]}"),
        )
        monkeypatch.setattr(
            dependabot_review, "request_dependabot_rebase",
            lambda pr_number, repo: actions.append("REBASE"),
        )
        monkeypatch.setattr(
            dependabot_review, "request_dependabot_recreate",
            lambda pr_number, repo: actions.append("RECREATE"),
        )

        self._stub_pipeline(monkeypatch, exit_code=1, package_count=3, is_stale=False)
        pr = dependabot_review.PRInfo(
            number=42, title="t", author_login="app/dependabot",
            body="fake", head_ref="r",
        )
        result = dependabot_review.process_pr(pr, "owner/repo", Path("/tmp/main"))
        assert result == "deferred"
        assert "RECREATE" in actions
        assert "REBASE" not in actions

    def test_current_branch_single_package_neither_action(self, monkeypatch):
        """Current + single-package failure: just the test-failure comment, no auto-action."""
        actions: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "comment_on_pr",
            lambda pr_number, repo, body: actions.append(f"comment: {body[:40]}"),
        )
        monkeypatch.setattr(
            dependabot_review, "request_dependabot_rebase",
            lambda pr_number, repo: actions.append("REBASE"),
        )
        monkeypatch.setattr(
            dependabot_review, "request_dependabot_recreate",
            lambda pr_number, repo: actions.append("RECREATE"),
        )

        self._stub_pipeline(monkeypatch, exit_code=1, package_count=1, is_stale=False)
        pr = dependabot_review.PRInfo(
            number=42, title="t", author_login="app/dependabot",
            body="fake", head_ref="r",
        )
        result = dependabot_review.process_pr(pr, "owner/repo", Path("/tmp/main"))
        assert result == "deferred"
        assert "REBASE" not in actions
        assert "RECREATE" not in actions
