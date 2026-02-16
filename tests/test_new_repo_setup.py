"""
Tests for new-repo-setup.py schema-driven project structure.

Per LLD-099: 19 test scenarios (T010-T190) for schema loading, flattening,
auditing, security validation, and structure creation.

Issue: #99
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from new_repo_setup import (
    SchemaValidationError,
    audit_project_structure,
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
