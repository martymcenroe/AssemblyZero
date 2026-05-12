"""Tests for tools/dependabot_review.py cleanup behavior (Issues #1107, #1116)."""
import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch

# Load the tools/ script as a module without polluting sys.path.
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_spec = importlib.util.spec_from_file_location(
    "dependabot_review", TOOLS_DIR / "dependabot_review.py"
)
dependabot_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dependabot_review)


def _mk_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---- Bug 1: cleanup_worktree must use `branch -d` (safe), never `branch -D` ----

def test_cleanup_worktree_uses_safe_branch_d_not_capital_D(tmp_path):
    main_repo = tmp_path / "repo"
    worktree = tmp_path / "repo-dependabot-756"
    (worktree / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
    (worktree / "pyproject.toml").write_text("")  # so evict_poetry_venv runs

    calls: list[list[str]] = []
    def fake_run(cmd, cwd=None, timeout=None):
        calls.append(cmd)
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        dependabot_review.cleanup_worktree(main_repo, worktree, "dependabot-audit-756")

    # Find every git branch ... call and assert they all use -d, never -D.
    branch_calls = [c for c in calls if len(c) >= 4 and c[0] == "git" and "branch" in c]
    assert branch_calls, "expected at least one git branch call"
    for c in branch_calls:
        assert "-d" in c, f"expected -d (lowercase) in {c}"
        assert "-D" not in c, f"BANNED: -D found in {c}"


def test_cleanup_worktree_call_order_evict_remove_branch(tmp_path):
    main_repo = tmp_path / "repo"
    worktree = tmp_path / "repo-dependabot-756"
    worktree.mkdir(parents=True)
    (worktree / "pyproject.toml").write_text("")

    calls: list[list[str]] = []
    def fake_run(cmd, cwd=None, timeout=None):
        calls.append(cmd)
        return _mk_completed()

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        dependabot_review.cleanup_worktree(main_repo, worktree, "dependabot-audit-756")

    # poetry env remove --all  ->  worktree remove  ->  branch -d
    cmd_summaries = [" ".join(c) for c in calls]
    assert any("poetry env remove" in s for s in cmd_summaries), cmd_summaries
    assert any("worktree remove" in s for s in cmd_summaries), cmd_summaries
    assert any("branch -d" in s for s in cmd_summaries), cmd_summaries


# ---- Bug 2: checkout_pr_into_worktree must pass --detach ----

def test_checkout_pr_into_worktree_uses_detach_flag(tmp_path):
    worktree = tmp_path / "wt"
    worktree.mkdir()

    captured: list[list[str]] = []
    def fake_run(cmd, cwd=None, timeout=None):
        captured.append(cmd)
        return _mk_completed(returncode=0)

    with patch.object(dependabot_review, "run", side_effect=fake_run):
        ok = dependabot_review.checkout_pr_into_worktree(worktree, 1234, "owner/repo")

    assert ok is True
    assert len(captured) == 1
    cmd = captured[0]
    assert cmd[0:3] == ["gh", "pr", "checkout"]
    assert "--detach" in cmd, f"--detach missing from {cmd} -- bug #1107 regression"
    assert "1234" in cmd
    assert "owner/repo" in cmd


# ---- #1116: ALL deferred/errored exit paths must call cleanup_worktree.
# No forensic retention. The PR + Actions output is the forensic record.

def test_gc_function_removed_no_forensic_retention():
    """Regression guard: the #1107 GC function and constant must NOT exist.
    #1116 removed them after user feedback that the 14-day retention window
    was unacceptable."""
    assert not hasattr(dependabot_review, "gc_stale_forensic_worktrees"), \
        "gc_stale_forensic_worktrees was removed in #1116 -- no forensic retention"
    assert not hasattr(dependabot_review, "FORENSIC_WORKTREE_AGE_DAYS"), \
        "FORENSIC_WORKTREE_AGE_DAYS was removed in #1116 -- no forensic retention"


def test_deferred_install_fail_path_calls_cleanup_worktree(tmp_path):
    """When poetry install fails, the worktree must be removed before
    returning 'deferred'. #1116."""
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    pr = dependabot_review.PRInfo(
        number=42, title="bump foo", author_login="dependabot[bot]",
        body="", head_ref="dependabot/pip/foo",
    )

    cleanup_called: list[tuple[Path, Path, str]] = []

    def fake_cleanup(main_repo_arg, worktree_arg, branch_arg):
        cleanup_called.append((main_repo_arg, worktree_arg, branch_arg))

    with patch.object(dependabot_review, "verify_author", return_value=True), \
         patch.object(dependabot_review, "create_audit_worktree",
                      return_value=(tmp_path / "repo-dependabot-42", "dependabot-audit-42")), \
         patch.object(dependabot_review, "checkout_pr_into_worktree", return_value=True), \
         patch.object(dependabot_review, "evict_poetry_venv"), \
         patch.object(dependabot_review, "install_deps", return_value=False), \
         patch.object(dependabot_review, "review_comment_on_pr"), \
         patch.object(dependabot_review, "cleanup_worktree", side_effect=fake_cleanup):
        status = dependabot_review.process_pr(pr, "owner/repo", main_repo)

    assert status == "deferred"
    assert len(cleanup_called) == 1, \
        f"cleanup_worktree must be called exactly once on install-fail path, got {len(cleanup_called)}"


def test_deferred_test_fail_path_calls_cleanup_worktree(tmp_path):
    """When pytest exits non-zero, the worktree must be removed before
    returning 'deferred'. #1116."""
    main_repo = tmp_path / "repo"
    main_repo.mkdir()
    pr = dependabot_review.PRInfo(
        number=43, title="bump foo", author_login="dependabot[bot]",
        body="", head_ref="dependabot/pip/foo",
    )

    cleanup_called: list[tuple[Path, Path, str]] = []

    def fake_cleanup(main_repo_arg, worktree_arg, branch_arg):
        cleanup_called.append((main_repo_arg, worktree_arg, branch_arg))

    with patch.object(dependabot_review, "verify_author", return_value=True), \
         patch.object(dependabot_review, "create_audit_worktree",
                      return_value=(tmp_path / "repo-dependabot-43", "dependabot-audit-43")), \
         patch.object(dependabot_review, "checkout_pr_into_worktree", return_value=True), \
         patch.object(dependabot_review, "evict_poetry_venv"), \
         patch.object(dependabot_review, "install_deps", return_value=True), \
         patch.object(dependabot_review, "run_tests", return_value=1), \
         patch.object(dependabot_review, "count_packages", return_value=1), \
         patch.object(dependabot_review, "review_comment_on_pr"), \
         patch.object(dependabot_review, "is_pr_branch_stale", return_value=False), \
         patch.object(dependabot_review, "cleanup_worktree", side_effect=fake_cleanup):
        status = dependabot_review.process_pr(pr, "owner/repo", main_repo)

    assert status == "deferred"
    assert len(cleanup_called) == 1, \
        f"cleanup_worktree must be called exactly once on test-fail path, got {len(cleanup_called)}"


# ---- #1133: cleanup contract hardening ----


class TestCleanupWorktreeReturnsBool:
    """#1133: cleanup_worktree now returns True on success, False on
    failure (previously returned None and discarded exit codes silently)."""

    def test_returns_true_when_all_subprocesses_succeed(self, tmp_path):
        main_repo = tmp_path / "repo"
        worktree = tmp_path / "repo-dependabot-42"
        with patch.object(dependabot_review, "run", return_value=_mk_completed(0)):
            result = dependabot_review.cleanup_worktree(
                main_repo, worktree, "dependabot-audit-42",
            )
        assert result is True

    def test_returns_false_when_worktree_remove_fails(self, tmp_path, capsys):
        """The original #1133 bug: `git worktree remove` returns non-zero
        on dirty worktrees, but the old code discarded the exit code."""
        main_repo = tmp_path / "repo"
        worktree = tmp_path / "repo-dependabot-42"

        def fake_run(cmd, cwd=None, timeout=None):
            joined = " ".join(cmd)
            if "worktree remove" in joined:
                return _mk_completed(1, stderr="fatal: 'foo' contains modified or untracked files")
            return _mk_completed(0)

        with patch.object(dependabot_review, "run", side_effect=fake_run):
            result = dependabot_review.cleanup_worktree(
                main_repo, worktree, "dependabot-audit-42",
            )
        assert result is False
        # Loud diagnostic must hit stderr
        err = capsys.readouterr().err
        assert "CLEANUP FAILURE" in err
        assert "worktree remove" in err
        assert "modified or untracked" in err

    def test_returns_false_when_branch_delete_fails(self, tmp_path, capsys):
        main_repo = tmp_path / "repo"
        worktree = tmp_path / "repo-dependabot-42"

        def fake_run(cmd, cwd=None, timeout=None):
            if "branch" in cmd and "-d" in cmd:
                return _mk_completed(1, stderr="error: branch 'dependabot-audit-42' is not fully merged")
            return _mk_completed(0)

        with patch.object(dependabot_review, "run", side_effect=fake_run):
            result = dependabot_review.cleanup_worktree(
                main_repo, worktree, "dependabot-audit-42",
            )
        assert result is False
        err = capsys.readouterr().err
        assert "CLEANUP FAILURE" in err
        assert "branch -d" in err

    def test_branch_delete_failure_silent_when_worktree_remove_already_failed(
        self, tmp_path, capsys,
    ):
        """When worktree remove fails, branch -d will likely also fail (the
        branch is still attached to the leaked worktree). Avoid duplicate
        CLEANUP FAILURE noise -- the worktree-remove failure is the root cause.
        """
        main_repo = tmp_path / "repo"
        worktree = tmp_path / "repo-dependabot-42"

        with patch.object(dependabot_review, "run",
                          return_value=_mk_completed(1, stderr="some failure")):
            dependabot_review.cleanup_worktree(
                main_repo, worktree, "dependabot-audit-42",
            )
        err = capsys.readouterr().err
        # Exactly ONE "CLEANUP FAILURE" header -- the worktree one.
        # branch -d failure does not duplicate the message.
        assert err.count("CLEANUP FAILURE") == 1


class TestProcessPrTryFinallyContract:
    """#1133: process_pr's cleanup_worktree call lives in `finally`, so it
    runs on every exit path including exceptions raised mid-flight."""

    def test_cleanup_called_when_inner_pipeline_raises(self, tmp_path):
        """Pre-#1133 bug: if anything between worktree creation and a return
        statement raised (KeyboardInterrupt, network error, subprocess timeout),
        cleanup was skipped and the worktree leaked."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        pr = dependabot_review.PRInfo(
            number=99, title="bump foo", author_login="dependabot[bot]",
            body="", head_ref="dependabot/pip/foo",
        )

        cleanup_calls: list[tuple] = []

        def boom(*args, **kwargs):
            raise RuntimeError("simulated mid-flight crash")

        def fake_cleanup(main_repo_arg, worktree_arg, branch_arg):
            cleanup_calls.append((main_repo_arg, worktree_arg, branch_arg))
            return True

        with patch.object(dependabot_review, "verify_author", return_value=True), \
             patch.object(dependabot_review, "create_audit_worktree",
                          return_value=(tmp_path / "repo-dependabot-99",
                                        "dependabot-audit-99")), \
             patch.object(dependabot_review, "checkout_pr_into_worktree",
                          side_effect=boom), \
             patch.object(dependabot_review, "cleanup_worktree",
                          side_effect=fake_cleanup):
            # Exception propagates -- but cleanup MUST run via finally
            try:
                dependabot_review.process_pr(pr, "owner/repo", main_repo)
            except RuntimeError:
                pass

        assert len(cleanup_calls) == 1, (
            "cleanup_worktree MUST run via finally even when inner pipeline "
            "raises -- pre-#1133 design only covered explicit return paths"
        )

    def test_cleanup_warning_emitted_when_cleanup_returns_false(self, tmp_path, capsys):
        """If cleanup_worktree returns False (failure), process_pr's finally
        block emits a WARNING about leftover state."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        pr = dependabot_review.PRInfo(
            number=77, title="bump foo", author_login="dependabot[bot]",
            body="", head_ref="dependabot/pip/foo",
        )

        with patch.object(dependabot_review, "verify_author", return_value=True), \
             patch.object(dependabot_review, "create_audit_worktree",
                          return_value=(tmp_path / "repo-dependabot-77",
                                        "dependabot-audit-77")), \
             patch.object(dependabot_review, "checkout_pr_into_worktree", return_value=False), \
             patch.object(dependabot_review, "cleanup_worktree", return_value=False):
            status = dependabot_review.process_pr(pr, "owner/repo", main_repo)

        assert status == "errored"  # inner pipeline returned errored
        err = capsys.readouterr().err
        assert "WARNING: leftover state for PR #77" in err
        assert "Manual cleanup required" in err

    def test_cleanup_no_warning_when_cleanup_returns_true(self, tmp_path, capsys):
        """Conversely: clean cleanup runs silently (no warning noise)."""
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        pr = dependabot_review.PRInfo(
            number=78, title="bump foo", author_login="dependabot[bot]",
            body="", head_ref="dependabot/pip/foo",
        )

        with patch.object(dependabot_review, "verify_author", return_value=True), \
             patch.object(dependabot_review, "create_audit_worktree",
                          return_value=(tmp_path / "repo-dependabot-78",
                                        "dependabot-audit-78")), \
             patch.object(dependabot_review, "checkout_pr_into_worktree", return_value=False), \
             patch.object(dependabot_review, "cleanup_worktree", return_value=True):
            dependabot_review.process_pr(pr, "owner/repo", main_repo)

        err = capsys.readouterr().err
        assert "WARNING" not in err


class TestCheckForOrphanWorktrees:
    """#1133: startup canary that enumerates pre-existing dependabot worktrees."""

    def test_returns_empty_when_no_orphans(self, tmp_path):
        main_repo = tmp_path / "AssemblyZero"
        porcelain = (
            "worktree /c/Users/foo/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
        )
        with patch.object(dependabot_review, "run",
                          return_value=_mk_completed(0, stdout=porcelain)):
            orphans = dependabot_review.check_for_orphan_worktrees(main_repo)
        assert orphans == []

    def test_returns_orphan_paths(self, tmp_path):
        main_repo = tmp_path / "AssemblyZero"
        porcelain = (
            "worktree /c/Users/foo/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /c/Users/foo/Projects/AssemblyZero-dependabot-1095\n"
            "HEAD def456\n"
            "detached\n"
            "\n"
            "worktree /c/Users/foo/Projects/AssemblyZero-dependabot-1097\n"
            "HEAD ghi789\n"
            "detached\n"
            "\n"
        )
        with patch.object(dependabot_review, "run",
                          return_value=_mk_completed(0, stdout=porcelain)):
            orphans = dependabot_review.check_for_orphan_worktrees(main_repo)
        assert len(orphans) == 2
        assert any("dependabot-1095" in o for o in orphans)
        assert any("dependabot-1097" in o for o in orphans)

    def test_ignores_non_dependabot_worktrees(self, tmp_path):
        """Other feature-branch worktrees (e.g., AssemblyZero-1135-foo) are
        NOT orphan dependabot worktrees and must not be flagged."""
        main_repo = tmp_path / "AssemblyZero"
        porcelain = (
            "worktree /c/Users/foo/Projects/AssemblyZero\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /c/Users/foo/Projects/AssemblyZero-1135-bootstrap\n"
            "HEAD def456\n"
            "branch refs/heads/1135-bootstrap\n"
            "\n"
        )
        with patch.object(dependabot_review, "run",
                          return_value=_mk_completed(0, stdout=porcelain)):
            orphans = dependabot_review.check_for_orphan_worktrees(main_repo)
        assert orphans == []

    def test_returns_empty_on_subprocess_error(self, tmp_path):
        """Diagnostic must not block the script: if `git worktree list` itself
        fails, return [] so the operator's run can proceed."""
        main_repo = tmp_path / "AssemblyZero"
        with patch.object(dependabot_review, "run",
                          return_value=_mk_completed(128, stderr="not a git repo")):
            orphans = dependabot_review.check_for_orphan_worktrees(main_repo)
        assert orphans == []
