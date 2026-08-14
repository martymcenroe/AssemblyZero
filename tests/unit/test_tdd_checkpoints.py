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


def test_never_pushes(tmp_path):
    """#2339: checkpoints are local crash resilience and do not push.

    This test asserted the opposite until 2026-08-14. The operator's ruling
    reversed it on the evidence of run-issue7-192332, where the push could
    only ever fail: a stale `origin/issue-7` rejected the upstream push at
    worktree creation, so all four checkpoints failed with "no upstream
    branch" and each printed git's four-line advice into the run log.
    """
    wt = tmp_path / "wt"
    wt.mkdir()

    cmds: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds.append(cmd)
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        assert checkpoints.commit_checkpoint(wt, 123, "post-scaffold") is True

    pushes = [c for c in cmds if "push" in c]
    assert pushes == [], f"checkpoints must not push, got {pushes}"


def test_a_stale_remote_cannot_affect_a_checkpoint(tmp_path, capsys):
    """The #2339 case, with the network hostile in every way it was.

    Any push here would be rejected non-fast-forward and any upstream lookup
    would fail. The checkpoint must still commit, still return True, and
    still print no git advice, because it makes no network call at all.
    """
    wt = tmp_path / "wt"
    wt.mkdir()

    def fake_run(cmd, **kw):
        if "diff" in cmd and "--quiet" in cmd:
            return _mk_completed(returncode=1)
        if "push" in cmd:
            return _mk_completed(
                returncode=128,
                stderr=(
                    "! [rejected] issue-7 -> issue-7 (non-fast-forward)\n"
                    "fatal: The current branch issue-7 has no upstream branch.\n"
                    "To push the current branch and set the remote as upstream, use\n"
                    "    git push --set-upstream origin issue-7\n"
                ),
            )
        return _mk_completed(returncode=0)

    with patch.object(checkpoints.subprocess, "run", side_effect=fake_run):
        assert checkpoints.commit_checkpoint(wt, 7, "post-impl") is True

    out = capsys.readouterr().out
    assert "set-upstream" not in out
    assert "non-fast-forward" not in out
    assert "push" not in out


def test_the_worktree_is_not_given_an_upstream_at_creation(tmp_path):
    """The other half of #2339, and the line that actually failed first.

    #1780 added a `push -u origin <branch>` at worktree creation so that
    checkpoint pushes would work. With checkpoints local, nothing in the run
    needs an upstream before the pr stage sets one, and that push was the
    single rejection every later failure descended from.
    """
    import inspect

    from assemblyzero.workflows.orchestrator import stages

    source = inspect.getsource(stages)
    assert '"push", "-u", "origin", branch_name' not in source
    assert "could not push" not in source


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
