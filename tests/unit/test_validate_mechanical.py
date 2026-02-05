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
        # Issue #306: Title issue number validation
        validate_title_issue_number,
        extract_title_issue_number,
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
    """LLD with risk mitigation that has explicit function reference not in 2.4.

    Issue #312: Only explicit function references (backticks, parens) trigger warnings.
    """
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
| Token exhaustion | High | Med | Call `track_token_count()` to implement rate limiting |

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
        """T120: Mitigation with explicit function reference not in 2.4 returns WARNING.

        Issue #312: Only explicit function references (backticks, parens) trigger warnings.
        """
        # Use explicit function reference (backticks) to trigger warning
        mitigations = ["Call `track_token_count()` to implement rate limiting"]
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

    def test_approach_mitigation_no_warning(self):
        """Issue #312: Approach-style mitigations don't trigger warnings."""
        mitigations = ["O(n) transformation, tested with 500+ rows"]
        functions = ["do_something"]

        warnings = trace_mitigations_to_functions(mitigations, functions)

        # Approach-style mitigation should not trigger warning
        assert len(warnings) == 0

    def test_encoding_approach_no_warning(self):
        """Issue #312: Encoding practice mitigations don't trigger warnings."""
        mitigations = ["Use UTF-8 encoding explicitly throughout"]
        functions = ["do_something"]

        warnings = trace_mitigations_to_functions(mitigations, functions)

        # Encoding practice should not trigger warning
        assert len(warnings) == 0

    def test_backtick_reference_matched_no_warning(self):
        """Issue #312: Backtick reference that matches function has no warning."""
        mitigations = ["Call `validate_input()` to check data"]
        functions = ["validate_input", "process_data"]

        warnings = trace_mitigations_to_functions(mitigations, functions)

        # Referenced function exists - no warning
        assert len(warnings) == 0


# =============================================================================
# Issue #312: Pattern Detection Tests
# =============================================================================


class TestContainsExplicitFunctionReference:
    """Tests for explicit function reference detection."""

    def test_detects_backtick_reference(self):
        """Backtick function reference detected."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            contains_explicit_function_reference,
        )

        has_ref, refs = contains_explicit_function_reference("Call `my_function` here")

        assert has_ref is True
        assert "my_function" in refs

    def test_detects_parentheses_reference(self):
        """Parentheses function reference detected."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            contains_explicit_function_reference,
        )

        has_ref, refs = contains_explicit_function_reference("Call my_function() here")

        assert has_ref is True
        assert "my_function" in refs

    def test_no_reference_returns_false(self):
        """Plain text without function reference returns False."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            contains_explicit_function_reference,
        )

        has_ref, refs = contains_explicit_function_reference("Just a plain description")

        assert has_ref is False
        assert len(refs) == 0


class TestIsApproachMitigation:
    """Tests for approach-style mitigation detection."""

    def test_detects_complexity_notation(self):
        """Complexity notation O(n) detected."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            is_approach_mitigation,
        )

        is_approach, patterns = is_approach_mitigation("O(n) transformation")

        assert is_approach is True
        assert len(patterns) > 0

    def test_detects_encoding_reference(self):
        """Encoding reference detected."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            is_approach_mitigation,
        )

        is_approach, patterns = is_approach_mitigation("Use UTF-8 encoding")

        assert is_approach is True

    def test_function_description_not_approach(self):
        """Function description is not classified as approach."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            is_approach_mitigation,
        )

        is_approach, patterns = is_approach_mitigation("Call validate_input to check")

        assert is_approach is False


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


# =============================================================================
# Issue #306: Title Issue Number Validation Tests
# =============================================================================


class TestExtractTitleIssueNumber:
    """Tests for extract_title_issue_number function."""

    def test_extracts_standard_format(self):
        """T010: Extract standard format # 306 - Feature."""
        content = "# 306 - Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result == 306

    def test_extracts_leading_zeros(self):
        """T040: Extract number with leading zeros (099 -> 99)."""
        content = "# 0099 - Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result == 99

    def test_extracts_with_en_dash(self):
        """T050: Extract with en-dash separator (–)."""
        content = "# 306 – Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result == 306

    def test_extracts_with_em_dash(self):
        """T060: Extract with em-dash separator (—)."""
        content = "# 306 — Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result == 306

    def test_extracts_multi_digit(self):
        """T080: Extract multi-digit issue numbers."""
        content = "# 1234 - Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result == 1234

    def test_extracts_single_digit(self):
        """T090: Extract single digit issue numbers."""
        content = "# 5 - Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result == 5

    def test_returns_none_for_missing_number(self):
        """T030: Return None when no number in title."""
        content = "# Feature: Test Title\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result is None

    def test_returns_none_for_no_h1(self):
        """T070: Return None when no H1 heading."""
        content = "## 306 - Not an H1\n\n## 1. Context"
        result = extract_title_issue_number(content)
        assert result is None


class TestValidateTitleIssueNumber:
    """Tests for validate_title_issue_number function."""

    def test_matching_number_returns_empty_list(self):
        """T010: Matching issue number returns empty error list."""
        content = "# 306 - Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 306)
        assert len(errors) == 0

    def test_mismatched_number_returns_block_error(self):
        """T020: Mismatched number returns BLOCK (ERROR severity) error."""
        content = "# 199 - Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 306)

        assert len(errors) == 1
        assert errors[0].severity == ValidationSeverity.ERROR
        assert "199" in errors[0].message
        assert "306" in errors[0].message

    def test_missing_number_returns_warning(self):
        """T030: Missing number in title returns WARNING."""
        content = "# Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 306)

        assert len(errors) == 1
        assert errors[0].severity == ValidationSeverity.WARNING
        assert "extract" in errors[0].message.lower()

    def test_leading_zeros_match(self):
        """T040: Leading zeros match correctly (099 matches 99)."""
        content = "# 0306 - Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 306)
        assert len(errors) == 0

    def test_en_dash_format_passes(self):
        """T050: En-dash separator passes validation."""
        content = "# 306 – Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 306)
        assert len(errors) == 0

    def test_em_dash_format_passes(self):
        """T060: Em-dash separator passes validation."""
        content = "# 306 — Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 306)
        assert len(errors) == 0

    def test_no_h1_returns_warning(self):
        """T070: No H1 heading returns WARNING."""
        content = "## 306 - Not an H1 Title\n\nContent here"
        errors = validate_title_issue_number(content, 306)

        assert len(errors) == 1
        assert errors[0].severity == ValidationSeverity.WARNING
        assert "H1" in errors[0].message

    def test_multi_digit_numbers_work(self):
        """T080: Multi-digit issue numbers validate correctly."""
        content = "# 1234 - Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 1234)
        assert len(errors) == 0

    def test_single_digit_numbers_work(self):
        """T090: Single digit issue numbers validate correctly."""
        content = "# 5 - Feature: Test Title\n\n## 1. Context"
        errors = validate_title_issue_number(content, 5)
        assert len(errors) == 0


# =============================================================================
# Issue #322: Repo Root Validation Tests
# =============================================================================


class TestRepoRootValidation:
    """Tests for repo_root validation in mechanical validation.

    Issue #322: Explicit check for invalid/missing repo_root, returning
    blocking error instead of silent skip.
    """

    def test_validation_blocks_when_repo_root_none(self):
        """T010: repo_root=None returns blocking error with BLOCKED status."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_repo_root,
        )

        is_valid, error = validate_repo_root(None)

        assert is_valid is False
        assert error is not None
        assert "not specified" in error.lower()

    def test_validation_blocks_when_repo_root_empty(self):
        """T020: repo_root=Path("") returns blocking error with BLOCKED status."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_repo_root,
        )

        is_valid, error = validate_repo_root(Path(""))

        assert is_valid is False
        assert error is not None
        assert "not specified" in error.lower() or "empty" in error.lower()

    def test_validation_blocks_when_repo_root_nonexistent(self):
        """T030: Non-existent repo_root returns blocking error with path in message."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_repo_root,
        )

        nonexistent_path = Path("/nonexistent/path/that/does/not/exist")
        is_valid, error = validate_repo_root(nonexistent_path)

        assert is_valid is False
        assert error is not None
        assert "does not exist" in error.lower()

    def test_validation_proceeds_when_repo_root_valid(self, tmp_path):
        """T040: Valid existing repo_root passes validation."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_repo_root,
        )

        is_valid, error = validate_repo_root(tmp_path)

        assert is_valid is True
        assert error is None

    def test_error_message_includes_path(self):
        """T050: Error message contains the invalid path for debugging."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_repo_root,
        )

        specific_path = Path("/specific/test/path/for/debugging")
        is_valid, error = validate_repo_root(specific_path)

        assert is_valid is False
        assert error is not None
        # Path separators vary by OS (/ on Unix, \ on Windows)
        assert "specific" in error and "test" in error and "path" in error


class TestRepoRootValidationIntegration:
    """Integration tests for repo_root validation in full mechanical validation."""

    def test_full_validation_blocks_on_none_repo(self):
        """Integration: validate_lld_mechanical returns BLOCKED when target_repo is None."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_lld_mechanical,
        )

        # Complete LLD with all required sections so we reach repo_root validation
        lld_content = """# 100 - Feature: Test

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `test.py` | Add | Test file |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| None | Low | Low | None |

## 12. Definition of Done

- [ ] Done
"""

        state = {
            "current_draft": lld_content,
            "target_repo": None,
            "issue_number": 100,
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") == "BLOCKED"
        assert len(result.get("validation_errors", [])) > 0
        # Check for repo-related error message
        errors_str = " ".join(str(e) for e in result.get("validation_errors", []))
        assert "target_repo" in errors_str.lower() or "not specified" in errors_str.lower()

    def test_full_validation_blocks_on_empty_repo(self):
        """Integration: validate_lld_mechanical returns BLOCKED when target_repo is empty."""
        from agentos.workflows.requirements.nodes.validate_mechanical import (
            validate_lld_mechanical,
        )

        # Complete LLD with all required sections so we reach repo_root validation
        lld_content = """# 100 - Feature: Test

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `test.py` | Add | Test file |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| None | Low | Low | None |

## 12. Definition of Done

- [ ] Done
"""

        state = {
            "current_draft": lld_content,
            "target_repo": "",
            "issue_number": 100,
        }

        result = validate_lld_mechanical(state)

        assert result.get("lld_status") == "BLOCKED"
        assert len(result.get("validation_errors", [])) > 0


class TestTitleValidationIntegration:
    """Integration tests for title validation in mechanical validation pipeline."""

    def test_validator_functions_exist(self):
        """T100: Title validation functions are callable."""
        # Verify functions exist and are callable
        assert callable(validate_title_issue_number)
        assert callable(extract_title_issue_number)

    def test_pipeline_invokes_title_validation_on_mismatch(self, mock_repo):
        """T110: validate_lld_mechanical calls title validation when issue_number provided."""
        # LLD with mismatched title
        content = """# 199 - Feature: Wrong Issue

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/test.py` | Add | New file |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| None | Low | Low | None |

## 12. Definition of Done

- [ ] Done
"""
        state = {
            "current_draft": content,
            "target_repo": str(mock_repo),
            "issue_number": 306,
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        # Should be blocked due to issue number mismatch
        assert result.get("lld_status") == "BLOCKED"
        assert any("199" in err and "306" in err for err in result.get("validation_errors", []))

    def test_pipeline_passes_with_matching_title(self, mock_repo):
        """Title validation passes when issue numbers match."""
        content = """# 306 - Feature: Correct Issue

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/graph.py` | Modify | Update |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| None | Low | Low | None |

## 12. Definition of Done

- [ ] Done
"""
        state = {
            "current_draft": content,
            "target_repo": str(mock_repo),
            "issue_number": 306,
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        # Should NOT be blocked
        assert result.get("lld_status") != "BLOCKED"

    def test_pipeline_skips_title_validation_without_issue_number(self, mock_repo):
        """Title validation skipped when issue_number not in state."""
        content = """# 999 - Feature: Wrong Issue

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/graph.py` | Modify | Update |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| None | Low | Low | None |

## 12. Definition of Done

- [ ] Done
"""
        state = {
            "current_draft": content,
            "target_repo": str(mock_repo),
            # No issue_number provided
            "lld_status": "PENDING",
            "workflow_type": "lld",
        }

        result = validate_lld_mechanical(state)

        # Should NOT be blocked (issue number not validated)
        assert result.get("lld_status") != "BLOCKED"
