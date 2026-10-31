"""The file janitor fails loudly (ADR 0236, #3585).

The janitor preserves pipeline-authored untracked files on a pushed graveyard
branch and then clears them. A `git status` that failed read as "no untracked
files", or was passed off as one line of operator dirt; a preservation step
that failed went to the caller's log at no level, or to a no-op when no log
was passed; a ledger record that could not be written was ignored; and a file
that could not be removed was a problem entry nobody was told about.

Now a failed status alerts and raises, every preservation failure and every
file left behind alerts the operator, the default log is stderr, and a branch
the ledger cannot record alerts while the files it holds are still cleared.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.speedrun import leavings as lv
from assemblyzero.speedrun.preserved import ledger_path

LEAVING = "docs/lld/active/LLD-002.md"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with a bare origin and a gitignored data/, as the janitor's suite builds."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "--initial-branch=main", str(origin))
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    return root


def _drop(repo: Path, rel: str = LEAVING) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("drafted by the pipeline\n", encoding="utf-8")
    return path


def _failing_status(monkeypatch, code: int = 128, stderr: str = "fatal: index file corrupt"):
    real = lv._run

    def run(cmd, cwd=None, env=None):
        if "status" in cmd:
            return subprocess.CompletedProcess(cmd, code, "", stderr)
        return real(cmd, cwd=cwd, env=env)

    monkeypatch.setattr(lv, "_run", run)


# --- kept behaviour --------------------------------------------------------


def test_a_healthy_janitor_alerts_nobody(repo, operator_alerts):
    _drop(repo)

    result = lv.preserve_and_clear(repo, [LEAVING], log=lambda _m: None)

    assert result.problems == [] and not (repo / LEAVING).exists()
    assert operator_alerts == []


def test_349_pruning_stops_at_a_directory_that_still_holds_something(repo, operator_alerts):
    _drop(repo)
    other = _drop(repo, "docs/lld/active/LLD-003.md")

    lv.preserve_and_clear(repo, [LEAVING], log=lambda _m: None)

    assert other.exists() and other.parent.is_dir()
    assert operator_alerts == []


# --- reading the tree ------------------------------------------------------


def test_180_a_status_that_fails_alerts_and_raises(repo, operator_alerts, monkeypatch):
    _failing_status(monkeypatch)

    with pytest.raises(RuntimeError, match="index file corrupt"):
        lv.untracked_files(repo)

    assert len(operator_alerts) == 1
    assert "128" in operator_alerts[0]["cause"]


def test_213_a_status_that_fails_is_not_passed_off_as_dirt(repo, operator_alerts, monkeypatch):
    _failing_status(monkeypatch)

    with pytest.raises(RuntimeError, match="index file corrupt"):
        lv.classify_dirt(repo)

    assert len(operator_alerts) == 1


# --- preserving and clearing -------------------------------------------------


def test_247_with_no_log_a_failure_still_reaches_stderr(repo, operator_alerts, capsys):
    _git(repo, "remote", "remove", "origin")
    _drop(repo)

    lv.preserve_and_clear(repo, [LEAVING])

    assert "push failed" in capsys.readouterr().err


def test_263_a_preservation_step_that_fails_alerts_and_clears_nothing(repo, operator_alerts):
    _git(repo, "remote", "remove", "origin")
    leaving = _drop(repo)

    result = lv.preserve_and_clear(repo, [LEAVING], log=lambda _m: None)

    assert leaving.exists(), "a file is never removed unpreserved"
    assert len(result.problems) == 1
    assert len(operator_alerts) == 1
    assert "push" in operator_alerts[0]["cause"]
    assert "nothing is cleared" in operator_alerts[0]["consequence"]


def test_312_a_branch_the_ledger_cannot_record_alerts_and_the_files_still_clear(
    repo, operator_alerts
):
    (repo / "data").mkdir()
    (repo / "data" / "speedrun").write_text("not a directory\n", encoding="utf-8")
    _drop(repo)

    result = lv.preserve_and_clear(repo, [LEAVING], log=lambda _m: None)

    assert result.branch and not (repo / LEAVING).exists(), "the pushed branch holds them"
    assert len(operator_alerts) == 1
    assert str(ledger_path(repo)) in operator_alerts[0]["cause"]
    assert result.branch in operator_alerts[0]["what"]


def test_321_a_file_that_cannot_be_removed_alerts(repo, operator_alerts, monkeypatch):
    target = _drop(repo)
    real_unlink = Path.unlink

    def unlink(self, *args, **kwargs):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)

    result = lv.preserve_and_clear(repo, [LEAVING], log=lambda _m: None)

    assert target.exists() and len(result.problems) == 1
    assert len(operator_alerts) == 1
    assert LEAVING in operator_alerts[0]["what"]
    assert "Permission denied" in operator_alerts[0]["cause"]
