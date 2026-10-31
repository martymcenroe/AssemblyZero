"""Rebuilding an input from refs fails loudly (ADR 0236, #3585).

``restore_artifact`` searches the refs for a missing pipeline input. A
``git for-each-ref`` that failed returned no refs, and a ``git show`` that
failed for any reason read as "not on this ref", so a git error made a
preserved artifact read as "not restorable". A path outside the repo was a
tagged ``return False``. Now each git failure raises ``RestoreError`` with the
command, the return code and stderr, and a path outside the repo raises
``ValueError``. Only "this ref does not exist" and "this path is not on this
ref" stay quiet: those are the search's real answers.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import subprocess

import pytest

from assemblyzero.speedrun import restore


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _failing_run(monkeypatch, match: str, returncode: int = 128, stderr: str = "fatal: boom"):
    real = restore._run

    def fake(cmd, cwd=None, env=None):
        if match in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode, "", stderr)
        return real(cmd, cwd=cwd, env=env)

    monkeypatch.setattr(restore, "_run", fake)


def _restore_error():
    return restore.RestoreError


def test_46_a_failing_for_each_ref_for_leavings_raises(repo, monkeypatch, operator_alerts):
    _failing_run(monkeypatch, "graveyard/leavings-*")

    with pytest.raises(Exception) as excinfo:
        restore.graveyard_leavings_refs(repo)

    assert type(excinfo.value).__name__ == "RestoreError"
    assert "128" in str(excinfo.value) and "boom" in str(excinfo.value)


def test_83_a_failing_for_each_ref_for_lld_grafts_raises(repo, monkeypatch, operator_alerts):
    _failing_run(monkeypatch, "graveyard/7-lld-*")

    with pytest.raises(Exception) as excinfo:
        restore.graveyard_issue_lld_refs(repo, 7)

    assert type(excinfo.value).__name__ == "RestoreError"


def test_140_a_path_outside_the_repo_raises(repo, tmp_path, operator_alerts):
    with pytest.raises(ValueError) as excinfo:
        restore.restore_artifact(repo, 7, str(tmp_path / "elsewhere" / "LLD-007.md"))

    assert "outside" in str(excinfo.value)


def test_140_the_withdrawn_tag_is_gone():
    source = restore.__loader__.get_source(restore.__name__)
    assert "fail-open" not in source


def test_150_a_git_show_that_fails_for_another_reason_raises(repo, monkeypatch, operator_alerts):
    _failing_run(monkeypatch, "git show", stderr="fatal: unable to read tree (corrupt object)")

    with pytest.raises(Exception) as excinfo:
        restore.restore_artifact(repo, 7, str(repo / "docs" / "lld" / "active" / "LLD-007.md"))

    assert type(excinfo.value).__name__ == "RestoreError"
    assert "corrupt object" in str(excinfo.value)


def test_a_missing_ref_and_a_missing_path_are_the_quiet_not_restorable(repo, operator_alerts):
    """No `7-lld` branch exists, and HEAD does not hold the file: False."""
    target = repo / "docs" / "lld" / "active" / "LLD-007.md"

    assert restore.restore_artifact(repo, 7, str(target)) is False
    assert not target.exists()


def test_a_file_on_head_is_restored(repo, operator_alerts):
    (repo / "notes.md").write_text("kept\n", encoding="utf-8")
    _git(repo, "add", "notes.md")
    _git(repo, "commit", "-q", "-m", "notes")
    (repo / "notes.md").unlink()

    assert restore.restore_artifact(repo, 7, str(repo / "notes.md")) is True
    assert (repo / "notes.md").read_text(encoding="utf-8") == "kept\n"
