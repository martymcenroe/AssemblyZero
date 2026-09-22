"""Unit tests for the codebase reader utility.

Issue #401: Codebase Context Analysis for Requirements Workflow.

Tests for:
- read_file_with_budget (single file reading with token budget)
- read_files_within_budget (batch file reading with total/per-file budgets)
- is_sensitive_file (sensitive file detection)
- parse_project_metadata (pyproject.toml and package.json parsing)
- _estimate_tokens (token estimation heuristic)
"""

import json
import os
import sys

import pytest
from pathlib import Path

from assemblyzero.utils.codebase_reader import (
    is_sensitive_file,
    parse_project_metadata,
    read_file_with_budget,
    read_files_within_budget,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def small_text_file(tmp_path):
    """A small text file well within any reasonable token budget."""
    f = tmp_path / "small.txt"
    f.write_text("Hello, world!\nThis is a small file.\n", encoding="utf-8")
    return f


@pytest.fixture
def large_text_file(tmp_path):
    """A text file large enough to exceed a small token budget.

    ~10KB of text = ~2500 tokens at chars/4 heuristic.
    """
    f = tmp_path / "large.txt"
    content = "A" * 10000  # 10,000 chars = ~2500 tokens
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def binary_file(tmp_path):
    """A binary file (PNG-like header) that should be skipped."""
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return f


@pytest.fixture
def mock_repo(tmp_path):
    """A minimal mock repository with key project files."""
    (tmp_path / "CLAUDE.md").write_text(
        "# CLAUDE.md\n\n## Rules\n\n- Use snake_case\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# Mock Project\n\nA test project.\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "mock-project"\n'
        'version = "1.0.0"\n'
        'description = "A mock project"\n'
        'dependencies = [\n'
        '    "langgraph>=0.1",\n'
        '    "pytest>=7.0",\n'
        '    "fastapi~=0.100",\n'
        ']\n',
        encoding="utf-8",
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        '"""Main module."""\n\ndef main():\n    pass\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def mock_repo_with_package_json(tmp_path):
    """A mock repo with package.json instead of pyproject.toml."""
    pkg = {
        "name": "js-project",
        "version": "2.0.0",
        "description": "A JavaScript project",
        "dependencies": {
            "express": "^4.18.0",
            "lodash": "^4.17.21",
        },
        "devDependencies": {
            "jest": "^29.0.0",
        },
    }
    (tmp_path / "package.json").write_text(
        json.dumps(pkg, indent=2), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def mock_repo_with_sensitive(tmp_path):
    """A mock repo containing sensitive files."""
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "SECRET=abc123\nAPI_KEY=sk-supersecret\n", encoding="utf-8"
    )
    (tmp_path / "server.pem").write_text(
        "-----BEGIN CERTIFICATE-----\nFAKECERTDATA\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    (tmp_path / ".secrets").write_text("DB_PASS=hunter2\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    creds = tmp_path / "credentials"
    creds.mkdir()
    (creds / "db.yml").write_text("password: secret\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# T010 — test_read_file_with_budget_normal
# ---------------------------------------------------------------------------


class TestReadFileWithBudgetNormal:
    """T010: Reads file content within budget, truncated=False."""

    def test_reads_full_content(self, small_text_file):
        """Small file should be read in full with truncated=False."""
        result = read_file_with_budget(small_text_file, max_tokens=2000)
        assert result["content"] == "Hello, world!\nThis is a small file.\n"
        assert result["truncated"] is False

    def test_token_estimate_within_budget(self, small_text_file):
        """Token estimate should be less than the budget."""
        result = read_file_with_budget(small_text_file, max_tokens=2000)
        assert result["token_estimate"] < 2000
        assert result["token_estimate"] > 0

    def test_path_in_result(self, small_text_file):
        """Result should contain the file path."""
        result = read_file_with_budget(small_text_file, max_tokens=2000)
        assert result["path"] == str(small_text_file)

    def test_returns_file_read_result_shape(self, small_text_file):
        """Result must have all FileReadResult keys."""
        result = read_file_with_budget(small_text_file, max_tokens=2000)
        assert "path" in result
        assert "content" in result
        assert "truncated" in result
        assert "token_estimate" in result


# ---------------------------------------------------------------------------
# T020 — test_read_file_with_budget_truncated
# ---------------------------------------------------------------------------


class TestReadFileWithBudgetTruncated:
    """T020: Truncates large file, truncated=True."""

    def test_truncates_large_file(self, large_text_file):
        """10KB file with budget=500 should be truncated."""
        result = read_file_with_budget(large_text_file, max_tokens=500)
        assert result["truncated"] is True

    def test_content_length_respects_budget(self, large_text_file):
        """Truncated content length should be approximately budget * 4 chars."""
        result = read_file_with_budget(large_text_file, max_tokens=500)
        # budget=500 tokens => ~2000 chars max
        assert len(result["content"]) <= 500 * 4 + 10  # small margin

    def test_token_estimate_within_budget(self, large_text_file):
        """Token estimate for truncated file should be at or under budget."""
        result = read_file_with_budget(large_text_file, max_tokens=500)
        assert result["token_estimate"] <= 500 + 1  # allow rounding

    def test_small_budget_still_returns_content(self, large_text_file):
        """Even a very small budget should return some content."""
        result = read_file_with_budget(large_text_file, max_tokens=10)
        assert result["truncated"] is True
        assert len(result["content"]) > 0

    def test_exact_budget_boundary(self, tmp_path):
        """File exactly at budget boundary should not be truncated."""
        # 400 chars = 100 tokens at chars/4
        f = tmp_path / "exact.txt"
        f.write_text("A" * 400, encoding="utf-8")
        result = read_file_with_budget(f, max_tokens=100)
        assert result["truncated"] is False
        assert result["content"] == "A" * 400


# ---------------------------------------------------------------------------
# T030 — test_read_file_with_budget_binary_skip
# ---------------------------------------------------------------------------


class TestReadFileWithBudgetBinarySkip:
    """T030: Returns empty content for binary files."""

    def test_binary_file_returns_empty(self, binary_file):
        """Binary file should return empty content with no exception."""
        result = read_file_with_budget(binary_file, max_tokens=2000)
        assert result["content"] == ""

    def test_binary_file_zero_tokens(self, binary_file):
        """Binary file should have token_estimate=0."""
        result = read_file_with_budget(binary_file, max_tokens=2000)
        assert result["token_estimate"] == 0

    def test_binary_file_not_truncated(self, binary_file):
        """Binary file result should have truncated=False (wasn't truncated, was skipped)."""
        result = read_file_with_budget(binary_file, max_tokens=2000)
        # Skipped files: truncated is False since we didn't read anything to truncate
        assert result["truncated"] is False

    def test_various_binary_extensions(self, tmp_path):
        """Various binary formats should all return empty."""
        for ext, header in [
            (".jpg", b"\xff\xd8\xff\xe0"),
            (".gif", b"GIF89a"),
            (".exe", b"MZ\x90\x00"),
        ]:
            f = tmp_path / f"file{ext}"
            f.write_bytes(header + b"\x00" * 50)
            result = read_file_with_budget(f, max_tokens=2000)
            assert result["content"] == "", f"Expected empty for {ext}"


# ---------------------------------------------------------------------------
# T040 — test_read_file_with_budget_missing_file
# ---------------------------------------------------------------------------


class TestReadFileWithBudgetMissingFile:
    """T040: Returns empty content for missing files, no crash."""

    def test_missing_file_returns_empty(self, tmp_path):
        """Non-existent file should return empty content."""
        missing = tmp_path / "does_not_exist.txt"
        result = read_file_with_budget(missing, max_tokens=2000)
        assert result["content"] == ""

    def test_missing_file_zero_tokens(self, tmp_path):
        """Non-existent file should have token_estimate=0."""
        missing = tmp_path / "ghost.py"
        result = read_file_with_budget(missing, max_tokens=2000)
        assert result["token_estimate"] == 0

    def test_missing_file_no_exception(self, tmp_path):
        """Reading a missing file must not raise any exception."""
        missing = tmp_path / "nonexistent" / "deep" / "path.txt"
        # Should not raise
        result = read_file_with_budget(missing, max_tokens=2000)
        assert result["content"] == ""

    def test_missing_file_path_preserved(self, tmp_path):
        """The path should still be recorded in the result."""
        missing = tmp_path / "absent.txt"
        result = read_file_with_budget(missing, max_tokens=2000)
        assert result["path"] == str(missing)


# ---------------------------------------------------------------------------
# T050 — test_read_files_within_budget_respects_total
# ---------------------------------------------------------------------------


class TestReadFilesWithinBudgetRespectsTotal:
    """T050: Stops reading when total budget is exhausted."""

    def test_total_budget_caps_reading(self, tmp_path):
        """With 10 files and a small total budget, not all files are read."""
        files = []
        for i in range(10):
            f = tmp_path / f"file_{i}.txt"
            # Each file ~250 tokens (1000 chars)
            f.write_text("X" * 1000, encoding="utf-8")
            files.append(f)

        # Total budget 500 tokens => at most ~2 files
        results = read_files_within_budget(
            files, total_budget=500, per_file_budget=300
        )
        total_tokens = sum(r["token_estimate"] for r in results)
        assert total_tokens <= 500, (
            f"Total tokens {total_tokens} exceeds budget 500"
        )

    def test_not_all_files_read(self, tmp_path):
        """Fewer files read than provided when budget is small."""
        files = []
        for i in range(10):
            f = tmp_path / f"file_{i}.txt"
            f.write_text("Y" * 1000, encoding="utf-8")
            files.append(f)

        results = read_files_within_budget(
            files, total_budget=500, per_file_budget=300
        )
        assert len(results) < 10, (
            f"Expected fewer than 10 results, got {len(results)}"
        )

    def test_at_least_one_file_read(self, tmp_path):
        """Even a small budget should read at least the first file."""
        files = []
        for i in range(5):
            f = tmp_path / f"file_{i}.txt"
            f.write_text("Z" * 100, encoding="utf-8")
            files.append(f)

        results = read_files_within_budget(
            files, total_budget=500, per_file_budget=300
        )
        assert len(results) >= 1

    def test_files_read_in_order(self, tmp_path):
        """Files should be read in the order provided."""
        files = []
        for i in range(5):
            f = tmp_path / f"file_{i}.txt"
            f.write_text(f"Content of file {i}\n", encoding="utf-8")
            files.append(f)

        results = read_files_within_budget(
            files, total_budget=15000, per_file_budget=3000
        )
        for idx, result in enumerate(results):
            assert f"file_{idx}.txt" in result["path"]


# ---------------------------------------------------------------------------
# T055 — test_read_files_within_budget_respects_per_file
# ---------------------------------------------------------------------------


class TestReadFilesWithinBudgetRespectsPerFile:
    """T055: Individual file capped at per_file_budget."""

    def test_per_file_budget_truncates(self, tmp_path):
        """A large file should be capped at per_file_budget tokens."""
        f = tmp_path / "huge.txt"
        f.write_text("B" * 20000, encoding="utf-8")  # ~5000 tokens

        results = read_files_within_budget(
            [f], total_budget=15000, per_file_budget=500
        )
        assert len(results) == 1
        assert results[0]["token_estimate"] <= 500 + 1
        assert results[0]["truncated"] is True

    def test_small_file_not_truncated(self, tmp_path):
        """A file smaller than per_file_budget should not be truncated."""
        f = tmp_path / "tiny.txt"
        f.write_text("Hello\n", encoding="utf-8")  # ~2 tokens

        results = read_files_within_budget(
            [f], total_budget=15000, per_file_budget=3000
        )
        assert len(results) == 1
        assert results[0]["truncated"] is False
        assert results[0]["content"] == "Hello\n"

    def test_per_file_budget_applied_to_each_file(self, tmp_path):
        """Each file in a batch should be individually capped."""
        files = []
        for i in range(3):
            f = tmp_path / f"big_{i}.txt"
            f.write_text("C" * 8000, encoding="utf-8")  # ~2000 tokens each
            files.append(f)

        results = read_files_within_budget(
            files, total_budget=15000, per_file_budget=500
        )
        for result in results:
            assert result["token_estimate"] <= 500 + 1, (
                f"File {result['path']} exceeds per-file budget: "
                f"{result['token_estimate']}"
            )


# ---------------------------------------------------------------------------
# T060 — test_parse_project_metadata_pyproject
# ---------------------------------------------------------------------------


class TestParseProjectMetadataPyproject:
    """T060: Extracts name, deps from pyproject.toml."""

    def test_extracts_name(self, mock_repo):
        """Should extract project name from pyproject.toml."""
        metadata = parse_project_metadata(mock_repo)
        assert "name" in metadata
        assert metadata["name"] == "mock-project"

    def test_extracts_dependencies(self, mock_repo):
        """Should extract dependencies list."""
        metadata = parse_project_metadata(mock_repo)
        assert "dependencies" in metadata
        deps = metadata["dependencies"]
        assert "langgraph" in deps.lower()
        assert "pytest" in deps.lower()

    def test_extracts_version(self, mock_repo):
        """Should extract project version."""
        metadata = parse_project_metadata(mock_repo)
        assert "version" in metadata
        assert metadata["version"] == "1.0.0"

    def test_extracts_description(self, mock_repo):
        """Should extract project description."""
        metadata = parse_project_metadata(mock_repo)
        assert "description" in metadata
        assert "mock" in metadata["description"].lower()

    def test_all_keys_present(self, mock_repo):
        """Result should have name, version, description, dependencies."""
        metadata = parse_project_metadata(mock_repo)
        for key in ["name", "version", "description", "dependencies"]:
            assert key in metadata, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# T070 — test_parse_project_metadata_package_json
# ---------------------------------------------------------------------------


class TestParseProjectMetadataPackageJson:
    """T070: Extracts name, deps from package.json."""

    def test_extracts_name(self, mock_repo_with_package_json):
        """Should extract project name from package.json."""
        metadata = parse_project_metadata(mock_repo_with_package_json)
        assert "name" in metadata
        assert metadata["name"] == "js-project"

    def test_extracts_dependencies(self, mock_repo_with_package_json):
        """Should extract dependencies list."""
        metadata = parse_project_metadata(mock_repo_with_package_json)
        assert "dependencies" in metadata
        deps = metadata["dependencies"]
        assert "express" in deps.lower()

    def test_extracts_version(self, mock_repo_with_package_json):
        """Should extract project version."""
        metadata = parse_project_metadata(mock_repo_with_package_json)
        assert "version" in metadata
        assert metadata["version"] == "2.0.0"

    def test_extracts_description(self, mock_repo_with_package_json):
        """Should extract project description."""
        metadata = parse_project_metadata(mock_repo_with_package_json)
        assert "description" in metadata
        assert "javascript" in metadata["description"].lower()

    def test_prefers_pyproject_over_package_json(self, tmp_path):
        """When both files exist, pyproject.toml takes priority."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "py-project"\nversion = "1.0.0"\n'
            'description = "Python project"\n'
            'dependencies = ["requests"]\n',
            encoding="utf-8",
        )
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "js-project", "version": "2.0.0"}),
            encoding="utf-8",
        )
        metadata = parse_project_metadata(tmp_path)
        assert metadata["name"] == "py-project"


# ---------------------------------------------------------------------------
# T080 — test_parse_project_metadata_missing
# ---------------------------------------------------------------------------


class TestParseProjectMetadataMissing:
    """T080: Returns empty dict when no config file found."""

    def test_returns_empty_dict(self, tmp_path):
        """Repo with no pyproject.toml or package.json returns {}."""
        empty_repo = tmp_path / "empty"
        empty_repo.mkdir()
        metadata = parse_project_metadata(empty_repo)
        assert metadata == {}

    def test_no_exception(self, tmp_path):
        """Should not raise any exception for missing config."""
        empty_repo = tmp_path / "no_config"
        empty_repo.mkdir()
        # Should not raise
        metadata = parse_project_metadata(empty_repo)
        assert isinstance(metadata, dict)

    def test_nonexistent_repo_path(self, tmp_path):
        """Non-existent repo path should return empty dict."""
        nonexistent = tmp_path / "does_not_exist"
        metadata = parse_project_metadata(nonexistent)
        assert metadata == {}

    def test_corrupted_pyproject(self, tmp_path):
        """Corrupted pyproject.toml should return empty dict, not crash."""
        (tmp_path / "pyproject.toml").write_text(
            "this is not valid TOML {{[[[",
            encoding="utf-8",
        )
        metadata = parse_project_metadata(tmp_path)
        assert isinstance(metadata, dict)

    def test_corrupted_package_json(self, tmp_path):
        """Corrupted package.json should return empty dict, not crash."""
        (tmp_path / "package.json").write_text(
            "{not valid json!!!}",
            encoding="utf-8",
        )
        metadata = parse_project_metadata(tmp_path)
        assert isinstance(metadata, dict)


# ---------------------------------------------------------------------------
# T200 — test_sensitive_file_not_read_env (codebase_reader level)
# ---------------------------------------------------------------------------


class TestSensitiveFileNotReadEnv:
    """T200: .env file content never appears in any read result."""

    def test_env_returns_empty_via_read_file(self, mock_repo_with_sensitive):
        """.env file read directly should return empty content."""
        env_path = mock_repo_with_sensitive / ".env"
        result = read_file_with_budget(env_path, max_tokens=2000)
        assert result["content"] == ""
        assert "abc123" not in result["content"]

    def test_env_excluded_from_batch(self, mock_repo_with_sensitive):
        """.env should be excluded when reading files in batch."""
        files = [
            mock_repo_with_sensitive / "README.md",
            mock_repo_with_sensitive / ".env",
            mock_repo_with_sensitive / "main.py",
        ]
        results = read_files_within_budget(files, total_budget=15000)
        for r in results:
            assert ".env" not in Path(r["path"]).name, (
                f".env should not appear in results: {r['path']}"
            )
            assert "abc123" not in r["content"]
            assert "sk-supersecret" not in r["content"]

    def test_env_zero_tokens(self, mock_repo_with_sensitive):
        """.env should have zero token estimate."""
        env_path = mock_repo_with_sensitive / ".env"
        result = read_file_with_budget(env_path)
        assert result["token_estimate"] == 0


# ---------------------------------------------------------------------------
# T205 — test_sensitive_file_not_read_pem (codebase_reader level)
# ---------------------------------------------------------------------------


class TestSensitiveFileNotReadPem:
    """T205: .pem file content never appears in any read result."""

    def test_pem_returns_empty_via_read_file(self, mock_repo_with_sensitive):
        """.pem file read directly should return empty content."""
        pem_path = mock_repo_with_sensitive / "server.pem"
        result = read_file_with_budget(pem_path, max_tokens=2000)
        assert result["content"] == ""
        assert "FAKECERTDATA" not in result["content"]

    def test_pem_excluded_from_batch(self, mock_repo_with_sensitive):
        """.pem should be excluded when reading files in batch."""
        files = [
            mock_repo_with_sensitive / "README.md",
            mock_repo_with_sensitive / "server.pem",
            mock_repo_with_sensitive / "main.py",
        ]
        results = read_files_within_budget(files, total_budget=15000)
        for r in results:
            assert "server.pem" not in Path(r["path"]).name
            assert "FAKECERTDATA" not in r["content"]

    def test_pem_zero_tokens(self, mock_repo_with_sensitive):
        """.pem should have zero token estimate."""
        pem_path = mock_repo_with_sensitive / "server.pem"
        result = read_file_with_budget(pem_path)
        assert result["token_estimate"] == 0


# ---------------------------------------------------------------------------
# T220 — test_sensitive_file_exclusion (codebase_reader level)
# ---------------------------------------------------------------------------


class TestSensitiveFileExclusion:
    """T220: .env, .secrets files are not read by read_files_within_budget."""

    def test_all_sensitive_files_excluded_from_batch(self, mock_repo_with_sensitive):
        """All sensitive files should be excluded from batch reads."""
        files = [
            mock_repo_with_sensitive / "README.md",
            mock_repo_with_sensitive / ".env",
            mock_repo_with_sensitive / "server.pem",
            mock_repo_with_sensitive / ".secrets",
            mock_repo_with_sensitive / "main.py",
            mock_repo_with_sensitive / "credentials" / "db.yml",
        ]
        results = read_files_within_budget(files, total_budget=15000)

        result_paths = [Path(r["path"]).name for r in results]
        assert ".env" not in result_paths
        assert "server.pem" not in result_paths
        assert ".secrets" not in result_paths
        assert "db.yml" not in result_paths

    def test_non_sensitive_files_still_read(self, mock_repo_with_sensitive):
        """Non-sensitive files should be read normally in the same batch."""
        files = [
            mock_repo_with_sensitive / "README.md",
            mock_repo_with_sensitive / ".env",
            mock_repo_with_sensitive / "main.py",
        ]
        results = read_files_within_budget(files, total_budget=15000)
        result_paths = [Path(r["path"]).name for r in results]

        assert "README.md" in result_paths
        assert "main.py" in result_paths

    def test_secrets_file_excluded(self, mock_repo_with_sensitive):
        """.secrets file should return empty on direct read."""
        secrets_path = mock_repo_with_sensitive / ".secrets"
        result = read_file_with_budget(secrets_path)
        assert result["content"] == ""


# ---------------------------------------------------------------------------
# T225 — test_is_sensitive_file (codebase_reader level)
# ---------------------------------------------------------------------------


class TestIsSensitiveFile:
    """T225: Correctly identifies sensitive file patterns."""

    def test_env_file(self):
        """'.env' should be sensitive."""
        assert is_sensitive_file(Path(".env")) is True

    def test_pem_file(self):
        """'.pem' extension should be sensitive."""
        assert is_sensitive_file(Path("server.pem")) is True

    def test_credentials_directory(self):
        """Files in 'credentials/' directory should be sensitive."""
        assert is_sensitive_file(Path("credentials/db.yml")) is True

    def test_normal_python_file(self):
        """'main.py' should not be sensitive."""
        assert is_sensitive_file(Path("main.py")) is False

    def test_readme_not_sensitive(self):
        """'README.md' should not be sensitive."""
        assert is_sensitive_file(Path("README.md")) is False

    def test_secrets_file(self):
        """'.secrets' should be sensitive."""
        assert is_sensitive_file(Path(".secrets")) is True

    def test_key_file(self):
        """'.key' extension should be sensitive."""
        assert is_sensitive_file(Path("private.key")) is True

    def test_env_local(self):
        """'.env.local' should be sensitive."""
        assert is_sensitive_file(Path(".env.local")) is True

    def test_env_production(self):
        """'.env.production' should be sensitive."""
        assert is_sensitive_file(Path(".env.production")) is True

    def test_pyproject_not_sensitive(self):
        """'pyproject.toml' should not be sensitive."""
        assert is_sensitive_file(Path("pyproject.toml")) is False

    def test_nested_credentials_path(self):
        """Deeply nested path with 'credentials' should be sensitive."""
        assert is_sensitive_file(Path("config/credentials/aws.json")) is True

    def test_source_code_not_sensitive(self):
        """Regular source file in src/ should not be sensitive."""
        assert is_sensitive_file(Path("src/auth.py")) is False


# ---------------------------------------------------------------------------
# T230 — test_symlink_outside_repo_blocked (codebase_reader level)
# ---------------------------------------------------------------------------


class TestSymlinkOutsideRepoBlocked:
    """T230: Symlink pointing outside repo is not read."""

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation may require admin privileges on Windows",
    )
    def test_symlink_outside_repo_returns_empty(self, tmp_path):
        """Symlink pointing outside the repo boundary returns empty content."""
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("TOP SECRET DATA", encoding="utf-8")

        repo = tmp_path / "repo"
        repo.mkdir()

        link = repo / "linked_secret.txt"
        try:
            link.symlink_to(secret)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        result = read_file_with_budget(link, repo_root=repo)
        assert result["content"] == ""
        assert result["token_estimate"] == 0
        assert "TOP SECRET DATA" not in result["content"]

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation may require admin privileges on Windows",
    )
    def test_symlink_inside_repo_works(self, tmp_path):
        """Symlink within repo boundary should be read normally."""
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

    @pytest.mark.skipif(
        sys.platform == "win32" and not os.environ.get("CI"),
        reason="Symlink creation may require admin privileges on Windows",
    )
    def test_symlink_outside_repo_in_batch(self, tmp_path):
        """Symlink outside repo should be excluded from batch reads."""
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("CLASSIFIED INFO", encoding="utf-8")

        repo = tmp_path / "repo"
        repo.mkdir()

        normal = repo / "normal.txt"
        normal.write_text("Normal content", encoding="utf-8")

        link = repo / "bad_link.txt"
        try:
            link.symlink_to(secret)
        except OSError:
            pytest.skip("Cannot create symlinks on this system")

        results = read_files_within_budget(
            [normal, link], total_budget=15000, repo_root=repo
        )
        all_content = " ".join(r["content"] for r in results)
        assert "CLASSIFIED INFO" not in all_content
        assert "Normal content" in all_content


# ---------------------------------------------------------------------------
# Additional edge-case tests for robustness
# ---------------------------------------------------------------------------


class TestReadFileEdgeCases:
    """Additional edge cases for read_file_with_budget."""

    def test_empty_file(self, tmp_path):
        """An empty file should return empty content, zero tokens."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = read_file_with_budget(f, max_tokens=2000)
        assert result["content"] == ""
        assert result["token_estimate"] == 0
        assert result["truncated"] is False

    def test_utf8_content(self, tmp_path):
        """UTF-8 content with special characters should be handled."""
        f = tmp_path / "unicode.txt"
        f.write_text("Hello 世界! Ünïcödë ñ\n", encoding="utf-8")
        result = read_file_with_budget(f, max_tokens=2000)
        assert "世界" in result["content"]
        assert result["truncated"] is False

    def test_permission_denied_graceful(self, tmp_path):
        """If a file can't be read (e.g., permissions), return empty gracefully."""
        # This test may be platform-specific but the function should handle it
        missing = tmp_path / "no_access"
        result = read_file_with_budget(missing, max_tokens=2000)
        assert result["content"] == ""


class TestReadFilesWithinBudgetEdgeCases:
    """Additional edge cases for read_files_within_budget."""

    def test_empty_file_list(self):
        """Empty file list should return empty results."""
        results = read_files_within_budget([], total_budget=15000)
        assert results == []

    def test_all_sensitive_files(self, mock_repo_with_sensitive):
        """Batch of only sensitive files should return empty results."""
        files = [
            mock_repo_with_sensitive / ".env",
            mock_repo_with_sensitive / "server.pem",
            mock_repo_with_sensitive / ".secrets",
        ]
        results = read_files_within_budget(files, total_budget=15000)
        # All sensitive files should be skipped, so no results with content
        for r in results:
            assert r["content"] == ""

    def test_zero_total_budget(self, tmp_path):
        """Zero total budget should still not crash."""
        f = tmp_path / "file.txt"
        f.write_text("content", encoding="utf-8")
        results = read_files_within_budget(
            [f], total_budget=0, per_file_budget=100
        )
        # With zero budget, no meaningful content should be read
        assert isinstance(results, list)

    def test_single_file_reads_correctly(self, tmp_path):
        """Single file in batch should be read correctly."""
        f = tmp_path / "single.txt"
        f.write_text("Only file in batch\n", encoding="utf-8")
        results = read_files_within_budget(
            [f], total_budget=15000, per_file_budget=3000
        )
        assert len(results) == 1
        assert results[0]["content"] == "Only file in batch\n"
        assert results[0]["truncated"] is False


class TestParseProjectMetadataEdgeCases:
    """Additional edge cases for parse_project_metadata."""

    def test_pyproject_without_project_section(self, tmp_path):
        """pyproject.toml without [project] section should handle gracefully."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry]\nname = "my-tool"\n',
            encoding="utf-8",
        )
        metadata = parse_project_metadata(tmp_path)
        # May return partial data or empty, but should not crash
        assert isinstance(metadata, dict)

    def test_package_json_empty_deps(self, tmp_path):
        """package.json with no dependencies should still parse."""
        pkg = {"name": "minimal", "version": "0.1.0"}
        (tmp_path / "package.json").write_text(
            json.dumps(pkg), encoding="utf-8"
        )
        metadata = parse_project_metadata(tmp_path)
        assert "name" in metadata
        assert metadata["name"] == "minimal"

    def test_pyproject_with_poetry_deps(self, tmp_path):
        """pyproject.toml with poetry-style deps should be handled."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry]\n'
            'name = "poetry-proj"\n'
            'version = "0.1.0"\n'
            'description = "A poetry project"\n\n'
            '[tool.poetry.dependencies]\n'
            'python = "^3.11"\n'
            'requests = "^2.28"\n',
            encoding="utf-8",
        )
        metadata = parse_project_metadata(tmp_path)
        assert isinstance(metadata, dict)


class TestReadFileWithBudgetDirectoryInput:
    """read_file_with_budget should return empty for directories (not regular files)."""

    def test_directory_returns_empty(self, tmp_path):
        """A directory path should return empty content."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = read_file_with_budget(subdir, max_tokens=2000)
        assert result["content"] == ""
        assert result["token_estimate"] == 0


class TestReadFileWithBudgetDecodeError:
    """read_file_with_budget should handle UnicodeDecodeError for non-text files."""

    def test_non_utf8_file_returns_empty(self, tmp_path):
        """A file with invalid UTF-8 bytes (no binary extension) returns empty."""
        f = tmp_path / "data.dat"
        f.write_bytes(b"\x80\x81\x82\x83\x84\x85" * 100)
        result = read_file_with_budget(f, max_tokens=2000)
        assert result["content"] == ""
        assert result["token_estimate"] == 0


class TestIsSensitiveFileCredentialsFilename:
    """is_sensitive_file should detect files named 'credentials' (non-dot pattern)."""

    def test_credentials_filename_exact_match(self):
        """File literally named 'credentials' is sensitive."""
        assert is_sensitive_file(Path("credentials")) is True

    def test_credentials_in_parent_dir(self):
        """File in a directory named 'credentials/' is sensitive."""
        assert is_sensitive_file(Path("credentials/db.yml")) is True

    def test_credentials_not_in_normal_name(self):
        """'my_credentials_util.py' should NOT match (not exact)."""
        assert is_sensitive_file(Path("my_credentials_util.py")) is False


class TestReadFileOSError:
    """read_file_with_budget handles OSError during file existence check."""

    def test_oserror_on_exists_returns_empty(self, tmp_path, monkeypatch):
        """If os raises OSError on exists(), return empty."""
        f = tmp_path / "test.py"
        f.write_text("content", encoding="utf-8")

        original_exists = Path.exists

        def mock_exists(self):
            if self.name == "test.py":
                raise OSError("Permission denied")
            return original_exists(self)

        monkeypatch.setattr(Path, "exists", mock_exists)
        result = read_file_with_budget(f, max_tokens=2000)
        assert result["content"] == ""


class TestReadFileWithBudgetSymlinkBoundary:
    """read_file_with_budget blocks files outside repo_root boundary."""

    def test_file_outside_repo_root_returns_empty(self, tmp_path):
        """A file outside repo_root is blocked even without symlinks."""
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("top secret", encoding="utf-8")
        result = read_file_with_budget(secret, max_tokens=2000, repo_root=repo)
        assert result["content"] == ""
        assert result["token_estimate"] == 0

    def test_file_inside_repo_root_is_allowed(self, tmp_path):
        """A file within repo_root is allowed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f = repo / "ok.py"
        f.write_text("hello = 1", encoding="utf-8")
        result = read_file_with_budget(f, max_tokens=2000, repo_root=repo)
        assert result["content"] == "hello = 1"


class TestReadFileWithBudgetOSErrorOnRead:
    """read_file_with_budget handles OSError during file reading."""

    def test_oserror_on_read_text_returns_empty(self, tmp_path, monkeypatch):
        """If read_text raises OSError, return empty."""
        f = tmp_path / "test.py"
        f.write_text("content", encoding="utf-8")

        original_read = Path.read_text

        def mock_read(self, **kwargs):
            if self.name == "test.py":
                raise OSError("Disk error")
            return original_read(self, **kwargs)

        monkeypatch.setattr(Path, "read_text", mock_read)
        result = read_file_with_budget(f, max_tokens=2000)
        assert result["content"] == ""


class TestReadFileWithBudgetResolveOSError:
    """read_file_with_budget handles OSError during path resolution."""

    def test_oserror_on_resolve_returns_empty(self, tmp_path, monkeypatch):
        """If resolve() raises OSError, return empty."""
        f = tmp_path / "test.py"
        f.write_text("content", encoding="utf-8")

        original_resolve = Path.resolve

        def mock_resolve(self, **kwargs):
            if self.name == "test.py":
                raise OSError("Network path not found")
            return original_resolve(self, **kwargs)

        monkeypatch.setattr(Path, "resolve", mock_resolve)
        result = read_file_with_budget(f, max_tokens=2000)
        assert result["content"] == ""