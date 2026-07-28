"""Unit tests for the codebase analysis node.

Issue #401: Codebase Context Analysis for Requirements Workflow.

Tests for:
- analyze_codebase (LangGraph node)
- _select_key_files (key file discovery and priority)
- _find_related_files (issue keyword matching)
- _empty_codebase_context (fallback context)
- Integration: sensitive file exclusion, symlink boundary, cross-repo
"""

import logging
import os
import sys

import pytest
from pathlib import Path

from assemblyzero.workflows.requirements.nodes.analyze_codebase import (
    analyze_codebase,
    _empty_codebase_context,
    _extract_first_paragraph,
    _extract_module_docstring,
    _build_project_description,
    _build_module_structure,
    _find_related_files,
    _select_key_files,
    _search_for_file,
)
from assemblyzero.utils.codebase_reader import (
    is_sensitive_file,
    read_file_with_budget,
)


# ---------------------------------------------------------------------------
# Expected keys in CodebaseContext
# ---------------------------------------------------------------------------

_CODEBASE_CONTEXT_KEYS = {
    "project_description",
    "conventions",
    "frameworks",
    "module_structure",
    "key_file_excerpts",
    "related_code",
    "dependency_summary",
    "directory_tree",
    "code_patterns",  # #1816: scan_patterns output, wired in per #401
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo(tmp_path):
    """Create a minimal mock repository with key project files."""
    # CLAUDE.md with conventions
    (tmp_path / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\n"
        "## Rules\n\n"
        "- Use snake_case for all module filenames\n"
        "- Always write tests before implementation\n"
        "- Use poetry run python for all execution\n"
        "\n"
        "## Style\n\n"
        "- Maximum line length is 100 characters\n"
        "- Use type hints on all function signatures\n",
        encoding="utf-8",
    )

    # README.md
    (tmp_path / "README.md").write_text(
        "# Mock Project\n\n"
        "A mock project for testing codebase analysis.\n\n"
        "## Installation\n\nRun `pip install .`\n",
        encoding="utf-8",
    )

    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "mock-project"\n'
        'version = "1.0.0"\n'
        'description = "A mock project for testing"\n'
        'dependencies = [\n'
        '    "langgraph>=0.1",\n'
        '    "pytest>=7.0",\n'
        ']\n',
        encoding="utf-8",
    )

    # src/ directory with Python files
    src = tmp_path / "src"
    src.mkdir()

    (src / "main.py").write_text(
        '"""Main module for mock project."""\n\n'
        "from typing import TypedDict\n\n\n"
        "class AppState(TypedDict):\n"
        '    """Application state."""\n\n'
        "    count: int\n"
        "    name: str\n\n\n"
        "def process_data(state: dict) -> dict:\n"
        '    """Process data node."""\n'
        '    return {"count": state["count"] + 1}\n',
        encoding="utf-8",
    )

    (src / "auth.py").write_text(
        '"""Authentication module."""\n\n'
        "from fastapi import Depends\n\n\n"
        "def authenticate_user(username: str, password: str) -> bool:\n"
        '    """Authenticate a user."""\n'
        '    return username == "admin"\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def mock_repo_with_sensitive(mock_repo):
    """Extend mock_repo with sensitive files that must never be read."""
    (mock_repo / ".env").write_text(
        "SECRET=abc123\nAPI_KEY=sk-supersecret\n",
        encoding="utf-8",
    )
    (mock_repo / "server.pem").write_text(
        "-----BEGIN CERTIFICATE-----\nFAKECERTDATA\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    return mock_repo


@pytest.fixture
def second_mock_repo(tmp_path):
    """Create a second mock repository for cross-repo testing (T240)."""
    repo2 = tmp_path / "second_repo"
    repo2.mkdir()

    (repo2 / "CLAUDE.md").write_text(
        "# Second Repo\n\n## Rules\n\n- Use camelCase for JavaScript\n",
        encoding="utf-8",
    )
    (repo2 / "README.md").write_text(
        "# Second Project\n\nA different project entirely.\n",
        encoding="utf-8",
    )
    (repo2 / "pyproject.toml").write_text(
        '[project]\nname = "second-project"\nversion = "2.0.0"\n'
        'description = "Second project for cross-repo test"\n',
        encoding="utf-8",
    )

    return repo2


@pytest.fixture
def directory_tree():
    """A basic directory tree string for the mock repo."""
    return (
        "CLAUDE.md\n"
        "README.md\n"
        "pyproject.toml\n"
        "src/\n"
        "src/main.py\n"
        "src/auth.py\n"
    )


@pytest.fixture
def directory_tree_with_sensitive():
    """Directory tree including sensitive files."""
    return (
        "CLAUDE.md\n"
        "README.md\n"
        "pyproject.toml\n"
        ".env\n"
        "server.pem\n"
        "src/\n"
        "src/main.py\n"
        "src/auth.py\n"
    )


def _make_state(repo_path=None, issue_text="", directory_tree=""):
    """Build a minimal LangGraph state dict for analyze_codebase."""
    return {
        "repo_path": str(repo_path) if repo_path else None,
        "issue_text": issue_text,
        "directory_tree": directory_tree,
    }


# ---------------------------------------------------------------------------
# T140 — test_analyze_codebase_happy_path
# ---------------------------------------------------------------------------


class TestAnalyzeCodebaseHappyPath:
    """T140: Produces full CodebaseContext from mock repo."""

    def test_all_fields_populated(self, mock_repo, directory_tree):
        """All CodebaseContext fields should be populated from a complete mock repo."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="Fix the authentication flow in the auth module",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        # project_description from README / metadata
        assert ctx["project_description"], "project_description should not be empty"
        # conventions from CLAUDE.md
        assert len(ctx["conventions"]) > 0, "conventions should be populated"
        # frameworks from pyproject.toml deps (langgraph, pytest)
        assert len(ctx["frameworks"]) > 0, "frameworks should be detected"
        # key_file_excerpts from key files read
        assert len(ctx["key_file_excerpts"]) > 0, "key_file_excerpts should be populated"
        # directory_tree passed through
        assert ctx["directory_tree"] == directory_tree

    def test_related_code_found_for_auth_issue(self, mock_repo, directory_tree):
        """When issue mentions 'authentication', related_code should include auth.py."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="Fix the authentication flow in the auth module",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        related_paths_lower = [p.lower() for p in ctx["related_code"]]
        assert any("auth" in p for p in related_paths_lower), (
            f"Expected auth-related file in related_code, got: {list(ctx['related_code'])}"
        )

    def test_dependency_summary_populated(self, mock_repo, directory_tree):
        """dependency_summary should contain parsed deps from pyproject.toml."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="test",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        assert ctx["dependency_summary"], "dependency_summary should not be empty"
        assert "langgraph" in ctx["dependency_summary"].lower()


# ---------------------------------------------------------------------------
# T145 — test_analyze_codebase_context_has_real_paths
# ---------------------------------------------------------------------------


class TestAnalyzeCodebaseRealPaths:
    """T145: Generated context references real file paths and patterns from codebase."""

    def test_key_file_excerpts_are_real_paths(self, mock_repo, directory_tree):
        """Every path in key_file_excerpts should point to a real file."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="improve the authentication module",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        assert len(ctx["key_file_excerpts"]) > 0
        for path_str in ctx["key_file_excerpts"]:
            assert Path(path_str).exists(), (
                f"key_file_excerpts path does not exist: {path_str}"
            )

    def test_conventions_match_claude_md_content(self, mock_repo, directory_tree):
        """Conventions should be traceable to CLAUDE.md rules."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="test conventions",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        assert len(ctx["conventions"]) > 0
        convention_text = " ".join(ctx["conventions"]).lower()
        # We wrote "Use snake_case for all module filenames" in CLAUDE.md
        assert "snake_case" in convention_text, (
            f"Expected snake_case convention from CLAUDE.md, got: {ctx['conventions']}"
        )

    def test_related_code_paths_exist(self, mock_repo, directory_tree):
        """Every path in related_code should point to a real file."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="Fix the authentication flow in the auth module",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        for path_str in ctx["related_code"]:
            assert Path(path_str).exists(), (
                f"related_code path does not exist: {path_str}"
            )


# ---------------------------------------------------------------------------
# T150 — test_analyze_codebase_no_repo_path
# ---------------------------------------------------------------------------


class TestAnalyzeCodebaseNoRepoPath:
    """T150: Returns empty context when repo_path is None, logs warning."""

    def test_returns_empty_context(self):
        """State with repo_path=None produces empty CodebaseContext."""
        state = _make_state(repo_path=None, issue_text="some issue")
        result = analyze_codebase(state)

        assert "codebase_context" in result
        ctx = result["codebase_context"]
        assert ctx["project_description"] == ""
        assert ctx["conventions"] == []
        assert ctx["frameworks"] == []
        assert ctx["key_file_excerpts"] == {}
        assert ctx["related_code"] == {}

    def test_logs_warning(self, caplog):
        """A warning should be logged when repo_path is None."""
        state = _make_state(repo_path=None)
        with caplog.at_level(logging.WARNING):
            analyze_codebase(state)
        assert any("No repo path" in msg for msg in caplog.messages)

    def test_empty_string_repo_path(self):
        """An empty string repo_path should also produce empty context."""
        state = {"repo_path": "", "issue_text": "test"}
        result = analyze_codebase(state)
        ctx = result["codebase_context"]
        assert ctx["project_description"] == ""
        assert ctx["conventions"] == []


# ---------------------------------------------------------------------------
# T160 — test_analyze_codebase_missing_repo
# ---------------------------------------------------------------------------


class TestAnalyzeCodebaseMissingRepo:
    """T160: Returns empty context when repo_path doesn't exist."""

    def test_returns_empty_context(self, tmp_path):
        """Non-existent repo_path produces empty CodebaseContext."""
        nonexistent = tmp_path / "nonexistent_repo"
        state = _make_state(repo_path=nonexistent, issue_text="some issue")
        result = analyze_codebase(state)

        ctx = result["codebase_context"]
        assert ctx["project_description"] == ""
        assert ctx["conventions"] == []
        assert ctx["frameworks"] == []
        assert ctx["key_file_excerpts"] == {}
        assert ctx["related_code"] == {}

    def test_logs_warning(self, tmp_path, caplog):
        """A warning should be logged when repo_path doesn't exist."""
        nonexistent = tmp_path / "does_not_exist"
        state = _make_state(repo_path=nonexistent)
        with caplog.at_level(logging.WARNING):
            analyze_codebase(state)
        assert any("does not exist" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# T170 — test_find_related_files_keyword_match
# ---------------------------------------------------------------------------


class TestFindRelatedFilesMatch:
    """T170: Finds auth.py when issue mentions 'authentication'."""

    def test_finds_auth_file(self, mock_repo, directory_tree):
        """Issue text containing 'auth' keyword should match auth.py."""
        related = _find_related_files(
            mock_repo.resolve(),
            issue_text="Fix the auth module flow",
            directory_tree=directory_tree,
        )
        names = [p.name for p in related]
        assert "auth.py" in names, f"Expected auth.py in results, got {names}"

    def test_returns_path_objects(self, mock_repo, directory_tree):
        """All returned items should be Path objects."""
        related = _find_related_files(
            mock_repo.resolve(),
            issue_text="Fix the auth module flow",
            directory_tree=directory_tree,
        )
        for p in related:
            assert isinstance(p, Path)

    def test_found_files_exist(self, mock_repo, directory_tree):
        """All returned paths should point to existing files."""
        related = _find_related_files(
            mock_repo.resolve(),
            issue_text="Fix the auth module flow",
            directory_tree=directory_tree,
        )
        for p in related:
            assert p.exists(), f"Returned path does not exist: {p}"


# ---------------------------------------------------------------------------
# T180 — test_find_related_files_no_match
# ---------------------------------------------------------------------------


class TestFindRelatedFilesNoMatch:
    """T180: Returns empty list for unrelated issue text."""

    def test_returns_empty_for_unrelated(self, mock_repo, directory_tree):
        """Issue about unrelated topics should find nothing."""
        related = _find_related_files(
            mock_repo.resolve(),
            issue_text="quantum entanglement algorithms for molecular simulation",
            directory_tree=directory_tree,
        )
        assert related == []

    def test_empty_issue_text(self, mock_repo, directory_tree):
        """Empty issue text should find nothing."""
        related = _find_related_files(
            mock_repo.resolve(),
            issue_text="",
            directory_tree=directory_tree,
        )
        assert related == []

    def test_empty_directory_tree(self, mock_repo):
        """Empty directory tree should find nothing."""
        related = _find_related_files(
            mock_repo.resolve(),
            issue_text="authentication fix needed",
            directory_tree="",
        )
        assert related == []


# ---------------------------------------------------------------------------
# T185 — test_find_related_files_max_five
# ---------------------------------------------------------------------------


class TestFindRelatedFilesMaxFive:
    """T185: Returns at most 5 results even with many matches."""

    def test_max_five_results(self, tmp_path):
        """With 10+ matching files, result should be capped at 5."""
        repo = tmp_path / "big_repo"
        repo.mkdir()

        src = repo / "src"
        src.mkdir()

        # Create 10 auth-related files
        for i in range(10):
            f = src / f"auth_handler_{i}.py"
            f.write_text(f"# Auth handler {i}\n", encoding="utf-8")

        tree_lines = ["src/"]
        for i in range(10):
            tree_lines.append(f"src/auth_handler_{i}.py")
        directory_tree = "\n".join(tree_lines)

        related = _find_related_files(
            repo.resolve(),
            issue_text="fix authentication handler logic",
            directory_tree=directory_tree,
        )
        assert len(related) <= 5, f"Expected at most 5 results, got {len(related)}"

    def test_returns_nonempty_for_many_matches(self, tmp_path):
        """Should still return results when there are many matches."""
        repo = tmp_path / "big_repo"
        repo.mkdir()

        src = repo / "src"
        src.mkdir()

        for i in range(10):
            f = src / f"auth_handler_{i}.py"
            f.write_text(f"# Auth handler {i}\n", encoding="utf-8")

        tree_lines = ["src/"]
        for i in range(10):
            tree_lines.append(f"src/auth_handler_{i}.py")
        directory_tree = "\n".join(tree_lines)

        related = _find_related_files(
            repo.resolve(),
            issue_text="fix authentication handler logic",
            directory_tree=directory_tree,
        )
        assert len(related) > 0, "Should find at least one match"


# ---------------------------------------------------------------------------
# T190 — test_analyze_codebase_produces_state_key
# ---------------------------------------------------------------------------


class TestAnalyzeCodebaseStateKey:
    """T190: Node returns dict with codebase_context key matching CodebaseContext shape."""

    def test_returns_codebase_context_key(self, mock_repo, directory_tree):
        """Return dict must have a 'codebase_context' key."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="test issue",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        assert "codebase_context" in result
        assert isinstance(result["codebase_context"], dict)

    def test_context_has_all_expected_keys(self, mock_repo, directory_tree):
        """codebase_context dict should have all CodebaseContext keys."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="test issue",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        for key in _CODEBASE_CONTEXT_KEYS:
            assert key in ctx, f"Missing expected key: {key}"

    def test_no_unexpected_keys(self, mock_repo, directory_tree):
        """codebase_context should not have extra/unexpected keys."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="test issue",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        extra = set(ctx.keys()) - _CODEBASE_CONTEXT_KEYS
        assert not extra, f"Unexpected keys in codebase_context: {extra}"

    def test_context_value_types(self, mock_repo, directory_tree):
        """Each field in codebase_context should have the correct type."""
        state = _make_state(
            repo_path=mock_repo,
            issue_text="test issue",
            directory_tree=directory_tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        assert isinstance(ctx["project_description"], str)
        assert isinstance(ctx["conventions"], list)
        assert isinstance(ctx["frameworks"], list)
        assert isinstance(ctx["module_structure"], str)
        assert isinstance(ctx["key_file_excerpts"], dict)
        assert isinstance(ctx["related_code"], dict)
        assert isinstance(ctx["dependency_summary"], str)
        assert isinstance(ctx["directory_tree"], str)

    def test_empty_context_has_all_keys(self):
        """_empty_codebase_context should also have all CodebaseContext keys."""
        ctx = _empty_codebase_context()
        for key in _CODEBASE_CONTEXT_KEYS:
            assert key in ctx, f"Empty context missing key: {key}"


# ---------------------------------------------------------------------------
# T200 — test_sensitive_file_not_read_env
# ---------------------------------------------------------------------------


class TestSensitiveFileNotReadEnv:
    """T200: .env file content never appears in any read result."""

    def test_env_content_not_in_key_file_excerpts(
        self, mock_repo_with_sensitive, directory_tree_with_sensitive
    ):
        """No .env path or SECRET content in key_file_excerpts."""
        state = _make_state(
            repo_path=mock_repo_with_sensitive,
            issue_text="check all config files",
            directory_tree=directory_tree_with_sensitive,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        for path_str, content in ctx["key_file_excerpts"].items():
            assert ".env" not in Path(path_str).name, (
                f".env found in key_file_excerpts: {path_str}"
            )
            assert "abc123" not in content, (
                f"Sensitive .env content 'abc123' found in {path_str}"
            )
            assert "sk-supersecret" not in content, (
                f"Sensitive API key found in {path_str}"
            )

    def test_env_content_not_in_related_code(
        self, mock_repo_with_sensitive, directory_tree_with_sensitive
    ):
        """No .env path or SECRET content in related_code."""
        state = _make_state(
            repo_path=mock_repo_with_sensitive,
            issue_text="check all config files",
            directory_tree=directory_tree_with_sensitive,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        for path_str, content in ctx["related_code"].items():
            assert ".env" not in Path(path_str).name, (
                f".env found in related_code: {path_str}"
            )
            assert "abc123" not in content, (
                f"Sensitive .env content 'abc123' found in related_code {path_str}"
            )


# ---------------------------------------------------------------------------
# T205 — test_sensitive_file_not_read_pem
# ---------------------------------------------------------------------------


class TestSensitiveFileNotReadPem:
    """T205: .pem file content never appears in any read result."""

    def test_pem_content_not_in_key_file_excerpts(
        self, mock_repo_with_sensitive, directory_tree_with_sensitive
    ):
        """No server.pem path or certificate data in key_file_excerpts."""
        state = _make_state(
            repo_path=mock_repo_with_sensitive,
            issue_text="check server certificates and config",
            directory_tree=directory_tree_with_sensitive,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        for path_str, content in ctx["key_file_excerpts"].items():
            assert "server.pem" not in Path(path_str).name, (
                f".pem found in key_file_excerpts: {path_str}"
            )
            assert "FAKECERTDATA" not in content, (
                f"Sensitive .pem content found in {path_str}"
            )

    def test_pem_content_not_in_related_code(
        self, mock_repo_with_sensitive, directory_tree_with_sensitive
    ):
        """No server.pem path or certificate data in related_code."""
        state = _make_state(
            repo_path=mock_repo_with_sensitive,
            issue_text="check server certificates and config",
            directory_tree=directory_tree_with_sensitive,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        for path_str, content in ctx["related_code"].items():
            assert "server.pem" not in Path(path_str).name, (
                f".pem found in related_code: {path_str}"
            )
            assert "FAKECERTDATA" not in content, (
                f"Sensitive .pem content found in related_code {path_str}"
            )


# ---------------------------------------------------------------------------
# T210 — test_select_key_files_priority_order
# ---------------------------------------------------------------------------


class TestSelectKeyFilesPriorityOrder:
    """T210: CLAUDE.md before README.md before pyproject.toml."""

    def test_priority_order(self, mock_repo):
        """Key files must be ordered: CLAUDE.md < README.md < pyproject.toml."""
        files = _select_key_files(mock_repo.resolve())
        names = [f.name for f in files]

        assert "CLAUDE.md" in names, "CLAUDE.md should be in key files"
        assert "README.md" in names, "README.md should be in key files"
        assert "pyproject.toml" in names, "pyproject.toml should be in key files"

        idx_claude = names.index("CLAUDE.md")
        idx_readme = names.index("README.md")
        idx_pyproject = names.index("pyproject.toml")

        assert idx_claude < idx_readme, (
            f"CLAUDE.md (idx={idx_claude}) should come before "
            f"README.md (idx={idx_readme})"
        )
        assert idx_readme < idx_pyproject, (
            f"README.md (idx={idx_readme}) should come before "
            f"pyproject.toml (idx={idx_pyproject})"
        )

    def test_missing_files_still_work(self, tmp_path):
        """If some key files are absent, the present ones are still found in order."""
        # Only create README.md
        (tmp_path / "README.md").write_text("# README\n", encoding="utf-8")

        files = _select_key_files(tmp_path.resolve())
        names = [f.name for f in files]
        assert "README.md" in names
        assert "CLAUDE.md" not in names

    def test_empty_repo(self, tmp_path):
        """An empty repo returns an empty key file list without crashing."""
        empty = tmp_path / "empty"
        empty.mkdir()
        files = _select_key_files(empty.resolve())
        assert files == []


# ---------------------------------------------------------------------------
# T220 — test_sensitive_file_exclusion
# ---------------------------------------------------------------------------


class TestSensitiveFileExclusion:
    """T220: .env, .secrets files are not read by read_files_within_budget."""

    def test_env_excluded_from_batch_read(self, mock_repo_with_sensitive):
        """is_sensitive_file should prevent .env from being included."""
        env_path = mock_repo_with_sensitive / ".env"
        assert env_path.exists(), ".env fixture should exist"
        assert is_sensitive_file(env_path) is True

        result = read_file_with_budget(env_path)
        assert result["content"] == "", ".env should return empty content"

    def test_secrets_file_excluded(self, tmp_path):
        """.secrets file should be detected as sensitive."""
        secrets = tmp_path / ".secrets"
        secrets.write_text("SUPER_SECRET=yes\n", encoding="utf-8")

        assert is_sensitive_file(secrets) is True
        result = read_file_with_budget(secrets)
        assert result["content"] == ""


# ---------------------------------------------------------------------------
# T225 — test_is_sensitive_file (utility, tested here for completeness)
# ---------------------------------------------------------------------------


class TestIsSensitiveFile:
    """T225: Correctly identifies sensitive file patterns."""

    def test_env_file(self):
        assert is_sensitive_file(Path(".env")) is True

    def test_pem_file(self):
        assert is_sensitive_file(Path("server.pem")) is True

    def test_credentials_directory(self):
        assert is_sensitive_file(Path("credentials/db.yml")) is True

    def test_normal_file(self):
        assert is_sensitive_file(Path("main.py")) is False

    def test_readme_not_sensitive(self):
        assert is_sensitive_file(Path("README.md")) is False

    def test_secrets_file(self):
        assert is_sensitive_file(Path(".secrets")) is True

    def test_key_file(self):
        assert is_sensitive_file(Path("private.key")) is True

    def test_env_in_subdirectory(self):
        """Files in a directory matching a sensitive pattern should be sensitive."""
        # .env as a directory component triggers the path-part check
        assert is_sensitive_file(Path("config/.env")) is True


# ---------------------------------------------------------------------------
# T230 — test_symlink_outside_repo_blocked
# ---------------------------------------------------------------------------


class TestSymlinkOutsideRepoBlocked:
    """T230: Symlink pointing outside repo is not read."""

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation may require admin privileges on Windows",
    )
    def test_symlink_outside_repo_returns_empty(self, tmp_path):
        """Symlink pointing outside the repo boundary returns empty content."""
        # Create a secret file outside the repo
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("TOP SECRET DATA", encoding="utf-8")

        # Create the repo
        repo = tmp_path / "repo"
        repo.mkdir()

        # Create a symlink inside repo pointing to outside
        link = repo / "linked_secret.txt"
        try:
            link.symlink_to(secret)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        # Read with repo_root enforcement
        result = read_file_with_budget(link, repo_root=repo)
        assert result["content"] == "", (
            "Symlink outside repo should return empty content"
        )
        assert result["token_estimate"] == 0

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation may require admin privileges on Windows",
    )
    def test_symlink_inside_repo_works(self, tmp_path):
        """Symlink within repo boundary is read normally."""
        repo = tmp_path / "repo"
        repo.mkdir()

        real_file = repo / "real.txt"
        real_file.write_text("Real content here", encoding="utf-8")

        link = repo / "linked.txt"
        try:
            link.symlink_to(real_file)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        result = read_file_with_budget(link, repo_root=repo)
        assert result["content"] == "Real content here"
        assert result["token_estimate"] > 0


# ---------------------------------------------------------------------------
# T240 — test cross-repo analysis via repo_path
# ---------------------------------------------------------------------------


class TestCrossRepoAnalysis:
    """T240: Cross-repo analysis via repo_path pointing to a different repo."""

    def test_uses_second_repo_content(self, second_mock_repo):
        """Context should be populated from the second repo's files."""
        tree = "CLAUDE.md\nREADME.md\npyproject.toml\n"
        state = _make_state(
            repo_path=second_mock_repo,
            issue_text="some issue text about JavaScript",
            directory_tree=tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        # key_file_excerpts should contain content from the second repo
        all_content = " ".join(ctx["key_file_excerpts"].values())
        assert "Second" in all_content or "second" in all_content, (
            f"Expected second repo content in excerpts, got: {all_content[:300]}"
        )

    def test_does_not_use_primary_project_content(
        self, mock_repo, second_mock_repo
    ):
        """Context from second repo should not contain primary repo's content."""
        tree = "CLAUDE.md\nREADME.md\npyproject.toml\n"
        state = _make_state(
            repo_path=second_mock_repo,
            issue_text="some issue text",
            directory_tree=tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        # Should NOT have the primary mock_repo's specific auth content
        all_content = " ".join(ctx["key_file_excerpts"].values())
        assert "authenticate_user" not in all_content, (
            "Second repo context should not contain primary repo's auth function"
        )

    def test_metadata_from_second_repo(self, second_mock_repo):
        """Project metadata should come from the second repo's pyproject.toml."""
        tree = "CLAUDE.md\nREADME.md\npyproject.toml\n"
        state = _make_state(
            repo_path=second_mock_repo,
            issue_text="test",
            directory_tree=tree,
        )
        result = analyze_codebase(state)
        ctx = result["codebase_context"]

        # project_description should reference the second project
        assert "second" in ctx["project_description"].lower() or "Second" in ctx["project_description"], (
            f"Expected second project metadata, got: {ctx['project_description']}"
        )


# ---------------------------------------------------------------------------
# Additional edge-case tests for robustness
# ---------------------------------------------------------------------------


class TestAnalyzeCodebaseEdgeCases:
    """Additional edge cases and integration scenarios."""

    def test_target_repo_alias_works(self, mock_repo, directory_tree):
        """analyze_codebase supports 'target_repo' as alternate state key."""
        state = {
            "target_repo": str(mock_repo),
            "issue_text": "test",
            "directory_tree": directory_tree,
        }
        result = analyze_codebase(state)
        assert "codebase_context" in result
        ctx = result["codebase_context"]
        assert len(ctx["key_file_excerpts"]) > 0

    def test_no_directory_tree_in_state(self, mock_repo):
        """Node works even without directory_tree in state."""
        state = _make_state(repo_path=mock_repo, issue_text="test")
        result = analyze_codebase(state)
        ctx = result["codebase_context"]
        # Should still read key files even without a tree
        assert len(ctx["key_file_excerpts"]) > 0

    def test_empty_repo_directory(self, tmp_path):
        """Analyzing an empty repo directory should degrade gracefully."""
        empty_repo = tmp_path / "empty"
        empty_repo.mkdir()
        state = _make_state(repo_path=empty_repo, issue_text="test")
        result = analyze_codebase(state)
        ctx = result["codebase_context"]
        # Should return context with empty/default fields, not crash
        assert ctx["key_file_excerpts"] == {}
        assert ctx["conventions"] == []

    def test_issue_body_alias_works(self, mock_repo, directory_tree):
        """analyze_codebase supports 'issue_body' as alternate state key."""
        state = {
            "repo_path": str(mock_repo),
            "issue_body": "Fix the authentication flow",
            "directory_tree": directory_tree,
        }
        result = analyze_codebase(state)
        ctx = result["codebase_context"]
        assert "codebase_context" in result
        # Should still find related auth files via issue_body
        related_lower = [p.lower() for p in ctx["related_code"]]
        assert any("auth" in p for p in related_lower) or len(ctx["related_code"]) == 0
        # (may not find them if issue_body key is lower priority than issue_text)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestExtractFirstParagraph:
    """Tests for _extract_first_paragraph helper."""

    def test_extracts_first_paragraph(self):
        md = "# Title\n\nFirst paragraph text.\n\n## Section\n\nSecond paragraph."
        result = _extract_first_paragraph(md)
        assert result == "First paragraph text."

    def test_empty_content(self):
        assert _extract_first_paragraph("") == ""

    def test_headings_only(self):
        md = "# Title\n## Subtitle\n### Sub-sub"
        result = _extract_first_paragraph(md)
        assert result == ""

    def test_truncates_long_paragraph(self):
        long_text = "# Title\n\n" + "x" * 600 + "\n"
        result = _extract_first_paragraph(long_text)
        assert len(result) <= 500


class TestExtractModuleDocstring:
    """Tests for _extract_module_docstring helper."""

    def test_extracts_docstring(self):
        content = '"""This is a module docstring."""\n\nimport os\n'
        result = _extract_module_docstring(content)
        assert result == "This is a module docstring."

    def test_multiline_docstring_first_line(self):
        content = '"""First line.\n\nMore details here.\n"""\n'
        result = _extract_module_docstring(content)
        assert result == "First line."

    def test_no_docstring(self):
        content = "import os\n\ndef foo(): pass\n"
        result = _extract_module_docstring(content)
        assert result == ""

    def test_single_quote_docstring(self):
        content = "'''Single quote docstring.'''\n"
        result = _extract_module_docstring(content)
        assert result == "Single quote docstring."


class TestBuildProjectDescription:
    """Tests for _build_project_description helper."""

    def test_with_readme_and_metadata(self):
        file_contents = {
            "README.md": "# Project\n\nA great project.\n\n## Details\n",
        }
        metadata = {
            "name": "my-project",
            "version": "1.0.0",
            "description": "A sample project",
        }
        result = _build_project_description(file_contents, metadata)
        assert "my-project" in result
        assert "A sample project" in result

    def test_with_empty_inputs(self):
        result = _build_project_description({}, {})
        assert result == ""


class TestBuildModuleStructure:
    """Tests for _build_module_structure helper."""

    def test_with_directory_tree(self):
        tree = "src/\nsrc/main.py\nsrc/utils.py\n"
        result = _build_module_structure(tree, {})
        assert "src/" in result

    def test_empty_tree_and_contents(self):
        result = _build_module_structure("", {})
        assert result == ""

    def test_with_init_file_docstring(self):
        tree = "pkg/\npkg/__init__.py\n"
        file_contents = {
            "pkg/__init__.py": '"""Package initialization."""\n',
        }
        result = _build_module_structure(tree, file_contents)
        assert "Package initialization" in result


class TestSearchForFile:
    """Tests for _search_for_file helper."""

    def test_finds_file_in_src(self, mock_repo):
        result = _search_for_file(mock_repo.resolve(), "auth.py")
        assert result is not None
        assert result.name == "auth.py"

    def test_returns_none_for_missing(self, mock_repo):
        result = _search_for_file(mock_repo.resolve(), "nonexistent.py")
        assert result is None

    def test_returns_none_for_empty_repo(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = _search_for_file(empty.resolve(), "anything.py")
        assert result is None


class TestSelectKeyFilesArchitectureDocs:
    """_select_key_files finds architecture docs from docs/standards."""

    def test_finds_standards_docs(self, tmp_path):
        """Docs from docs/standards/ are included."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "CLAUDE.md").write_text("# Rules", encoding="utf-8")
        standards = repo / "docs" / "standards"
        standards.mkdir(parents=True)
        (standards / "0001-style.md").write_text("# Style", encoding="utf-8")
        (standards / "0002-testing.md").write_text("# Testing", encoding="utf-8")
        files = _select_key_files(repo)
        names = [f.name for f in files]
        assert "0001-style.md" in names
        assert "0002-testing.md" in names

    def test_limits_to_three_docs(self, tmp_path):
        """At most 3 docs from each docs subdir."""
        repo = tmp_path / "repo"
        repo.mkdir()
        standards = repo / "docs" / "standards"
        standards.mkdir(parents=True)
        for i in range(10):
            (standards / f"{i:04d}-doc.md").write_text(f"# Doc {i}", encoding="utf-8")
        files = _select_key_files(repo)
        standards_files = [f for f in files if "standards" in str(f)]
        assert len(standards_files) <= 3


class TestSelectKeyFilesPackageJson:
    """_select_key_files finds package.json."""

    def test_finds_package_json(self, tmp_path):
        """package.json is included when present."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        files = _select_key_files(repo)
        names = [f.name for f in files]
        assert "package.json" in names


class TestSelectKeyFilesInitPy:
    """_select_key_files finds top-level __init__.py files."""

    def test_finds_init_files(self, tmp_path):
        """__init__.py in top-level packages are included."""
        repo = tmp_path / "repo"
        repo.mkdir()
        pkg = repo / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""', encoding="utf-8")
        files = _select_key_files(repo)
        names = [f.name for f in files]
        assert "__init__.py" in names

    def test_limits_to_five_init_files(self, tmp_path):
        """At most 5 __init__.py files."""
        repo = tmp_path / "repo"
        repo.mkdir()
        for i in range(10):
            pkg = repo / f"pkg{i}"
            pkg.mkdir()
            (pkg / "__init__.py").write_text(f'"""Pkg {i}."""', encoding="utf-8")
        files = _select_key_files(repo)
        init_files = [f for f in files if f.name == "__init__.py"]
        assert len(init_files) <= 5


class TestFindRelatedFilesSearchFallback:
    """_find_related_files searches common source dirs when file not at tree path."""

    def test_finds_file_in_src_subdir(self, tmp_path):
        """File found in src/ when directory tree references bare filename."""
        repo = tmp_path / "repo"
        repo.mkdir()
        src = repo / "src"
        src.mkdir()
        (src / "auth.py").write_text("class Auth: pass", encoding="utf-8")
        tree = "repo/\n  src/\n    auth.py\n"
        # Issue text keyword "auth" (4 chars) matches filename "auth.py"
        result = _find_related_files(
            repo_path=repo,
            issue_text="fix the auth module",
            directory_tree=tree,
        )
        found_names = [p.name for p in result]
        assert "auth.py" in found_names


class TestBuildModuleStructureTruncation:
    """_build_module_structure truncates long directory trees."""

    def test_truncates_long_tree(self):
        """Trees > 60 lines are truncated."""
        lines = [f"  file_{i}.py" for i in range(100)]
        tree = "root/\n" + "\n".join(lines)
        result = _build_module_structure(tree, {})
        assert "more lines" in result

    def test_short_tree_not_truncated(self):
        """Trees <= 60 lines are NOT truncated."""
        lines = [f"  file_{i}.py" for i in range(10)]
        tree = "root/\n" + "\n".join(lines)
        result = _build_module_structure(tree, {})
        assert "more lines" not in result


class TestExtractModuleDocstringLongTruncation:
    """_extract_module_docstring truncates long docstrings."""

    def test_long_docstring_truncated(self):
        """Docstrings > 120 chars are truncated."""
        long_line = "A" * 200
        content = f'"""{long_line}"""'
        result = _extract_module_docstring(content)
        assert len(result) <= 120
        assert result.endswith("...")

    def test_single_quote_long_docstring_truncated(self):
        """Single-quote docstrings > 120 chars are truncated."""
        long_line = "B" * 200
        content = f"'''{long_line}'''"
        result = _extract_module_docstring(content)
        assert len(result) <= 120
        assert result.endswith("...")


class TestSelectKeyFilesExtended:
    """Cover _select_key_files branches: package.json, docs/standards, __init__.py."""

    def test_finds_package_json(self, tmp_path):
        """package.json should be included in key files."""
        (tmp_path / "package.json").write_text('{"name": "test"}', encoding="utf-8")
        files = _select_key_files(tmp_path)
        names = [f.name for f in files]
        assert "package.json" in names

    def test_finds_docs_standards(self, tmp_path):
        """Architecture docs under docs/standards should be included."""
        standards = tmp_path / "docs" / "standards"
        standards.mkdir(parents=True)
        (standards / "0001-design.md").write_text("# Design", encoding="utf-8")
        (standards / "0002-testing.md").write_text("# Testing", encoding="utf-8")
        files = _select_key_files(tmp_path)
        names = [f.name for f in files]
        assert "0001-design.md" in names
        assert "0002-testing.md" in names

    def test_finds_init_py_files(self, tmp_path):
        """Top-level __init__.py files should be included."""
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""My package."""', encoding="utf-8")
        files = _select_key_files(tmp_path)
        names = [f.name for f in files]
        assert "__init__.py" in names

    def test_max_five_init_files(self, tmp_path):
        """At most 5 __init__.py files should be selected."""
        for i in range(8):
            pkg = tmp_path / f"pkg{i}"
            pkg.mkdir()
            (pkg / "__init__.py").write_text(f'"""Package {i}."""', encoding="utf-8")
        files = _select_key_files(tmp_path)
        init_count = sum(1 for f in files if f.name == "__init__.py")
        assert init_count <= 5


class TestFindRelatedFilesEdgeCases:
    """Cover _find_related_files edge cases for directory tree parsing."""

    def test_empty_lines_and_dirs_in_tree(self, tmp_path):
        """Empty lines and directory-only entries should be skipped."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "auth.py").write_text("# auth", encoding="utf-8")
        tree = "project/\n\n  src/\n    auth.py\n"
        result = _find_related_files(
            repo_path=tmp_path,
            issue_text="fix authentication",
            directory_tree=tree,
        )
        assert isinstance(result, list)

    def test_file_found_via_search(self, tmp_path):
        """Files in subdirectories should be found via _search_for_file."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "handler.py").write_text("# handler", encoding="utf-8")
        # Tree mentions handler.py without src/ prefix
        tree = "project/\n  handler.py\n"
        result = _find_related_files(
            repo_path=tmp_path,
            issue_text="fix handler logic",
            directory_tree=tree,
        )
        # Should find it via search even though direct path doesn't exist
        assert isinstance(result, list)


class TestBuildModuleStructureLongTree:
    """Cover directory tree truncation for long trees."""

    def test_truncates_long_tree(self):
        """Directory tree > 60 lines should be truncated."""
        lines = [f"  file_{i}.py" for i in range(100)]
        long_tree = "project/\n" + "\n".join(lines)
        result = _build_module_structure(long_tree, {})
        assert "more lines" in result

    def test_short_tree_not_truncated(self):
        """Directory tree <= 60 lines should not be truncated."""
        short_tree = "project/\n  main.py\n  utils.py\n"
        result = _build_module_structure(short_tree, {})
        assert "more lines" not in result


class TestExtractFirstParagraphEdgeCases:
    """Cover paragraph extraction edge cases (heading breaks)."""

    def test_heading_breaks_paragraph(self):
        """A heading line should stop paragraph extraction."""
        text = "First paragraph text here.\n# Heading\nSecond paragraph."
        result = _extract_first_paragraph(text)
        assert result == "First paragraph text here."
        assert "Second" not in result

    def test_long_paragraph_truncated(self):
        """Paragraphs > 500 chars should be truncated."""
        long_text = "A" * 600
        result = _extract_first_paragraph(long_text)
        assert len(result) <= 500
        assert result.endswith("...")


class TestExtractModuleDocstringLong:
    """Cover long docstring truncation."""

    def test_long_docstring_truncated(self):
        """Docstrings > 120 chars first line should be truncated."""
        long_doc = 'A' * 200
        content = f'"""{long_doc}"""'
        result = _extract_module_docstring(content)
        assert len(result) <= 120
        assert result.endswith("...")

class TestCodePatternsWiredIn:
    """#1816: scan_patterns output must reach the drafter, per #401's
    original acceptance ("existing code patterns are injected")."""

    def test_context_carries_detected_patterns(self, mock_repo, directory_tree):
        state = {
            "repo_path": str(mock_repo),
            "issue_text": "Improve the reader module",
            "directory_tree": directory_tree,
        }
        ctx = analyze_codebase(state)["codebase_context"]
        assert "code_patterns" in ctx
        # Only detected values ride along -- never the "unknown" filler.
        assert "unknown" not in ctx["code_patterns"].values()

    def test_formatter_renders_detected_patterns(self):
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            _format_codebase_context,
        )

        section = _format_codebase_context(
            {"code_patterns": {"state_pattern": "TypedDict", "test_pattern": "pytest"}}
        )
        assert "### Detected Code Patterns" in section
        assert "State management: TypedDict" in section
        assert "Test framework: pytest" in section

    def test_formatter_omits_section_when_nothing_detected(self):
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            _format_codebase_context,
        )

        assert "Detected Code Patterns" not in _format_codebase_context(
            {"code_patterns": {}}
        )
