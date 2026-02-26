"""Unit tests for extract_files_to_modify() fence filtering and directory skipping.

Issue #471: Parser matched tables inside code fences (embedded fixture content).
Issue #472: Directory entries (e.g., 'tests/fixtures/lld_tracking/') crashed
the file writer downstream.

Tests verify:
- Tables inside code fences are skipped
- Real table outside fences is found even when a fake one is inside fences
- Directory entries (Add (Directory), trailing slash) are excluded
- Normal file entries are preserved
"""

from __future__ import annotations

from assemblyzero.workflows.testing.nodes.load_lld import extract_files_to_modify


# --- Issue #471: Code fence filtering ---


def test_table_inside_code_fence_is_skipped():
    """A table inside ``` fences should NOT be parsed."""
    content = (
        "# Implementation Spec\n\n"
        "```markdown\n"
        "### 2.1 Files Changed\n\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| fake/file.py | Add | Fake entry |\n"
        "```\n"
    )
    result = extract_files_to_modify(content)
    assert len(result) == 0, f"Should find 0 files but got: {result}"


def test_real_table_outside_fence_found():
    """Real table outside fences should be found even with fenced fake table."""
    content = (
        "# Implementation Spec\n\n"
        "```markdown\n"
        "### 2.1 Files Changed\n\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| fake/inside_fence.py | Add | Fake entry |\n"
        "```\n\n"
        "### 2.1 Files Changed\n\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| real/outside_fence.py | Modify | Real entry |\n"
    )
    result = extract_files_to_modify(content)
    assert len(result) == 1
    assert result[0]["path"] == "real/outside_fence.py"


def test_spec_format_table_outside_fence():
    """Spec format (## 2. Files to Implement) should also skip fenced tables."""
    content = (
        "# Spec\n\n"
        "```\n"
        "## 2. Files to Implement\n\n"
        "| Order | File | Change Type | Description |\n"
        "|-------|------|-------------|-------------|\n"
        "| 1 | fake/fenced.py | Add | Fake |\n"
        "```\n\n"
        "## 2. Files to Implement\n\n"
        "| Order | File | Change Type | Description |\n"
        "|-------|------|-------------|-------------|\n"
        "| 1 | real/spec_file.py | Modify | Real |\n"
    )
    result = extract_files_to_modify(content)
    assert len(result) == 1
    assert result[0]["path"] == "real/spec_file.py"


# --- Issue #472: Directory entry filtering ---


def test_directory_add_entry_excluded():
    """Entries with 'Add (Directory)' change type should be excluded."""
    content = (
        "### 2.1 Files Changed\n\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| tests/fixtures/tracking/ | Add (Directory) | New fixture dir |\n"
        "| tests/fixtures/tracking/data.json | Add | Test data |\n"
    )
    result = extract_files_to_modify(content)
    assert len(result) == 1
    assert result[0]["path"] == "tests/fixtures/tracking/data.json"


def test_trailing_slash_path_excluded():
    """Paths ending in '/' should be excluded (directory indicator)."""
    content = (
        "### 2.1 Files Changed\n\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| src/utils/ | Add | Utils directory |\n"
        "| src/utils/helpers.py | Add | Helper functions |\n"
    )
    result = extract_files_to_modify(content)
    assert len(result) == 1
    assert result[0]["path"] == "src/utils/helpers.py"


def test_normal_entries_preserved():
    """Normal file entries should pass through unmodified."""
    content = (
        "### 2.1 Files Changed\n\n"
        "| File | Change Type | Description |\n"
        "|------|-------------|-------------|\n"
        "| src/main.py | Modify | Update logic |\n"
        "| tests/test_main.py | Add | New tests |\n"
    )
    result = extract_files_to_modify(content)
    assert len(result) == 2
    assert result[0]["path"] == "src/main.py"
    assert result[1]["path"] == "tests/test_main.py"
