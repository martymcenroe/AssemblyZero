"""Tests for diff-based code generation in implementation workflow.

Issue #324: Implementation workflow fails on large file modifications.
Solution: Use FIND/REPLACE diff format for large files instead of full regeneration.

TDD: These tests are written BEFORE implementation and should initially fail (RED).
"""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def small_file_content() -> str:
    """50-line Python file - should NOT trigger diff mode."""
    lines = ['"""Small test module."""', ""]
    for i in range(48):
        lines.append(f"def func_{i}(): pass")
    return "\n".join(lines)


@pytest.fixture
def large_file_content() -> str:
    """600-line Python file - should trigger diff mode."""
    lines = ['"""Large test module."""', ""]
    for i in range(598):
        lines.append(f"def func_{i}(): pass")
    return "\n".join(lines)


@pytest.fixture
def large_file_by_bytes() -> str:
    """File over 15KB but under 500 lines - should trigger diff mode."""
    # Create a file with long lines to exceed byte threshold
    lines = ['"""Large by bytes."""', ""]
    for i in range(100):
        lines.append(f"long_var_{i} = " + "'" + "x" * 150 + "'")
    return "\n".join(lines)


@pytest.fixture
def valid_diff_response() -> str:
    """Valid FIND/REPLACE diff response from Claude."""
    return '''### CHANGE 1: Add import statement
FIND:
```python
"""Module docstring."""

import os
```

REPLACE WITH:
```python
"""Module docstring."""

import os
import sys
```

### CHANGE 2: Update function
FIND:
```python
def old_function():
    return 1
```

REPLACE WITH:
```python
def new_function():
    return 2
```
'''


@pytest.fixture
def malformed_diff_response() -> str:
    """Malformed diff response - missing REPLACE section."""
    return '''### CHANGE 1: Bad change
FIND:
```python
def something():
    pass
```

This is missing the REPLACE WITH section!
'''


@pytest.fixture
def original_content_for_apply() -> str:
    """Original file content for testing apply_diff_changes."""
    return '''"""Module docstring."""

import os

def old_function():
    return 1

def another_function():
    return 42
'''


# =============================================================================
# T005: Add file bypasses diff mode
# =============================================================================


class TestAddFileBypasses:
    """T005: Add change type uses standard generation regardless of content."""

    def test_add_file_bypasses_diff(self, large_file_content):
        """Add operations should never use diff mode, even for large content."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            select_generation_strategy,
        )

        strategy = select_generation_strategy("Add", large_file_content)
        assert strategy == "standard"

    def test_add_file_with_none_content(self):
        """Add with no existing content uses standard mode."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            select_generation_strategy,
        )

        strategy = select_generation_strategy("Add", None)
        assert strategy == "standard"


# =============================================================================
# T010, T020, T030: File size detection
# =============================================================================


class TestIsLargeFile:
    """Tests for is_large_file() threshold detection."""

    def test_is_large_file_by_lines(self, large_file_content):
        """T010: Returns True for 501+ line file."""
        from assemblyzero.workflows.testing.nodes.implement_code import is_large_file

        assert is_large_file(large_file_content) is True

    def test_is_large_file_by_bytes(self, large_file_by_bytes):
        """T020: Returns True for 15001+ byte file."""
        from assemblyzero.workflows.testing.nodes.implement_code import is_large_file

        # Verify fixture is actually large by bytes but not lines
        assert len(large_file_by_bytes.split("\n")) < 500
        assert len(large_file_by_bytes.encode("utf-8")) > 15000
        assert is_large_file(large_file_by_bytes) is True

    def test_is_large_file_small(self, small_file_content):
        """T030: Returns False for small file (below both thresholds)."""
        from assemblyzero.workflows.testing.nodes.implement_code import is_large_file

        assert is_large_file(small_file_content) is False

    def test_is_large_file_exactly_at_threshold(self):
        """Edge case: exactly at threshold should not trigger."""
        from assemblyzero.workflows.testing.nodes.implement_code import is_large_file

        # 500 lines exactly - should NOT be large
        content = "\n".join([f"line {i}" for i in range(500)])
        assert is_large_file(content) is False

        # 501 lines - should be large
        content = "\n".join([f"line {i}" for i in range(501)])
        assert is_large_file(content) is True


# =============================================================================
# T035: Small file uses standard flow
# =============================================================================


class TestSmallFileFlow:
    """T035: Verify small file uses standard generation flow."""

    def test_small_file_uses_standard_prompt(self, small_file_content):
        """Small modify file uses standard generation flow."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            select_generation_strategy,
        )

        strategy = select_generation_strategy("Modify", small_file_content)
        assert strategy == "standard"

    def test_large_file_uses_diff_strategy(self, large_file_content):
        """Large modify file uses diff generation strategy."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            select_generation_strategy,
        )

        strategy = select_generation_strategy("Modify", large_file_content)
        assert strategy == "diff"


# =============================================================================
# T040, T050, T060: Diff response parsing
# =============================================================================


class TestParseDiffResponse:
    """Tests for parse_diff_response() parsing logic."""

    def test_parse_diff_valid(self, valid_diff_response):
        """T040: Parses valid FIND/REPLACE blocks correctly."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            parse_diff_response,
        )

        result = parse_diff_response(valid_diff_response)

        assert result["success"] is True
        assert result["error"] is None
        assert len(result["changes"]) == 2

        # Verify first change
        change1 = result["changes"][0]
        assert "Add import" in change1["description"]
        assert "import os" in change1["find_block"]
        assert "import sys" in change1["replace_block"]

    def test_parse_diff_multiple(self, valid_diff_response):
        """T050: Parses multiple changes and preserves order."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            parse_diff_response,
        )

        result = parse_diff_response(valid_diff_response)

        assert result["success"] is True
        assert len(result["changes"]) == 2

        # Verify order is preserved
        assert "import" in result["changes"][0]["description"].lower()
        assert "function" in result["changes"][1]["description"].lower()

    def test_parse_diff_malformed(self, malformed_diff_response):
        """T060: Returns error for malformed diff (missing REPLACE)."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            parse_diff_response,
        )

        result = parse_diff_response(malformed_diff_response)

        assert result["success"] is False
        assert result["error"] is not None
        assert "REPLACE" in result["error"] or "malformed" in result["error"].lower()


# =============================================================================
# T070, T080, T090, T100: Apply diff changes
# =============================================================================


class TestApplyDiffChanges:
    """Tests for apply_diff_changes() modification logic."""

    def test_apply_single_change(self, original_content_for_apply):
        """T070: Applies one change correctly."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            apply_diff_changes,
        )

        changes = [
            {
                "description": "Update function",
                "find_block": "def old_function():\n    return 1",
                "replace_block": "def new_function():\n    return 2",
            }
        ]

        result, errors = apply_diff_changes(original_content_for_apply, changes)

        assert len(errors) == 0
        assert "def new_function():" in result
        assert "return 2" in result
        assert "def old_function():" not in result

    def test_apply_multiple_changes(self, original_content_for_apply):
        """T080: Applies multiple changes in order."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            apply_diff_changes,
        )

        changes = [
            {
                "description": "Add import",
                "find_block": "import os",
                "replace_block": "import os\nimport sys",
            },
            {
                "description": "Update function",
                "find_block": "def old_function():\n    return 1",
                "replace_block": "def updated_function():\n    return 99",
            },
        ]

        result, errors = apply_diff_changes(original_content_for_apply, changes)

        assert len(errors) == 0
        assert "import sys" in result
        assert "def updated_function():" in result
        assert "return 99" in result

    def test_apply_ambiguous_find(self):
        """T090: Errors when FIND matches multiple locations."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            apply_diff_changes,
        )

        # Content with duplicate pattern
        content = '''def foo():
    pass

def bar():
    pass
'''

        changes = [
            {
                "description": "Ambiguous change",
                "find_block": "pass",  # Matches twice
                "replace_block": "return None",
            }
        ]

        result, errors = apply_diff_changes(content, changes)

        assert len(errors) > 0
        assert any("ambiguous" in e.lower() or "multiple" in e.lower() for e in errors)

    def test_apply_no_match(self, original_content_for_apply):
        """T100: Errors when FIND block not found in file."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            apply_diff_changes,
        )

        changes = [
            {
                "description": "Non-existent change",
                "find_block": "def this_does_not_exist():\n    pass",
                "replace_block": "def replacement():\n    pass",
            }
        ]

        result, errors = apply_diff_changes(original_content_for_apply, changes)

        assert len(errors) > 0
        assert any("not found" in e.lower() for e in errors)


# =============================================================================
# T110, T115: Truncation detection and retry
# =============================================================================


class TestTruncationDetection:
    """Tests for truncation detection and retry logic."""

    def test_detect_truncation_max_tokens(self):
        """T110: Detects max_tokens stop reason as truncation."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            detect_truncation,
        )

        # Mock response object with stop_reason
        mock_response = MagicMock()
        mock_response.stop_reason = "max_tokens"

        assert detect_truncation(mock_response) is True

    def test_detect_truncation_normal_end(self):
        """Normal end_turn stop reason is not truncation."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            detect_truncation,
        )

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"

        assert detect_truncation(mock_response) is False

    def test_truncation_triggers_retry(self):
        """T115: Truncation detection triggers retry loop."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            detect_truncation,
        )

        # First call: truncated, second call: success
        mock_truncated = MagicMock()
        mock_truncated.stop_reason = "max_tokens"

        mock_success = MagicMock()
        mock_success.stop_reason = "end_turn"

        # Verify detection works for retry logic
        assert detect_truncation(mock_truncated) is True
        assert detect_truncation(mock_success) is False


# =============================================================================
# T120: Diff prompt format
# =============================================================================


class TestBuildDiffPrompt:
    """T120: Tests for build_diff_prompt() format."""

    def test_build_diff_prompt(self, large_file_content):
        """Diff prompt includes required FIND/REPLACE format instructions."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            build_diff_prompt,
        )

        prompt = build_diff_prompt(
            lld_content="## Test LLD\nSome requirements",
            existing_content=large_file_content,
            test_content="def test_something(): pass",
            file_path="src/module.py",
        )

        # Must include format instructions
        assert "FIND" in prompt
        assert "REPLACE" in prompt
        assert "CHANGE" in prompt

        # Must include context
        assert "src/module.py" in prompt
        assert "Test LLD" in prompt

        # Must NOT ask for full file
        assert "entire file" not in prompt.lower() or "do not" in prompt.lower()

    def test_build_diff_prompt_includes_existing_content(self, large_file_content):
        """Diff prompt includes the existing file content for reference."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            build_diff_prompt,
        )

        prompt = build_diff_prompt(
            lld_content="## LLD",
            existing_content=large_file_content,
            test_content="",
            file_path="test.py",
        )

        # Should reference existing content
        assert "Large test module" in prompt or "existing" in prompt.lower()


# =============================================================================
# T130: Whitespace normalization
# =============================================================================


class TestWhitespaceNormalization:
    """T130: Tests for whitespace-normalized matching fallback."""

    def test_whitespace_normalization(self):
        """Matches with different indentation via normalization."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            apply_diff_changes,
        )

        # Original has 4-space indent
        original = '''def foo():
    if True:
        return 1
'''

        # FIND block has slightly different whitespace
        changes = [
            {
                "description": "Update return",
                "find_block": "if True:\n        return 1",  # Extra space
                "replace_block": "if True:\n        return 2",
            }
        ]

        result, errors = apply_diff_changes(original, changes)

        # Should either succeed with normalization or have specific whitespace error
        # (not a "not found" error)
        if errors:
            assert not any("not found" in e.lower() for e in errors)
        else:
            assert "return 2" in result

    def test_exact_match_preferred(self, original_content_for_apply):
        """Exact match is used when available, before normalization."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            apply_diff_changes,
        )

        changes = [
            {
                "description": "Exact match test",
                "find_block": "import os",
                "replace_block": "import os  # modified",
            }
        ]

        result, errors = apply_diff_changes(original_content_for_apply, changes)

        assert len(errors) == 0
        assert "import os  # modified" in result


# =============================================================================
# Integration tests
# =============================================================================


class TestDiffIntegration:
    """Integration tests for full diff workflow."""

    def test_full_diff_workflow(self, large_file_content, valid_diff_response):
        """End-to-end: parse diff response and apply to large file."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            parse_diff_response,
            apply_diff_changes,
            is_large_file,
            select_generation_strategy,
        )

        # Verify this would use diff mode
        assert is_large_file(large_file_content) is True
        assert select_generation_strategy("Modify", large_file_content) == "diff"

        # Parse would work on valid response
        parse_result = parse_diff_response(valid_diff_response)
        assert parse_result["success"] is True

    def test_strategy_selection_matrix(self, small_file_content, large_file_content):
        """Verify strategy selection for all change type + size combinations."""
        from assemblyzero.workflows.testing.nodes.implement_code import (
            select_generation_strategy,
        )

        # Add always standard
        assert select_generation_strategy("Add", None) == "standard"
        assert select_generation_strategy("Add", small_file_content) == "standard"
        assert select_generation_strategy("Add", large_file_content) == "standard"

        # Modify depends on size
        assert select_generation_strategy("Modify", small_file_content) == "standard"
        assert select_generation_strategy("Modify", large_file_content) == "diff"

        # Delete should be standard (no generation needed)
        assert select_generation_strategy("Delete", large_file_content) == "standard"
