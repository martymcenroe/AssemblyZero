"""The requirements workflow's audit helpers under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/audit.py``. A repo structure that cannot
be read raises instead of handing the drafter a placeholder; a lineage move
that cannot happen alerts and raises; a context file the operator named and
the workflow cannot use raises; an approval cache that cannot be read alerts
and raises before anything can overwrite it; a review row that cannot be
embedded raises. What stays quiet is pinned: an empty repo, no context files,
a directory outside any git tree, a cache never written.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements import audit
from assemblyzero.workflows.requirements.git_operations import GitOperationError

LOGGER = "assemblyzero.workflows.requirements.audit"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _refuse_iterdir(monkeypatch, target: Path) -> None:
    real = Path.iterdir

    def iterdir(self):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "iterdir", iterdir)


def _errors(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


class TestRepoStructure:
    def test_133_a_repo_that_does_not_exist_raises(self, tmp_path):
        missing = tmp_path / "nope"
        with pytest.raises(FileNotFoundError) as raised:
            audit.get_repo_structure(missing)
        assert str(missing) in str(raised.value)

    def test_150_a_subdirectory_that_cannot_be_listed_raises(
        self, tmp_path, monkeypatch, caplog
    ):
        sub = tmp_path / "src" / "pkg"
        sub.mkdir(parents=True)
        _refuse_iterdir(monkeypatch, sub)

        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(PermissionError):
            audit.get_repo_structure(tmp_path)
        assert any(str(sub) in m for m in _errors(caplog))

    def test_179_a_root_that_cannot_be_listed_raises(self, tmp_path, monkeypatch, caplog):
        (tmp_path / "src").mkdir()
        _refuse_iterdir(monkeypatch, tmp_path)

        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(PermissionError):
            audit.get_repo_structure(tmp_path)
        assert any(str(tmp_path) in m for m in _errors(caplog))

    def test_a_readable_repo_is_listed(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
        assert "src/" in audit.get_repo_structure(tmp_path)

    def test_an_empty_repo_is_described_not_failed(self, tmp_path):
        """Kept: a new repo with no directories is an answer."""
        assert audit.get_repo_structure(tmp_path) == "(No relevant directories found)"


class TestLineageMove:
    def test_333_a_missing_lineage_dir_alerts_and_raises(self, tmp_path, operator_alerts):
        missing = tmp_path / "docs" / "lineage" / "active" / "42-lld"

        with pytest.raises(FileNotFoundError) as raised:
            audit.move_lineage_to_done(missing, tmp_path)
        assert str(missing) in str(raised.value)
        assert len(operator_alerts) == 1
        assert str(missing) in operator_alerts[0]["what"]
        assert operator_alerts[0]["repo"] == str(tmp_path)

    def test_359_a_move_that_fails_alerts_and_raises(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        active = tmp_path / "docs" / "lineage" / "active" / "42-lld"
        active.mkdir(parents=True)

        def refuse(*_a, **_kw):
            raise PermissionError(13, "Permission denied", str(active))

        monkeypatch.setattr(shutil, "move", refuse)

        with pytest.raises(PermissionError):
            audit.move_lineage_to_done(active, tmp_path)
        assert active.exists()
        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert "PermissionError" in alert["cause"]
        assert alert["repo"] == str(tmp_path)
        assert "42-lld" in alert["what"]

    def test_a_lineage_dir_moves_to_done(self, tmp_path, operator_alerts):
        active = tmp_path / "docs" / "lineage" / "active" / "42-lld"
        active.mkdir(parents=True)
        (active / "001-issue.md").write_text("x", encoding="utf-8")

        done = audit.move_lineage_to_done(active, tmp_path)
        assert done == tmp_path / "docs" / "lineage" / "done" / "42-lld"
        assert (done / "001-issue.md").exists()
        assert operator_alerts == []


class TestContext:
    def test_539_a_context_file_outside_the_repo_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "secret.md"
        outside.write_text("not in the repo", encoding="utf-8")

        with pytest.raises(ValueError) as raised:
            audit.assemble_context([str(outside)], repo)
        assert str(outside) in str(raised.value)
        assert "outside" in str(raised.value)

    def test_539_a_missing_context_file_raises(self, tmp_path):
        with pytest.raises(ValueError) as raised:
            audit.assemble_context(["docs/gone.md"], tmp_path)
        assert "gone.md" in str(raised.value)
        assert "does not exist" in str(raised.value)

    def test_558_an_unreadable_context_file_raises(self, tmp_path, monkeypatch, caplog):
        ctx = tmp_path / "notes.md"
        ctx.write_text("context", encoding="utf-8")
        real = Path.read_text

        def read_text(self, *args, **kwargs):
            if self == ctx:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(PermissionError):
            audit.assemble_context([str(ctx)], tmp_path)
        assert any(str(ctx) in m for m in _errors(caplog))

    def test_no_context_files_is_no_context(self, tmp_path):
        """Kept: nothing named, nothing assembled."""
        assert audit.assemble_context([], tmp_path) == ""

    def test_validate_context_path_still_answers_none(self, tmp_path):
        """Kept: the lookup's contract is None for a path it rejects; the
        caller that needs the file is the one that raises."""
        assert audit.validate_context_path("gone.md", tmp_path) is None


class TestRepoRoot:
    def test_613_a_repo_key_that_cannot_be_resolved_raises(
        self, tmp_path, monkeypatch, caplog
    ):
        def refuse(_path):
            raise PermissionError(13, "Permission denied", str(tmp_path))

        monkeypatch.setattr(audit, "_main_worktree_root", refuse)

        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(PermissionError):
            audit._repo_key(tmp_path)
        assert any(str(tmp_path) in m for m in _errors(caplog))

    def test_646_a_git_failure_inside_a_repo_raises(self, tmp_path, monkeypatch):
        _git(tmp_path, "init", "-b", "main")

        def failing(*_a, **_kw):
            return subprocess.CompletedProcess(
                args=["git"], returncode=128, stdout="", stderr="fatal: index is corrupt"
            )

        monkeypatch.setattr(audit.subprocess, "run", failing)

        with pytest.raises(GitOperationError) as raised:
            audit._main_worktree_root(tmp_path)
        message = str(raised.value)
        assert "rc=128" in message
        assert "index is corrupt" in message
        assert str(tmp_path) in message

    def test_a_directory_outside_any_repo_is_its_own_root(self, tmp_path):
        """Kept: a target that is not a git tree keeps its cache in itself."""
        plain = tmp_path / "plain"
        plain.mkdir()
        assert audit._main_worktree_root(plain) == plain

    def test_a_worktree_resolves_to_its_main_checkout(self, tmp_path):
        main = tmp_path / "main"
        main.mkdir()
        _git(main, "init", "-b", "main")
        (main / "x").write_text("x", encoding="utf-8")
        _git(main, "add", "-A")
        _git(main, "commit", "-m", "init")
        _git(main, "worktree", "add", str(tmp_path / "wt"), "-b", "wt")

        assert audit._main_worktree_root(tmp_path / "wt").resolve() == main.resolve()


class TestApprovalCache:
    def _cache(self, repo: Path) -> Path:
        path = audit.lld_status_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_680_a_corrupt_cache_alerts_raises_and_is_not_overwritten(
        self, tmp_path, operator_alerts
    ):
        path = self._cache(tmp_path)
        path.write_text("not json {", encoding="utf-8")

        with pytest.raises(ValueError, match="cannot be read"):
            audit.load_lld_tracking(tmp_path)
        with pytest.raises(ValueError):
            audit.update_lld_status(42, "docs/lld/active/LLD-042.md", {}, tmp_path)
        assert path.read_text(encoding="utf-8") == "not json {"
        assert len(operator_alerts) == 2
        assert str(path) in operator_alerts[0]["what"]
        assert "JSONDecodeError" in operator_alerts[0]["cause"]

    def test_680_an_unreadable_cache_alerts_and_raises(self, tmp_path, operator_alerts):
        path = audit.lld_status_path(tmp_path)
        path.mkdir(parents=True)  # exists, and reading it fails

        with pytest.raises(ValueError, match="cannot be read"):
            audit.load_lld_tracking(tmp_path)
        assert len(operator_alerts) == 1
        assert "IsADirectoryError" in operator_alerts[0]["cause"]

    def test_683_a_cache_that_is_not_an_object_raises(self, tmp_path, operator_alerts):
        path = self._cache(tmp_path)
        path.write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(ValueError, match="not a JSON object") as raised:
            audit.load_lld_tracking(tmp_path)
        assert str(path) in str(raised.value)
        assert path.read_text(encoding="utf-8") == "[1, 2, 3]"
        assert len(operator_alerts) == 1

    def test_697_a_malformed_repos_field_raises_and_is_not_overwritten(
        self, tmp_path, operator_alerts
    ):
        path = self._cache(tmp_path)
        original = json.dumps({"version": "2.0", "repos": ["a", "b"]})
        path.write_text(original, encoding="utf-8")

        with pytest.raises(ValueError, match="repos") as raised:
            audit.save_lld_tracking({"issues": {}}, tmp_path)
        assert str(path) in str(raised.value)
        assert path.read_text(encoding="utf-8") == original
        assert len(operator_alerts) == 1

    def test_a_cache_never_written_is_empty_and_quiet(self, tmp_path, operator_alerts):
        """Kept: no file means nothing was ever approved here."""
        assert audit.load_lld_tracking(tmp_path)["issues"] == {}
        assert operator_alerts == []

    def test_816_an_lld_path_outside_the_repo_is_stored_as_given(self, tmp_path):
        """Compliant, pinned: the documented behaviour ("keep as-is"); every
        reader only stores or displays the path."""
        outside = tmp_path.parent / "elsewhere" / "LLD-042.md"
        audit.update_lld_status(42, str(outside), {}, tmp_path)

        entry = audit.load_lld_tracking(tmp_path)["issues"]["42"]
        assert entry["lld_path"] == str(outside)


class TestReviewEvidence:
    def test_1183_a_review_summary_without_its_table_raises(self):
        content = "# 42 - Feature\n\n### Review Summary\n\nReviewed twice, see notes.\n"

        with pytest.raises(ValueError, match="Review Summary"):
            audit.embed_review_evidence(
                content, verdict="APPROVED", review_date="2026-10-30",
                review_count=1, reviewer_model="m", reviewer_spec="s",
            )

    def test_a_review_summary_table_gets_the_row(self):
        content = (
            "# 42 - Feature\n\n### Review Summary\n\n"
            "| Review | Date | Verdict | Model |\n"
            "|--------|------|---------|-------|\n"
            "| 1 | 2026-10-29 | BLOCKED | `m` |\n"
        )
        result = audit.embed_review_evidence(
            content, verdict="APPROVED", review_date="2026-10-30",
            review_count=2, reviewer_model="m", reviewer_spec="s",
        )
        assert "| 2 | 2026-10-30 | APPROVED | `m` (`s`) |" in result
