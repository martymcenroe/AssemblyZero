"""The requirements finalize node under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). A finalize
that cannot finish says so on standard error at the point of failure, names
what it was finishing (the repository, the issue, the draft), and sets
``error_message``, which ``route_after_finalize`` sends to HALT, and HALT
alerts the operator. Nothing outward happens after a precondition fails: no
issue is filed and no LLD is written when the audit trail is missing, and an
LLD the reviewer did not approve is neither saved nor landed.
"""
from __future__ import annotations

import importlib
import inspect
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.git_operations import GitOperationError
from assemblyzero.workflows.requirements.graph import route_after_finalize

fz = importlib.import_module("assemblyzero.workflows.requirements.nodes.finalize")

ISSUE_DRAFT = "# Add a widget\n\nThe widget body.\n"


def _gh(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["gh"], returncode=rc, stdout=stdout, stderr=stderr)


def _issue_state(tmp_path: Path, **overrides) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "workflow_type": "issue",
        "target_repo": str(repo),
        "current_draft": ISSUE_DRAFT,
        "audit_dir": str(audit),
        "error_message": "",
    }
    state.update(overrides)
    return state


def _lld_state(tmp_path: Path, **overrides) -> dict:
    from assemblyzero.core.llm_provider import MockProvider
    from assemblyzero.workflows.requirements.state import create_initial_state

    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = dict(create_initial_state(
        workflow_type="lld", assemblyzero_root=str(tmp_path / "az"),
        target_repo=str(repo), issue_number=42, base_branch="main",
    ))
    state.update({
        "current_draft": MockProvider.DEFAULT_RESPONSES["lld"][0],
        "lld_status": "APPROVED",
        "verdict_count": 1,
        "open_questions_status": "NONE",
        "audit_dir": str(audit),
    })
    state.update(overrides)
    return state


def _halts(state: dict, out: dict | None = None) -> bool:
    merged = {**state, **(out or {})}
    return bool(merged.get("error_message")) and route_after_finalize(merged) == "HALT"


def _said_error(capsys) -> str:
    err = capsys.readouterr().err
    assert "ERROR" in err, f"nothing at ERROR on stderr: {err!r}"
    return err


# --------------------------------------------------------------------------
# The issue workflow: _finalize_issue
# --------------------------------------------------------------------------


class TestFinalizeIssue:
    def test_112_a_draft_without_a_title_halts_naming_the_repo(self, tmp_path, capsys):
        state = _issue_state(tmp_path, current_draft="no heading here\n\nbody\n")

        with patch.object(fz, "run_command") as gh:
            out = fz._finalize_issue(state)

        gh.assert_not_called()
        assert _halts(state, out)
        assert state["target_repo"] in out["error_message"]
        assert "title" in out["error_message"]
        _said_error(capsys)

    def test_126_gh_failing_halts_with_its_exit_code_and_stderr(self, tmp_path, capsys):
        state = _issue_state(tmp_path)

        with patch.object(fz, "run_command", return_value=_gh(stderr="HTTP 422: label not found", rc=1)):
            out = fz._finalize_issue(state)

        assert _halts(state, out)
        message = out["error_message"]
        assert "HTTP 422: label not found" in message
        assert "exit 1" in message
        assert state["target_repo"] in message
        assert "Add a widget" in message
        _said_error(capsys)

    @pytest.mark.parametrize("url", [
        "https://github.com/o/r/issues/not-a-number",
        "https://github.com/o/r/pull/7",
        "",
    ])
    def test_136_an_issue_url_without_a_number_halts_naming_it(self, tmp_path, capsys, url):
        state = _issue_state(tmp_path)

        with patch.object(fz, "run_command", return_value=_gh(stdout=url + "\n")):
            out = fz._finalize_issue(state)

        assert _halts(state, out)
        assert repr(url) in out["error_message"]
        assert out.get("filed_issue_number", 0) == 0
        _said_error(capsys)

    def test_136_kept_a_well_formed_url_files_with_its_number(self, tmp_path):
        state = _issue_state(tmp_path)

        with patch.object(fz, "run_command", return_value=_gh(stdout="https://github.com/o/r/issues/57\n")):
            out = fz._finalize_issue(state)

        assert out["error_message"] == ""
        assert out["filed_issue_number"] == 57
        assert out["issue_url"] == "https://github.com/o/r/issues/57"
        assert list(Path(state["audit_dir"]).glob("*-final.md"))

    def test_140_a_timeout_halts_naming_the_repo_and_the_title(self, tmp_path, capsys):
        state = _issue_state(tmp_path)

        with patch.object(fz, "run_command", side_effect=subprocess.TimeoutExpired(["gh"], 30)):
            out = fz._finalize_issue(state)

        assert _halts(state, out)
        assert state["target_repo"] in out["error_message"]
        assert "Add a widget" in out["error_message"]
        _said_error(capsys)

    def test_142_a_missing_gh_halts_naming_the_repo(self, tmp_path, capsys):
        state = _issue_state(tmp_path)

        with patch.object(fz, "run_command", side_effect=FileNotFoundError(2, "No such file", "gh")):
            out = fz._finalize_issue(state)

        assert _halts(state, out)
        assert state["target_repo"] in out["error_message"]
        assert "gh" in out["error_message"]
        _said_error(capsys)

    @pytest.mark.parametrize("audit", ["", "missing"])
    def test_145_no_audit_dir_halts_before_anything_is_filed(self, tmp_path, capsys, audit):
        state = _issue_state(tmp_path)
        state["audit_dir"] = str(tmp_path / audit) if audit else ""

        with patch.object(fz, "run_command") as gh:
            out = fz._finalize_issue(state)

        gh.assert_not_called()
        assert _halts(state, out)
        assert "audit" in out["error_message"]
        _said_error(capsys)


class TestCleanupSourceIdea:
    def test_673_a_declared_idea_that_is_gone_halts_naming_it(self, tmp_path, capsys):
        missing = tmp_path / "ideas" / "active" / "widget.md"
        state = _issue_state(tmp_path, source_idea=str(missing))

        with patch.object(fz, "run_command", return_value=_gh(stdout="https://github.com/o/r/issues/57\n")), \
             patch.object(fz, "log_workflow_execution"):
            out = fz.finalize(state)

        assert _halts(out)
        assert str(missing) in out["error_message"]
        assert "https://github.com/o/r/issues/57" in out["error_message"]
        _said_error(capsys)

    def test_673_kept_a_present_idea_moves_to_done(self, tmp_path):
        idea = tmp_path / "ideas" / "active" / "widget.md"
        idea.parent.mkdir(parents=True)
        idea.write_text("an idea\n", encoding="utf-8")
        state = _issue_state(tmp_path, source_idea=str(idea))

        with patch.object(fz, "run_command", return_value=_gh(stdout="https://github.com/o/r/issues/57\n")), \
             patch.object(fz, "log_workflow_execution"):
            out = fz.finalize(state)

        assert out["error_message"] == ""
        assert not idea.exists()
        assert (tmp_path / "ideas" / "done" / "57-widget.md").is_file()

    def test_673_kept_no_declared_idea_is_quiet(self, tmp_path, capsys):
        """Absence is an answer: a workflow started from an issue, not an idea,
        has nothing to move."""
        state = _issue_state(tmp_path, source_idea="")

        with patch.object(fz, "run_command", return_value=_gh(stdout="https://github.com/o/r/issues/57\n")), \
             patch.object(fz, "log_workflow_execution"):
            out = fz.finalize(state)

        assert out["error_message"] == ""
        assert "ERROR" not in capsys.readouterr().err


# --------------------------------------------------------------------------
# The LLD workflow: _save_lld_file and finalize
# --------------------------------------------------------------------------


class TestSaveLld:
    def test_532_no_issue_number_halts_naming_the_repo(self, tmp_path, capsys):
        state = _lld_state(tmp_path, issue_number=0)

        out = fz._save_lld_file(state)

        assert _halts(out)
        assert out["target_repo"] in out["error_message"]
        _said_error(capsys)

    def test_535_no_draft_halts(self, tmp_path, capsys):
        state = _lld_state(tmp_path, current_draft="")

        with patch.object(fz, "lld_write_root") as root:
            out = fz._save_lld_file(state)

        root.assert_not_called()
        assert _halts(out)
        assert "#42" in out["error_message"]
        assert "draft" in out["error_message"]
        _said_error(capsys)

    @pytest.mark.parametrize("status", ["BLOCKED", "REVISE", "PENDING"])
    def test_798_an_lld_that_is_not_approved_halts_and_is_not_saved(
        self, tmp_path, capsys, status
    ):
        state = _lld_state(tmp_path, lld_status=status)
        write_root = tmp_path / "wt"

        with patch.object(fz, "lld_write_root", return_value=write_root), \
             patch.object(fz, "update_lld_status") as cache:
            out = fz._save_lld_file(state)

        assert _halts(out)
        assert status in out["error_message"]
        assert not (write_root / "docs" / "lld" / "active" / "LLD-042.md").exists()
        assert not fz.durable_lld_path(out["target_repo"], 42).exists()
        cache.assert_not_called()
        _said_error(capsys)

    def test_798_a_non_approved_lld_is_not_logged_complete_nor_landed(self, tmp_path):
        state = _lld_state(tmp_path, lld_status="BLOCKED")

        with patch.object(fz, "lld_write_root", return_value=tmp_path / "wt"), \
             patch.object(fz, "log_workflow_execution") as log, \
             patch.object(fz, "move_lineage_to_done") as move, \
             patch.object(fz, "_commit_and_push_files") as land:
            out = fz.finalize(state)

        assert _halts(out)
        log.assert_not_called()
        move.assert_not_called()
        land.assert_not_called()

    def test_573_a_worktree_that_cannot_be_cut_halts_and_the_tag_is_gone(self, tmp_path, capsys):
        state = _lld_state(tmp_path)

        with patch.object(fz, "lld_write_root", side_effect=GitOperationError("no arc to cut from")):
            out = fz._save_lld_file(state)

        assert _halts(out)
        assert "no arc to cut from" in out["error_message"]
        assert "fail-open" not in inspect.getsource(fz._save_lld_file)
        _said_error(capsys)

    def test_590_an_lld_not_on_disk_after_the_write_halts(self, tmp_path, monkeypatch, capsys):
        state = _lld_state(tmp_path)
        write_root = tmp_path / "wt"
        real_write = Path.write_text

        def write_text(self, *args, **kwargs):
            if self.name == "LLD-042.md" and "active" in self.parts and "lld" in self.parts:
                return 0  # the write "succeeds" and nothing lands
            return real_write(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", write_text)
        with patch.object(fz, "lld_write_root", return_value=write_root), \
             patch.object(fz, "update_lld_status") as cache:
            out = fz._save_lld_file(state)

        assert _halts(out)
        assert "LLD-042.md" in out["error_message"]
        cache.assert_not_called()
        _said_error(capsys)

    @pytest.mark.parametrize("audit", ["", "missing"])
    def test_653_no_audit_dir_halts_before_the_lld_is_written(self, tmp_path, capsys, audit):
        state = _lld_state(tmp_path)
        state["audit_dir"] = str(tmp_path / audit) if audit else ""

        with patch.object(fz, "lld_write_root") as root:
            out = fz._save_lld_file(state)

        root.assert_not_called()
        assert _halts(out)
        assert "audit" in out["error_message"]
        _said_error(capsys)


class TestFinalizeLineage:
    def test_787_an_audit_dir_gone_at_the_lineage_move_halts(self, tmp_path, capsys):
        state = _lld_state(tmp_path)
        state["audit_dir"] = str(tmp_path / "vanished")

        with patch.object(fz, "_save_lld_file", side_effect=lambda s: s), \
             patch.object(fz, "log_workflow_execution"), \
             patch.object(fz, "move_lineage_to_done") as move, \
             patch.object(fz, "_commit_and_push_files") as land:
            out = fz.finalize(state)

        move.assert_not_called()
        land.assert_not_called()
        assert _halts(out)
        assert "vanished" in out["error_message"]
        _said_error(capsys)


class TestRepairBudget:
    @pytest.mark.parametrize("bad", ["three", [3], {"n": 3}])
    def test_450_a_malformed_max_iterations_raises_naming_it(self, bad):
        with pytest.raises(ValueError, match="max_iterations"):
            fz._finalize_repair_budget({"max_iterations": bad})

    def test_450_kept_absent_or_numeric_caps_still_size_the_budget(self):
        assert fz._finalize_repair_budget({}) == fz.MAX_FINALIZE_REPAIRS
        assert fz._finalize_repair_budget({"max_iterations": "1"}) == 1
        assert fz._finalize_repair_budget({"max_iterations": 9}) == fz.MAX_FINALIZE_REPAIRS

    def test_487_a_spent_repair_budget_halts(self, tmp_path):
        """Already routed to HALT by #3864's route_after_finalize; pinned."""
        state = _lld_state(tmp_path, finalize_repair_count=fz.MAX_FINALIZE_REPAIRS)

        out = fz._request_finalize_repair(state, ["Unresolved open questions remain"])

        assert out["finalize_repair_pending"] is False
        assert _halts(out)
        assert "Unresolved open questions remain" in out["error_message"]


class TestValidateLldFinal:
    @pytest.mark.parametrize("content", ["", "   \n\t\n"])
    def test_an_empty_lld_fails_validation(self, content):
        with pytest.raises(ValueError, match="empty"):
            fz.validate_lld_final(content)

    def test_kept_a_clean_lld_passes(self):
        assert fz.validate_lld_final("# LLD\n\n## Design\n\nIt works.\n") == []


# --------------------------------------------------------------------------
# The landing: _commit_and_push_files
# --------------------------------------------------------------------------


class TestLanding:
    def _landing_state(self, tmp_path: Path) -> dict:
        worktree_lld = tmp_path / "data" / "worktrees" / "42-lld" / "docs" / "lld" / "active" / "LLD-042.md"
        return {
            "created_files": [str(worktree_lld)], "workflow_type": "lld",
            "issue_number": 42, "target_repo": str(tmp_path), "base_branch": "arc",
            "final_lld_path": str(worktree_lld), "error_message": "",
        }

    def test_247_a_landing_without_the_durable_copy_halts(self, tmp_path, capsys):
        state = self._landing_state(tmp_path)
        worktree = tmp_path / "data" / "worktrees" / "42-lld"

        with patch.object(fz, "setup_lld_worktree", return_value=(worktree, "42-lld")), \
             patch.object(fz, "_mirror_to_worktree", return_value=state["created_files"]), \
             patch.object(fz, "commit_and_pr", return_value=("abc1234", "https://github.com/o/r/pull/9")):
            out = fz._commit_and_push_files(state)

        assert _halts(out)
        assert str(fz.durable_lld_path(tmp_path, 42)) in out["error_message"]
        assert "https://github.com/o/r/pull/9" in out["error_message"]
        _said_error(capsys)

    def test_261_a_failed_landing_halts_and_keeps_commit_error(self, tmp_path, capsys):
        state = self._landing_state(tmp_path)
        worktree = tmp_path / "data" / "worktrees" / "42-lld"

        with patch.object(fz, "setup_lld_worktree", return_value=(worktree, "42-lld")), \
             patch.object(fz, "_mirror_to_worktree", return_value=state["created_files"]), \
             patch.object(fz, "commit_and_pr", side_effect=GitOperationError("AZ_MERGE_DRIVER is not set")):
            out = fz._commit_and_push_files(state)

        assert _halts(out)
        assert "AZ_MERGE_DRIVER is not set" in out["error_message"]
        assert "AZ_MERGE_DRIVER is not set" in out["commit_error"]
        _said_error(capsys)

    def test_261_a_failed_landing_is_never_logged_complete(self, tmp_path):
        state = _lld_state(tmp_path)
        worktree = tmp_path / "wt"

        with patch.object(fz, "lld_write_root", return_value=worktree), \
             patch.object(fz, "update_lld_status"), \
             patch.object(fz, "move_lineage_to_done"), \
             patch.object(fz, "log_workflow_execution") as log, \
             patch.object(fz, "setup_lld_worktree", return_value=(worktree, "42-lld")), \
             patch.object(fz, "commit_and_pr", side_effect=GitOperationError("checks failed")):
            out = fz.finalize(state)

        assert _halts(out)
        assert "checks failed" in out["error_message"]
        log.assert_not_called()

    def test_261_a_failed_issue_workflow_push_halts(self, tmp_path, capsys):
        state = {
            "created_files": [str(tmp_path / "x.md")], "workflow_type": "issue",
            "target_repo": str(tmp_path), "error_message": "",
        }

        with patch.object(fz, "commit_and_push", side_effect=GitOperationError("push rejected")):
            out = fz._commit_and_push_files(state)

        assert _halts(out)
        assert "push rejected" in out["error_message"]
        _said_error(capsys)

    def test_297_kept_a_file_outside_the_repo_passes_through(self, tmp_path):
        """Compliant by the ledger: commit_and_pr's git add then fails loudly."""
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x\n", encoding="utf-8")
        repo = tmp_path / "repo"
        repo.mkdir()

        out = fz._mirror_to_worktree([str(outside)], repo, repo / "data" / "worktrees" / "1-lld")

        assert out == [str(outside)]


def test_no_fail_open_tag_remains_in_finalize():
    assert "fail-open" not in inspect.getsource(fz)


def test_the_node_never_swallows_into_a_partial_success(tmp_path):
    """A finalize that halts reports no filed issue as a success."""
    state = _issue_state(tmp_path)

    with patch.object(fz, "run_command", return_value=_gh(stderr="boom", rc=1)), \
         patch.object(fz, "log_workflow_execution") as log:
        out = fz.finalize(state)

    assert _halts(out)
    assert not out.get("issue_url")
    log.assert_not_called()
