"""Mechanical LLD validation (N1.5) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``). A title
check that cannot run now blocks the draft instead of warning; a git probe
that cannot answer raises instead of reading as "not on the base"; a crash in
the similar-file search or the AST sentinel raises naming the file; a lineage
record or a telemetry record that cannot be written stops the run. A blocked
draft still goes back to the drafter, and absence that is an answer (no base
branch declared, no lineage folder given, a path the base does not ship) stays
quiet.
"""
from __future__ import annotations

import inspect
import logging
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.git_operations import GitOperationError
from assemblyzero.workflows.requirements.nodes import validate_mechanical as vm

LOGGER = "assemblyzero.workflows.requirements.nodes.validate_mechanical"

BODY = (
    "## 1. Context & Goal\n\nA small change.\n\n"
    "## 2. Proposed Changes\n\n"
    "### 2.1 Files Changed\n\n"
    "| File | Change Type | Description |\n"
    "|------|-------------|-------------|\n"
    "| `{path}` | {change} | The module |\n\n"
    "### 2.4 Function Signatures\n\n"
    "```python\ndef feature() -> int: ...\n```\n\n"
    "## 11. Risks & Mitigations\n\n"
    "| Risk | Impact | Likelihood | Mitigation |\n"
    "|------|--------|------------|------------|\n"
    "| None | Low | Low | Not applicable |\n\n"
    "## 12. Definition of Done\n\n"
    "- [x] `feature()` returns `1` (T010)\n"
)


def _lld(title: str = "# 42 - Feature: a small change", path: str = "feature.py",
         change: str = "Add") -> str:
    return f"{title}\n\n" + BODY.format(path=path, change=change)


def _state(repo: Path, draft: str, **extra) -> dict:
    state = {"current_draft": draft, "target_repo": str(repo), "issue_number": 42}
    state.update(extra)
    return state


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo_with_base(tmp_path):
    """A repo whose origin/main ships shipped.py; no remote is needed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "shipped.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


class TestTheGoodDraftStillPasses:
    def test_a_draft_with_the_right_title_passes(self, tmp_path):
        """Kept: the sanity case every blocking test below departs from."""
        result = vm._validate_lld_mechanical_inner(_state(tmp_path, _lld()))
        assert result["lld_status"] == "PENDING", result
        assert result["validation_errors"] == []


class TestTheTitleCheck:
    def test_548_the_dead_handler_is_gone(self):
        """Group 1 is digits, so int() cannot fail; the handler hid nothing
        and implied a failure mode that does not exist."""
        assert "except" not in inspect.getsource(vm.extract_title_issue_number)
        assert vm.extract_title_issue_number("# 0099 - Feature: x") == 99

    def test_571_a_draft_with_no_h1_is_blocked(self, tmp_path):
        errors = vm.validate_title_issue_number("## 42 - not an h1\n", 42)
        assert [e.severity for e in errors] == [vm.ValidationSeverity.ERROR]
        assert "No H1" in errors[0].message

        result = vm._validate_lld_mechanical_inner(
            _state(tmp_path, _lld(title="Feature: no heading at all"))
        )
        assert result["lld_status"] == "BLOCKED"
        assert any("No H1" in e for e in result["validation_errors"])

    def test_584_a_title_with_no_number_is_blocked(self, tmp_path):
        errors = vm.validate_title_issue_number("# Feature: no number\n", 42)
        assert [e.severity for e in errors] == [vm.ValidationSeverity.ERROR]
        assert "issue number" in errors[0].message
        assert "42" in errors[0].message

        result = vm._validate_lld_mechanical_inner(
            _state(tmp_path, _lld(title="# Feature: no number"))
        )
        assert result["lld_status"] == "BLOCKED"
        assert any("Could not extract" in e for e in result["validation_errors"])


class TestTheSimilarFileSearch:
    def test_1056_a_search_that_fails_raises_naming_the_directory(
        self, tmp_path, monkeypatch, caplog
    ):
        tools = tmp_path / "tools"
        tools.mkdir()
        real_glob = Path.glob

        def glob(self, pattern, *args, **kwargs):
            if self == tools:
                raise PermissionError(13, "Permission denied", str(self))
            return real_glob(self, pattern, *args, **kwargs)

        monkeypatch.setattr(Path, "glob", glob)

        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(PermissionError):
            vm.find_similar_files("gauge.py", tmp_path)
        assert any(
            r.levelno == logging.ERROR and str(tools) in r.getMessage()
            for r in caplog.records
        )

    def test_no_similar_file_is_an_empty_answer(self, tmp_path):
        """Kept: a search that runs and finds nothing is an answer."""
        (tmp_path / "tools").mkdir()
        assert vm.find_similar_files("gauge.py", tmp_path) == []


class TestTheBaseProbe:
    def test_1080_git_that_cannot_be_run_raises(self, tmp_path, monkeypatch):
        def no_git(*_a, **_kw):
            raise FileNotFoundError(2, "No such file or directory", "git")

        monkeypatch.setattr(subprocess, "run", no_git)

        with pytest.raises(GitOperationError) as raised:
            vm._exists_on_base(tmp_path, "main", "src/gauge.py")
        message = str(raised.value)
        assert str(tmp_path) in message
        assert "origin/main" in message
        assert "src/gauge.py" in message
        assert "FileNotFoundError" in message

    def test_1082_a_base_that_does_not_resolve_raises_with_stderr(self, repo_with_base):
        with pytest.raises(GitOperationError) as raised:
            vm._exists_on_base(repo_with_base, "no-such-branch", "shipped.py")
        message = str(raised.value)
        assert "origin/no-such-branch" in message
        assert "shipped.py" in message
        assert "rc=" in message
        assert "no-such-branch" in message.split("stderr")[-1]

    def test_1082_a_directory_that_is_not_a_repo_raises(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(GitOperationError, match="rc="):
            vm._exists_on_base(plain, "main", "shipped.py")

    def test_1082_the_node_stops_when_the_base_probe_fails(self, repo_with_base):
        draft = _lld(path="gone.py", change="Modify")
        with pytest.raises(GitOperationError):
            vm._validate_lld_mechanical_inner(
                _state(repo_with_base, draft, base_branch="no-such-branch")
            )

    def test_a_path_the_base_ships_is_found(self, repo_with_base):
        (repo_with_base / "shipped.py").unlink()
        assert vm._exists_on_base(repo_with_base, "main", "shipped.py") is True
        assert vm._exists_on_base(repo_with_base, "origin/main", "shipped.py") is True

    def test_a_path_the_base_does_not_ship_is_an_answer(self, repo_with_base):
        """Kept: absence on a base that resolves is the question's answer."""
        assert vm._exists_on_base(repo_with_base, "main", "src/nope.py") is False

    def test_no_base_branch_asks_git_nothing(self, tmp_path, monkeypatch):
        """Kept: a run with no integration branch has nothing to probe."""
        def no_git(*_a, **_kw):
            raise AssertionError("git must not run without a base branch")

        monkeypatch.setattr(subprocess, "run", no_git)
        assert vm._exists_on_base(tmp_path, "", "src/gauge.py") is False


class TestTheAstSentinel:
    def test_1513_a_sentinel_crash_raises_naming_the_file(
        self, tmp_path, monkeypatch, caplog
    ):
        (tmp_path / "mod.py").write_text("import os\n", encoding="utf-8")

        def crash(_path):
            raise RuntimeError("sentinel bug")

        monkeypatch.setattr(vm, "ast_analyze_file", crash)
        files = [{"path": "mod.py", "change_type": "Modify", "is_directory": False}]

        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(
            RuntimeError, match="sentinel bug"
        ):
            vm.run_ast_sentinel_on_modify_files(files, tmp_path)
        assert any(
            r.levelno == logging.ERROR and "mod.py" in r.getMessage()
            for r in caplog.records
        )


def _unwritable_lineage(monkeypatch):
    def refuse(*_a, **_kw):
        raise PermissionError(13, "Permission denied", "lineage")

    monkeypatch.setattr(vm, "save_validation_errors_to_lineage", refuse)


def _assert_lineage_failure_is_loud(caplog, lineage: Path) -> None:
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors, "the failed lineage write must be an ERROR line"
    text = errors[-1].getMessage()
    assert "#42" in text
    assert str(lineage) in text
    assert "PermissionError" in text


class TestTheLineageRecord:
    @pytest.fixture
    def lineage(self, tmp_path):
        return tmp_path / "lineage"

    def _run(self, caplog, state):
        with caplog.at_level(logging.ERROR, logger=LOGGER), pytest.raises(PermissionError):
            vm._validate_lld_mechanical_inner(state)

    def test_1583_the_empty_draft_record_stops_the_run(
        self, tmp_path, lineage, monkeypatch, caplog
    ):
        _unwritable_lineage(monkeypatch)
        self._run(caplog, _state(tmp_path, "   ", lineage_path=str(lineage)))
        _assert_lineage_failure_is_loud(caplog, lineage)

    def test_1617_the_missing_sections_record_stops_the_run(
        self, tmp_path, lineage, monkeypatch, caplog
    ):
        _unwritable_lineage(monkeypatch)
        self._run(caplog, _state(
            tmp_path, "# 42 - Feature: x\n\nno sections\n", lineage_path=str(lineage)
        ))
        _assert_lineage_failure_is_loud(caplog, lineage)

    def test_1653_the_parse_error_record_stops_the_run(
        self, tmp_path, lineage, monkeypatch, caplog
    ):
        _unwritable_lineage(monkeypatch)
        draft = "# 42 - Feature: x\n\n### 2.1 Files\n\nnone\n\n## 11\n\n## 12\n"
        self._run(caplog, _state(tmp_path, draft, lineage_path=str(lineage)))
        _assert_lineage_failure_is_loud(caplog, lineage)

    def test_1694_the_bad_repo_root_record_stops_the_run(
        self, tmp_path, lineage, monkeypatch, caplog
    ):
        _unwritable_lineage(monkeypatch)
        state = _state(tmp_path, _lld(), lineage_path=str(lineage))
        state["target_repo"] = ""
        self._run(caplog, state)
        _assert_lineage_failure_is_loud(caplog, lineage)

    def test_1766_the_aggregate_errors_record_stops_the_run(
        self, tmp_path, lineage, monkeypatch, caplog
    ):
        _unwritable_lineage(monkeypatch)
        draft = _lld(path="missing.py", change="Modify")
        self._run(caplog, _state(tmp_path, draft, lineage_path=str(lineage)))
        _assert_lineage_failure_is_loud(caplog, lineage)

    def test_a_written_record_lands_in_the_lineage_folder(self, tmp_path, lineage):
        """Kept: the audit trail the lineage write exists for."""
        draft = _lld(path="missing.py", change="Modify")
        result = vm._validate_lld_mechanical_inner(
            _state(tmp_path, draft, lineage_path=str(lineage))
        )
        assert result["lld_status"] == "BLOCKED"
        assert len(list(lineage.glob("validation-errors-draft*.md"))) == 1

    def test_no_lineage_folder_means_no_record_and_no_noise(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        """Kept: a caller that names no lineage folder (the answer-key replay)
        asked for no audit trail, so none is written."""
        _unwritable_lineage(monkeypatch)
        result = vm._validate_lld_mechanical_inner(_state(tmp_path, "   "))
        assert result["lld_status"] == "BLOCKED"
        assert operator_alerts == []


class TestTheBlockedRoute:
    def test_1775_a_blocked_draft_goes_back_to_the_drafter(self, tmp_path):
        """Compliant, pinned: BLOCKED carries error_message, the router loops
        to N1 under the cap, and the cap sends it to HALT, which alerts."""
        from assemblyzero.workflows.requirements.graph import (
            route_after_validate_mechanical,
        )

        result = vm._validate_lld_mechanical_inner(
            _state(tmp_path, _lld(path="missing.py", change="Modify"))
        )
        assert result["lld_status"] == "BLOCKED"
        assert result["error_message"].startswith("MECHANICAL VALIDATION FAILED")
        state = {**result, "iteration_count": 0, "max_iterations": 3}
        assert route_after_validate_mechanical(state) == "N1_generate_draft"


class TestTheTelemetryRecord:
    def _blocked(self, monkeypatch):
        monkeypatch.setattr(
            vm, "_validate_lld_mechanical_inner",
            lambda _state: {
                "validation_errors": ["boom"], "lld_status": "BLOCKED",
                "error_message": "MECHANICAL VALIDATION FAILED:\n  - boom",
            },
        )

    def test_1825_a_telemetry_failure_alerts_and_raises(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        from assemblyzero.speedrun import prompt_telemetry as pt

        self._blocked(monkeypatch)

        def explode(*_a, **_kw):
            raise RuntimeError("telemetry is broken")

        monkeypatch.setattr(pt, "record_failures", explode)

        with pytest.raises(RuntimeError, match="telemetry is broken"):
            vm.validate_lld_mechanical({"target_repo": str(tmp_path), "issue_number": 42})
        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert "RuntimeError: telemetry is broken" in alert["cause"]
        assert alert["issue"] == 42
        assert alert["repo"] == str(tmp_path)
        assert "validate_lld_mechanical" in alert["where"]

    def test_a_passing_draft_records_nothing_and_alerts_nothing(
        self, tmp_path, monkeypatch, operator_alerts
    ):
        """Kept: no failures, no telemetry call."""
        from assemblyzero.speedrun import prompt_telemetry as pt

        monkeypatch.setattr(
            vm, "_validate_lld_mechanical_inner",
            lambda _state: {"validation_errors": [], "lld_status": "PENDING",
                            "error_message": ""},
        )

        def never(*_a, **_kw):
            raise AssertionError("no telemetry for a passing draft")

        monkeypatch.setattr(pt, "record_failures", never)
        result = vm.validate_lld_mechanical({"target_repo": str(tmp_path), "issue_number": 42})
        assert result["lld_status"] == "PENDING"
        assert operator_alerts == []
