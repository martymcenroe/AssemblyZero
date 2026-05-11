"""Tests for the TDD workflow checkpoint helper (Issue #689)."""
import subprocess
from unittest.mock import patch

from assemblyzero.workflows.testing import checkpoints


def _mk_completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---- commit_checkpoint -- best-effort guards ----

def test_returns_false_when_worktree_is_none():
    assert checkpoints.commit_checkpoint(None, 123, "post-scaffold") is False


def test_returns_false_when_worktree_path_is_not_directory(tmp_path):
    nonexistent = tmp_path / "nope"
    assert checkpoints.commit_checkpoint(nonexistent, 123, "post-scaffold") is False


def test_returns_false_when_nothing_to_commit(tmp_path):
    """If `git diff --cached --quiet` returns 0, no commit is created (idempotent)."""
    wt = tmp_path / "wt"
    wt.mkdir()

    def fake_run(cmd, **kw):
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=0)  # nothing staged
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        assert checkpoints.commit_checkpoint(wt, 123, "post-scaffold") is False


def test_creates_commit_when_diff_has_staged_changes(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()

    cmds: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)  # diff non-empty -> 1
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        assert checkpoints.commit_checkpoint(wt, 123, "post-scaffold") is True

    # Verify commit message contains [CP:post-scaffold] and issue #123
    commit_calls = [c for c in cmds if "commit" in c]
    assert any("[CP:post-scaffold]" in arg for c in commit_calls for arg in c), commit_calls
    assert any("#123" in arg for c in commit_calls for arg in c), commit_calls


def test_pushes_after_successful_commit(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()

    cmds: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        checkpoints.commit_checkpoint(wt, 123, "post-scaffold")

    pushes = [c for c in cmds if "push" in c]
    assert len(pushes) == 1, f"expected exactly one push, got {pushes}"


def test_returns_true_even_when_push_fails(tmp_path):
    """commit succeeded -> True. Push failure is logged but not propagated."""
    wt = tmp_path / "wt"
    wt.mkdir()

    def fake_run(cmd, **kw):
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        if "push" in cmd:
            return _mk_completed(returncode=128, stderr="fatal: could not resolve host")
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        assert checkpoints.commit_checkpoint(wt, 123, "post-scaffold") is True


def test_returns_false_when_commit_itself_fails(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()

    def fake_run(cmd, **kw):
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        if "commit" in cmd:
            return _mk_completed(returncode=128, stderr="fatal: not a git repo")
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        assert checkpoints.commit_checkpoint(wt, 123, "post-scaffold") is False


def test_omits_issue_reference_when_issue_number_is_none(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()

    cmds: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        checkpoints.commit_checkpoint(wt, None, "post-scaffold")

    commit_calls = [c for c in cmds if "commit" in c]
    # When issue is None, the message should NOT contain "issue #"
    for c in commit_calls:
        for arg in c:
            assert "issue #" not in arg, f"message should not reference issue when None: {arg}"


def test_excludes_workflow_internal_dirs_from_staging(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()

    cmds: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        checkpoints.commit_checkpoint(wt, 123, "post-scaffold")

    add_calls = [c for c in cmds if "add" in c]
    assert add_calls, f"expected at least one git add call, got {cmds}"
    # Each add call should include the exclude pathspecs for workflow-internal dirs
    add_args = " ".join(add_calls[0])
    assert ":!.assemblyzero" in add_args, f"exclude missing in {add_args}"
    assert ":!data/lineage" in add_args, f"exclude missing in {add_args}"


def test_timeout_handled_as_non_fatal(tmp_path):
    """A subprocess timeout must not propagate -- the workflow node would
    otherwise fail on a transient git issue."""
    wt = tmp_path / "wt"
    wt.mkdir()

    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        # Should not raise
        result = checkpoints.commit_checkpoint(wt, 123, "post-scaffold")
    assert result is False


# ---- _run wrapper has encoding defaults from #837 ----

def test_underscore_run_uses_utf8_encoding_with_replace(tmp_path):
    """The _run helper inherits the #837 defaults so any UTF-8 in git output
    doesn't crash the checkpoint helper itself."""
    captured_kw: list[dict] = []

    def fake_run(cmd, **kw):
        captured_kw.append(kw)
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        checkpoints._run(["git", "--version"], timeout=10)

    assert captured_kw[0].get("encoding") == "utf-8"
    assert captured_kw[0].get("errors") == "replace"
