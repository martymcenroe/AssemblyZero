"""The requirements codebase analysis node (N0b) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). An analysis
that cannot read what it analyzes returns ``error_message``, which
``route_after_analyze_codebase`` sends to HALT before N0c spends a model call,
and HALT alerts. A file left out to fit the token budget is a designed cap and
is named in the log; a sensitive, binary or empty file is skipped quietly; a
selected file that cannot be read is a failure.
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.git_operations import GitOperationError
from assemblyzero.workflows.requirements.graph import route_after_analyze_codebase

ac = importlib.import_module("assemblyzero.workflows.requirements.nodes.analyze_codebase")


def _repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Demo\n\nA demo project.\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "1.0.0"\n', encoding="utf-8",
    )
    src = root / "src"
    src.mkdir(exist_ok=True)
    (src / "widget.py").write_text("def make_widget() -> int:\n    return 1\n", encoding="utf-8")
    return root


def _state(repo, **overrides) -> dict:
    state = {
        "target_repo": str(repo) if repo is not None else None,
        "issue_body": "Make the widget faster.",
        "directory_tree": "README.md\npyproject.toml\nsrc/\nsrc/widget.py\n",
    }
    state.update(overrides)
    return state


def _halts(out: dict) -> bool:
    return bool(out.get("error_message")) and route_after_analyze_codebase(out) == "HALT"


def _said_error(capsys) -> str:
    err = capsys.readouterr().err
    assert "ERROR" in err, f"nothing at ERROR on stderr: {err!r}"
    return err


class TestRepoPath:
    @pytest.mark.parametrize("repo", [None, "", "   "])
    def test_107_no_repo_path_halts(self, capsys, repo):
        out = ac.analyze_codebase({"target_repo": repo, "issue_body": "x"})

        assert _halts(out)
        assert "repo" in out["error_message"]
        _said_error(capsys)

    def test_112_a_repo_path_that_does_not_exist_halts_naming_it(self, tmp_path, capsys):
        missing = tmp_path / "no-such-repo"

        out = ac.analyze_codebase(_state(missing))

        assert _halts(out)
        assert str(missing) in out["error_message"]
        _said_error(capsys)

    def test_153_an_arc_that_cannot_be_cut_halts_before_n0c(self, tmp_path):
        """Routed to HALT by #3864's route_after_analyze_codebase; pinned."""
        repo = _repo(tmp_path / "repo")
        state = _state(repo, base_branch="main", issue_number=42)

        with patch(
            "assemblyzero.workflows.requirements.git_operations.setup_lld_worktree",
            side_effect=GitOperationError("origin/main does not resolve"),
        ):
            out = ac.analyze_codebase(state)

        assert _halts(out)
        assert "origin/main does not resolve" in out["error_message"]


class TestProjectMetadata:
    def test_a_project_config_that_will_not_parse_halts_naming_it(self, tmp_path, capsys):
        """The reader raises on it (#4417); N0b halts, never an uncaught raise."""
        repo = _repo(tmp_path / "repo")
        (repo / "pyproject.toml").write_text("[project\nname = ", encoding="utf-8")

        out = ac.analyze_codebase(_state(repo))

        assert _halts(out)
        assert "pyproject.toml" in out["error_message"]
        _said_error(capsys)


class TestSelectedFiles:
    def test_191_a_key_file_that_cannot_be_read_halts_naming_it(self, tmp_path, capsys):
        repo = _repo(tmp_path / "repo")
        (repo / "README.md").write_bytes(b"\xff\xfe not utf-8 \xc3\x28")

        out = ac.analyze_codebase(_state(repo))

        assert _halts(out)
        assert str(repo / "README.md") in out["error_message"]
        assert "UnicodeDecodeError" in out["error_message"]
        _said_error(capsys)

    def test_191_kept_an_empty_key_file_is_skipped_quietly(self, tmp_path, capsys):
        repo = _repo(tmp_path / "repo")
        (repo / "CLAUDE.md").write_text("", encoding="utf-8")

        out = ac.analyze_codebase(_state(repo))

        assert not out.get("error_message")
        assert "ERROR" not in capsys.readouterr().err

    def test_191_kept_key_files_past_the_budget_are_named_in_the_log(self, tmp_path, caplog):
        repo = _repo(tmp_path / "repo")
        (repo / "CLAUDE.md").write_text("x" * 100, encoding="utf-8")

        with patch.object(ac, "_TOTAL_TOKEN_BUDGET", 10), \
             caplog.at_level(logging.WARNING, logger=ac.__name__):
            out = ac.analyze_codebase(_state(repo))

        assert not out.get("error_message")
        assert any("README.md" in m and "budget" in m for m in caplog.messages)

    def test_268_a_related_file_that_cannot_be_read_halts_naming_it(self, tmp_path, capsys):
        repo = _repo(tmp_path / "repo")
        (repo / "src" / "widget.py").write_bytes(b"\xff\xfe\x00 not text")

        with patch.object(ac, "build_interface_map", return_value={}):
            out = ac.analyze_codebase(_state(repo))

        assert _halts(out)
        assert "widget.py" in out["error_message"]
        _said_error(capsys)

    def test_268_kept_a_related_binary_file_is_skipped_quietly(self, tmp_path):
        repo = _repo(tmp_path / "repo")
        (repo / "src" / "widget.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        state = _state(repo, directory_tree="README.md\nsrc/\nsrc/widget.png\n")

        out = ac.analyze_codebase(state)

        assert not out.get("error_message")


class TestInterfaceSurface:
    @pytest.mark.parametrize("exc", [
        PermissionError(13, "Permission denied", "src/widget.py"),
        SyntaxError("invalid syntax"),
        ValueError("outside the repo"),
    ])
    def test_285_a_failing_extraction_halts_naming_the_cause(self, tmp_path, capsys, exc):
        repo = _repo(tmp_path / "repo")

        with patch.object(ac, "build_interface_map", side_effect=exc):
            out = ac.analyze_codebase(_state(repo))

        assert _halts(out)
        assert type(exc).__name__ in out["error_message"]
        _said_error(capsys)

    def test_285_kept_a_repo_with_no_python_has_an_empty_surface(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("# Docs only\n", encoding="utf-8")

        out = ac.analyze_codebase(_state(repo, directory_tree="README.md\n"))

        assert not out.get("error_message")
        assert out["interface_map"] == {}


class TestListingFailures:
    def test_361_a_docs_listing_that_fails_halts(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path / "repo")
        (repo / "docs" / "adrs").mkdir(parents=True)
        real_glob = Path.glob

        def glob(self, pattern, *args, **kwargs):
            if self.name == "adrs":
                raise PermissionError(13, "Permission denied", str(self))
            return real_glob(self, pattern, *args, **kwargs)

        monkeypatch.setattr(Path, "glob", glob)
        out = ac.analyze_codebase(_state(repo))

        assert _halts(out)
        assert "PermissionError" in out["error_message"]
        _said_error(capsys)

    def test_375_a_repo_root_listing_that_fails_halts(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path / "repo")
        real_iterdir = Path.iterdir

        def iterdir(self):
            if self == repo.resolve():
                raise PermissionError(13, "Permission denied", str(self))
            return real_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", iterdir)
        out = ac.analyze_codebase(_state(repo))

        assert _halts(out)
        assert "PermissionError" in out["error_message"]
        _said_error(capsys)

    def test_460_kept_a_candidate_outside_the_repo_is_skipped(self, tmp_path):
        """Compliant by the ledger: the boundary filter."""
        repo = _repo(tmp_path / "repo")
        outside = tmp_path / "elsewhere.py"
        outside.write_text("x = 1\n", encoding="utf-8")
        (repo / "widgetlink.py").symlink_to(outside)

        found = ac._find_related_files(repo.resolve(), "widgetlink", "widgetlink.py\n")

        assert found == []

    def test_502_a_search_that_fails_raises(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path / "repo")

        def rglob(self, pattern, *args, **kwargs):
            raise PermissionError(13, "Permission denied", str(self))

        monkeypatch.setattr(Path, "rglob", rglob)
        with pytest.raises(PermissionError):
            ac._search_for_file(repo, "widget.py")

    def test_502_a_search_that_fails_halts_the_node(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path / "repo")
        state = _state(repo, directory_tree="README.md\nwidget.py\n")

        def rglob(self, pattern, *args, **kwargs):
            raise PermissionError(13, "Permission denied", str(self))

        monkeypatch.setattr(Path, "rglob", rglob)
        with patch.object(ac, "build_interface_map", return_value={}):
            out = ac.analyze_codebase(state)

        assert _halts(out)
        assert "PermissionError" in out["error_message"]
        _said_error(capsys)
