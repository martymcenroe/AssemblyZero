"""Tests for LLD path extraction and enforcement.

Issue #188: Test IDs match LLD Section 10.0.
"""


from assemblyzero.utils.lld_path_enforcer import (
    LLDPathSpec,
    build_implementation_prompt_section,
    detect_scaffolded_test_files,
    extract_paths_from_lld,
    parse_files_changed_table,
)


SAMPLE_LLD = """# 188 - Feature: Enforce File Paths

## 1. Context & Goal

Something here.

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/utils/lld_path_enforcer.py` | Add | Path extraction and enforcement |
| `assemblyzero/hooks/file_write_validator.py` | Add | Pre-write validation hook |
| `tests/unit/test_lld_path_enforcer.py` | Add | Unit tests for path enforcement |

### 2.2 Dependencies

None.
"""

SAMPLE_LLD_NO_TABLE = """# 188 - Feature: Something

## 1. Context & Goal

Something here.

### 2.1 Files Changed

No files changed in this LLD.

### 2.2 Dependencies
"""

SAMPLE_LLD_MALFORMED = """# 188 - Feature: Something

### 2.1 Files Changed

| File | Change Type
| `broken/path.py` | Add
not a table row at all
| `valid/path.py` | Modify | A valid row |

### 2.2 Dependencies
"""


class TestParseFilesChangedTable:
    """Tests for markdown table parsing."""

    def test_parse_valid_table(self):
        """Parse a well-formed Files Changed table."""
        table = """\
| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/utils/lld.py` | Add | New module |
| `tests/test_lld.py` | Add | Tests |
"""
        result = parse_files_changed_table(table)
        assert len(result) == 2
        assert result[0] == ("assemblyzero/utils/lld.py", "Add", "New module")
        assert result[1] == ("tests/test_lld.py", "Add", "Tests")

    def test_parse_empty_table(self):
        """Empty table returns empty list."""
        result = parse_files_changed_table("")
        assert result == []

    def test_skip_header_and_separator(self):
        """Header and separator rows are skipped."""
        table = """\
| File | Change Type | Description |
|------|-------------|-------------|
| `src/main.py` | Modify | Update logic |
"""
        result = parse_files_changed_table(table)
        assert len(result) == 1
        assert result[0][0] == "src/main.py"


class TestExtractPathsFromLLD:
    """T010, T020, T025: Test LLD path extraction."""

    def test_extract_paths_from_valid_lld(self):
        """T010: Extract paths from valid LLD."""
        spec = extract_paths_from_lld(SAMPLE_LLD)

        assert "assemblyzero/utils/lld_path_enforcer.py" in spec["implementation_files"]
        assert "assemblyzero/hooks/file_write_validator.py" in spec["implementation_files"]
        assert "tests/unit/test_lld_path_enforcer.py" in spec["test_files"]
        assert len(spec["all_allowed_paths"]) == 3

    def test_extract_paths_from_lld_no_table(self):
        """T020: LLD with no table returns empty spec."""
        spec = extract_paths_from_lld(SAMPLE_LLD_NO_TABLE)

        assert spec["implementation_files"] == []
        assert spec["test_files"] == []
        assert len(spec["all_allowed_paths"]) == 0

    def test_extract_paths_from_malformed_table(self):
        """T025: Malformed table returns partial results, no crash."""
        spec = extract_paths_from_lld(SAMPLE_LLD_MALFORMED)

        # Should extract the valid row
        assert "valid/path.py" in spec["all_allowed_paths"]

    def test_extract_categorizes_test_files(self):
        """Test files under tests/ are categorized as test_files."""
        spec = extract_paths_from_lld(SAMPLE_LLD)
        assert "tests/unit/test_lld_path_enforcer.py" in spec["test_files"]
        assert "tests/unit/test_lld_path_enforcer.py" not in spec["implementation_files"]

    def test_empty_lld_content(self):
        """Empty LLD content returns empty spec."""
        spec = extract_paths_from_lld("")
        assert len(spec["all_allowed_paths"]) == 0


class TestDetectScaffoldedTestFiles:
    """T065: Test scaffolded test file detection."""

    def test_detect_existing_test_files(self, tmp_path):
        """T065: Returns set of test files that exist on disk."""
        test_dir = tmp_path / "tests" / "unit"
        test_dir.mkdir(parents=True)
        (test_dir / "test_existing.py").write_text("# test")

        result = detect_scaffolded_test_files(
            ["tests/unit/test_existing.py", "tests/unit/test_missing.py"],
            tmp_path,
        )

        assert "tests/unit/test_existing.py" in result
        assert "tests/unit/test_missing.py" not in result

    def test_empty_test_files(self, tmp_path):
        """Empty list returns empty set."""
        result = detect_scaffolded_test_files([], tmp_path)
        assert result == set()


class TestBuildImplementationPromptSection:
    """T060, T090: Test prompt section generation."""

    def test_build_prompt_with_scaffolded_test(self):
        """T060: Generate markdown with DO NOT MODIFY for scaffolded tests."""
        spec: LLDPathSpec = {
            "implementation_files": ["assemblyzero/utils/lld.py"],
            "test_files": ["tests/test_lld.py"],
            "config_files": [],
            "all_allowed_paths": {"assemblyzero/utils/lld.py", "tests/test_lld.py"},
            "scaffolded_test_files": {"tests/test_lld.py"},
        }

        result = build_implementation_prompt_section(spec)

        assert "assemblyzero/utils/lld.py" in result
        assert "tests/test_lld.py" in result
        assert "DO NOT MODIFY" in result
        assert "do not deviate" in result.lower()

    def test_build_prompt_without_scaffolded(self):
        """Prompt section without scaffolded tests has no DO NOT MODIFY."""
        spec: LLDPathSpec = {
            "implementation_files": ["src/main.py"],
            "test_files": ["tests/test_main.py"],
            "config_files": [],
            "all_allowed_paths": {"src/main.py", "tests/test_main.py"},
            "scaffolded_test_files": set(),
        }

        result = build_implementation_prompt_section(spec)

        assert "DO NOT MODIFY" not in result
        assert "src/main.py" in result

    def test_build_prompt_empty_paths(self):
        """Empty paths returns empty string."""
        spec: LLDPathSpec = {
            "implementation_files": [],
            "test_files": [],
            "config_files": [],
            "all_allowed_paths": set(),
            "scaffolded_test_files": set(),
        }

        result = build_implementation_prompt_section(spec)
        assert result == ""

    def test_prompt_includes_rejection_warning(self):
        """T090: Prompt includes warning about path rejection."""
        spec: LLDPathSpec = {
            "implementation_files": ["src/main.py"],
            "test_files": [],
            "config_files": [],
            "all_allowed_paths": {"src/main.py"},
            "scaffolded_test_files": set(),
        }

        result = build_implementation_prompt_section(spec)
        assert "rejected" in result.lower()
