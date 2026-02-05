"""Tests for mechanical LLD validation node.

Issue #277: Mechanical validation catches path errors and section inconsistencies
before Gemini review.

TDD: These tests are written before implementation and should initially fail (RED).
"""

import pytest
from pathlib import Path
from unittest.mock import patch

# Import will fail until implementation exists - that's expected for TDD
try:
    from agentos.workflows.requirements.nodes.validate_mechanical import (
        validate_lld_mechanical,
        validate_mandatory_sections,
        parse_files_changed_table,
        validate_file_paths,
        detect_placeholder_prefixes,
        extract_files_from_section,
        cross_reference_sections,
        extract_mitigations_from_risks,
        extract_function_names,
        trace_mitigations_to_functions,
        extract_keywords,
        ValidationSeverity,
        ValidationError,
    )
except ImportError:
    # Expected during TDD - tests will fail with import error
    pass


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_repo(tmp_path):
    """Create a mock repository structure for path validation tests."""
    # Create directories
    (tmp_path / "agentos" / "workflows" / "requirements" / "nodes").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "docs" / "templates").mkdir(parents=True)

    # Create some existing files
    (tmp_path / "agentos" / "workflows" / "requirements" / "nodes" / "finalize.py").write_text("# existing")
    (tmp_path / "agentos" / "workflows" / "requirements" / "graph.py").write_text("# existing")
    (tmp_path / "agentos" / "workflows" / "requirements" / "state.py").write_text("# existing")

    return tmp_path


@pytest.fixture
def valid_lld_content():
    """A valid LLD with all required sections."""
    return """# 1001 - Feature: Test Feature

## 1. Context & Goal
Test objective.

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | Add | New validation node |
| `agentos/workflows/requirements/graph.py` | Modify | Insert validation node |
| `agentos/workflows/requirements/state.py` | Modify | Add validation fields |

### 2.4 Function Signatures

```python
def validate_lld_mechanical(state):
    '''Validate LLD mechanically.'''
    ...

def validate_file_paths(files, repo_root):
    '''Validate file paths exist.'''
    ...
```

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Regex fails | Med | Low | Add comprehensive tests |
| False positives | High | Med | Validate file paths conservatively |

## 12. Definition of Done

- [ ] `agentos/workflows/requirements/nodes/validate_mechanical.py` implemented
- [ ] `agentos/workflows/requirements/graph.py` updated
- [ ] `agentos/workflows/requirements/state.py` updated
"""


@pytest.fixture
def lld_missing_section_21():
    """LLD missing mandatory Section 2.1."""
    return """# 1001 - Feature: Test Feature

## 1. Context & Goal
Test objective.

## 11. Risks & Mitigations

| Risk | Impact |
|------|--------|
| Test | Low |

## 12. Definition of Done

- [ ] Something done
"""


@pytest.fixture
def lld_missing_section_11():
    """LLD missing mandatory Section 11."""
    return """# 1001 - Feature: Test Feature

## 1. Context & Goal
Test objective.

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `test.py` | Add | Test file |

## 12. Definition of Done

- [ ] Something done
"""


@pytest.fixture
def lld_missing_section_12():
    """LLD missing mandatory Section 12."""
    return """# 1001 - Feature: Test Feature

## 1. Context & Goal
Test objective.

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `test.py` | Add | Test file |

## 11. Risks & Mitigations

| Risk | Impact |
|------|--------|
| Test | Low |
"""


@pytest.fixture
def lld_with_invalid_modify_path():
    """LLD with a Modify file that doesn't exist."""
    return """# 1001 - Feature: Test

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/nonexistent.py` | Modify | Does not exist |
| `agentos/workflows/requirements/graph.py` | Modify | Exists |

## 11. Risks & Mitigations

| Risk | Impact |
|------|--------|
| Test | Low |

## 12. Definition of Done

- [ ] Done
"""


@pytest.fixture
def lld_with_placeholder_prefix():
    """LLD using src/ placeholder when it doesn't exist."""
    return """# 1001 - Feature: Test

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/components/Button.tsx` | Add | New component |

## 11. Risks & Mitigations

| Risk | Impact |
|------|--------|
| Test | Low |

## 12. Definition of Done

- [ ] Done
"""


@pytest.fixture
def lld_with_dod_mismatch():
    """LLD with DoD referencing file not in Section 2.1."""
    return """# 1001 - Feature: Test

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/graph.py` | Modify | Update graph |

## 11. Risks & Mitigations

| Risk | Impact |
|------|--------|
| Test | Low |

## 12. Definition of Done

- [ ] `agentos/workflows/requirements/graph.py` updated
- [ ] `agentos/workflows/requirements/extra_file.py` created
- [ ] Tests pass
"""


@pytest.fixture
def lld_with_untraced_mitigation():
    """LLD with risk mitigation that has no matching function."""
    return """# 1001 - Feature: Test

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `test.py` | Add | Test |

### 2.4 Function Signatures

```python
def do_something():
    '''Does something.'''
    ...
```

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Token exhaustion | High | Med | Track token count and implement rate limiting |

## 12. Definition of Done

- [ ] Done
"""


@pytest.fixture
def lld_with_malformed_table():
    """LLD with Section 2.1 header but unparseable table."""
    return """# 1001 - Feature: Test

### 2.1 Files Changed

This section has text but no proper table format.

Just some random content without table structure.

## 11. Risks & Mitigations

| Risk | Impact |
|------|--------|
| Test | Low |

## 12. Definition of Done

- [ ] Done
"""


# =============================================================================
# T010: Parse Valid Files Table
# =============================================================================


class TestParseFilesChangedTable:
    """Tests for parse_files_changed_table function."""

    def test_parse_valid_table(self, valid_lld_content):
        """T010: Parse well-formed table returns list of file dicts."""
        files, errors = parse_files_changed_table(valid_lld_content)

        assert len(errors) == 0
        assert len(files) == 3

        # Check first file
        assert files[0]["path"] == "agentos/workflows/requirements/nodes/validate_mechanical.py"
        assert files[0]["change_type"] == "Add"

        # Check second file
        assert files[1]["path"] == "agentos/workflows/requirements/graph.py"
        assert files[1]["change_type"] == "Modify"

    def test_parse_malformed_table_returns_error(self, lld_with_malformed_table):
        """T020: Parse malformed table returns error, not empty list."""
        files, errors = parse_files_changed_table(lld_with_malformed_table)

        assert len(errors) > 0
        assert any("malformed" in e.message.lower() or "parse" in e.message.lower() for e in errors)


# =============================================================================
# T025-T027: Missing Mandatory Sections
# =============================================================================


class TestValidateMandatorySections:
    """Tests for mandatory section validation."""

    def test_missing_section_21_returns_error(self, lld_missing_section_21):
        """T025: Missing mandatory section 2.1 returns critical ERROR."""
        errors = validate_mandatory_sections(lld_missing_section_21)

        assert len(errors) >= 1
        assert any("2.1" in e.message for e in errors)
        assert all(e.severity == ValidationSeverity.ERROR for e in errors)

    def test_missing_section_11_returns_error(self, lld_missing_section_11):
        """T026: Missing mandatory section 11 returns critical ERROR."""
        errors = validate_mandatory_sections(lld_missing_section_11)

        assert len(errors) >= 1
        assert any("11" in e.message for e in errors)
        assert all(e.severity == ValidationSeverity.ERROR for e in errors)

    def test_missing_section_12_returns_error(self, lld_missing_section_12):
        """T027: Missing mandatory section 12 returns critical ERROR."""
        errors = validate_mandatory_sections(lld_missing_section_12)

        assert len(errors) >= 1
        assert any("12" in e.message for e in errors)
        assert all(e.severity == ValidationSeverity.ERROR for e in errors)

    def test_all_sections_present_no_error(self, valid_lld_content):
        """Valid LLD with all sections returns no errors."""
        errors = validate_mandatory_sections(valid_lld_content)

        assert len(errors) == 0


# =============================================================================
# T030-T060: File Path Validation
# =============================================================================


class TestValidateFilePaths:
    """Tests for file path validation."""

    def test_existing_modify_file_no_error(self, mock_repo):
        """T030: Validate existing Modify file returns no error."""
        files = [{"path": "agentos/workflows/requirements/graph.py", "change_type": "Modify"}]
        errors = validate_file_paths(files, mock_repo)

        assert len(errors) == 0

    def test_nonexistent_modify_file_returns_error(self, mock_repo):
        """T040: Validate non-existent Modify file returns ERROR."""
        files = [{"path": "agentos/workflows/requirements/nonexistent.py", "change_type": "Modify"}]
        errors = validate_file_paths(files, mock_repo)

        assert len(errors) == 1
        assert "nonexistent.py" in errors[0].message
        assert errors[0].severity == ValidationSeverity.ERROR

    def test_add_file_with_valid_parent_no_error(self, mock_repo):
        """T050: Validate Add file with valid parent returns no error."""
        files = [{"path": "agentos/workflows/requirements/nodes/new_file.py", "change_type": "Add"}]
        errors = validate_file_paths(files, mock_repo)

        assert len(errors) == 0

    def test_add_file_with_invalid_parent_returns_error(self, mock_repo):
        """T060: Validate Add file with invalid parent returns ERROR."""
        files = [{"path": "agentos/nonexistent_dir/new_file.py", "change_type": "Add"}]
        errors = validate_file_paths(files, mock_repo)

        assert len(errors) == 1
        assert "parent" in errors[0].message.lower() or "directory" in errors[0].message.lower()
        assert errors[0].severity == ValidationSeverity.ERROR

    def test_delete_nonexistent_file_returns_error(self, mock_repo):
        """Delete file that doesn't exist returns ERROR."""
        files = [{"path": "agentos/workflows/requirements/deleted.py", "change_type": "Delete"}]
        errors = validate_file_paths(files, mock_repo)

        assert len(errors) == 1
        assert errors[0].severity == ValidationSeverity.ERROR


# =============================================================================
# T070-T080: Placeholder Prefix Detection
# =============================================================================


class TestDetectPlaceholderPrefixes:
    """Tests for placeholder prefix detection."""

    def test_src_placeholder_detected_when_missing(self, mock_repo):
        """T070: Detect src/ placeholder returns ERROR when src/ missing."""
        files = [{"path": "src/components/Button.tsx", "change_type": "Add"}]
        errors = detect_placeholder_prefixes(files, mock_repo)

        assert len(errors) == 1
        assert "src" in errors[0].message.lower()
        assert errors[0].severity == ValidationSeverity.ERROR

    def test_src_allowed_when_exists(self, mock_repo):
        """T080: Allow src/ when directory exists."""
        # Create src/ directory
        (mock_repo / "src").mkdir()

        files = [{"path": "src/components/Button.tsx", "change_type": "Add"}]
        errors = detect_placeholder_prefixes(files, mock_repo)

        assert len(errors) == 0

    def test_lib_placeholder_detected(self, mock_repo):
        """Detect lib/ placeholder when missing."""
        files = [{"path": "lib/utils/helper.py", "change_type": "Add"}]
        errors = detect_placeholder_prefixes(files, mock_repo)

        assert len(errors) == 1
        assert "lib" in errors[0].message.lower()

    def test_app_placeholder_detected(self, mock_repo):
        """Detect app/ placeholder when missing."""
        files = [{"path": "app/routes/index.ts", "change_type": "Add"}]
        errors = detect_placeholder_prefixes(files, mock_repo)

        assert len(errors) == 1
        assert "app" in errors[0].message.lower()

    def test_existing_prefix_not_flagged(self, mock_repo):
        """Existing directory prefix (agentos/) not flagged."""
        files = [{"path": "agentos/new_module.py", "change_type": "Add"}]
        errors = detect_placeholder_prefixes(files, mock_repo)

        assert len(errors) == 0


# =============================================================================
# T090-T100: Cross-Reference Sections
# =============================================================================


class TestCrossReferenceSections:
    """Tests for DoD / Files Changed cross-reference."""

    def test_dod_matches_files_changed_no_error(self, valid_lld_content):
        """T090: DoD cross-reference match returns no error."""
        files, _ = parse_files_changed_table(valid_lld_content)
        errors = cross_reference_sections(valid_lld_content, files)

        assert len(errors) == 0

    def test_dod_has_extra_file_returns_error(self, lld_with_dod_mismatch):
        """T100: DoD has extra file not in Files Changed returns ERROR."""
        files, _ = parse_files_changed_table(lld_with_dod_mismatch)
        errors = cross_reference_sections(lld_with_dod_mismatch, files)

        assert len(errors) >= 1
        assert any("extra_file.py" in e.message for e in errors)
        assert all(e.severity == ValidationSeverity.ERROR for e in errors)


# =============================================================================
# T110-T120: Risk Mitigation Tracing
# =============================================================================


class TestTraceMitigationsToFunctions:
    """Tests for risk mitigation tracing."""

    def test_mitigation_with_matching_function_no_warning(self):
        """T110: Mitigation with matching function returns no warning."""
        mitigations = ["Implement rate limiting"]
        functions = ["rate_limit", "do_something", "validate_input"]

        warnings = trace_mitigations_to_functions(mitigations, functions)

        assert len(warnings) == 0

    def test_mitigation_without_matching_function_returns_warning(self):
        """T120: Mitigation without matching function returns WARNING."""
        mitigations = ["Track token count and implement rate limiting"]
        functions = ["do_something", "validate_input"]

        warnings = trace_mitigations_to_functions(mitigations, functions)

        assert len(warnings) >= 1
        assert all(w.severity == ValidationSeverity.WARNING for w in warnings)

    def test_partial_keyword_match_passes(self):
        """Partial keyword match (substring) passes."""
        mitigations = ["Add validation for input"]
        functions = ["validate_user_input", "process_data"]

        warnings = trace_mitigations_to_functions(mitigations, functions)

        # "validation" should match "validate" via keyword extraction
        assert len(warnings) == 0


# =============================================================================
# T130-T140: Full Validation Integration
# =============================================================================


class TestValidateLldMechanical:
    """Integration tests for full validation node."""

    def test_valid_lld_passes_validation(self, mock_repo, valid_lld_content):
        """T130: All checks pass returns state unchanged (not BLOCKED)."""
        state = {
            "current_draft": valid_lld_content,
            "target_repo": str(mock_repo),
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") != "BLOCKED"
        assert not result.get("error_message")

    def test_invalid_path_blocks_validation(self, mock_repo, lld_with_invalid_modify_path):
        """T140: Path check fails returns state BLOCKED."""
        state = {
            "current_draft": lld_with_invalid_modify_path,
            "target_repo": str(mock_repo),
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") == "BLOCKED"
        assert result.get("error_message")
        assert "validation_errors" in result
        assert len(result["validation_errors"]) > 0

    def test_missing_section_blocks_validation(self, mock_repo, lld_missing_section_21):
        """Missing mandatory section blocks validation."""
        state = {
            "current_draft": lld_missing_section_21,
            "target_repo": str(mock_repo),
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") == "BLOCKED"
        assert "2.1" in result.get("error_message", "")

    def test_placeholder_prefix_blocks_validation(self, mock_repo, lld_with_placeholder_prefix):
        """Placeholder prefix without matching directory blocks."""
        state = {
            "current_draft": lld_with_placeholder_prefix,
            "target_repo": str(mock_repo),
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") == "BLOCKED"
        assert "src" in result.get("error_message", "").lower()

    def test_warnings_do_not_block(self, mock_repo, lld_with_untraced_mitigation):
        """Warnings (untraced mitigations) do not block workflow."""
        state = {
            "current_draft": lld_with_untraced_mitigation,
            "target_repo": str(mock_repo),
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        # Should not be blocked (warnings only)
        assert result.get("lld_status") != "BLOCKED"
        # But should have warnings
        assert len(result.get("validation_warnings", [])) > 0

    def test_empty_draft_returns_error(self, mock_repo):
        """Empty draft content returns clear error."""
        state = {
            "current_draft": "",
            "target_repo": str(mock_repo),
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") == "BLOCKED"
        assert result.get("error_message")


# =============================================================================
# Extract Keywords Tests
# =============================================================================


class TestExtractKeywords:
    """Tests for keyword extraction."""

    def test_extracts_significant_words(self):
        """Extracts significant words, filters stopwords."""
        text = "Track the token count and implement rate limiting"
        keywords = extract_keywords(text)

        assert "token" in keywords
        assert "count" in keywords
        assert "rate" in keywords
        assert "limit" in keywords or "limiting" in keywords

        # Stopwords should be filtered
        assert "the" not in keywords
        assert "and" not in keywords

    def test_handles_empty_string(self):
        """Empty string returns empty list."""
        keywords = extract_keywords("")
        assert keywords == []


# =============================================================================
# Extract Functions Tests
# =============================================================================


class TestExtractFunctionNames:
    """Tests for function name extraction from Section 2.4."""

    def test_extracts_function_names(self, valid_lld_content):
        """Extracts function names from code blocks."""
        functions = extract_function_names(valid_lld_content)

        assert "validate_lld_mechanical" in functions
        assert "validate_file_paths" in functions

    def test_handles_no_functions(self):
        """LLD without function signatures returns empty list."""
        content = """# Test LLD

### 2.4 Function Signatures

No code blocks here, just text.
"""
        functions = extract_function_names(content)
        assert functions == []


# =============================================================================
# Extract Mitigations Tests
# =============================================================================


class TestExtractMitigationsFromRisks:
    """Tests for mitigation extraction from Section 11."""

    def test_extracts_mitigations(self, valid_lld_content):
        """Extracts mitigation text from risks table."""
        mitigations = extract_mitigations_from_risks(valid_lld_content)

        assert len(mitigations) >= 1
        assert any("test" in m.lower() for m in mitigations)

    def test_handles_no_mitigations(self):
        """LLD without proper Section 11 returns empty list."""
        content = """# Test LLD

## 11. Risks & Mitigations

No table here.
"""
        mitigations = extract_mitigations_from_risks(content)
        assert mitigations == []
