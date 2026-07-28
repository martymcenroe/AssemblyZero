"""Unit tests for tools/dependabot_review.py.

Issue #957: Regression test for the Windows CreateProcess argv-size limit.
The tool used to pass full PR bodies via `gh pr edit --body "<string>"`,
which crashed on Windows with WinError 206 when bodies exceeded ~32KB
(common for multi-package dependabot group bumps with embedded release
notes). The fix routes large bodies through `--body-file <tempfile>`.
"""

from __future__ import annotations

import json
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
    """Issue #971: accept 'unstable' in addition to 'clean'.
    Issue #1399: poll through 'blocked' until MERGEABLE_TIMEOUT_S timeout
    (was: bailed after the second poll, which silently failed every PR
    where cerberus-az took longer than POLL_INTERVAL_S to arrive)."""

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

    def test_persistent_blocked_returns_false_at_timeout(self, monkeypatch):
        """#1399: persistent blocked polls until the full timeout, then
        returns False. Pre-#1399 it bailed after poll #2 (~10s), which
        silently failed every PR where cerberus took longer than one
        POLL_INTERVAL_S to arrive (#84, #47 on 2026-05-29/30)."""
        # Tiny timeout so the test exits quickly without burning 15 min.
        monkeypatch.setattr(dependabot_review, "MERGEABLE_TIMEOUT_S", 0.01)
        monkeypatch.setattr(
            dependabot_review, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="blocked", stderr=""),
        )
        monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is False

    def test_blocked_then_clean_returns_true(self, monkeypatch):
        """Race tolerance: Cerberus arrives between two of our polls."""
        self._stub_state(monkeypatch, ["blocked", "clean"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_multiple_blocked_then_clean_returns_true(self, monkeypatch):
        """#1399: blocked-blocked-blocked-clean now succeeds. Pre-#1399 it
        would have bailed at poll #2 even though cerberus arrived at #4."""
        self._stub_state(monkeypatch, ["blocked", "blocked", "blocked", "clean"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_pending_then_clean_returns_true(self, monkeypatch):
        """Normal happy path: state resolves after a few cycles."""
        self._stub_state(monkeypatch, ["unknown", "unknown", "clean"])
        assert dependabot_review.wait_for_mergeable(1, "owner/repo") is True

    def test_default_timeout_is_900s(self):
        """Issue #971: bumped from 300 -> 900 to cover Cerberus tail."""
        assert dependabot_review.MERGEABLE_TIMEOUT_S == 900

    def test_elapsed_time_is_logged(self, monkeypatch, capsys):
        """#1399: each poll logs elapsed seconds so the operator can tell
        cerberus-timing-tail from polling-logic bugs."""
        self._stub_state(monkeypatch, ["clean"])
        dependabot_review.wait_for_mergeable(1, "owner/repo")
        out = capsys.readouterr().out
        assert "elapsed" in out


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


class TestRunTestsDisablesBytecode:
    """#1371: run_tests must disable Python bytecode caching so pytest does not
    write __pycache__/*.pyc into the audit worktree. Untracked .pyc files dirty
    the worktree and make `git worktree remove` (no --force) refuse, leaking it.
    """

    def test_run_tests_sets_pythondontwritebytecode(self, monkeypatch, tmp_path):
        captured: dict = {}

        def _capture(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        dependabot_review.run_tests(tmp_path)

        assert captured["env"] is not None, "run_tests must pass env to run()"
        assert captured["env"].get("PYTHONDONTWRITEBYTECODE") == "1"


class TestCleanupWorktreeNoGitRestore:
    """#1377: cleanup_worktree must NOT use `git restore` (banned B7 pattern).
    A dirty worktree is surfaced loudly and left for the non-`--force`
    `git worktree remove` to refuse, never silently wiped.
    """

    def _run_cleanup(self, monkeypatch, tmp_path, dirt: str):
        """Drive cleanup_worktree with a stubbed run() that reports `dirt`
        (a git status --porcelain string) and otherwise succeeds. Returns
        (result, list_of_commands_run)."""
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv", lambda wt: None)
        commands: list[list[str]] = []

        def _fake_run(cmd, *args, **kwargs):
            commands.append(list(cmd))
            stdout = ""
            if "status" in cmd and "--porcelain" in cmd:
                stdout = dirt
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

        monkeypatch.setattr(dependabot_review, "run", _fake_run)
        result = dependabot_review.cleanup_worktree(tmp_path, tmp_path, "dependabot-audit-1")
        return result, commands

    def test_never_invokes_git_restore_when_clean(self, monkeypatch, tmp_path):
        result, commands = self._run_cleanup(monkeypatch, tmp_path, dirt="")
        assert result is True
        assert not any("restore" in c for c in commands), \
            f"cleanup_worktree must not call git restore; saw: {commands}"

    def test_never_invokes_git_restore_when_dirty(self, monkeypatch, tmp_path):
        # Even with a dirty tree, the banned restore must NOT appear.
        result, commands = self._run_cleanup(
            monkeypatch, tmp_path, dirt=" M docs/0003-file-inventory.md"
        )
        assert not any("restore" in c for c in commands), \
            f"cleanup_worktree must not call git restore even when dirty; saw: {commands}"

    def test_dirty_worktree_emits_warning(self, monkeypatch, tmp_path, capsys):
        self._run_cleanup(monkeypatch, tmp_path, dirt=" M docs/0003-file-inventory.md")
        err = capsys.readouterr().err
        assert "dirty" in err.lower()
        assert "docs/0003-file-inventory.md" in err
        assert "do NOT add a `git restore`" in err

    def test_clean_worktree_emits_no_dirty_warning(self, monkeypatch, tmp_path, capsys):
        self._run_cleanup(monkeypatch, tmp_path, dirt="")
        err = capsys.readouterr().err
        assert "dirty" not in err.lower()


class TestExitCodeFiveIsPass:
    """#1397: pytest exit 5 (no tests collected) is the normal result for
    test-less repos (decorative-deps honeypots, scaffold stubs). The gate
    must treat exit 5 as pass, not failure. A dep bump cannot turn N>0
    tests into 0, so exit 5 reliably means "this repo has no test suite"
    -- safe to merge for the dep-bump gate's purpose."""

    def _stub_inner_pipeline(self, monkeypatch, exit_code):
        """Stub everything _process_pr_inside_worktree calls except the gate,
        so we can isolate the exit-code decision. Green-path helpers all
        return success, so a non-deferred run reaches the green path."""
        monkeypatch.setattr(dependabot_review, "checkout_pr_into_worktree",
                            lambda worktree, pr_number, repo: True)
        # #1400/#1839: force the Python gate ON (and the npm gate OFF) so
        # these exit-code tests exercise the install/test path they are
        # testing, regardless of what the stubbed `run` returns for the
        # changed-files listing.
        monkeypatch.setattr(dependabot_review, "_pr_changed_files",
                            lambda pr, repo: ["pyproject.toml"])
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv", lambda wt: None)
        monkeypatch.setattr(dependabot_review, "install_deps", lambda wt: True)
        monkeypatch.setattr(dependabot_review, "run_tests", lambda wt: exit_code)
        # Green-path stubs (only used when the gate doesn't defer).
        monkeypatch.setattr(dependabot_review, "inject_no_issue", lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review, "approve_pr",
                            lambda pr, repo, gate_desc: True)
        monkeypatch.setattr(dependabot_review, "wait_for_mergeable",
                            lambda pr, repo, timeout=900: True)
        monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)
        # Catch-all for the gh pr merge subprocess call on the green path.
        monkeypatch.setattr(
            dependabot_review, "run",
            lambda cmd, *a, **kw: subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""),
        )

    def _track_review_comments(self, monkeypatch):
        """Capture (pr, body) tuples for every review_comment_on_pr call so
        we can assert the deferral comment was/wasn't posted."""
        calls: list[tuple[int, str]] = []
        monkeypatch.setattr(dependabot_review, "review_comment_on_pr",
                            lambda pr, repo, body: calls.append((pr, body)) or True)
        return calls

    def _pr(self):
        return dependabot_review.PRInfo(
            number=42, title="bump foo", author_login="app/dependabot",
            body="Updates `foo`", head_ref="dependabot/pip/foo",
        )

    def test_exit_5_does_not_defer(self, monkeypatch, capsys):
        """The bug: clean test-less PR with pytest exit 5 must NOT be deferred."""
        self._stub_inner_pipeline(monkeypatch, exit_code=5)
        calls = self._track_review_comments(monkeypatch)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        # The deferral path posts a review-comment containing "FAILED".
        failed_comments = [body for _, body in calls if "FAILED" in body]
        assert not failed_comments, (
            f"exit 5 must NOT trigger the deferral review-comment; "
            f"got: {failed_comments}"
        )
        # Result must not be 'deferred' -- we took the green path.
        assert result != "deferred", f"exit 5 must not defer; got {result!r}"

    def test_exit_5_logs_treating_as_pass(self, monkeypatch, capsys):
        """The fix must log loudly so operators see why a no-tests repo passed."""
        self._stub_inner_pipeline(monkeypatch, exit_code=5)
        self._track_review_comments(monkeypatch)

        dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        out = capsys.readouterr().out
        assert "no tests collected" in out
        assert "treating as PASS" in out

    def test_exit_0_unchanged_green_path(self, monkeypatch):
        """Exit 0 (tests passed) must continue to take the green path."""
        self._stub_inner_pipeline(monkeypatch, exit_code=0)
        calls = self._track_review_comments(monkeypatch)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        failed_comments = [body for _, body in calls if "FAILED" in body]
        assert not failed_comments
        assert result != "deferred"

    def test_exit_1_still_defers(self, monkeypatch):
        """Real test failure (exit 1) must still defer -- existing behavior."""
        self._stub_inner_pipeline(monkeypatch, exit_code=1)
        # Stub the deferral-only helpers we'd otherwise miss.
        monkeypatch.setattr(dependabot_review, "is_pr_branch_stale",
                            lambda pr, repo: False)
        monkeypatch.setattr(dependabot_review, "count_packages", lambda body: 1)
        calls = self._track_review_comments(monkeypatch)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        failed_comments = [body for _, body in calls if "FAILED (exit 1)" in body]
        assert failed_comments, "exit 1 must still post the FAILED deferral comment"
        assert result == "deferred"

    def test_constant_is_five(self):
        """Lock the named constant to pytest's documented exit code."""
        assert dependabot_review.PYTEST_EXIT_NO_TESTS_COLLECTED == 5


class TestWaitForMergeableTimeoutDeferred:
    """#1399: when wait_for_mergeable returns False due to timeout (state
    still 'blocked' / 'behind' / 'unknown'), the caller must classify the
    PR as DEFERRED, not ERRORED. The approval persists; the next run will
    merge it. Pre-#1399 the tool returned 'errored', misclassifying healthy
    in-flight PRs as failures (#84 round 1, #47 round 2)."""

    def _stub_to_wait_for_mergeable(self, monkeypatch):
        """Stub everything up to wait_for_mergeable; the test then patches
        wait_for_mergeable + the final-state re-query to control the exit
        path under test."""
        monkeypatch.setattr(dependabot_review, "checkout_pr_into_worktree",
                            lambda worktree, pr_number, repo: True)
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv", lambda wt: None)
        monkeypatch.setattr(dependabot_review, "install_deps", lambda wt: True)
        monkeypatch.setattr(dependabot_review, "run_tests", lambda wt: 0)
        monkeypatch.setattr(dependabot_review, "inject_no_issue", lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review, "approve_pr",
                            lambda pr, repo, gate_desc: True)
        monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)

    def _pr(self):
        return dependabot_review.PRInfo(
            number=42, title="bump foo", author_login="app/dependabot",
            body="Updates `foo`", head_ref="dependabot/pip/foo",
        )

    def _stub_wait_then_final_state(self, monkeypatch, final_state):
        """wait_for_mergeable returns False; the post-wait re-query returns
        `final_state`."""
        monkeypatch.setattr(dependabot_review, "wait_for_mergeable",
                            lambda pr, repo: False)
        monkeypatch.setattr(
            dependabot_review, "run",
            lambda cmd, *a, **kw: subprocess.CompletedProcess(
                args=cmd, returncode=0,
                stdout=f'"{final_state}"', stderr=""),
        )

    def test_blocked_after_timeout_returns_deferred(self, monkeypatch, capsys):
        """The exact #84/#47 case: cerberus did not approve before timeout."""
        self._stub_to_wait_for_mergeable(monkeypatch)
        self._stub_wait_then_final_state(monkeypatch, "blocked")

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        assert result == "deferred", (
            "blocked-at-timeout must be deferred, not errored (approval persists; "
            "next run merges it)"
        )
        out = capsys.readouterr().out
        assert "DEFER" in out
        assert "#1399" in out

    def test_behind_after_timeout_returns_deferred(self, monkeypatch):
        """`behind` = base branch moved; still transient, recoverable."""
        self._stub_to_wait_for_mergeable(monkeypatch)
        self._stub_wait_then_final_state(monkeypatch, "behind")
        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )
        assert result == "deferred"

    def test_unknown_after_timeout_returns_deferred(self, monkeypatch):
        """`unknown` = GitHub still computing; also transient."""
        self._stub_to_wait_for_mergeable(monkeypatch)
        self._stub_wait_then_final_state(monkeypatch, "unknown")
        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )
        assert result == "deferred"

    def test_dirty_returns_errored_with_rebase(self, monkeypatch):
        """`dirty` = merge conflict, NOT transient. Existing behavior
        preserved: errored + @dependabot rebase requested."""
        self._stub_to_wait_for_mergeable(monkeypatch)
        rebase_calls: list = []
        monkeypatch.setattr(dependabot_review, "request_dependabot_rebase",
                            lambda pr, repo: rebase_calls.append((pr, repo)))
        self._stub_wait_then_final_state(monkeypatch, "dirty")
        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )
        assert result == "errored"
        assert rebase_calls == [(42, "owner/repo")], (
            "dirty path must still request @dependabot rebase"
        )


class TestPrTouchesPython:
    """#1400: pr_touches_python decides whether to run the Python gate
    (poetry install + pytest). True iff the PR's diff contains any Python
    file (*.py) or Python manifest (pyproject.toml, poetry.lock, etc.).
    Conservative: returns True if the diff query fails (no false-pass)."""

    def _stub_diff(self, monkeypatch, files, returncode=0):
        """Make `run` return the given file list as gh pr diff --name-only output."""
        stdout = "\n".join(files) + ("\n" if files else "")

        def _capture(cmd, *args, **kwargs):
            assert "diff" in cmd and "--name-only" in cmd, (
                f"pr_touches_python must shell out to gh pr diff --name-only; saw {cmd}"
            )
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode, stdout=stdout, stderr="",
            )

        monkeypatch.setattr(dependabot_review, "run", _capture)

    def test_python_source_file_is_relevant(self, monkeypatch):
        self._stub_diff(monkeypatch, ["src/foo.py"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True

    def test_pyproject_toml_is_relevant(self, monkeypatch):
        self._stub_diff(monkeypatch, ["pyproject.toml", "poetry.lock"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True

    def test_requirements_txt_is_relevant(self, monkeypatch):
        self._stub_diff(monkeypatch, ["requirements.txt"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True

    def test_requirements_dev_txt_is_relevant(self, monkeypatch):
        """requirements-dev.txt, requirements/base.txt etc. all count."""
        self._stub_diff(monkeypatch, ["requirements-dev.txt"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True

    def test_setup_py_is_relevant(self, monkeypatch):
        self._stub_diff(monkeypatch, ["setup.py"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True

    def test_dockerfile_only_is_not_relevant(self, monkeypatch):
        """The exact #52/#53/#55 honeypot case: docker bump alone."""
        self._stub_diff(monkeypatch, ["Dockerfile"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is False

    def test_package_json_only_is_not_relevant(self, monkeypatch):
        """npm bump should NOT trigger the Python gate."""
        self._stub_diff(monkeypatch, ["package.json", "package-lock.json"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is False

    def test_workflow_only_is_not_relevant(self, monkeypatch):
        self._stub_diff(monkeypatch, [".github/workflows/ci.yml"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is False

    def test_empty_diff_is_not_relevant(self, monkeypatch):
        """Edge case: empty diff (unlikely for dependabot but defensive)."""
        self._stub_diff(monkeypatch, [])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is False

    def test_mixed_diff_with_one_python_file_is_relevant(self, monkeypatch):
        """A single .py file in the diff is enough to trigger the gate."""
        self._stub_diff(monkeypatch, ["Dockerfile", "src/util.py", "README.md"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True

    def test_gh_diff_failure_returns_true_conservatively(self, monkeypatch, capsys):
        """If gh pr diff fails, default to running the Python gate (no
        false-pass). A WARNING is logged so the operator sees why."""
        self._stub_diff(monkeypatch, [], returncode=1)
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True
        err = capsys.readouterr().err
        assert "could not list" in err.lower()
        assert "#1400" in err

    def test_nested_pyproject_is_relevant(self, monkeypatch):
        """Monorepo pattern: pyproject.toml at any depth, not just root."""
        self._stub_diff(monkeypatch, ["services/api/pyproject.toml"])
        assert dependabot_review.pr_touches_python(1, "owner/repo") is True


class TestPipelineSkippedForNonPythonPR:
    """#1400: _process_pr_inside_worktree skips poetry install + pytest
    when the PR touches no Python files. Goes straight to the green path
    (inject_no_issue -> approve -> merge)."""

    def _stub_green_path(self, monkeypatch):
        """Stub the green-path helpers as success no-ops, so we can run
        the function without hitting the network."""
        monkeypatch.setattr(dependabot_review, "checkout_pr_into_worktree",
                            lambda worktree, pr_number, repo: True)
        monkeypatch.setattr(dependabot_review, "inject_no_issue",
                            lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review, "approve_pr",
                            lambda pr, repo, gate_desc: True)
        monkeypatch.setattr(dependabot_review, "wait_for_mergeable",
                            lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review, "squash_merge",
                            lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)

    def _pr(self):
        return dependabot_review.PRInfo(
            number=52, title="bump alpine", author_login="app/dependabot",
            body="", head_ref="dependabot/docker/alpine-3.23.4",
        )

    def test_non_python_pr_skips_install_and_test(self, monkeypatch, capsys):
        """The headline #1400 contract: docker-only PR never invokes
        install_deps or run_tests."""
        self._stub_green_path(monkeypatch)
        monkeypatch.setattr(dependabot_review, "_pr_changed_files",
                            lambda pr, repo: ["Dockerfile"])
        install_called = []
        tests_called = []
        monkeypatch.setattr(dependabot_review, "install_deps",
                            lambda wt: install_called.append(wt) or True)
        monkeypatch.setattr(dependabot_review, "run_tests",
                            lambda wt: tests_called.append(wt) or 0)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        assert install_called == [], (
            "install_deps must NOT be called when PR touches no Python files"
        )
        assert tests_called == [], (
            "run_tests must NOT be called when PR touches no Python files"
        )
        assert result == "merged"
        out = capsys.readouterr().out
        assert "skipping install/test gates" in out
        assert "#1400" in out

    def test_python_pr_still_runs_install_and_test(self, monkeypatch):
        """Existing behavior preserved for Python PRs."""
        self._stub_green_path(monkeypatch)
        monkeypatch.setattr(dependabot_review, "_pr_changed_files",
                            lambda pr, repo: ["poetry.lock"])
        install_called = []
        tests_called = []
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv", lambda wt: None)
        monkeypatch.setattr(dependabot_review, "install_deps",
                            lambda wt: install_called.append(wt) or True)
        monkeypatch.setattr(dependabot_review, "run_tests",
                            lambda wt: tests_called.append(wt) or 0)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"),
        )

        assert len(install_called) == 1, "install_deps must run for Python PRs"
        assert len(tests_called) == 1, "run_tests must run for Python PRs"
        assert result == "merged"


class TestHasDevGroup:
    """#1406: detect whether pyproject.toml declares a `dev` poetry group so
    install_deps can decide whether to pass `--with dev`. The flag was passed
    unconditionally; the docstring claimed Poetry warns when the group is
    absent, but Poetry actually errors out -- deferring every repo without a
    dev group (e.g. patent-general) for a tool-level reason unrelated to the
    dep upgrade."""

    def _write(self, tmp_path, body):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(body, encoding="utf-8")
        return pyproject

    def test_dep_groups_dev_present(self, tmp_path):
        """PEP 735 [dependency-groups] dev = [...] (the AssemblyZero pattern)."""
        pyproject = self._write(tmp_path, '[dependency-groups]\ndev = ["pytest>=8.0"]\n')
        assert dependabot_review._has_dev_group(pyproject) is True

    def test_poetry_group_dev_present(self, tmp_path):
        """Poetry-native [tool.poetry.group.dev] section."""
        pyproject = self._write(
            tmp_path,
            '[tool.poetry.group.dev]\noptional = false\n\n'
            '[tool.poetry.group.dev.dependencies]\npytest = "^8.0"\n',
        )
        assert dependabot_review._has_dev_group(pyproject) is True

    def test_poetry_group_dev_dependencies_only(self, tmp_path):
        """Compact form: only [tool.poetry.group.dev.dependencies]."""
        pyproject = self._write(
            tmp_path,
            '[tool.poetry.group.dev.dependencies]\npytest = "^8.0"\n',
        )
        assert dependabot_review._has_dev_group(pyproject) is True

    def test_other_group_only_returns_false(self, tmp_path):
        """A test group is not a dev group; PEP 735 docs group is not dev."""
        pyproject = self._write(
            tmp_path,
            '[tool.poetry.group.test]\noptional = false\n\n'
            '[dependency-groups]\ndocs = ["mkdocs"]\n',
        )
        assert dependabot_review._has_dev_group(pyproject) is False

    def test_no_groups_returns_false(self, tmp_path):
        """The patent-general case: pyproject exists, no dev group."""
        pyproject = self._write(
            tmp_path,
            '[tool.poetry]\nname = "patent-general"\nversion = "0.1.0"\n\n'
            '[tool.poetry.dependencies]\npython = "^3.11"\n',
        )
        assert dependabot_review._has_dev_group(pyproject) is False

    def test_empty_pyproject_returns_false(self, tmp_path):
        pyproject = self._write(tmp_path, "")
        assert dependabot_review._has_dev_group(pyproject) is False


class TestInstallDepsDevGroupConditional:
    """#1406: install_deps must only pass --with dev when the group exists."""

    def _stub_run(self, monkeypatch, captured, returncode=0):
        def _capture(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode, stdout="", stderr="",
            )
        monkeypatch.setattr(dependabot_review, "run", _capture)

    def test_with_dev_group_passes_flag(self, monkeypatch, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[dependency-groups]\ndev = ["pytest"]\n', encoding="utf-8",
        )
        captured: dict = {}
        self._stub_run(monkeypatch, captured)

        assert dependabot_review.install_deps(tmp_path) is True
        assert "--with" in captured["cmd"]
        assert "dev" in captured["cmd"]

    def test_without_dev_group_omits_flag(self, monkeypatch, tmp_path):
        """The patent-general case that motivated #1406."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8",
        )
        captured: dict = {}
        self._stub_run(monkeypatch, captured)

        assert dependabot_review.install_deps(tmp_path) is True
        assert "--with" not in captured["cmd"], (
            f"install_deps must NOT pass --with when pyproject has no dev "
            f"group; got {captured['cmd']}"
        )

    def test_no_pyproject_returns_true_without_running_poetry(
        self, monkeypatch, tmp_path,
    ):
        """Pre-existing behavior: no pyproject = not a poetry project = skip."""
        called = []
        monkeypatch.setattr(
            dependabot_review, "run",
            lambda *a, **kw: called.append(a) or subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""),
        )
        assert dependabot_review.install_deps(tmp_path) is True
        assert called == [], (
            "install_deps must not invoke poetry when pyproject is absent"
        )


class TestCleanSubprocessEnv:
    """#1415: strip poetry-activation hints (VIRTUAL_ENV, POETRY_ACTIVE) so
    subprocess `poetry` calls resolve the venv per cwd. The tool is invoked
    via `poetry run python tools/dependabot_review.py`, so the inherited env
    has those vars pointing at AZ's venv -- if they leak through, every
    audit runs in AZ's venv instead of the target repo's."""

    def test_strips_virtual_env(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_ENV", "C:/some/venv/path")
        env = dependabot_review._clean_subprocess_env()
        assert "VIRTUAL_ENV" not in env

    def test_strips_poetry_active(self, monkeypatch):
        monkeypatch.setenv("POETRY_ACTIVE", "1")
        env = dependabot_review._clean_subprocess_env()
        assert "POETRY_ACTIVE" not in env

    def test_strips_both_when_both_set(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_ENV", "C:/some/venv/path")
        monkeypatch.setenv("POETRY_ACTIVE", "1")
        env = dependabot_review._clean_subprocess_env()
        assert "VIRTUAL_ENV" not in env
        assert "POETRY_ACTIVE" not in env

    def test_preserves_other_env_vars(self, monkeypatch):
        """PATH and other env must still be present so subprocess can run."""
        monkeypatch.setenv("VIRTUAL_ENV", "C:/some/venv/path")
        monkeypatch.setenv("MY_TEST_VAR", "preserved")
        env = dependabot_review._clean_subprocess_env()
        assert "VIRTUAL_ENV" not in env
        assert env.get("MY_TEST_VAR") == "preserved"
        assert "PATH" in env

    def test_no_op_when_neither_set(self, monkeypatch):
        """Doesn't crash if neither var is in the env (idempotent)."""
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.delenv("POETRY_ACTIVE", raising=False)
        env = dependabot_review._clean_subprocess_env()
        assert "VIRTUAL_ENV" not in env
        assert "POETRY_ACTIVE" not in env


class TestInstallDepsStripsVirtualEnv:
    """#1415: install_deps must pass a cleaned env to poetry so the target's
    venv is resolved, not AZ's."""

    def test_install_deps_passes_clean_env_to_run(self, monkeypatch, tmp_path):
        monkeypatch.setenv("VIRTUAL_ENV", "C:/AZ/venv/that/should/not/leak")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8",
        )
        captured: dict = {}

        def _capture(cmd, *args, **kwargs):
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)
        assert dependabot_review.install_deps(tmp_path) is True

        assert captured["env"] is not None, (
            "install_deps must pass env= to run() so VIRTUAL_ENV is stripped"
        )
        assert "VIRTUAL_ENV" not in captured["env"], (
            "VIRTUAL_ENV must be stripped before poetry install — otherwise "
            "poetry uses AZ venv instead of the target's"
        )


class TestRunTestsStripsVirtualEnv:
    """#1415: run_tests must pass a cleaned env to pytest so the target's
    venv is used, not AZ's. Composes with #1371's PYTHONDONTWRITEBYTECODE."""

    def test_run_tests_strips_virtual_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("VIRTUAL_ENV", "C:/AZ/venv/that/should/not/leak")
        captured: dict = {}

        def _capture(cmd, *args, **kwargs):
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)
        dependabot_review.run_tests(tmp_path)

        assert captured["env"] is not None
        assert "VIRTUAL_ENV" not in captured["env"], (
            "VIRTUAL_ENV must be stripped before pytest — otherwise pytest "
            "runs in AZ venv and target tests see foreign deps (sqlalchemy "
            "via langgraph-checkpoint-sqlite was the recurring case)"
        )

    def test_run_tests_still_sets_pythondontwritebytecode(self, monkeypatch, tmp_path):
        """Compose with #1371: env stripping must not remove the bytecode-
        suppression that prevents __pycache__/*.pyc dirtying the worktree."""
        captured: dict = {}

        def _capture(cmd, *args, **kwargs):
            captured["env"] = kwargs.get("env")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)
        dependabot_review.run_tests(tmp_path)

        assert captured["env"].get("PYTHONDONTWRITEBYTECODE") == "1"


class TestAlreadyDeferredAtHead:
    """#1838: skip re-audit when a tool-authored deferral review exists at
    the PR's current head SHA. Standing deferrals were re-audited (and
    re-commented) every scheduled run; under --limit 15 they consumed the
    entire daily budget before fresh PRs were reached."""

    HEAD = "abc123def4567890abc123def4567890abc123de"

    def _pr(self, head_oid=None):
        return dependabot_review.PRInfo(
            number=42, title="bump x", author_login="app/dependabot",
            body="", head_ref="dependabot/pip/x-1.0",
            head_oid=self.HEAD if head_oid is None else head_oid,
        )

    def _review(self, *, user="martymcenroe", state="COMMENTED",
                commit_id=None, body=None):
        return {
            "user": user,
            "state": state,
            "commit_id": self.HEAD if commit_id is None else commit_id,
            "body": (
                dependabot_review.REVIEW_BODY_PREFIX
                + " -- test suite FAILED (exit 1). Not approving, not merging."
            ) if body is None else body,
        }

    def _stub(self, monkeypatch, reviews, returncode=0, raw=None):
        def _fake(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode,
                stdout=raw if raw is not None else json.dumps(reviews),
                stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)

    def test_matching_deferral_review_skips(self, monkeypatch):
        self._stub(monkeypatch, [self._review()])
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is True

    def test_commit_mismatch_reaudits(self, monkeypatch):
        """A rebase/new push moves the head SHA -- must re-audit (#994)."""
        self._stub(monkeypatch, [self._review(commit_id="0" * 40)])
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is False

    def test_approved_review_does_not_skip(self, monkeypatch):
        """An APPROVED review at head is the green path, not a deferral --
        the #1399 timeout-deferral case must keep retrying the merge."""
        self._stub(monkeypatch, [self._review(state="APPROVED")])
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is False

    def test_foreign_reviewer_does_not_skip(self, monkeypatch):
        self._stub(monkeypatch, [self._review(user="cerberus-az[bot]")])
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is False

    def test_non_tool_body_does_not_skip(self, monkeypatch):
        self._stub(monkeypatch, [self._review(body="LGTM, nice bump")])
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is False

    def test_gh_failure_is_conservative(self, monkeypatch):
        self._stub(monkeypatch, [], returncode=1)
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is False

    def test_bad_json_is_conservative(self, monkeypatch):
        self._stub(monkeypatch, [], raw="not-json{")
        assert dependabot_review.already_deferred_at_head(
            self._pr(), "o/r") is False

    def test_missing_head_oid_reaudits_without_api_call(self, monkeypatch):
        """PRInfo from an older listing (no headRefOid) must not skip and
        must not spend an API call."""
        called = []

        def _fake(*args, **kwargs):
            called.append(args)
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="[]", stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)
        assert dependabot_review.already_deferred_at_head(
            self._pr(head_oid=""), "o/r") is False
        assert called == []


class TestListPRsCarriesHeadOid:
    """#1838: the PR listing must request headRefOid and map it onto
    PRInfo.head_oid so the skip check has a SHA to compare against."""

    def test_head_oid_requested_and_mapped(self, monkeypatch):
        captured: dict = {}
        payload = [{
            "number": 7, "title": "t", "author": {"login": "app/dependabot"},
            "body": None, "headRefName": "dependabot/npm_and_yarn/x-2",
            "headRefOid": "feedbeef" * 5,
        }]

        def _fake(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps(payload), stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)
        prs = dependabot_review.list_dependabot_prs("o/r")
        assert "headRefOid" in " ".join(captured["cmd"])
        assert prs[0].head_oid == "feedbeef" * 5

    def test_missing_oid_field_maps_to_empty(self, monkeypatch):
        payload = [{
            "number": 7, "title": "t", "author": {"login": "app/dependabot"},
            "body": "", "headRefName": "h",
        }]

        def _fake(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps(payload), stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)
        assert dependabot_review.list_dependabot_prs("o/r")[0].head_oid == ""


class TestProcessRepoSkipsUnchanged:
    """#1838: the skip happens BEFORE budget accounting and before any
    worktree work; skipped PRs land in skipped_unchanged, visibly."""

    def _wire(self, monkeypatch, tmp_path, deferred_at_head):
        pr = dependabot_review.PRInfo(
            number=9, title="bump y", author_login="app/dependabot",
            body="", head_ref="h", head_oid="cafe1234" * 5)
        monkeypatch.setattr(dependabot_review, "resolve_target_repo_dir",
                            lambda repo, parent: tmp_path)
        monkeypatch.setattr(dependabot_review, "check_for_orphan_worktrees",
                            lambda t: [])
        monkeypatch.setattr(dependabot_review, "list_dependabot_prs",
                            lambda repo: [pr])
        monkeypatch.setattr(dependabot_review, "already_deferred_at_head",
                            lambda p, repo: deferred_at_head)
        processed: list[int] = []
        monkeypatch.setattr(
            dependabot_review, "process_pr",
            lambda p, repo, target: processed.append(p.number) or "merged")
        return processed

    def test_unchanged_pr_is_skipped_and_budget_untouched(
            self, monkeypatch, tmp_path):
        processed = self._wire(monkeypatch, tmp_path, deferred_at_head=True)
        budget = dependabot_review.PRBudget(5)
        sub = dependabot_review.process_repo("o/r", tmp_path, budget=budget)
        assert sub["skipped_unchanged"] == ["o/r#9"]
        assert processed == []
        assert budget.used == 0, (
            "skip must happen BEFORE budget.try_acquire -- a skipped PR "
            "consuming budget recreates the starvation #1838 fixes"
        )

    def test_changed_pr_still_processes(self, monkeypatch, tmp_path):
        processed = self._wire(monkeypatch, tmp_path, deferred_at_head=False)
        sub = dependabot_review.process_repo("o/r", tmp_path)
        assert processed == [9]
        assert sub["merged"] == ["o/r#9"]
        assert sub["skipped_unchanged"] == []


class TestJsManifestDirs:
    """#1839: pure predicate mapping changed files to npm gate dirs."""

    def test_root_package_json(self):
        assert dependabot_review._js_manifest_dirs(["package.json"]) == ["."]

    def test_subdir_lockfile(self):
        assert dependabot_review._js_manifest_dirs(
            ["dashboard/package-lock.json"]) == ["dashboard"]

    def test_dedup_and_sort(self):
        files = ["web/package.json", "web/package-lock.json",
                 "api/package.json", "README.md"]
        assert dependabot_review._js_manifest_dirs(files) == ["api", "web"]

    def test_node_modules_excluded(self):
        assert dependabot_review._js_manifest_dirs(
            ["web/node_modules/foo/package.json"]) == []

    def test_yarn_and_pnpm_locks_recognized(self):
        assert dependabot_review._js_manifest_dirs(
            ["a/yarn.lock", "b/pnpm-lock.yaml"]) == ["a", "b"]

    def test_unrelated_files_empty(self):
        assert dependabot_review._js_manifest_dirs(
            ["Dockerfile", ".github/workflows/ci.yml", "src/x.py"]) == []


class TestNpmTestScript:
    """#1839: what counts as a runnable npm test script."""

    def _write(self, tmp_path, obj):
        (tmp_path / "package.json").write_text(
            json.dumps(obj), encoding="utf-8")

    def test_missing_package_json(self, tmp_path):
        assert dependabot_review._npm_test_script(tmp_path) is None

    def test_no_scripts_section(self, tmp_path):
        self._write(tmp_path, {"name": "x"})
        assert dependabot_review._npm_test_script(tmp_path) is None

    def test_npm_init_placeholder_counts_as_none(self, tmp_path):
        self._write(tmp_path, {"scripts": {
            "test": 'echo "Error: no test specified" && exit 1'}})
        assert dependabot_review._npm_test_script(tmp_path) is None

    def test_blank_script_counts_as_none(self, tmp_path):
        self._write(tmp_path, {"scripts": {"test": "   "}})
        assert dependabot_review._npm_test_script(tmp_path) is None

    def test_real_script_returned(self, tmp_path):
        self._write(tmp_path, {"scripts": {"test": "vitest run"}})
        assert dependabot_review._npm_test_script(tmp_path) == "vitest run"

    def test_malformed_json_counts_as_none(self, tmp_path):
        (tmp_path / "package.json").write_text("{not json", encoding="utf-8")
        assert dependabot_review._npm_test_script(tmp_path) is None


class TestRunJsGate:
    """#1839: npm install + test per touched dir, node_modules cleanup."""

    def _pkg(self, d, script="run-my-tests", lock=True):
        d.mkdir(parents=True, exist_ok=True)
        (d / "package.json").write_text(
            json.dumps({"scripts": {"test": script}}), encoding="utf-8")
        if lock:
            (d / "package-lock.json").write_text("{}", encoding="utf-8")

    def _stub_run(self, monkeypatch, calls, test_exit=0, install_exit=0):
        def _fake(cmd, *args, **kwargs):
            calls.append({"cmd": list(cmd), "cwd": kwargs.get("cwd"),
                          "env": kwargs.get("env")})
            rc = test_exit if cmd[-1] == "test" else install_exit
            return subprocess.CompletedProcess(args=cmd, returncode=rc,
                                               stdout="", stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)

    def test_no_test_script_fails_gate(self, monkeypatch, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        calls: list = []
        self._stub_run(monkeypatch, calls)
        ok, desc = dependabot_review.run_js_gate(tmp_path, ["."])
        assert ok is False
        assert "no runnable npm test script" in desc
        assert calls == [], "no npm subprocess may run without a test script"

    def test_lockfile_uses_npm_ci_then_test(self, monkeypatch, tmp_path):
        self._pkg(tmp_path)
        calls: list = []
        self._stub_run(monkeypatch, calls)
        ok, desc = dependabot_review.run_js_gate(tmp_path, ["."])
        assert ok is True
        assert "npm test passed" in desc
        assert calls[0]["cmd"][1:] == ["ci"]
        assert calls[1]["cmd"][1:] == ["test"]

    def test_no_lockfile_falls_back_to_install_no_package_lock(
            self, monkeypatch, tmp_path):
        self._pkg(tmp_path, lock=False)
        calls: list = []
        self._stub_run(monkeypatch, calls)
        ok, _ = dependabot_review.run_js_gate(tmp_path, ["."])
        assert ok is True
        assert calls[0]["cmd"][1:] == ["install", "--no-package-lock"]

    def test_test_failure_fails_gate(self, monkeypatch, tmp_path):
        self._pkg(tmp_path)
        calls: list = []
        self._stub_run(monkeypatch, calls, test_exit=1)
        ok, desc = dependabot_review.run_js_gate(tmp_path, ["."])
        assert ok is False
        assert "npm test FAILED (exit 1)" in desc

    def test_install_failure_fails_gate_without_running_tests(
            self, monkeypatch, tmp_path):
        self._pkg(tmp_path)
        calls: list = []
        self._stub_run(monkeypatch, calls, install_exit=1)
        ok, desc = dependabot_review.run_js_gate(tmp_path, ["."])
        assert ok is False
        assert "npm install failed" in desc
        assert len(calls) == 1

    def test_subdir_runs_in_subdir(self, monkeypatch, tmp_path):
        self._pkg(tmp_path / "dashboard")
        calls: list = []
        self._stub_run(monkeypatch, calls)
        ok, desc = dependabot_review.run_js_gate(tmp_path, ["dashboard"])
        assert ok is True
        assert calls[0]["cwd"] == str(tmp_path / "dashboard")
        assert "'dashboard'" in desc

    def test_node_modules_removed_after_gate(self, monkeypatch, tmp_path):
        self._pkg(tmp_path)
        nm = tmp_path / "node_modules" / "leftover"
        nm.mkdir(parents=True)
        (nm / "file.js").write_text("x", encoding="utf-8")
        calls: list = []
        self._stub_run(monkeypatch, calls)
        dependabot_review.run_js_gate(tmp_path, ["."])
        assert not (tmp_path / "node_modules").exists(), (
            "node_modules must be removed -- git worktree remove (no "
            "--force) refuses on untracked files"
        )

    def test_node_modules_removed_even_on_failure(self, monkeypatch, tmp_path):
        self._pkg(tmp_path)
        (tmp_path / "node_modules").mkdir()
        calls: list = []
        self._stub_run(monkeypatch, calls, test_exit=1)
        dependabot_review.run_js_gate(tmp_path, ["."])
        assert not (tmp_path / "node_modules").exists()

    def test_env_strips_virtual_env(self, monkeypatch, tmp_path):
        """Compose with #1415: npm subprocesses get the cleaned env too."""
        monkeypatch.setenv("VIRTUAL_ENV", "C:/AZ/venv/should/not/leak")
        self._pkg(tmp_path)
        calls: list = []
        self._stub_run(monkeypatch, calls)
        dependabot_review.run_js_gate(tmp_path, ["."])
        assert calls, "gate must have invoked npm"
        assert all("VIRTUAL_ENV" not in c["env"] for c in calls)


class TestProcessPrJsFlow:
    """#1839: gate selection inside _process_pr_inside_worktree."""

    def _stub_green_path(self, monkeypatch):
        monkeypatch.setattr(dependabot_review, "checkout_pr_into_worktree",
                            lambda worktree, pr_number, repo: True)
        monkeypatch.setattr(dependabot_review, "inject_no_issue",
                            lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review, "wait_for_mergeable",
                            lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review, "squash_merge",
                            lambda pr, repo: True)
        monkeypatch.setattr(dependabot_review.time, "sleep", lambda s: None)

    def _pr(self):
        return dependabot_review.PRInfo(
            number=99, title="bump chalk", author_login="app/dependabot",
            body="", head_ref="dependabot/npm_and_yarn/chalk-6")

    def test_npm_only_pr_runs_js_gate_not_python(self, monkeypatch):
        self._stub_green_path(monkeypatch)
        monkeypatch.setattr(
            dependabot_review, "_pr_changed_files",
            lambda pr, repo: ["dashboard/package.json",
                              "dashboard/package-lock.json"])
        approvals: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "approve_pr",
            lambda pr, repo, gate_desc: approvals.append(gate_desc) or True)
        installs, tests, js = [], [], []
        monkeypatch.setattr(dependabot_review, "install_deps",
                            lambda wt: installs.append(wt) or True)
        monkeypatch.setattr(dependabot_review, "run_tests",
                            lambda wt: tests.append(wt) or 0)
        monkeypatch.setattr(
            dependabot_review, "run_js_gate",
            lambda wt, dirs: js.append(dirs) or
            (True, "npm test passed (exit 0) in 'dashboard'"))

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"))

        assert result == "merged"
        assert installs == [] and tests == []
        assert js == [["dashboard"]]
        assert approvals and "npm test passed" in approvals[0]

    def test_js_gate_failure_defers_with_reason(self, monkeypatch):
        self._stub_green_path(monkeypatch)
        monkeypatch.setattr(dependabot_review, "_pr_changed_files",
                            lambda pr, repo: ["package.json"])
        monkeypatch.setattr(
            dependabot_review, "run_js_gate",
            lambda wt, dirs: (False, "no runnable npm test script in '.' -- "
                              "not auto-merging unverified (#1839)"))
        reviews: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "review_comment_on_pr",
            lambda pr, repo, body: reviews.append(body) or True)
        monkeypatch.setattr(dependabot_review, "is_pr_branch_stale",
                            lambda pr, repo: False)
        approvals: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "approve_pr",
            lambda pr, repo, gate_desc: approvals.append(gate_desc) or True)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"))

        assert result == "deferred"
        assert approvals == []
        assert reviews and "no runnable npm test script" in reviews[0]

    def test_grouped_pr_runs_both_gates(self, monkeypatch):
        self._stub_green_path(monkeypatch)
        monkeypatch.setattr(
            dependabot_review, "_pr_changed_files",
            lambda pr, repo: ["poetry.lock", "web/package.json"])
        approvals: list[str] = []
        monkeypatch.setattr(
            dependabot_review, "approve_pr",
            lambda pr, repo, gate_desc: approvals.append(gate_desc) or True)
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv",
                            lambda wt: None)
        monkeypatch.setattr(dependabot_review, "install_deps",
                            lambda wt: True)
        monkeypatch.setattr(dependabot_review, "run_tests", lambda wt: 0)
        js: list = []
        monkeypatch.setattr(
            dependabot_review, "run_js_gate",
            lambda wt, dirs: js.append(dirs) or
            (True, "npm test passed (exit 0) in 'web'"))

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"))

        assert result == "merged"
        assert js == [["web"]]
        assert "pytest passed (exit 0)" in approvals[0]
        assert "npm test passed" in approvals[0]

    def test_python_failure_short_circuits_js_gate(self, monkeypatch):
        self._stub_green_path(monkeypatch)
        monkeypatch.setattr(
            dependabot_review, "_pr_changed_files",
            lambda pr, repo: ["poetry.lock", "web/package.json"])
        monkeypatch.setattr(dependabot_review, "evict_poetry_venv",
                            lambda wt: None)
        monkeypatch.setattr(dependabot_review, "install_deps",
                            lambda wt: True)
        monkeypatch.setattr(dependabot_review, "run_tests", lambda wt: 1)
        js: list = []
        monkeypatch.setattr(dependabot_review, "run_js_gate",
                            lambda wt, dirs: js.append(dirs) or (True, "x"))
        monkeypatch.setattr(dependabot_review, "review_comment_on_pr",
                            lambda pr, repo, body: True)
        monkeypatch.setattr(dependabot_review, "is_pr_branch_stale",
                            lambda pr, repo: False)

        result = dependabot_review._process_pr_inside_worktree(
            self._pr(), "owner/repo", Path("/tmp/wt"))

        assert result == "deferred"
        assert js == [], "js gate must not run when the Python gate failed"


class TestListFleetReposByOpenPrs:
    """#1839: fleet = repos with open dependabot PRs, intersected with the
    user's non-archived non-fork repos, sorted."""

    def test_intersection_sorted_archived_excluded(self, monkeypatch):
        def _fake(cmd, *args, **kwargs):
            if cmd[1] == "repo" and cmd[2] == "list":
                payload = [
                    {"name": "beta", "nameWithOwner": "o/beta",
                     "isArchived": False, "isFork": False},
                    {"name": "alpha", "nameWithOwner": "o/alpha",
                     "isArchived": False, "isFork": False},
                    {"name": "old", "nameWithOwner": "o/old",
                     "isArchived": True, "isFork": False},
                    {"name": "fork", "nameWithOwner": "o/fork",
                     "isArchived": False, "isFork": True},
                ]
            else:
                payload = [
                    {"repository": {"nameWithOwner": "o/beta"}},
                    {"repository": {"nameWithOwner": "o/alpha"}},
                    {"repository": {"nameWithOwner": "o/alpha"}},
                    {"repository": {"nameWithOwner": "o/old"}},
                    {"repository": {"nameWithOwner": "o/fork"}},
                ]
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=json.dumps(payload), stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)
        assert dependabot_review.list_fleet_repos("o") == ["o/alpha", "o/beta"]


class TestApprovePrGateDesc:
    """#1839: the approval body names the gate that actually ran."""

    def test_gate_desc_lands_in_review_body(self, monkeypatch):
        captured: dict = {}

        def _fake(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            return subprocess.CompletedProcess(args=cmd, returncode=0,
                                               stdout="", stderr="")
        monkeypatch.setattr(dependabot_review, "run", _fake)
        assert dependabot_review.approve_pr(
            5, "o/r", "npm test passed (exit 0) in '.'") is True
        body = captured["cmd"][captured["cmd"].index("--body") + 1]
        assert "gate: npm test passed (exit 0) in '.'" in body
        assert body.startswith(dependabot_review.REVIEW_BODY_PREFIX)


# vitest/jest and pytest benchmark tables emit these routinely; cp1252
# cannot encode any of them.
NON_ASCII_LINE = "  | ✓ src/x.test.ts (3 tests) │ ── 456ms"


class _Cp1252Stream:
    """stdout double whose encoding cannot represent non-ASCII -- the
    exact 2026-07-28 career-run condition (#1876)."""

    encoding = "cp1252"

    def __init__(self):
        self.written: list[str] = []

    def write(self, text: str) -> int:
        text.encode("cp1252")  # raises UnicodeEncodeError like the real one
        self.written.append(text)
        return len(text)

    def flush(self) -> None:
        pass


class TestForceUtf8Streams:
    """#1876: the tool must not depend on its launcher's env for
    encoding correctness."""

    def test_reconfigures_each_stream_to_utf8_replace(self):
        calls: list[dict] = []

        class _Stream:
            def reconfigure(self, **kw):
                calls.append(kw)

        dependabot_review._force_utf8_streams([_Stream(), _Stream()])
        assert len(calls) == 2
        assert all(c == {"encoding": "utf-8", "errors": "replace"}
                   for c in calls)

    def test_stream_without_reconfigure_does_not_raise(self):
        """A test double or already-wrapped stream must be tolerated --
        _Tee.write's fallback covers that case."""
        dependabot_review._force_utf8_streams([object()])

    def test_reconfigure_failure_is_swallowed(self):
        class _Stream:
            def reconfigure(self, **kw):
                raise ValueError("detached buffer")

        dependabot_review._force_utf8_streams([_Stream()])

    def test_reconfigured_stream_accepts_non_ascii(self):
        """End-to-end intent: after reconfigure, the write that crashed
        the career run succeeds."""
        import io
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with pytest.raises(UnicodeEncodeError):
            stream.write(NON_ASCII_LINE)
            stream.flush()
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        dependabot_review._force_utf8_streams([stream])
        stream.write(NON_ASCII_LINE)
        stream.flush()


class TestTeeSurvivesUndecodableTerminal:
    """#1876: a failed *print* must never abort the drain."""

    def test_write_does_not_raise_on_unicode_error(self, tmp_path):
        logfile = (tmp_path / "run.log").open("w", encoding="utf-8")
        tee = dependabot_review._Tee(_Cp1252Stream(), logfile)
        tee.write(NON_ASCII_LINE)  # must not raise
        logfile.close()

    def test_faithful_text_still_reaches_the_log(self, tmp_path):
        log_path = tmp_path / "run.log"
        logfile = log_path.open("w", encoding="utf-8")
        tee = dependabot_review._Tee(_Cp1252Stream(), logfile)
        tee.write(NON_ASCII_LINE)
        logfile.close()
        assert NON_ASCII_LINE in log_path.read_text(encoding="utf-8"), (
            "the run log is UTF-8 and must keep the exact text even when "
            "the terminal can only render a lossy version"
        )

    def test_terminal_gets_lossy_render_not_nothing(self, tmp_path):
        logfile = (tmp_path / "run.log").open("w", encoding="utf-8")
        stream = _Cp1252Stream()
        tee = dependabot_review._Tee(stream, logfile)
        tee.write(NON_ASCII_LINE)
        logfile.close()
        assert stream.written, "output must degrade, not disappear"
        assert "src/x.test.ts (3 tests)" in stream.written[0], (
            "the ASCII substance of the line must survive the fallback"
        )

    def test_ascii_write_is_unaffected(self, tmp_path):
        logfile = (tmp_path / "run.log").open("w", encoding="utf-8")
        stream = _Cp1252Stream()
        tee = dependabot_review._Tee(stream, logfile)
        assert tee.write("plain ascii line") == len("plain ascii line")
        logfile.close()
        assert stream.written == ["plain ascii line"]
