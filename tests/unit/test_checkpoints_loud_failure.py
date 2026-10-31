"""testing/checkpoints.py under standard 0034 (#3810).

A checkpoint commit and N5's measurement note used to be best-effort: every
git failure printed "(non-fatal)" to stdout and returned False or None, which
the callers read as "nothing to commit" or "no measurement". Each failure now
writes an ERROR line to stderr and raises ``CheckpointError`` naming the
worktree or commit and git's own stderr. The caller that can stop alerts: the
graph's checkpoint wrapper, the standalone finish's entry point, N5, and the
impl stage's entry point. Nothing here alerts itself, so one failure is one
alert.

Kept, and pinned below: no worktree named is a False no-op, nothing staged is
a False no-op, and a commit git says carries no note reads as None. Line
numbers in the test names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.testing import checkpoints


def _done(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "wt"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "base.txt")
    _git(root, "commit", "-qm", "base")
    return root


def _scripted(monkeypatch, answers: dict[str, subprocess.CompletedProcess | BaseException]):
    """Replace subprocess.run: the git subcommand names its answer."""
    seen: list[list[str]] = []

    def fake_run(cmd, **_kw):
        seen.append(list(cmd))
        sub = cmd[3]  # git -C <path> <sub>
        answer = answers.get(sub, _done())
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(checkpoints.subprocess, "run", fake_run)
    return seen


def _assert_checkpoint_error(raised) -> None:
    assert type(raised.value).__name__ == "CheckpointError"


# =============================================================================
# commit_checkpoint
# =============================================================================


class TestCommitCheckpoint:
    def test_89_a_worktree_that_is_not_a_directory_raises_naming_it(self, tmp_path, capsys):
        missing = tmp_path / "gone"

        with pytest.raises(RuntimeError, match="post-impl") as raised:
            checkpoints.commit_checkpoint(missing, 42, "post-impl")

        _assert_checkpoint_error(raised)
        assert str(missing) in str(raised.value)
        assert "ERROR" in capsys.readouterr().err

    def test_96_a_failed_git_add_raises_with_its_stderr(self, tmp_path, monkeypatch, capsys):
        wt = tmp_path / "wt"
        wt.mkdir()
        seen = _scripted(monkeypatch, {
            "add": _done(128, stderr="fatal: Unable to create '.git/index.lock': File exists."),
            "diff": _done(1),
        })

        with pytest.raises(RuntimeError, match="index.lock") as raised:
            checkpoints.commit_checkpoint(wt, 42, "post-scaffold")

        _assert_checkpoint_error(raised)
        assert "git add" in str(raised.value)
        assert not [c for c in seen if c[3] == "commit"], seen
        assert "ERROR" in capsys.readouterr().err

    def test_103_a_failed_diff_raises_rather_than_reading_as_staged(self, tmp_path, monkeypatch):
        wt = tmp_path / "wt"
        wt.mkdir()
        seen = _scripted(monkeypatch, {"diff": _done(128, stderr="fatal: index file corrupt")})

        with pytest.raises(RuntimeError, match="index file corrupt") as raised:
            checkpoints.commit_checkpoint(wt, 42, "post-green")

        _assert_checkpoint_error(raised)
        assert "exit 128" in str(raised.value)
        assert not [c for c in seen if c[3] == "commit"], seen

    def test_103_kept_exit_1_means_staged_and_commits(self, repo):
        (repo / "impl.py").write_text("x = 1\n", encoding="utf-8")

        assert checkpoints.commit_checkpoint(repo, 42, "post-impl") is True
        assert _git(repo, "log", "-1", "--format=%s") == "[CP:post-impl] issue #42: workflow checkpoint"

    def test_103_kept_nothing_staged_is_a_quiet_false(self, repo, capsys):
        """Kept: a clean tree has nothing to checkpoint, which is an answer."""
        assert checkpoints.commit_checkpoint(repo, 42, "post-impl") is False
        assert capsys.readouterr().err == ""

    def test_115_a_failed_commit_raises_and_is_an_error_on_stderr(self, tmp_path, monkeypatch, capsys):
        wt = tmp_path / "wt"
        wt.mkdir()
        _scripted(monkeypatch, {
            "diff": _done(1),
            "commit": _done(1, stderr="pre-commit hook refused the commit"),
        })

        with pytest.raises(RuntimeError, match="hook refused") as raised:
            checkpoints.commit_checkpoint(wt, 42, "post-impl")

        _assert_checkpoint_error(raised)
        assert str(wt) in str(raised.value)
        captured = capsys.readouterr()
        assert "ERROR [CP:post-impl]" in captured.err
        assert "non-fatal" not in captured.out + captured.err

    def test_115_a_real_commit_failure_raises(self, repo):
        """Real git: a commit refused by a hook is a failure, not a no-op."""
        hooks = repo / "test-hooks"
        hooks.mkdir()
        _git(repo, "config", "core.hooksPath", str(hooks))
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\necho refused by the test hook >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        (repo / "impl.py").write_text("x = 1\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="refused by the test hook"):
            checkpoints.commit_checkpoint(repo, 42, "post-impl")

    def test_125_a_git_timeout_raises(self, tmp_path, monkeypatch, capsys):
        wt = tmp_path / "wt"
        wt.mkdir()
        _scripted(monkeypatch, {"add": subprocess.TimeoutExpired(cmd=["git"], timeout=30)})

        with pytest.raises(RuntimeError, match="TimeoutExpired") as raised:
            checkpoints.commit_checkpoint(wt, 42, "post-scaffold")

        _assert_checkpoint_error(raised)
        assert isinstance(raised.value.__cause__, subprocess.TimeoutExpired)
        assert "ERROR" in capsys.readouterr().err

    def test_125_git_that_cannot_run_raises(self, tmp_path, monkeypatch):
        wt = tmp_path / "wt"
        wt.mkdir()
        _scripted(monkeypatch, {"add": FileNotFoundError(2, "No such file or directory", "git")})

        with pytest.raises(RuntimeError, match="FileNotFoundError") as raised:
            checkpoints.commit_checkpoint(wt, 42, "post-scaffold")

        _assert_checkpoint_error(raised)

    def test_kept_no_worktree_named_is_a_quiet_false(self, capsys):
        """Kept: the caller named no worktree, so there is nothing to commit;
        the docstring says so."""
        assert checkpoints.commit_checkpoint(None, 42, "post-impl") is False
        assert capsys.readouterr().err == ""
        assert "None" in inspect.getdoc(checkpoints.commit_checkpoint)

    def test_nothing_here_alerts_itself(self, tmp_path, operator_alerts):
        """The caller that can stop alerts, so one failure is one alert."""
        with pytest.raises(RuntimeError):
            checkpoints.commit_checkpoint(tmp_path / "gone", 42, "post-impl")
        assert operator_alerts == []


# =============================================================================
# record_measurement
# =============================================================================


class TestRecordMeasurement:
    def test_193_a_note_git_cannot_run_raises(self, repo, monkeypatch, capsys):
        _scripted(monkeypatch, {"notes": OSError("git vanished")})

        with pytest.raises(RuntimeError, match="git vanished") as raised:
            checkpoints.record_measurement(repo, 44, 47, 91.0)

        _assert_checkpoint_error(raised)
        assert str(repo) in str(raised.value)
        assert "ERROR [N5]" in capsys.readouterr().err

    def test_194_the_fail_open_tag_is_gone(self):
        assert "fail-open:" not in inspect.getsource(checkpoints.record_measurement)

    def test_200_a_failed_notes_add_raises_with_its_stderr(self, repo, monkeypatch, capsys):
        _scripted(monkeypatch, {"notes": _done(128, stderr="fatal: refs/notes/az-measure is locked")})

        with pytest.raises(RuntimeError, match="is locked") as raised:
            checkpoints.record_measurement(repo, 44, 47, 91.0)

        _assert_checkpoint_error(raised)
        captured = capsys.readouterr()
        assert "ERROR [N5]" in captured.err
        assert "non-fatal" not in captured.out + captured.err

    def test_200_a_worktree_git_cannot_read_raises(self, tmp_path):
        """Real git: a directory that is no repository has no HEAD to note."""
        plain = tmp_path / "plain"
        plain.mkdir()

        with pytest.raises(RuntimeError, match="git notes"):
            checkpoints.record_measurement(plain, 1, 1, 100.0)

    def test_kept_a_recorded_measurement_reads_back(self, repo):
        assert checkpoints.record_measurement(repo, 44, 47, 91.0) is True
        sha = _git(repo, "rev-parse", "HEAD")
        assert checkpoints.read_measurement(repo, sha) == checkpoints.Measurement(44, 47, 91.0)


# =============================================================================
# read_measurement
# =============================================================================


class TestReadMeasurement:
    def test_222_notes_git_cannot_run_raises(self, repo, monkeypatch, capsys):
        _scripted(monkeypatch, {"notes": subprocess.TimeoutExpired(cmd=["git"], timeout=30)})

        with pytest.raises(RuntimeError, match="TimeoutExpired") as raised:
            checkpoints.read_measurement(repo, "a7a387e")

        _assert_checkpoint_error(raised)
        assert "a7a387e" in str(raised.value)
        assert "ERROR" in capsys.readouterr().err

    def test_223_the_first_fail_open_tag_is_gone(self):
        source = inspect.getsource(checkpoints.read_measurement)
        assert "fail-open:" not in source

    def test_229_a_failed_notes_show_raises(self, tmp_path):
        """Real git: no repository at all is not "no note"."""
        plain = tmp_path / "plain"
        plain.mkdir()

        with pytest.raises(RuntimeError, match="exit 128") as raised:
            checkpoints.read_measurement(plain, "a7a387e")

        _assert_checkpoint_error(raised)
        assert "a7a387e" in str(raised.value)

    def test_229_an_unknown_commit_raises(self, repo):
        with pytest.raises(RuntimeError, match="deadbeef"):
            checkpoints.read_measurement(repo, "deadbeef")

    def test_229_kept_a_commit_with_no_note_is_none(self, repo, capsys):
        """Kept: git's own "no note found" (exit 1) is the answer "unmeasured",
        and the resume then takes the newest attempt (#2845)."""
        sha = _git(repo, "rev-parse", "HEAD")

        assert checkpoints.read_measurement(repo, sha) is None
        assert capsys.readouterr().err == ""

    def test_232_a_corrupt_note_raises_naming_commit_and_text(self, repo, capsys):
        sha = _git(repo, "rev-parse", "HEAD")
        _git(repo, "notes", f"--ref={checkpoints.MEASURE_NOTES_REF}", "add", "-f", "-m",
             "not a measurement", sha)

        with pytest.raises(RuntimeError, match="not a measurement") as raised:
            checkpoints.read_measurement(repo, sha)

        _assert_checkpoint_error(raised)
        assert sha in str(raised.value)
        assert "ERROR" in capsys.readouterr().err

    def test_232_a_note_missing_a_field_raises(self, repo):
        sha = _git(repo, "rev-parse", "HEAD")
        _git(repo, "notes", f"--ref={checkpoints.MEASURE_NOTES_REF}", "add", "-f", "-m",
             "passed=44 total=47", sha)

        with pytest.raises(RuntimeError, match="coverage"):
            checkpoints.read_measurement(repo, sha)

    def test_238_numbers_that_do_not_convert_raise_naming_the_commit(self, repo):
        sha = _git(repo, "rev-parse", "HEAD")
        _git(repo, "notes", f"--ref={checkpoints.MEASURE_NOTES_REF}", "add", "-f", "-m",
             "passed=forty total=47 coverage=91.0", sha)

        with pytest.raises(RuntimeError, match="forty") as raised:
            checkpoints.read_measurement(repo, sha)

        _assert_checkpoint_error(raised)
        assert sha in str(raised.value)
        assert isinstance(raised.value.__cause__, ValueError)

    def test_239_the_second_fail_open_tag_is_gone(self):
        assert "fail-open:" not in inspect.getsource(checkpoints)

    def test_kept_no_repo_or_commit_named_is_none(self):
        """Kept: nothing was asked about; the docstring says so."""
        assert checkpoints.read_measurement("", "a7a387e") is None
        assert checkpoints.read_measurement("/somewhere", "") is None


# =============================================================================
# The callers that stop: N5, for a note it cannot write
# =============================================================================


class TestN5HaltsOnANoteItCannotWrite:
    @pytest.fixture
    def verify_phases(self, monkeypatch):
        from assemblyzero.workflows.testing.nodes import verify_phases

        # The unit conftest stubs the name N5 calls through; this test is
        # about the real one.
        monkeypatch.setattr(verify_phases, "record_measurement", checkpoints.record_measurement)
        return verify_phases

    def test_a_note_git_cannot_write_is_n5s_halt(self, verify_phases, tmp_path, capsys):
        plain = tmp_path / "plain"
        plain.mkdir()

        halt = verify_phases._note_measurement(plain, 44, 47, 91.0)

        assert halt is not None
        assert halt["error_message"].startswith("[N5] the measurement (44 passing of 47")
        assert "git notes add" in halt["error_message"]
        assert "ERROR [N5]" in capsys.readouterr().err

    def test_the_halt_routes_to_halt(self, verify_phases, tmp_path):
        from assemblyzero.workflows.testing.graph import route_after_green

        plain = tmp_path / "plain"
        plain.mkdir()

        halt = verify_phases._note_measurement(plain, 1, 1, 100.0)

        assert route_after_green(halt) == "HALT"

    def test_a_written_note_is_no_halt(self, verify_phases, repo):
        assert verify_phases._note_measurement(repo, 44, 47, 91.0) is None
        sha = _git(repo, "rev-parse", "HEAD")
        assert checkpoints.read_measurement(repo, sha) == checkpoints.Measurement(44, 47, 91.0)

    def test_the_halt_site_is_registered(self):
        from assemblyzero.core.gate_registry import GATE_REGISTRY

        key = ("assemblyzero/workflows/testing/nodes/verify_phases.py::"
               "_note_measurement::return::0")
        assert [g.key for g in GATE_REGISTRY if key in g.sites] == ["impl.measurement_not_noted"]
