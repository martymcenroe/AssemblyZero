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

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from new_repo_setup import (
    PROJECT_TYPES,
    SchemaValidationError,
    _project_specific_context,
    audit_project_structure,
    create_claude_md,
    create_structure,
    flatten_directories,
    flatten_files,
    load_structure_schema,
    validate_paths_no_traversal,
    validate_template_files_exist,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "standards" / "0009-structure-schema.json"
STANDARD_PATH = Path(__file__).parent.parent / "docs" / "standards" / "0009-canonical-project-structure.md"


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
        path = _write_schema(tmp_path, schema)
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

from unittest.mock import patch, MagicMock

from new_repo_setup import (
    main,
    validate_name,
    get_github_username,
    audit_structure,
)


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

    @patch("new_repo_setup.run_command")
    def test_T280_happy_path_writes_artifacts(self, mock_run, tmp_path):
        """Successful poetry calls produce pyproject append + conftest.py."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
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
        from new_repo_setup import create_python_project
        ok = create_python_project(project, "TestProject", "polyform")
        assert ok is True
        content = (project / "pyproject.toml").read_text(encoding="utf-8")
        assert "[tool.pytest.ini_options]" in content
        assert 'testpaths = ["tests"]' in content
        conftest = project / "tests" / "conftest.py"
        assert conftest.exists()
        body = conftest.read_text(encoding="utf-8")
        assert 'sys.path.insert(0, str(ROOT / "src"))' in body

    @patch("new_repo_setup.run_command")
    def test_T281_poetry_init_failure_returns_false(self, mock_run, tmp_path):
        """If poetry init fails, function returns False without writing files."""
        mock_run.return_value = MagicMock(returncode=1, stderr="poetry: not found")
        project = tmp_path / "FailProject"
        project.mkdir()
        from new_repo_setup import create_python_project
        ok = create_python_project(project, "FailProject", "polyform")
        assert ok is False
        assert not (project / "tests" / "conftest.py").exists()

    @patch("new_repo_setup.run_command")
    def test_T282_license_polyform_maps_correctly(self, mock_run, tmp_path):
        """polyform license maps to PolyForm-Noncommercial-1.0.0 in poetry init."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        project = tmp_path / "PolyProject"
        project.mkdir()
        (project / "pyproject.toml").write_text("# stub\n", encoding="utf-8")
        from new_repo_setup import create_python_project
        create_python_project(project, "PolyProject", "polyform")
        init_cmd = mock_run.call_args_list[0][0][0]
        license_idx = init_cmd.index("--license")
        assert init_cmd[license_idx + 1] == "PolyForm-Noncommercial-1.0.0"

    @patch("new_repo_setup.run_command")
    def test_T283_license_mit_maps_correctly(self, mock_run, tmp_path):
        """mit license maps to MIT in poetry init."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        project = tmp_path / "MitProject"
        project.mkdir()
        (project / "pyproject.toml").write_text("# stub\n", encoding="utf-8")
        from new_repo_setup import create_python_project
        create_python_project(project, "MitProject", "mit")
        init_cmd = mock_run.call_args_list[0][0][0]
        license_idx = init_cmd.index("--license")
        assert init_cmd[license_idx + 1] == "MIT"

    @patch("new_repo_setup.run_command")
    def test_T284_package_name_is_lowercased(self, mock_run, tmp_path):
        """Mixed-case repo names are lowercased for the Poetry package name."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        project = tmp_path / "CamelCaseRepo"
        project.mkdir()
        (project / "pyproject.toml").write_text("# stub\n", encoding="utf-8")
        from new_repo_setup import create_python_project
        create_python_project(project, "CamelCaseRepo", "polyform")
        init_cmd = mock_run.call_args_list[0][0][0]
        name_idx = init_cmd.index("--name")
        assert init_cmd[name_idx + 1] == "camelcaserepo"

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T285_lang_none_skips_poetry(self, mock_run, mock_config, tmp_path):
        """--lang none short-circuits the Python bootstrap (no poetry calls)."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        with patch("sys.argv",
                   ["new_repo_setup.py", "NoLang", "--no-github", "--lang", "none"]):
            main()
        commands = [call[0][0] for call in mock_run.call_args_list]
        assert not any(cmd[0] == "poetry" for cmd in commands), \
            f"unexpected poetry calls: {[c for c in commands if c[0] == 'poetry']}"

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T286_lang_python_default_invokes_poetry(
        self, mock_run, mock_config, tmp_path
    ):
        """--lang python (the default) calls poetry init + poetry add."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with patch("sys.argv", ["new_repo_setup.py", "PyDefault", "--no-github"]):
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

    @patch("new_repo_setup.run_command")
    def test_T215_creates_all_canonical_labels(self, mock_run):
        """Both implementation and lld labels get created."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from new_repo_setup import create_canonical_labels
        created, total = create_canonical_labels("martymcenroe", "boostgauge")
        assert created == 2
        assert total == 2
        # Both labels were attempted via gh CLI.
        commands = [call[0][0] for call in mock_run.call_args_list]
        label_names = [c[3] for c in commands if c[:3] == ["gh", "label", "create"]]
        assert "implementation" in label_names
        assert "lld" in label_names

    @patch("new_repo_setup.run_command")
    def test_T216_uses_force_for_idempotency(self, mock_run):
        """gh label create is invoked with --force so reruns succeed."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from new_repo_setup import create_canonical_labels
        create_canonical_labels("martymcenroe", "TestRepo")
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "--force" in cmd, f"--force missing from: {cmd}"

    @patch("new_repo_setup.run_command")
    def test_T217_targets_correct_repo(self, mock_run):
        """--repo flag is set to {github_user}/{repo_name}."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from new_repo_setup import create_canonical_labels
        create_canonical_labels("martymcenroe", "MyRepo")
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            repo_idx = cmd.index("--repo")
            assert cmd[repo_idx + 1] == "martymcenroe/MyRepo"

    @patch("new_repo_setup.run_command")
    def test_T218_partial_failure_returns_partial_count(self, mock_run, capsys):
        """If one label fails, count reflects only successes; warning printed."""
        # First call succeeds, second call fails.
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="GraphQL error: insufficient scope"),
        ]
        from new_repo_setup import create_canonical_labels
        created, total = create_canonical_labels("martymcenroe", "TestRepo")
        assert created == 1
        assert total == 2
        captured = capsys.readouterr()
        assert "WARNING" in captured.out

    @patch("new_repo_setup.run_command")
    def test_T219_check_false_passed(self, mock_run):
        """run_command is called with check=False so non-zero exit doesn't raise."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from new_repo_setup import create_canonical_labels
        create_canonical_labels("martymcenroe", "TestRepo")
        for call in mock_run.call_args_list:
            kwargs = call[1] if len(call) > 1 else call.kwargs
            assert kwargs.get("check") is False, \
                f"check=False missing from call: {call}"


class TestMainAuditMode:
    """T220: --audit flag triggers audit path."""

    @patch("new_repo_setup.config")
    def test_T220_audit_nonexistent_directory(self, mock_config, tmp_path):
        """--audit on non-existent directory exits with error."""
        mock_config.projects_root.return_value = str(tmp_path)
        with patch("sys.argv", ["new_repo_setup.py", "NonExistent", "--audit"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.audit_structure")
    def test_T221_audit_existing_directory(self, mock_audit, mock_config, tmp_path):
        """--audit on existing directory calls audit_structure."""
        mock_config.projects_root.return_value = str(tmp_path)
        (tmp_path / "TestProject").mkdir()
        mock_audit.return_value = 0
        with patch("sys.argv", ["new_repo_setup.py", "TestProject", "--audit"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        mock_audit.assert_called_once()


class TestMainDirectoryExists:
    """T230: Error when target directory already exists."""

    @patch("new_repo_setup.config")
    def test_T230_directory_already_exists(self, mock_config, tmp_path):
        """Exit with error if project directory already exists."""
        mock_config.projects_root.return_value = str(tmp_path)
        (tmp_path / "ExistingProject").mkdir()
        with patch("sys.argv", ["new_repo_setup.py", "ExistingProject"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestMainGitHubAuth:
    """T240: GitHub username retrieval failure."""

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.get_github_username")
    def test_T240_gh_not_authenticated(self, mock_gh, mock_config, tmp_path):
        """Exit with error when gh CLI is not authenticated."""
        mock_config.projects_root.return_value = str(tmp_path)
        mock_gh.side_effect = subprocess.CalledProcessError(1, "gh")
        with patch("sys.argv", ["new_repo_setup.py", "NewProject"]):
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

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T250_no_github_skips_remote(self, mock_run, mock_config, tmp_path):
        """--no-github skips GitHub repo creation and starring."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        with patch("sys.argv", ["new_repo_setup.py", "LocalProject", "--no-github"]):
            main()
        # Should have called git init and git commit, but NOT gh repo create
        commands = [call[0][0] for call in mock_run.call_args_list]
        assert any(cmd[0] == "git" and cmd[1] == "init" for cmd in commands)
        assert not any(cmd[0] == "gh" for cmd in commands)

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T260_local_creates_all_files(self, mock_run, mock_config, tmp_path):
        """--no-github creates directory structure, config, and content files."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        with patch("sys.argv", ["new_repo_setup.py", "FullLocal", "--no-github"]):
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

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T265_unleashed_json_defaults(self, mock_run, mock_config, tmp_path):
        """`.unleashed.json` defaults to assemblyZero=true (#1059) and
        does NOT include the deprecated pickupThresholdMinutes (#1060)."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        with patch("sys.argv", ["new_repo_setup.py", "DefaultsProject", "--no-github"]):
            main()
        unleashed_json = (tmp_path / "DefaultsProject" / ".unleashed.json").read_text()
        config = json.loads(unleashed_json)
        # #1059: AZ-managed repos load AZ rules on /onboard.
        assert config["assemblyZero"] is True
        # #1060: deprecated and ignored by /onboard; should not be emitted.
        assert "pickupThresholdMinutes" not in config["onboard"]
        # Sanity: still has the rest of the structure.
        assert config["claude"]["model"] == "claude-opus-4-7[1M]"
        assert config["claude"]["effort"] == "max"
        assert config["onboard"]["auto"] is True

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T270_force_flag_passed(self, mock_run, mock_config, tmp_path):
        """--force flag is accepted without error."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        with patch("sys.argv", ["new_repo_setup.py", "ForceProject", "--no-github", "--force"]):
            main()
        assert (tmp_path / "ForceProject").exists()


# ===========================================================================
# Pillar 1 — Required --cerberus-pem (#1206) + GitHub-side verification (#1200, #1202)
# ===========================================================================

import base64 as _base64  # noqa: E402

from new_repo_setup import (  # noqa: E402
    _CANONICAL_AUTO_REVIEWER_CALLER,
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

    @patch("new_repo_setup.DEFAULT_CERBERUS_PEM_GPG",
           Path("/nonexistent-for-T290/cerberus-pem.gpg"))
    @patch("new_repo_setup.config")
    def test_T290_missing_pem_without_no_github_exits_one(self, mock_config, tmp_path):
        """Without --cerberus-pem and without --no-github, exit 1 BEFORE any creation."""
        _setup_config_mock(mock_config, tmp_path)
        with patch("sys.argv", ["new_repo_setup.py", "RequiredTest"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        # Pre-flight must exit BEFORE creating the local directory.
        assert not (tmp_path / "RequiredTest").exists()

    @patch("new_repo_setup.config")
    @patch("new_repo_setup.run_command")
    def test_T291_no_github_bypasses_requirement(self, mock_run, mock_config, tmp_path):
        """--no-github skips the requirement — local scaffold proceeds without --cerberus-pem."""
        _setup_config_mock(mock_config, tmp_path)
        mock_run.return_value = MagicMock(returncode=0)
        with patch("sys.argv", ["new_repo_setup.py", "NoGitTest", "--no-github"]):
            main()  # should NOT raise
        assert (tmp_path / "NoGitTest").exists()

    @patch("new_repo_setup.config")
    def test_T292_cerberus_pem_plus_no_github_still_conflict(self, mock_config, tmp_path):
        """Pre-existing conflict check still fires: --cerberus-pem + --no-github → exit 1."""
        _setup_config_mock(mock_config, tmp_path)
        with patch("sys.argv", [
            "new_repo_setup.py", "ConflictTest", "--no-github", "--cerberus-pem", "/tmp/fake.pem",
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("new_repo_setup.config")
    def test_T292b_default_gpg_fallback_used_when_neither_flag_passed(
            self, mock_config, tmp_path, capsys):
        """When neither flag passed AND DEFAULT_CERBERUS_PEM_GPG exists → fallback fires (#1543).

        Uses an invalid name so the script exits AFTER the fallback prints its
        confirmation line but BEFORE any GitHub creation logic is reached.
        """
        _setup_config_mock(mock_config, tmp_path)
        fake_pem = tmp_path / "fake-cerberus-pem.gpg"
        fake_pem.write_bytes(b"fake encrypted blob")
        with patch("new_repo_setup.DEFAULT_CERBERUS_PEM_GPG", fake_pem):
            # "bad/name" fails validate_name's regex, exiting 1 — but AFTER the
            # default-fallback block, so the confirmation line still prints.
            with patch("sys.argv", ["new_repo_setup.py", "bad/name"]):
                with pytest.raises(SystemExit):
                    main()
        captured = capsys.readouterr().out
        assert "Using Cerberus PEM:" in captured
        assert str(fake_pem) in captured


class TestVerifyBranchProtection:
    """T293-T295: verify_branch_protection_on_origin (#1200)."""

    @patch("new_repo_setup._request_with_retry")
    def test_T293_pass_when_all_dimensions_match(self, mock_req):
        """enforce_admins=True, 1 review, pr-sentinel check present → (True, ...)."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        }
        mock_req.return_value = mock_resp
        ok, msg = verify_branch_protection_on_origin("owner", "repo", "pat")
        assert ok is True

    @patch("new_repo_setup._request_with_retry")
    def test_T294_fail_when_enforce_admins_off(self, mock_req):
        """enforce_admins=False → (False, msg) and msg names the dimension."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "enforce_admins": {"enabled": False},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        }
        mock_req.return_value = mock_resp
        ok, msg = verify_branch_protection_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "enforce_admins" in msg

    @patch("new_repo_setup._request_with_retry")
    def test_T295_fail_on_404(self, mock_req):
        """404 → (False, 'no branch protection set on origin')."""
        mock_resp = MagicMock(status_code=404, text="Not Found")
        mock_req.return_value = mock_resp
        ok, msg = verify_branch_protection_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "no branch protection" in msg


class TestVerifyRepoSettings:
    """T296-T297: verify_repo_settings_on_origin (#1200)."""

    @patch("new_repo_setup._request_with_retry")
    def test_T296_pass_when_squash_only_no_wiki(self, mock_req):
        """All settings match fleet standard → (True, ...)."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "has_wiki": False,
            "has_projects": False,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "allow_squash_merge": True,
            "delete_branch_on_merge": True,
        }
        mock_req.return_value = mock_resp
        ok, msg = verify_repo_settings_on_origin("owner", "repo", "pat")
        assert ok is True

    @patch("new_repo_setup._request_with_retry")
    def test_T297_fail_when_wiki_enabled(self, mock_req):
        """has_wiki=True → (False, msg) and msg names the violation."""
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "has_wiki": True,
            "has_projects": False,
            "allow_merge_commit": False,
            "allow_rebase_merge": False,
            "allow_squash_merge": True,
            "delete_branch_on_merge": True,
        }
        mock_req.return_value = mock_resp
        ok, msg = verify_repo_settings_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "has_wiki" in msg


class TestVerifyWorkflowContent:
    """T298-T299: verify_workflow_content_on_origin — the #1193 regression test."""

    @patch("new_repo_setup._request_with_retry")
    def test_T298_pass_when_content_matches_canonical(self, mock_req):
        """Origin content == _CANONICAL_AUTO_REVIEWER_CALLER → (True, ...)."""
        encoded = _base64.b64encode(
            _CANONICAL_AUTO_REVIEWER_CALLER.encode("utf-8")
        ).decode("ascii")
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"content": encoded}
        mock_req.return_value = mock_resp
        ok, msg = verify_workflow_content_on_origin("owner", "repo", "pat")
        assert ok is True

    @patch("new_repo_setup._request_with_retry")
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
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"content": encoded}
        mock_req.return_value = mock_resp
        ok, msg = verify_workflow_content_on_origin("owner", "repo", "pat")
        assert ok is False
        assert "differs from canonical" in msg


class TestVerifyPrSentinelInstallation:
    """T300-T302: verify_pr_sentinel_installation (#1202, refactored #1274).

    Post-#1274: function uses requests + classic PAT (not gh CLI). Tests
    mock requests.get with status-code/json-shaped responses.
    """

    @patch("new_repo_setup.requests.get")
    def test_T300_pass_when_repo_in_installation(self, mock_get):
        """Worker installation found AND covers the new repo → (True, ...)."""
        installations_resp = MagicMock(status_code=200)
        installations_resp.json.return_value = {
            "installations": [
                {"app_slug": "pr-sentinel-mm", "id": 12345},
            ],
        }
        repos_resp = MagicMock(status_code=200)
        repos_resp.json.return_value = {
            "repositories": [
                {"full_name": "martymcenroe/some-other"},
                {"full_name": "martymcenroe/repo-name"},
            ],
        }
        mock_get.side_effect = [installations_resp, repos_resp]
        ok, msg = verify_pr_sentinel_installation(
            "martymcenroe", "repo-name", "fake-pat",
        )
        assert ok is True
        assert "covers" in msg

    @patch("new_repo_setup.requests.get")
    def test_T301_warn_when_installation_missing(self, mock_get):
        """No pr-sentinel-mm in /user/installations → (False, 'not found')."""
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"installations": [
            {"app_slug": "some-other-app", "id": 99},
        ]}
        mock_get.return_value = resp
        ok, msg = verify_pr_sentinel_installation(
            "martymcenroe", "repo-name", "fake-pat",
        )
        assert ok is False
        assert "not found" in msg

    @patch("new_repo_setup.requests.get")
    def test_T302_warn_when_repo_not_in_installation_repos(self, mock_get):
        """Installation exists but doesn't cover the new repo → App scope drift warning."""
        installations_resp = MagicMock(status_code=200)
        installations_resp.json.return_value = {
            "installations": [
                {"app_slug": "pr-sentinel-mm", "id": 12345},
            ],
        }
        repos_resp = MagicMock(status_code=200)
        repos_resp.json.return_value = {
            "repositories": [
                {"full_name": "martymcenroe/some-other-only"},
            ],
        }
        mock_get.side_effect = [installations_resp, repos_resp]
        ok, msg = verify_pr_sentinel_installation(
            "martymcenroe", "repo-name", "fake-pat",
        )
        assert ok is False
        assert "does NOT cover" in msg or "drift" in msg.lower()


# ===========================================================================
# #1201 — PyPI 0934 reminder
# ===========================================================================

from new_repo_setup import _maybe_print_pypi_reminder  # noqa: E402


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
        script = Path(__file__).resolve().parent.parent / "tools" / "new_repo_setup.py"
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
        script = Path(__file__).resolve().parent.parent / "tools" / "new_repo_setup.py"
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
        script = Path(__file__).resolve().parent.parent / "tools" / "new_repo_setup.py"
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
    """#1536: the post-deploy success message must distinguish between
    the plaintext flow (`--cerberus-pem`, .pem deleted, revoke-the-key
    correct) and the encrypted-reusable flow (`--cerberus-pem-gpg`, blob
    preserved, revoke-the-key catastrophic — would invalidate the
    reusable encrypted file).

    Bug pre-fix: a single `print(\"REMEMBER to revoke the key...\")` line
    fired for both flows. The operator following it under the
    encrypted-reusable flow would lose the ability to use the encrypted
    PEM for subsequent new-repo runs.
    """

    def test_revoke_advice_only_present_in_plaintext_branch(self):
        """The string 'REMEMBER to revoke' should only appear inside a
        conditional that checks args.cerberus_pem (the plaintext flow)."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "tools" / "new_repo_setup.py"
        content = script.read_text(encoding="utf-8")
        # The advisory text must exist (it's correct for the plaintext flow)
        assert "REMEMBER to revoke the key in the app UI" in content
        # And the encrypted-flow branch must have the NEGATING advice
        assert "DO NOT revoke the key in the app UI" in content, (
            "regression #1536: the encrypted-reusable flow "
            "(--cerberus-pem-gpg) lost its do-not-revoke guidance. The "
            "post-deploy success message must distinguish the two flows."
        )

    def test_anchor_comment_naming_issue_present(self):
        """A comment naming #1536 should sit at the cerberus_status branch
        so future agents understand why the two flows produce different
        end-of-run advice."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "tools" / "new_repo_setup.py"
        content = script.read_text(encoding="utf-8")
        assert "#1536" in content
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
        from new_repo_setup import detect_dependabot_ecosystems
        assert ("github-actions", "github-actions") in detect_dependabot_ecosystems(tmp_path)

    def test_no_markers_yields_only_github_actions(self, tmp_path):
        from new_repo_setup import detect_dependabot_ecosystems
        assert detect_dependabot_ecosystems(tmp_path) == [("github-actions", "github-actions")]

    def test_pip_detected_from_pyproject(self, tmp_path):
        from new_repo_setup import detect_dependabot_ecosystems
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
        assert ("pip", "python") in detect_dependabot_ecosystems(tmp_path)

    def test_npm_and_docker_detected(self, tmp_path):
        from new_repo_setup import detect_dependabot_ecosystems
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        keys = {eco for eco, _ in detect_dependabot_ecosystems(tmp_path)}
        assert {"npm", "docker", "github-actions"} <= keys

    def test_create_writes_file_and_returns_ecosystems(self, tmp_path):
        from new_repo_setup import create_dependabot_config
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
        written = create_dependabot_config(tmp_path)
        assert (tmp_path / ".github" / "dependabot.yml").exists()
        assert "pip" in written and "github-actions" in written

    def test_yml_has_fleet_standard_fields(self, tmp_path):
        from new_repo_setup import create_dependabot_config
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
        from new_repo_setup import create_dependabot_config
        create_dependabot_config(tmp_path)
        raw = (tmp_path / ".github" / "dependabot.yml").read_bytes()
        assert b"\r\n" not in raw


# ===========================================================================
# TestDataGConvention (#1563)
# ===========================================================================


class TestDataGConvention:
    """data-g/ git-tracked source-of-truth data directory."""

    def test_create_writes_readme(self, tmp_path):
        from new_repo_setup import create_data_g_readme
        create_data_g_readme(tmp_path)
        assert (tmp_path / "data-g" / "README.md").exists()

    def test_create_removes_schema_gitkeep(self, tmp_path):
        from new_repo_setup import create_data_g_readme
        data_g = tmp_path / "data-g"
        data_g.mkdir()
        (data_g / ".gitkeep").touch()  # simulate schema-created placeholder
        create_data_g_readme(tmp_path)
        assert not (data_g / ".gitkeep").exists()

    def test_readme_explains_split_and_cites_issue(self, tmp_path):
        from new_repo_setup import create_data_g_readme
        create_data_g_readme(tmp_path)
        text = (tmp_path / "data-g" / "README.md").read_text(encoding="utf-8")
        assert "data/" in text and "data-g/" in text
        assert "#1563" in text

    def test_schema_includes_data_g(self):
        from new_repo_setup import load_structure_schema
        schema = load_structure_schema()
        assert "data-g" in schema["directories"]

    def test_claude_md_documents_convention(self, tmp_path):
        from new_repo_setup import create_claude_md
        create_claude_md(tmp_path, "demo", "martymcenroe", "minimal")
        text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert "data-g/" in text
