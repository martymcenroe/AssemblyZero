"""
Tests for new-repo-setup.py schema-driven project structure.

Per LLD-099: 19 test scenarios (T010-T190) for schema loading, flattening,
auditing, security validation, and structure creation.

Issue: #99
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from new_repo import (
    PROJECT_TYPES,
    SchemaValidationError,
    _project_specific_context,
    audit_project_structure,
    create_claude_md,
    create_structure,
    flatten_directories,
    flatten_files,
    load_structure_schema,
    main,
    validate_name,
    validate_paths_no_traversal,
    validate_template_files_exist,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# #1934 / standard 0024: the I/O BOUNDARY is what gets patched -- subprocess.run,
# requests.get, the PAT session. What those boundaries RETURN is ordinary data,
# and standing a MagicMock in for it is the hasattr placebo from the standard's
# §2: a MagicMock answers `.stdout`, `.ok`, `.anything` truthfully, so a test
# written against one verifies the mock's willingness to invent attributes
# rather than the code's handling of a real result.


# mock-ok: `new_repo.run_command` shells out to poetry, git and gh -- real
#   subprocess execution against a real GitHub account is not a unit test.
# mock-ok: `new_repo.requests.get` and `new_repo._request_with_retry` are
#   network calls to the GitHub REST API.
# mock-ok: `new_repo.pr_sentinel_app_session` decrypts a GPG-encrypted
#   credential bundle and would raise a pinentry prompt.
# mock-ok: `new_repo.config` reads machine-level fleet configuration from
#   outside the repo under test.
# Everything these boundaries RETURN is constructed for real above.


def completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """A real CompletedProcess, which is what run_command actually returns.

    Construction is free, so the standard's first preference applies: use the
    real class. A wrong attribute name in production now raises AttributeError
    here instead of silently passing.
    """
    return subprocess.CompletedProcess(
        args=["fake-command"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeResponse:
    """Typed stand-in for `requests.Response`, with proof-of-life.

    Only the surface the production code actually touches: `status_code`,
    `text`, and `json()`. Anything else raises AttributeError, which is the
    point -- a MagicMock would invent it.

    `json_calls` is the standard's §4 proof-of-life: a test asserting a payload
    was parsed can prove the parse happened rather than trusting that it did.
    """

    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self.json_calls = 0

    def json(self):
        self.json_calls += 1
        if self._payload is None:
            raise ValueError("no JSON payload configured for this FakeResponse")
        return self._payload


class FakeSession:
    """Typed context manager standing in for the credential-session helpers.

    Yields a fixed value and records that the context was entered AND exited,
    so a test can prove the caller used `with` rather than leaking the
    credential -- which a pair of bare MagicMocks on __enter__/__exit__ cannot
    distinguish from never being called at all.
    """

    def __init__(self, value="bundle"):
        self.value = value
        self.entered = 0
        self.exited = 0

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        self.entered += 1
        return self.value

    def __exit__(self, *exc):
        self.exited += 1
        return False


SCHEMA_PATH = Path(__file__).parent.parent.parent / "docs" / "standards" / "0009-structure-schema.json"
STANDARD_PATH = Path(__file__).parent.parent.parent / "docs" / "standards" / "0009-canonical-project-structure.md"


def _minimal_schema():
    """Return a minimal valid schema for unit tests."""
    return {
        "version": "1.0",
        "directories": {
            "src": {"required": True, "description": "Source code"},
            "docs": {
                "required": True,
                "description": "Documentation",
                "children": {
                    "adrs": {"required": True, "description": "ADRs"},
                    "design": {"required": False, "description": "Design files"},
                },
            },
        },
        "files": {
            "README.md": {"required": True, "description": "Overview"},
            "LICENSE": {"required": False, "description": "License"},
        },
    }


def _write_schema(tmp_path, schema_dict):
    """Write a schema dict to a JSON file and return the path."""
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(schema_dict), encoding="utf-8")
    return path


# ===========================================================================
# TestSchemaLoading
# ===========================================================================


class TestSchemaLoading:
    """T010-T040: Schema loading and validation."""

    def test_T010_load_schema_valid(self, tmp_path):
        """Load a well-formed schema successfully."""
        schema = _minimal_schema()
        path = _write_schema(tmp_path, schema)
        result = load_structure_schema(path)
        assert result["version"] == "1.0"
        assert "directories" in result
        assert "files" in result

    def test_T020_load_schema_file_not_found(self):
        """Raise FileNotFoundError for a non-existent path."""
        with pytest.raises(FileNotFoundError):
            load_structure_schema(Path("/nonexistent/schema.json"))

    def test_T030_load_schema_invalid_json(self, tmp_path):
        """Raise JSONDecodeError for malformed JSON."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json!!!", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_structure_schema(bad)

    def test_T040_load_schema_missing_version(self, tmp_path):
        """Raise SchemaValidationError when 'version' key is absent."""
        schema = _minimal_schema()
        del schema["version"]
        path = _write_schema(tmp_path, schema)
        with pytest.raises(SchemaValidationError, match="version"):
            load_structure_schema(path)


# ===========================================================================
# TestFlatten
# ===========================================================================


class TestFlatten:
    """T050-T080: Flattening nested schema into flat lists."""

    def test_T050_flatten_directories_all(self):
        """Return all directories (required and optional)."""
        schema = _minimal_schema()
        dirs = flatten_directories(schema)
        assert "src" in dirs
        assert "docs" in dirs
        assert "docs/adrs" in dirs
        assert "docs/design" in dirs

    def test_T060_flatten_directories_required_only(self):
        """Filter to required directories only."""
        schema = _minimal_schema()
        dirs = flatten_directories(schema, required_only=True)
        assert "src" in dirs
        assert "docs" in dirs
        assert "docs/adrs" in dirs
        assert "docs/design" not in dirs  # optional

    def test_T070_flatten_directories_nested(self):
        """Handle 3-level nesting correctly."""
        schema = {
            "version": "1.0",
            "directories": {
                "docs": {
                    "required": True,
                    "description": "Docs",
                    "children": {
                        "lineage": {
                            "required": True,
                            "description": "Lineage",
                            "children": {
                                "active": {
                                    "required": True,
                                    "description": "Active",
                                },
                                "done": {
                                    "required": True,
                                    "description": "Done",
                                },
                            },
                        }
                    },
                }
            },
            "files": {},
        }
        dirs = flatten_directories(schema)
        assert "docs/lineage/active" in dirs
        assert "docs/lineage/done" in dirs

    def test_T080_flatten_files_all(self):
        """Return all file definitions."""
        schema = _minimal_schema()
        files = flatten_files(schema)
        paths = [f["path"] for f in files]
        assert "README.md" in paths
        assert "LICENSE" in paths


# ===========================================================================
# TestAudit
# ===========================================================================


class TestAudit:
    """T090-T110: Auditing project structure against schema."""

    def test_T090_audit_valid_project(self, tmp_path):
        """Return valid=True for a project with all required items."""
        schema = _minimal_schema()
        # Create required dirs
        for d in flatten_directories(schema, required_only=True):
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        # Create required files
        for f in flatten_files(schema, required_only=True):
            p = tmp_path / f["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        result = audit_project_structure(tmp_path, schema)
        assert result["valid"] is True
        assert result["missing_required_dirs"] == []
        assert result["missing_required_files"] == []

    def test_T100_audit_missing_required(self, tmp_path):
        """Return valid=False with missing required directory listed."""
        schema = _minimal_schema()
        # Only create src/, skip docs/ (required)
        (tmp_path / "src").mkdir()
        # Create required files
        for f in flatten_files(schema, required_only=True):
            p = tmp_path / f["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        result = audit_project_structure(tmp_path, schema)
        assert result["valid"] is False
        assert "docs" in result["missing_required_dirs"] or "docs/adrs" in result["missing_required_dirs"]

    def test_T110_audit_missing_optional(self, tmp_path):
        """Return valid=True even when optional items are missing."""
        schema = _minimal_schema()
        # Create all required dirs
        for d in flatten_directories(schema, required_only=True):
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        # Create all required files
        for f in flatten_files(schema, required_only=True):
            p = tmp_path / f["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
        # Skip optional docs/design dir and LICENSE file
        result = audit_project_structure(tmp_path, schema)
        assert result["valid"] is True
        assert "docs/design" in result["missing_optional_dirs"]


# ===========================================================================
# TestSecurity
# ===========================================================================


class TestSecurity:
    """T120-T130: Path traversal and absolute path rejection."""

    def test_T120_validate_paths_rejects_traversal(self):
        """Raise SchemaValidationError for paths containing '..'."""
        schema = _minimal_schema()
        schema["directories"]["../etc"] = {
            "required": True,
            "description": "malicious",
        }
        with pytest.raises(SchemaValidationError, match="traversal"):
            validate_paths_no_traversal(schema)

    def test_T130_validate_paths_rejects_absolute(self):
        """Raise SchemaValidationError for absolute paths."""
        schema = _minimal_schema()
        schema["directories"]["/etc/passwd"] = {
            "required": True,
            "description": "malicious",
        }
        with pytest.raises(SchemaValidationError, match="(?i)absolute"):
            validate_paths_no_traversal(schema)


# ===========================================================================
# TestCreateStructure
# ===========================================================================


class TestCreateStructure:
    """T140, T180, T190: Creating structure on disk."""

    def test_T140_create_structure_happy_path(self, tmp_path):
        """Create all directories from schema on disk."""
        schema = _minimal_schema()
        result = create_structure(tmp_path, schema)
        assert (tmp_path / "src").is_dir()
        assert (tmp_path / "docs" / "adrs").is_dir()
        assert (tmp_path / "docs" / "design").is_dir()
        assert len(result["created_dirs"]) > 0

    def test_T180_create_structure_no_overwrite(self, tmp_path):
        """Skip existing files without --force."""
        schema = _minimal_schema()
        # Pre-create README with custom content
        readme = tmp_path / "README.md"
        readme.write_text("MY CUSTOM README", encoding="utf-8")
        result = create_structure(tmp_path, schema, force=False)
        # Original content must be preserved
        assert readme.read_text(encoding="utf-8") == "MY CUSTOM README"
        assert "README.md" in result["skipped_files"]

    def test_T190_create_structure_force_overwrite(self, tmp_path):
        """Overwrite existing files with --force."""
        schema = {
            "version": "1.0",
            "directories": {},
            "files": {
                "README.md": {
                    "required": True,
                    "description": "Overview",
                    "template": None,
                },
            },
        }
        readme = tmp_path / "README.md"
        readme.write_text("OLD CONTENT", encoding="utf-8")
        result = create_structure(tmp_path, schema, force=True)
        assert "README.md" in result["created_files"]


# ===========================================================================
# TestIntegrity
# ===========================================================================


class TestIntegrity:
    """T150, T160, T170: Production schema and documentation integrity."""

    def test_T150_production_schema_integrity(self):
        """Production schema contains all required canonical paths."""
        schema = load_structure_schema(SCHEMA_PATH)
        dirs = flatten_directories(schema)

        # All former hardcoded DOCS_STRUCTURE paths must be present
        expected_docs = [
            "docs/adrs",
            "docs/standards",
            "docs/templates",
            "docs/lld/active",
            "docs/lld/done",
            "docs/reports/active",
            "docs/reports/done",
            "docs/runbooks",
            "docs/session-logs",
            "docs/audit-results",
            "docs/media",
            "docs/legal",
            "docs/design",
            "docs/lineage/active",
            "docs/lineage/done",
        ]
        for path in expected_docs:
            assert path in dirs, f"Missing docs path: {path}"

        # All former hardcoded TESTS_STRUCTURE paths must be present
        expected_tests = [
            "tests/unit",
            "tests/integration",
            "tests/e2e",
            "tests/smoke",
            "tests/contract",
            "tests/visual",
            "tests/benchmark",
            "tests/security",
            "tests/accessibility",
            "tests/compliance",
            "tests/fixtures",
            "tests/harness",
        ]
        for path in expected_tests:
            assert path in dirs, f"Missing tests path: {path}"

        # All former hardcoded OTHER_STRUCTURE paths must be present
        expected_other = [
            "src",
            "tools",
            "data",
            ".claude/hooks",
            ".claude/commands",
            ".claude/gemini-prompts",
        ]
        for path in expected_other:
            assert path in dirs, f"Missing other path: {path}"

    def test_T160_schema_template_validation(self, tmp_path):
        """Raise error for missing template files."""
        schema = _minimal_schema()
        schema["files"]["README.md"]["template"] = "readme-template.md"
        _write_schema(tmp_path, schema)
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        # Template file does NOT exist
        with pytest.raises(SchemaValidationError, match="template"):
            validate_template_files_exist(schema, template_dir)

    def test_T170_standard_documentation_references_schema(self):
        """Standard 0009 markdown contains a reference to the schema file."""
        content = STANDARD_PATH.read_text(encoding="utf-8")
        assert "0009-structure-schema.json" in content


# ===========================================================================
# TestMain — Issue #451: main() workflow coverage
# ===========================================================================


class TestValidateName:
    """T200-T210: Repository name validation."""

    def test_T200_valid_names(self):
        """Accept valid repository names."""
        for name in ["MyProject", "hello-world", "foo_bar", "A123"]:
            valid, error = validate_name(name)
            assert valid, f"{name} should be valid but got: {error}"

    def test_T210_reject_invalid_names(self):
        """Reject names with invalid characters or format."""
        invalid = [
            ("", "empty"),
            ("123start", "starts with digit"),
            ("has spaces", "contains space"),
            ("a" * 101, "too long"),
        ]
        for name, reason in invalid:
            valid, error = validate_name(name)
            assert not valid, f"'{name}' ({reason}) should be invalid"


class TestPythonBootstrap:
    """T280-T286: create_python_project (#1058)."""

    @patch("new_repo.run_command")
    def test_T280_happy_path_writes_artifacts(self, mock_run, tmp_path):
        """Successful poetry calls produce pyproject append + conftest.py."""
        mock_run.return_value = completed(returncode=0)
        project = tmp_path / "TestProject"
        project.mkdir()
        # poetry init normally writes this; with mocked run_command,
        # we pre-create it so the append step has a target. Must
        # include `description = ""` because create_python_project
        # anchors its `packages` directive injection on that line --
        # poetry init always emits it (even with --description "")
        # but the mocked run_command skips the actual poetry call,
        # so the fixture has to include it explicitly.
        (project / "pyproject.toml").write_text(
            "[tool.poetry]\n"
            "name = \"testproject\"\n"
            "version = \"0.1.0\"\n"
            "description = \"\"\n",
            encoding="utf-8",
        )
        from new_repo import create_python_project
        ok = create_python_project(project, "TestProject", "polyform")
        assert ok is True
        content = (project / "pyproject.toml").read_text(encoding="utf-8")
        assert "[tool.pytest.ini_options]" in content
        assert 'testpaths = ["tests"]' in content
        conftest = project / "tests" / "conftest.py"
        assert conftest.exists()
        body = conftest.read_text(encoding="utf-8")
        assert 'sys.path.insert(0, str(ROOT / "src"))' in body

    @patch("new_repo.run_command")
    def test_T281_poetry_init_failure_returns_false(self, mock_run, tmp_path):
        """If poetry init fails, function returns False without writing files."""
        mock_run.return_value = completed(returncode=1, stderr="poetry: not found")
        project = tmp_path / "FailProject"
        project.mkdir()
        from new_repo import create_python_project
        ok = create_python_project(project, "FailProject", "polyform")
        assert ok is False
        assert not (project / "tests" / "conftest.py").exists()

    @patch("new_repo.run_command")
    def test_T282_license_polyform_maps_correctly(self, mock_run, tmp_path):
        """polyform license maps to PolyForm-Noncommercial-1.0.0 in poetry init."""
        mock_run.return_value = completed(returncode=0)
        project = tmp_path / "PolyProject"
        project.mkdir()
        (project / "pyproject.toml").write_text("# stub\n", encoding="utf-8")
        from new_repo import create_python_project
        create_python_project(project, "PolyProject", "polyform")
        init_cmd = mock_run.call_args_list[0][0][0]
        license_idx = init_cmd.index("--license")
        assert init_cmd[license_idx + 1] == "PolyForm-Noncommercial-1.0.0"

    @patch("new_repo.run_command")
    def test_T283_license_mit_maps_correctly(self, mock_run, tmp_path):
        """mit license maps to MIT in poetry init."""
        mock_run.return_value = completed(returncode=0)
        project = tmp_path / "MitProject"
        project.mkdir()
        (project / "pyproject.toml").write_text("# stub\n", encoding="utf-8")
        from new_repo import create_python_project
        create_python_project(project, "MitProject", "mit")
        init_cmd = mock_run.call_args_list[0][0][0]
        license_idx = init_cmd.index("--license")
        assert init_cmd[license_idx + 1] == "MIT"

    @patch("new_repo.run_command")
    def test_T284_package_name_is_lowercased(self, mock_run, tmp_path):
        """Mixed-case repo names are lowercased for the Poetry package name."""
        mock_run.return_value = completed(returncode=0)
        project = tmp_path / "CamelCaseRepo"
        project.mkdir()
        (project / "pyproject.toml").write_text("# stub\n", encoding="utf-8")
        from new_repo import create_python_project
        create_python_project(project, "CamelCaseRepo", "polyform")
        init_cmd = mock_run.call_args_list[0][0][0]
        name_idx = init_cmd.index("--name")
        assert init_cmd[name_idx + 1] == "camelcaserepo"

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T285_lang_none_skips_poetry(self, mock_run, mock_config, tmp_path):
        """--lang none short-circuits the Python bootstrap (no poetry calls)."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv",
                   ["new_repo.py", "NoLang", "--no-github", "--lang", "none"]):
            main()
        commands = [call[0][0] for call in mock_run.call_args_list]
        assert not any(cmd[0] == "poetry" for cmd in commands), \
            f"unexpected poetry calls: {[c for c in commands if c[0] == 'poetry']}"

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T286_lang_python_default_invokes_poetry(
        self, mock_run, mock_config, tmp_path
    ):
        """--lang python (the default) calls poetry init + poetry add."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv", ["new_repo.py", "PyDefault", "--no-github"]):
            main()
        commands = [call[0][0] for call in mock_run.call_args_list]
        poetry_inits = [c for c in commands if c[:2] == ["poetry", "init"]]
        poetry_adds = [c for c in commands if c[:2] == ["poetry", "add"]]
        assert len(poetry_inits) == 1, f"expected 1 poetry init, got {poetry_inits}"
        assert len(poetry_adds) == 1, f"expected 1 poetry add, got {poetry_adds}"
        add = poetry_adds[0]
        assert "pytest" in add
        assert "pytest-cov" in add
        assert "--group" in add and "dev" in add


class TestCanonicalLabels:
    """T215-T219: create_canonical_labels (#1061)."""

    @patch("new_repo.run_command")
    def test_T215_creates_all_canonical_labels(self, mock_run):
        """Both implementation and lld labels get created."""
        mock_run.return_value = completed(returncode=0)
        from new_repo import create_canonical_labels
        created, total = create_canonical_labels("martymcenroe", "boostgauge")
        assert created == 2
        assert total == 2
        # Both labels were attempted via gh CLI.
        commands = [call[0][0] for call in mock_run.call_args_list]
        label_names = [c[3] for c in commands if c[:3] == ["gh", "label", "create"]]
        assert "implementation" in label_names
        assert "lld" in label_names

    @patch("new_repo.run_command")
    def test_T216_uses_force_for_idempotency(self, mock_run):
        """gh label create is invoked with --force so reruns succeed."""
        mock_run.return_value = completed(returncode=0)
        from new_repo import create_canonical_labels
        create_canonical_labels("martymcenroe", "TestRepo")
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "--force" in cmd, f"--force missing from: {cmd}"

    @patch("new_repo.run_command")
    def test_T217_targets_correct_repo(self, mock_run):
        """--repo flag is set to {github_user}/{repo_name}."""
        mock_run.return_value = completed(returncode=0)
        from new_repo import create_canonical_labels
        create_canonical_labels("martymcenroe", "MyRepo")
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            repo_idx = cmd.index("--repo")
            assert cmd[repo_idx + 1] == "martymcenroe/MyRepo"

    @patch("new_repo.run_command")
    def test_T218_partial_failure_returns_partial_count(self, mock_run, capsys):
        """If one label fails, count reflects only successes; warning printed."""
        # First call succeeds, second call fails.
        mock_run.side_effect = [
            completed(returncode=0),
            completed(returncode=1, stderr="GraphQL error: insufficient scope"),
        ]
        from new_repo import create_canonical_labels
        created, total = create_canonical_labels("martymcenroe", "TestRepo")
        assert created == 1
        assert total == 2
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    @patch("new_repo.run_command")
    def test_T219_check_false_passed(self, mock_run):
        """run_command is called with check=False so non-zero exit doesn't raise."""
        mock_run.return_value = completed(returncode=0)
        from new_repo import create_canonical_labels
        create_canonical_labels("martymcenroe", "TestRepo")
        for call in mock_run.call_args_list:
            kwargs = call[1] if len(call) > 1 else call.kwargs
            assert kwargs.get("check") is False, \
                f"check=False missing from call: {call}"


class TestMainAuditMode:
    """T220: --audit flag triggers audit path."""

    @patch("new_repo.config")
    def test_T220_audit_nonexistent_directory(self, mock_config, tmp_path):
        """--audit on non-existent directory exits with error."""
        mock_config.projects_root.return_value = str(tmp_path)
        with patch("sys.argv", ["new_repo.py", "NonExistent", "--audit"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("new_repo.config")
    @patch("new_repo.audit_structure")
    def test_T221_audit_existing_directory(self, mock_audit, mock_config, tmp_path):
        """--audit on existing directory calls audit_structure."""
        mock_config.projects_root.return_value = str(tmp_path)
        (tmp_path / "TestProject").mkdir()
        mock_audit.return_value = 0
        with patch("sys.argv", ["new_repo.py", "TestProject", "--audit"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        mock_audit.assert_called_once()


class TestMainDirectoryExists:
    """T230: Error when target directory already exists."""

    @patch("new_repo.config")
    def test_T230_directory_already_exists(self, mock_config, tmp_path):
        """Exit with error if project directory already exists."""
        mock_config.projects_root.return_value = str(tmp_path)
        (tmp_path / "ExistingProject").mkdir()
        with patch("sys.argv", ["new_repo.py", "ExistingProject"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestMainGitHubAuth:
    """T240: GitHub username retrieval failure."""

    @patch("new_repo.config")
    @patch("new_repo.get_github_username")
    def test_T240_gh_not_authenticated(self, mock_gh, mock_config, tmp_path):
        """Exit with error when gh CLI is not authenticated."""
        mock_config.projects_root.return_value = str(tmp_path)
        mock_gh.side_effect = subprocess.CalledProcessError(1, "gh")
        with patch("sys.argv", ["new_repo.py", "NewProject"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


def _setup_config_mock(mock_config, tmp_path):
    """Configure the mock config object with all required attributes."""
    mock_config.projects_root.return_value = str(tmp_path)
    mock_config.projects_root_unix.return_value = "/tmp/projects"
    mock_config.assemblyzero_root.return_value = str(tmp_path / "AssemblyZero")


class TestMainLocalWorkflow:
    """T250-T260: Full local-only workflow (--no-github)."""

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T250_no_github_skips_remote(self, mock_run, mock_config, tmp_path):
        """--no-github skips GitHub repo creation and starring."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv", ["new_repo.py", "LocalProject", "--no-github"]):
            main()
        # Should have called git init and git commit, but NOT gh repo create
        commands = [call[0][0] for call in mock_run.call_args_list]
        assert any(cmd[0] == "git" and cmd[1] == "init" for cmd in commands)
        assert not any(cmd[0] == "gh" for cmd in commands)

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T260_local_creates_all_files(self, mock_run, mock_config, tmp_path):
        """--no-github creates directory structure, config, and content files."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv", ["new_repo.py", "FullLocal", "--no-github"]):
            main()
        project = tmp_path / "FullLocal"
        assert project.exists()
        assert (project / ".claude").is_dir()
        assert (project / "CLAUDE.md").exists()
        assert (project / "GEMINI.md").exists()
        assert (project / "README.md").exists()
        assert (project / "LICENSE").exists()
        assert (project / ".gitignore").exists()
        assert (project / ".unleashed.json").exists()
        assert (project / "docs").is_dir()
        assert (project / "src").is_dir()
        assert (project / "tests" / "unit").is_dir()

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T265_unleashed_json_defaults(self, mock_run, mock_config, tmp_path):
        """`.unleashed.json` defaults to assemblyZero=true (#1059) and
        does NOT include the deprecated pickupThresholdMinutes (#1060)."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv", ["new_repo.py", "DefaultsProject", "--no-github"]):
            main()
        unleashed_json = (tmp_path / "DefaultsProject" / ".unleashed.json").read_text()
        config = json.loads(unleashed_json)
        # #1059: AZ-managed repos load AZ rules on /onboard.
        assert config["assemblyZero"] is True
        # #1060: deprecated and ignored by /onboard; should not be emitted.
        assert "pickupThresholdMinutes" not in config["onboard"]
        # Sanity: still has the rest of the structure.
        # #1727/#1732: no claude block at all — the wrapper retired --model
        # and --effort injection; scaffolding either would be inert config
        # that misleads readers. The wrapper handles absence via .get().
        assert "claude" not in config
        assert config["onboard"]["auto"] is True

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T270_force_flag_passed(self, mock_run, mock_config, tmp_path):
        """--force flag is accepted without error."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv", ["new_repo.py", "ForceProject", "--no-github", "--force"]):
            main()
        assert (tmp_path / "ForceProject").exists()


# ===========================================================================
# Pillar 1 — Required --cerberus-pem (#1206) + GitHub-side verification (#1200, #1202)
# ===========================================================================

import base64 as _base64  # noqa: E402

from new_repo import (  # noqa: E402
    _CANONICAL_AUTO_REVIEWER_CALLER,
    _mint_github_app_jwt,
    _parse_sentinel_app_bundle,
    run_pr_sentinel_check,
    verify_branch_protection_on_origin,
    verify_pr_sentinel_installation,
    verify_repo_settings_on_origin,
    verify_workflow_content_on_origin,
)


class TestCerberusPemRequired:
    """T290-T292: --cerberus-pem is REQUIRED for new GitHub repos (#1206).

    The DEFAULT_CERBERUS_PEM_GPG patch in T290 forces the default-PEM-fallback
    branch (#1543) to miss, so the test continues to exercise the exit-1 path
    even on a developer machine that has the real encrypted PEM at the
    canonical location.
    """

    @patch("new_repo.DEFAULT_CERBERUS_PEM_GPG",
           Path("/nonexistent-for-T290/cerberus-pem.gpg"))
    @patch("new_repo.config")
    def test_T290_missing_pem_without_no_github_exits_one(self, mock_config, tmp_path):
        """Without --cerberus-pem and without --no-github, exit 1 BEFORE any creation."""
        _setup_config_mock(mock_config, tmp_path)
        with patch("sys.argv", ["new_repo.py", "RequiredTest"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        # Pre-flight must exit BEFORE creating the local directory.
        assert not (tmp_path / "RequiredTest").exists()

    @patch("new_repo.config")
    @patch("new_repo.run_command")
    def test_T291_no_github_bypasses_requirement(self, mock_run, mock_config, tmp_path):
        """--no-github skips the requirement — local scaffold proceeds without --cerberus-pem."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = completed(returncode=0)
        with patch("sys.argv", ["new_repo.py", "NoGitTest", "--no-github"]):
            main()  # should NOT raise
        assert (tmp_path / "NoGitTest").exists()

    @patch("new_repo.config")
    def test_T292_cerberus_pem_plus_no_github_still_conflict(self, mock_config, tmp_path):
        """Pre-existing conflict check still fires: --cerberus-pem + --no-github → exit 1."""
        _setup_config_mock(mock_config, tmp_path)
        with patch("sys.argv", [
            "new_repo.py", "ConflictTest", "--no-github", "--cerberus-pem", "/tmp/fake.pem",
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("new_repo.config")
    def test_T292b_default_gpg_fallback_used_when_neither_flag_passed(
            self, mock_config, tmp_path, capsys):
        """When neither flag passed AND DEFAULT_CERBERUS_PEM_GPG exists → fallback fires (#1543).

        Uses an invalid name so the script exits AFTER the fallback prints its
        confirmation line but BEFORE any GitHub creation logic is reached.
        """
        _setup_config_mock(mock_config, tmp_path)
        fake_pem = tmp_path / "fake-cerberus-pem.gpg"
        fake_pem.write_bytes(b"fake encrypted blob")
        with patch("new_repo.DEFAULT_CERBERUS_PEM_GPG", fake_pem):
            # "bad/name" fails validate_name's regex, exiting 1 — but AFTER the
            # default-fallback block, so the confirmation line still prints.
            with patch("sys.argv", ["new_repo.py", "bad/name"]):
                with pytest.raises(SystemExit):
                    main()
        captured = capsys.readouterr().out
        assert "Using Cerberus PEM:" in captured
        assert str(fake_pem) in captured


class TestVerifyBranchProtection:
    """T293-T295: verify_branch_protection_on_origin (#1200)."""

    @patch("new_repo._request_with_retry")
    def test_T293_pass_when_all_dimensions_match(self, mock_req):
        """enforce_admins=True, 1 review, pr-sentinel check present → (True, ...)."""
        mock_resp = FakeResponse(200, payload={
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        })
        mock_req.return_value = mock_resp
        ok, msg = verify_branch_protection_on_origin("owner", "repo", "pat")
        assert ok is True
        # Standard 0024 §4 proof-of-life: a verdict reached without reading the
        # payload would be a test asserting its own fixture.
        assert mock_resp.json_calls == 1

    @patch("new_repo._request_with_retry")
    def test_T294_fail_when_enforce_admins_off(self, mock_req):
        """enforce_admins=False → (False, msg) and msg names the dimension."""
        mock_resp = FakeResponse(200, payload={
            "enforce_admins": {"enabled": False},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        })
        mock_req.return_value = mock_resp
        ok, msg = verify_branch_protection_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "enforce_admins" in msg

    @patch("new_repo._request_with_retry")
    def test_T295_fail_on_404(self, mock_req):
        """404 → (False, 'no branch protection set on origin')."""
        mock_resp = FakeResponse(404, text="Not Found")
        mock_req.return_value = mock_resp
        ok, msg = verify_branch_protection_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "no branch protection" in msg


class TestVerifyRepoSettings:
    """T296-T297: verify_repo_settings_on_origin (#1200)."""

    @patch("new_repo._request_with_retry")
    def test_T296_pass_when_squash_only_no_wiki(self, mock_req):
        """All settings match fleet standard → (True, ...)."""
        mock_resp = FakeResponse(200, payload={
            "has_wiki": False,
            "has_projects": False,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "allow_squash_merge": True,
            "delete_branch_on_merge": True,
        })
        mock_req.return_value = mock_resp
        ok, msg = verify_repo_settings_on_origin("owner", "repo", "pat")
        assert ok is True

    @patch("new_repo._request_with_retry")
    def test_T297_fail_when_wiki_enabled(self, mock_req):
        """has_wiki=True → (False, msg) and msg names the violation."""
        mock_resp = FakeResponse(200, payload={
            "has_wiki": True,
            "has_projects": False,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "allow_squash_merge": True,
            "delete_branch_on_merge": True,
        })
        mock_req.return_value = mock_resp
        ok, msg = verify_repo_settings_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "has_wiki" in msg


class TestVerifyWorkflowContent:
    """T298-T299: verify_workflow_content_on_origin — the #1193 regression test."""

    @patch("new_repo._request_with_retry")
    def test_T298_pass_when_content_matches_canonical(self, mock_req):
        """Origin content == _CANONICAL_AUTO_REVIEWER_CALLER → (True, ...)."""
        encoded = _base64.b64encode(
            _CANONICAL_AUTO_REVIEWER_CALLER.encode("utf-8")
        ).decode("ascii")
        mock_resp = FakeResponse(200, payload={"content": encoded})
        mock_req.return_value = mock_resp
        ok, msg = verify_workflow_content_on_origin("owner", "repo", "pat")
        assert ok is True

    @patch("new_repo._request_with_retry")
    def test_T299_fail_when_old_format_signature(self, mock_req):
        """Origin content uses OLD caller format → (False, ...). The #1193 failure mode.

        OLD format: `name: auto-reviewer` (lowercase), no permissions: block,
        no with: required_checks input, secrets: inherit. Reusable workflow
        fails with startup_failure.
        """
        old_format = (
            "name: auto-reviewer\n"
            "\n"
            "on:\n"
            "  pull_request:\n"
            "    types: [opened, synchronize, reopened]\n"
            "\n"
            "jobs:\n"
            "  review:\n"
            "    uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main\n"
            "    secrets: inherit\n"
        )
        encoded = _base64.b64encode(old_format.encode("utf-8")).decode("ascii")
        mock_resp = FakeResponse(200, payload={"content": encoded})
        mock_req.return_value = mock_resp
        ok, msg = verify_workflow_content_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "differs from canonical" in msg


class TestVerifyPrSentinelInstallation:
    """T300-T302: verify_pr_sentinel_installation (#1202, #1274, #1822).

    Post-#1822: the function authenticates AS the App (JWT) and probes
    GET /repos/{owner}/{repo}/installation — 200 = installed, 404 = not.
    The old /user/installations flow was rejected 403 for any PAT, so the
    check could never pass; these tests mock the new endpoint only.
    """

    @patch("new_repo.requests.get")
    def test_T300_pass_when_app_installed_on_repo(self, mock_get):
        """200 from /repos/{o}/{r}/installation → (True, covers)."""
        resp = FakeResponse(200, payload={"id": 12345})
        mock_get.return_value = resp
        ok, msg = verify_pr_sentinel_installation(
            "martymcenroe", "repo-name", "fake-jwt",
        )
        assert ok is True
        assert "covers" in msg
        assert resp.json_calls == 1, "the installation id must actually be read"
        # Bearer auth with the App JWT, not a PAT token header.
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer fake-jwt"

    @patch("new_repo.requests.get")
    def test_T301_fail_when_app_not_installed(self, mock_get):
        """404 → (False, NOT installed / scope drift)."""
        resp = FakeResponse(404, text="Not Found")
        mock_get.return_value = resp
        ok, msg = verify_pr_sentinel_installation(
            "martymcenroe", "repo-name", "fake-jwt",
        )
        assert ok is False
        assert "NOT installed" in msg
        assert "drift" in msg.lower()

    @patch("new_repo.requests.get")
    def test_T302_fail_on_unexpected_http_status(self, mock_get):
        """Non-200/404 (e.g. 401 bad JWT) → (False, HTTP detail)."""
        resp = FakeResponse(401, text="Bad credentials")
        mock_get.return_value = resp
        ok, msg = verify_pr_sentinel_installation(
            "martymcenroe", "repo-name", "fake-jwt",
        )
        assert ok is False
        assert "401" in msg


class TestSentinelAppBundleAndJwt:
    """T310-T313: _parse_sentinel_app_bundle + _mint_github_app_jwt (#1822)."""

    @staticmethod
    def _test_pem() -> str:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

    def test_T310_parse_valid_bundle(self):
        """App ID line + PEM body parses into the pair."""
        pem = self._test_pem()
        app_id, parsed_pem = _parse_sentinel_app_bundle(f"123456\n{pem}")
        assert app_id == "123456"
        assert "PRIVATE KEY" in parsed_pem

    def test_T311_parse_rejects_non_numeric_app_id(self):
        """Line 1 must be the numeric App ID."""
        with pytest.raises(ValueError, match="numeric App ID"):
            _parse_sentinel_app_bundle("not-a-number\n-----BEGIN PRIVATE KEY-----\nx\n")

    def test_T312_parse_rejects_missing_pem(self):
        """A bare App ID with no PEM body is malformed."""
        with pytest.raises(ValueError):
            _parse_sentinel_app_bundle("123456")

    def test_T313_minted_jwt_has_app_claims_and_valid_signature(self):
        """JWT: three segments, iss = App ID, iat backdated, RS256-verifiable."""
        import base64
        import json

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        pem = self._test_pem()
        token = _mint_github_app_jwt("123456", pem)
        header_b64, payload_b64, sig_b64 = token.split(".")

        def unb64(seg: str) -> bytes:
            return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))

        header = json.loads(unb64(header_b64))
        payload = json.loads(unb64(payload_b64))
        assert header == {"alg": "RS256", "typ": "JWT"}
        assert payload["iss"] == "123456"
        assert payload["exp"] - payload["iat"] == 600  # -60s iat, +540s exp
        # Signature must verify against the key's public half.
        pub = serialization.load_pem_private_key(
            pem.encode(), password=None,
        ).public_key()
        pub.verify(  # raises InvalidSignature on mismatch
            unb64(sig_b64),
            f"{header_b64}.{payload_b64}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )


class TestRunPrSentinelCheck:
    """T314-T317: run_pr_sentinel_check three-state dispatch (#1822).

    "skip" outcomes must NOT count toward the GitHub-side denominator —
    that is the whole point of the fix: an unperformable check must not
    produce the WARNING banner.
    """

    def test_T314_skip_when_bundle_not_provisioned(self, tmp_path):
        """Missing encrypted bundle → ('skip', not attempted)."""
        outcome, msg = run_pr_sentinel_check(
            "martymcenroe", "repo-name", tmp_path / "absent.gpg",
        )
        assert outcome == "skip"
        assert "not provisioned" in msg
        assert "not attempted" in msg

    @patch("new_repo.pr_sentinel_app_session")
    def test_T315_skip_when_decrypt_declined(self, mock_session, tmp_path):
        """Operator cancels pinentry (RuntimeError) → ('skip', ...)."""
        mock_session.side_effect = RuntimeError(
            "decrypt declined by operator (pinentry cancelled)"
        )
        outcome, msg = run_pr_sentinel_check(
            "martymcenroe", "repo-name", tmp_path / "any.gpg",
        )
        assert outcome == "skip"
        assert "declined" in msg

    @patch("new_repo.verify_pr_sentinel_installation")
    @patch("new_repo._mint_github_app_jwt")
    @patch("new_repo._parse_sentinel_app_bundle")
    @patch("new_repo.pr_sentinel_app_session")
    def test_T316_pass_when_verified(
        self, mock_session, mock_parse, mock_mint, mock_verify,
    ):
        """Decrypt + mint + 200 probe → ('pass', ...)."""
        session = FakeSession("bundle")
        mock_session.side_effect = session
        mock_parse.return_value = ("123456", "PEM")
        mock_mint.return_value = "jwt"
        mock_verify.return_value = (True, "App installation covers this repo (id 1)")
        outcome, msg = run_pr_sentinel_check(
            "martymcenroe", "repo-name", Path("ignored.gpg"),
        )
        assert outcome == "pass"
        assert "covers" in msg
        # Proof-of-life: the credential was borrowed through `with`, and given
        # back. A pair of bare mocks could not tell this from never running.
        assert (session.entered, session.exited) == (1, 1)

    @patch("new_repo.verify_pr_sentinel_installation")
    @patch("new_repo._mint_github_app_jwt")
    @patch("new_repo._parse_sentinel_app_bundle")
    @patch("new_repo.pr_sentinel_app_session")
    def test_T317_fail_when_app_absent(
        self, mock_session, mock_parse, mock_mint, mock_verify,
    ):
        """Credential fine but App genuinely not installed → ('fail', ...)."""
        session = FakeSession("bundle")
        mock_session.side_effect = session
        mock_parse.return_value = ("123456", "PEM")
        mock_mint.return_value = "jwt"
        mock_verify.return_value = (False, "App is NOT installed on o/r")
        outcome, msg = run_pr_sentinel_check(
            "martymcenroe", "repo-name", Path("ignored.gpg"),
        )
        assert outcome == "fail"
        assert "NOT installed" in msg


# ===========================================================================
# #1201 — PyPI 0934 reminder
# ===========================================================================

from new_repo import _maybe_print_pypi_reminder  # noqa: E402


class TestPypiReminder:
    """T303-T306: _maybe_print_pypi_reminder fires only when release.yml shipped."""

    def test_T303_prints_when_python_pypi_github(self, capsys):
        """Default config (python + pypi + github) → reminder prints with repo-specific values."""
        _maybe_print_pypi_reminder(
            lang="python",
            no_pypi=False,
            no_github=False,
            github_user="owner",
            repo_name="myproject",
        )
        out = capsys.readouterr().out
        assert "pending-publisher registration" in out
        assert "myproject" in out
        assert "owner" in out
        assert "release.yml" in out
        assert "0934" in out

    def test_T304_silent_when_no_github(self, capsys):
        """--no-github → no remote, reminder suppressed."""
        _maybe_print_pypi_reminder(
            lang="python",
            no_pypi=False,
            no_github=True,
            github_user="owner",
            repo_name="myproject",
        )
        assert capsys.readouterr().out == ""

    def test_T305_silent_when_lang_none(self, capsys):
        """--lang none → no Python project, no release.yml shipped, no reminder."""
        _maybe_print_pypi_reminder(
            lang="none",
            no_pypi=False,
            no_github=False,
            github_user="owner",
            repo_name="myproject",
        )
        assert capsys.readouterr().out == ""

    def test_T306_silent_when_no_pypi(self, capsys):
        """--no-pypi → release.yml explicitly suppressed, no reminder."""
        _maybe_print_pypi_reminder(
            lang="python",
            no_pypi=True,
            no_github=False,
            github_user="owner",
            repo_name="myproject",
        )
        assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# CLAUDE.md emission per ADR 0219 (#1258) + --project-type branching (#1291)
# Tests #1292 — assert lean shape + per-type stubs + no banned content.
# ---------------------------------------------------------------------------

# Phrases that MUST NOT appear in any scaffolded CLAUDE.md per ADR 0219 —
# these belong to the universal CLAUDE.md, and restating them creates drift
# on every universal-CLAUDE.md edit.
BANNED_PHRASES = [
    "merge sequence",
    "Closes #N must appear in ALL THREE",
    "enforce_admins",
    "FIRST: Read AssemblyZero",
    "banned commands",
    "pr-sentinel / issue-reference",
]


class TestCreateClaudeMdLeanShape:
    """ADR 0219 — emitted CLAUDE.md must be additive only, no duplicated content."""

    def test_minimal_is_default_and_emits_todo_stub(self, tmp_path):
        create_claude_md(tmp_path, "myrepo", "alice")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "## Project Identifiers" in text
        assert "myrepo" in text
        assert "alice/myrepo" in text
        # default minimal emits the TODO block (not a typed stack note)
        assert "**Stack:**" not in text
        assert "TODO: Add tech stack" in text

    def test_no_banned_universal_content_in_minimal(self, tmp_path):
        create_claude_md(tmp_path, "myrepo", "alice")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        for phrase in BANNED_PHRASES:
            assert phrase not in text, (
                f"Banned phrase {phrase!r} found in scaffolded CLAUDE.md — "
                f"ADR 0219 forbids restating universal CLAUDE.md content."
            )

    def test_no_banned_universal_content_in_any_project_type(self, tmp_path):
        """Across all project types, no stub may restate universal content."""
        for pt in PROJECT_TYPES:
            target = tmp_path / pt
            target.mkdir()
            create_claude_md(target, f"sample-{pt}", "alice", pt)
            text = (target / "CLAUDE.md").read_text(encoding="utf-8")
            for phrase in BANNED_PHRASES:
                assert phrase not in text, (
                    f"Banned phrase {phrase!r} found in {pt!r} stub — "
                    f"per ADR 0219 stubs must be ADDITIVE only."
                )

    def test_invalid_project_type_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown project_type"):
            create_claude_md(tmp_path, "myrepo", "alice", "nonexistent-type")


class TestProjectTypeStubs:
    """Each project type emits a recognizable stack identifier + ADR 0219 ref."""

    def test_python_stub_mentions_poetry_and_pytest(self):
        text = _project_specific_context("python", "myrepo")
        assert "**Stack:**" in text
        assert "Poetry" in text
        assert "pytest" in text
        assert "ADR 0219" in text

    def test_python_stub_stack_line_is_layout_agnostic(self):
        """#1304: Python stub's Stack line doesn't hardcode src/{name}/.

        The Stack line names Poetry + pytest + tests/ but defers source layout
        to the TODO block so script-collection repos (e.g. automation-scripts)
        don't get a factually wrong claim. The TODO MAY mention src/{name}/ as
        one example shape, but the Stack line itself must not claim it.
        """
        text = _project_specific_context("python", "myrepo")
        stack_line = next(
            line for line in text.splitlines() if line.startswith("**Stack:**")
        )
        assert "src/myrepo/" not in stack_line
        assert "src/" not in stack_line

    def test_chrome_extension_stub_mentions_mv3(self):
        text = _project_specific_context("chrome-extension", "myrepo")
        assert "Manifest V3" in text
        assert "jest" in text
        assert "ADR 0219" in text

    def test_pypi_stub_mentions_release_yml(self):
        text = _project_specific_context("pypi", "myrepo")
        assert "PyPI" in text
        assert "release.yml" in text
        assert "[tool.poetry.scripts]" in text
        assert "runbook 0934" in text
        assert "ADR 0219" in text

    def test_cf_worker_stub_mentions_wrangler(self):
        text = _project_specific_context("cf-worker", "myrepo")
        assert "Cloudflare Worker" in text
        assert "wrangler" in text
        assert "ADR 0219" in text

    def test_web_stub_mentions_deploy_targets(self):
        text = _project_specific_context("web", "myrepo")
        assert "Web (static or SPA)" in text
        # at least one of the listed deploy targets
        assert any(t in text for t in ("Cloudflare Pages", "GitHub Pages", "Netlify"))
        assert "ADR 0219" in text

    def test_minimal_stub_has_no_stack_line(self):
        text = _project_specific_context("minimal", "myrepo")
        assert "**Stack:**" not in text
        assert "TODO: Add tech stack" in text
        assert "ADR 0219" in text

    def test_each_stub_includes_project_specific_context_header(self):
        for pt in PROJECT_TYPES:
            text = _project_specific_context(pt, "myrepo")
            assert text.startswith("## Project-Specific Context"), pt

    def test_each_typed_stub_includes_todo(self):
        """Even typed stubs must leave a TODO — the stack note is a head start, not a finish."""
        for pt in PROJECT_TYPES:
            text = _project_specific_context(pt, "myrepo")
            assert "TODO" in text, f"{pt} stub has no TODO marker"


class TestProjectTypeBranchingCallSite:
    """End-to-end: create_claude_md passes the project_type through to the stub."""

    def test_python_call_site_emits_stack_line(self, tmp_path):
        create_claude_md(tmp_path, "myrepo", "alice", "python")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "**Stack:** Python (Poetry)" in text

    def test_cf_worker_call_site_emits_wrangler(self, tmp_path):
        create_claude_md(tmp_path, "myrepo", "alice", "cf-worker")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "wrangler" in text

    def test_chrome_extension_call_site_emits_mv3(self, tmp_path):
        create_claude_md(tmp_path, "myrepo", "alice", "chrome-extension")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Manifest V3" in text

    def test_default_call_site_emits_minimal(self, tmp_path):
        """No explicit project_type = minimal stub (TODO, no stack note)."""
        create_claude_md(tmp_path, "myrepo", "alice")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "**Stack:**" not in text


class TestGitHubRepoNameCasePreservation:
    """#1533: GitHub repo name preserves the operator's input case verbatim.

    Pre-fix: line 2671 of the script unconditionally did
    `repo_name_lower = args.name.lower()` before sending the name to GitHub.
    Result: `Chiron` input produced `martymcenroe/chiron` on GitHub while the
    local directory at `Projects/Chiron/` kept its case — asymmetric and
    against the operator's intent.

    The fix is structural (remove the variable; use `args.name` directly in
    all 14 GitHub-side call sites). This regression pin asserts the variable
    name is gone from the script so a future edit can't quietly reintroduce
    the lowercase normalization. The fix-anchor comment naming the issue
    must also be present.
    """

    def test_no_lowercased_repo_name_variable_in_script(self):
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent.parent / "tools" / "new_repo.py"
        content = script.read_text(encoding="utf-8")
        assert "repo_name_lower" not in content, (
            "regression: `repo_name_lower` was reintroduced. The GitHub repo "
            "name must preserve the operator's input case verbatim — use "
            "`args.name` in the GitHub-create / -PATCH / -GET paths instead. "
            "See AssemblyZero #1533."
        )

    def test_fix_anchor_comment_naming_issue_present(self):
        """The inline comment naming #1533 should remain at the GitHub-create
        site so a future agent reading the code understands why no
        lowercasing happens there."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent.parent / "tools" / "new_repo.py"
        content = script.read_text(encoding="utf-8")
        assert "#1533" in content
        # The comment must sit in the GitHub-side flow. Use the `GITHUB REMOTE`
        # banner print as the canonical anchor for that flow — it appears
        # exactly once and only inside the post-no-github-gate block.
        gh_banner = content.find("GITHUB REMOTE (single classic-PAT")
        anchor = content.find("#1533")
        assert gh_banner != -1 and anchor != -1
        # The comment naming #1533 should appear within ~600 chars BEFORE
        # the banner (the comment explains why no lowercase happens at this
        # gate; banner follows immediately after).
        delta = gh_banner - anchor
        assert 0 < delta < 600, (
            f"#1533 comment is at offset {anchor}; GITHUB REMOTE banner at "
            f"{gh_banner} (delta={delta}). The fix-anchor comment is no "
            "longer adjacent to the GitHub-side flow it explains."
        )

    def test_no_late_args_name_lowercase_mutation(self):
        """#1535: the regression-pin above missed three direct mutations of
        `args.name` in the final-summary block (`args.name = args.name.lower()`)
        because it only checked for the `repo_name_lower` variable name. This
        pin catches the direct-mutation form.

        Legitimate `.lower()` uses in the script that we must NOT flag:
        - `name.lower()` inside `create_python_project` (line ~1252-1253) —
          generating Python package + module names per PEP 503
        - `args.name.lower().replace(\"-\", \"_\")` for module-name substitution
          at line ~2550 (same intent as line 1253, in the config-file flow)

        What we DO flag:
        - `args.name = args.name.lower()` anywhere — assignment that overwrites
          the operator's input case
        - `args.name.lower()` passed as `repo_name=...` to anything (those
          arguments flow into displayed URLs / paths and must preserve case)
        """
        from pathlib import Path
        import re
        script = Path(__file__).resolve().parent.parent.parent / "tools" / "new_repo.py"
        content = script.read_text(encoding="utf-8")

        # Direct mutation: `args.name = args.name.lower()`
        assert "args.name = args.name.lower()" not in content, (
            "regression #1535: a direct mutation `args.name = args.name.lower()` "
            "is present. That overwrites the operator's input case after the "
            "GitHub repo was already created with the verbatim case (#1533). "
            "Display lines downstream will then show the lowercased form, "
            "diverging from the local dir name and the actual GitHub repo."
        )

        # Inline `args.name.lower()` passed to a `repo_name=` kwarg
        # (the PyPI reminder path). The kwarg is supposed to receive a name
        # that matches the actual GitHub repo.
        matches = re.findall(r"repo_name\s*=\s*args\.name\.lower\(\)", content)
        assert not matches, (
            "regression #1535: `repo_name=args.name.lower()` is present. "
            "Pass `repo_name=args.name` so the displayed PyPI URL matches "
            "the actual GitHub repo name."
        )


class TestCerberusPostDeployAdvice:
    """#134 supersedes #1536. The post-deploy advice must NOT branch.

    #1536 split the advice by flow: the plaintext flow (`--cerberus-pem`)
    deletes the .pem, so it was told to revoke as belt-and-braces, while
    the encrypted-reusable flow (`--cerberus-pem-gpg`) was told not to,
    because revoking would invalidate the blob it had just kept.

    That split asks the wrong question. Revoking does not retire an
    on-disk copy — it removes the PUBLIC half registered on the App, so
    GitHub can no longer validate a JWT signed by that key, and the
    REVIEWER_APP_PRIVATE_KEY secret the run just deployed becomes dead
    bytes. No installation token, no approving review, mergeable_state
    stuck at `blocked` — in the new repo AND in every other repo holding
    the same key.

    The question is not "did a plaintext file survive this run". It is
    "is this key deployed anywhere", and after either flow the answer is
    yes, because deploying it is the point of the run. So the advice is
    the same on both paths: keep the key active, rotate via runbook 0939.

    These tests previously asserted the presence of the revoke
    instruction, which is how the defect stayed shipped through a green
    suite. They now assert its absence.
    """

    def test_no_revoke_instruction_on_any_flow(self):
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent.parent / "tools" / "new_repo.py"
        content = script.read_text(encoding="utf-8")
        assert "REMEMBER to revoke the key in the app UI" not in content, (
            "#134: deploy-then-revoke instruction is back. Revoking "
            "invalidates the Actions secret this run just deployed."
        )
        assert "Revoke the key you just used" not in content

    def test_keep_active_guidance_is_present_on_both_flows(self):
        """Deleting the bad advice without replacing it would pass the test
        above and leave the operator at a Revoke button with no guidance."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent.parent / "tools" / "new_repo.py"
        content = script.read_text(encoding="utf-8")
        assert "do NOT revoke" in content or "Do NOT revoke" in content
        assert "0939" in content, "must point at the rotation runbook"

    def test_anchor_comment_naming_issue_present(self):
        """A comment naming #134 should sit at the cerberus_status branch so
        the next reader does not re-derive the on-disk model and
        re-introduce the split."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent.parent / "tools" / "new_repo.py"
        content = script.read_text(encoding="utf-8")
        assert "#134" in content
        # The #1536 anchor must be near the `elif cerberus_status == \"OK\":`
        # branch (within a few hundred chars BEFORE the branch text — the
        # anchor comment introduces the conditional).
        branch_loc = content.find('elif cerberus_status == "OK":')
        anchor = content.find("#1536")
        assert branch_loc != -1 and anchor != -1
        delta = branch_loc - anchor
        # Comment may sit ON the same logical block as the branch, so the
        # offset is small in either direction; just check they are within
        # 800 chars of each other.
        assert abs(delta) < 800, (
            f"#1536 anchor at offset {anchor}; cerberus_status branch at "
            f"{branch_loc} (delta={delta}). The fix-anchor comment is no "
            "longer adjacent to the cerberus advice branch."
        )


# ===========================================================================
# TestDependabotConfig (#1334)
# ===========================================================================


class TestDependabotConfig:
    """`.github/dependabot.yml` version-update generation at scaffold time."""

    def test_github_actions_always_present(self, tmp_path):
        from new_repo import detect_dependabot_ecosystems
        assert ("github-actions", "github-actions") in detect_dependabot_ecosystems(tmp_path)

    def test_no_markers_yields_only_github_actions(self, tmp_path):
        from new_repo import detect_dependabot_ecosystems
        assert detect_dependabot_ecosystems(tmp_path) == [("github-actions", "github-actions")]

    def test_pip_detected_from_pyproject(self, tmp_path):
        from new_repo import detect_dependabot_ecosystems
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
        assert ("pip", "python") in detect_dependabot_ecosystems(tmp_path)

    def test_npm_and_docker_detected(self, tmp_path):
        from new_repo import detect_dependabot_ecosystems
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        keys = {eco for eco, _ in detect_dependabot_ecosystems(tmp_path)}
        assert {"npm", "docker", "github-actions"} <= keys

    def test_create_writes_file_and_returns_ecosystems(self, tmp_path):
        from new_repo import create_dependabot_config
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
        written = create_dependabot_config(tmp_path)
        assert (tmp_path / ".github" / "dependabot.yml").exists()
        assert "pip" in written and "github-actions" in written

    def test_yml_has_fleet_standard_fields(self, tmp_path):
        from new_repo import create_dependabot_config
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
        create_dependabot_config(tmp_path)
        text = (tmp_path / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        assert "version: 2" in text
        assert 'package-ecosystem: "pip"' in text
        assert 'package-ecosystem: "github-actions"' in text
        assert 'timezone: "America/Chicago"' in text
        assert 'prefix: "chore(deps)"' in text
        assert "open-pull-requests-limit: 5" in text
        # grouped minor + patch present
        assert '"minor"' in text and '"patch"' in text

    def test_yml_is_lf_only(self, tmp_path):
        # newline="" must keep LF on Windows, matching the rest of the fleet.
        from new_repo import create_dependabot_config
        create_dependabot_config(tmp_path)
        raw = (tmp_path / ".github" / "dependabot.yml").read_bytes()
        assert b"\r\n" not in raw


# ===========================================================================
# TestDataGConvention (#1563)
# ===========================================================================


class TestDataGConvention:
    """data-g/ git-tracked source-of-truth data directory."""

    def test_create_writes_readme(self, tmp_path):
        from new_repo import create_data_g_readme
        create_data_g_readme(tmp_path)
        assert (tmp_path / "data-g" / "README.md").exists()

    def test_create_removes_schema_gitkeep(self, tmp_path):
        from new_repo import create_data_g_readme
        data_g = tmp_path / "data-g"
        data_g.mkdir()
        (data_g / ".gitkeep").touch()  # simulate schema-created placeholder
        create_data_g_readme(tmp_path)
        assert not (data_g / ".gitkeep").exists()

    def test_readme_explains_split_and_cites_issue(self, tmp_path):
        from new_repo import create_data_g_readme
        create_data_g_readme(tmp_path)
        text = (tmp_path / "data-g" / "README.md").read_text(encoding="utf-8")
        assert "data/" in text and "data-g/" in text
        assert "#1563" in text

    # --- data-dl/ (#2485) ---------------------------------------------------
    # data-g/ was absorbing downloaded material because there was nowhere else
    # for it to go. These assert the third directory exists, that it is really
    # ignored, and -- the part that actually breaks -- that its README survives
    # the ignore rule.

    def test_create_writes_data_dl_readme(self, tmp_path):
        from new_repo import create_data_g_readme
        create_data_g_readme(tmp_path)
        assert (tmp_path / "data-dl" / "README.md").exists()

    def test_create_removes_data_dl_schema_gitkeep(self, tmp_path):
        from new_repo import create_data_g_readme
        data_dl = tmp_path / "data-dl"
        data_dl.mkdir()
        (data_dl / ".gitkeep").touch()
        create_data_g_readme(tmp_path)
        assert not (data_dl / ".gitkeep").exists()

    def test_both_readmes_carry_the_full_three_way_table(self, tmp_path):
        """A README that only describes its own directory does not help someone
        choosing between directories. Both must show all three."""
        from new_repo import create_data_g_readme
        create_data_g_readme(tmp_path)
        for where in ("data-g", "data-dl"):
            text = (tmp_path / where / "README.md").read_text(encoding="utf-8")
            assert "`data/`" in text, where
            assert "`data-dl/`" in text, where
            assert "`data-g/`" in text, where

    def test_data_dl_readme_cites_issue(self, tmp_path):
        from new_repo import create_data_g_readme
        create_data_g_readme(tmp_path)
        text = (tmp_path / "data-dl" / "README.md").read_text(encoding="utf-8")
        assert "#2485" in text

    def test_gitignore_template_ignores_data_dl_but_not_its_readme(self, tmp_path):
        """The bug this guards: a bare `data-dl/` rule would swallow the README,
        because git cannot re-include a file underneath an ignored directory.
        Asserted against real git rather than by reading the template."""
        import subprocess
        from new_repo import create_gitignore, create_data_g_readme

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        create_gitignore(tmp_path)
        create_data_g_readme(tmp_path)
        (tmp_path / "data-dl" / "paper.pdf").write_text("x", encoding="utf-8")

        def ignored(rel):
            return subprocess.run(
                ["git", "check-ignore", "-q", rel],
                cwd=tmp_path, capture_output=True,
            ).returncode == 0

        assert ignored("data-dl/paper.pdf"), "downloaded material must be ignored"
        assert not ignored("data-dl/README.md"), "the README must stay tracked"

    def test_gitignore_template_does_not_ignore_data_g(self, tmp_path):
        """A `data-*/` glob would match data-g/ and silently stop tracking the
        one directory that is meant to be committed."""
        import subprocess
        from new_repo import create_gitignore, create_data_g_readme

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        create_gitignore(tmp_path)
        create_data_g_readme(tmp_path)
        (tmp_path / "data-g" / "roster.json").write_text("{}", encoding="utf-8")

        for rel in ("data-g/README.md", "data-g/roster.json"):
            assert subprocess.run(
                ["git", "check-ignore", "-q", rel],
                cwd=tmp_path, capture_output=True,
            ).returncode != 0, f"{rel} must remain tracked"

    def test_schema_includes_data_g(self):
        from new_repo import load_structure_schema
        schema = load_structure_schema()
        assert "data-g" in schema["directories"]

    def test_claude_md_documents_convention(self, tmp_path):
        from new_repo import create_claude_md
        create_claude_md(tmp_path, "demo", "martymcenroe", "minimal")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "data-g/" in text


# ===========================================================================
# TestRequiresPythonNormalization (#1573)
# ===========================================================================


class TestRequiresPythonNormalization:
    """_normalize_requires_python: Poetry caret -> valid PEP 440."""

    def test_caret_310(self):
        from new_repo import _normalize_requires_python
        out = _normalize_requires_python('requires-python = "^3.10"\n')
        assert 'requires-python = ">=3.10,<4.0"' in out

    def test_caret_311_and_312_preserve_floor(self):
        from new_repo import _normalize_requires_python
        assert ">=3.11,<4.0" in _normalize_requires_python('requires-python = "^3.11"')
        assert ">=3.12,<4.0" in _normalize_requires_python('requires-python = "^3.12"')

    def test_already_valid_is_unchanged(self):
        from new_repo import _normalize_requires_python
        src = 'requires-python = ">=3.10,<4.0"\n'
        assert _normalize_requires_python(src) == src

    def test_result_parses_as_pep440(self):
        import re
        from packaging.specifiers import SpecifierSet
        from new_repo import _normalize_requires_python
        out = _normalize_requires_python('requires-python = "^3.10"')
        val = re.search(r'requires-python = "([^"]+)"', out).group(1)
        SpecifierSet(val)  # raises InvalidSpecifier if the rewrite is wrong


# ===========================================================================
# TestScaffoldValidationGate (#1575)
# ===========================================================================


class TestScaffoldValidationGate:
    """validate_scaffold: blocks on structural invalidity, passes valid repos."""

    @staticmethod
    def _valid_pyproject(tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n'
            'requires-python = ">=3.10,<4.0"\n',
            encoding="utf-8",
        )

    def test_valid_scaffold_has_no_blocking(self, tmp_path):
        from new_repo import validate_scaffold
        self._valid_pyproject(tmp_path)
        blocking, _ = validate_scaffold(tmp_path)
        assert blocking == []

    def test_empty_dir_has_no_blocking(self, tmp_path):
        from new_repo import validate_scaffold
        blocking, _ = validate_scaffold(tmp_path)
        assert blocking == []

    def test_caret_requires_python_blocks(self, tmp_path):
        from new_repo import validate_scaffold
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nrequires-python = "^3.10"\n', encoding="utf-8"
        )
        blocking, _ = validate_scaffold(tmp_path)
        assert any("requires-python" in m for m in blocking), blocking

    def test_unparseable_pyproject_blocks(self, tmp_path):
        from new_repo import validate_scaffold
        (tmp_path / "pyproject.toml").write_text("this = = not toml\n", encoding="utf-8")
        blocking, _ = validate_scaffold(tmp_path)
        assert any("does not parse" in m for m in blocking), blocking

    def test_invalid_dependabot_yaml_blocks(self, tmp_path):
        from new_repo import validate_scaffold
        self._valid_pyproject(tmp_path)
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "dependabot.yml").write_text(
            "version: 2\nupdates: [\n", encoding="utf-8"
        )
        blocking, _ = validate_scaffold(tmp_path)
        assert any("dependabot.yml" in m for m in blocking), blocking

    def test_invalid_json_blocks(self, tmp_path):
        from new_repo import validate_scaffold
        self._valid_pyproject(tmp_path)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "project.json").write_text("{ not json", encoding="utf-8")
        blocking, _ = validate_scaffold(tmp_path)
        assert any("project.json" in m for m in blocking), blocking


# ---- #2113: create_settings_json must merge, never overwrite ----
#
# The scaffolder is re-run over existing repos as a normal catch-up when a
# template change needs to reach repos created before it. The previous
# implementation wrote a fixed dict unconditionally, silently destroying
# whatever that repo had added since.

import new_repo as _nr  # noqa: E402


def _settings_dir(tmp_path):
    d = tmp_path / "myrepo" / ".claude"
    d.mkdir(parents=True)
    return tmp_path / "myrepo"


def _read(project):
    return json.loads(
        (project / ".claude" / "settings.json").read_text(encoding="utf-8")
    )


def _guard_entry(settings):
    return next(
        e for e in settings["hooks"]["PreToolUse"]
        if e.get("matcher") == _nr._GUARD_MATCHER
    )


def test_creates_settings_when_absent(tmp_path):
    project = _settings_dir(tmp_path)
    assert _nr.create_settings_json(project) == "created"
    assert _guard_entry(_read(project))["hooks"][0]["type"] == "command"


def test_preserves_unrelated_top_level_keys(tmp_path):
    """A repo's own permissions must survive a scaffolder re-run.

    This is the actual reported harm: permission rules vanishing, discovered
    later as a repo prompting for something it never prompted for.
    """
    project = _settings_dir(tmp_path)
    (project / ".claude" / "settings.json").write_text(json.dumps({
        "permissions": {"allow": ["Bash(gh:*)"], "deny": ["Read(.env)"]},
        "model": "opus",
    }), encoding="utf-8")

    assert _nr.create_settings_json(project) == "merged"
    after = _read(project)
    assert after["permissions"] == {"allow": ["Bash(gh:*)"], "deny": ["Read(.env)"]}
    assert after["model"] == "opus"
    assert _guard_entry(after)["hooks"][0]["command"].endswith("secret-file-guard.sh")


def test_preserves_other_hook_events(tmp_path):
    """The old code wrote PostToolUse: [] — erasing post-hooks outright."""
    project = _settings_dir(tmp_path)
    post = [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}]
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"PostToolUse": post}}), encoding="utf-8")

    assert _nr.create_settings_json(project) == "merged"
    assert _read(project)["hooks"]["PostToolUse"] == post


def test_preserves_other_matchers_in_pretooluse(tmp_path):
    project = _settings_dir(tmp_path)
    other = {"matcher": "Bash", "hooks": [{"type": "command", "command": "guard.sh"}]}
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [other]}}), encoding="utf-8")

    assert _nr.create_settings_json(project) == "merged"
    pre = _read(project)["hooks"]["PreToolUse"]
    assert other in pre
    assert any(e.get("matcher") == _nr._GUARD_MATCHER for e in pre)


def test_preserves_sibling_hooks_on_our_own_matcher(tmp_path):
    """A repo may add its own hook to the same matcher; it must survive."""
    project = _settings_dir(tmp_path)
    sibling = {"type": "command", "command": "bash /repo/.claude/hooks/mine.sh"}
    (project / ".claude" / "settings.json").write_text(json.dumps({
        "hooks": {"PreToolUse": [
            {"matcher": _nr._GUARD_MATCHER, "hooks": [sibling]}
        ]}
    }), encoding="utf-8")

    assert _nr.create_settings_json(project) == "merged"
    entry_hooks = _guard_entry(_read(project))["hooks"]
    assert sibling in entry_hooks
    assert any(h["command"].endswith("secret-file-guard.sh") for h in entry_hooks)


def test_rerun_is_a_no_op_and_does_not_touch_the_file(tmp_path):
    """A catch-up sweep over compliant repos must produce no diff, no churn."""
    project = _settings_dir(tmp_path)
    assert _nr.create_settings_json(project) == "created"

    path = project / ".claude" / "settings.json"
    before_bytes = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns

    assert _nr.create_settings_json(project) == "unchanged"
    assert path.read_bytes() == before_bytes
    assert path.stat().st_mtime_ns == before_mtime


def test_unparseable_file_is_backed_up_never_discarded(tmp_path):
    """The one remaining destructive path must preserve the original."""
    project = _settings_dir(tmp_path)
    path = project / ".claude" / "settings.json"
    garbage = "{ this is not json"
    path.write_text(garbage, encoding="utf-8")

    assert _nr.create_settings_json(project) == "replaced-unparseable"
    backup = project / ".claude" / "settings.json.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == garbage
    assert _guard_entry(_read(project))["hooks"][0]["type"] == "command"


def test_json_array_at_top_level_is_treated_as_unparseable(tmp_path):
    """Valid JSON that is not an object cannot be merged into; back it up."""
    project = _settings_dir(tmp_path)
    path = project / ".claude" / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert _nr.create_settings_json(project) == "replaced-unparseable"
    assert (project / ".claude" / "settings.json.bak").read_text(
        encoding="utf-8") == "[1, 2, 3]"


def test_merge_helper_does_not_mutate_its_input():
    """Purity matters: the caller compares merged against existing."""
    existing = {"hooks": {"PreToolUse": []}}
    snapshot = json.dumps(existing, sort_keys=True)
    _nr._merge_settings(existing, {"type": "command", "command": "x"})
    assert json.dumps(existing, sort_keys=True) == snapshot


# ---- #2182: the scaffolder names npm dirs whose PRs could never merge ----

def test_warns_for_npm_dir_without_runnable_test_script(tmp_path, capsys):
    """A repo must not be born receiving PRs it cannot pass review on."""
    web = tmp_path / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text(json.dumps({"name": "web"}), encoding="utf-8")
    (web / "package-lock.json").write_text("{}", encoding="utf-8")

    warned = _nr.warn_npm_dirs_without_test_script(tmp_path)

    assert warned == ["/web"]
    out = capsys.readouterr().out
    assert "/web" in out
    assert "1839" in out          # names the gate that will refuse the merge
    assert "no test specified" in out   # tells them the placeholder won't do


def test_compliant_repo_produces_no_warning(tmp_path, capsys):
    web = tmp_path / "web"
    web.mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({"name": "web", "scripts": {"test": "vitest run"}}),
        encoding="utf-8")
    (web / "package-lock.json").write_text("{}", encoding="utf-8")

    assert _nr.warn_npm_dirs_without_test_script(tmp_path) == []
    assert capsys.readouterr().out == ""


def test_warns_about_a_directory_dependabot_yml_never_declared(tmp_path, capsys):
    """The case that prompted this: security updates ignore dependabot.yml.

    AssemblyZero declared npm for /sentinel only and never for /dashboard,
    yet /dashboard received npm PRs and deferred on every harvest. A guard
    that only checked configured directories would have missed it.
    """
    for name, scripts in (("sentinel", {"test": "vitest run"}), ("dashboard", None)):
        d = tmp_path / name
        d.mkdir(parents=True)
        body = {"name": name}
        if scripts:
            body["scripts"] = scripts
        (d / "package.json").write_text(json.dumps(body), encoding="utf-8")
        (d / "package-lock.json").write_text("{}", encoding="utf-8")

    assert _nr.warn_npm_dirs_without_test_script(tmp_path) == ["/dashboard"]
