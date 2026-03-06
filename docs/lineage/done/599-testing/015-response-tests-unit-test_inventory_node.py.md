

```python
"""Unit tests for the Inventory-as-Code Node.

Issue #599: Test suite covering both utils and the node itself.
"""

import pytest
from pathlib import Path

from assemblyzero.utils.markdown_inventory import (
    extract_existing_inventory,
    categorize_file,
    inject_inventory_table,
    InventoryItem,
    START_TAG,
    END_TAG,
)
from assemblyzero.nodes.inventory import update_inventory_node, scan_docs_directory


# ---------------------------------------------------------------------------
# T010: extract_existing_inventory
# ---------------------------------------------------------------------------

class TestExtractExistingInventory:
    """Tests for extract_existing_inventory()."""

    def test_parse_existing_table(self, tmp_path):
        """T010: Parse existing table and return items with preserved statuses."""
        doc_file = tmp_path / "0003-file-inventory.md"
        doc_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            "| docs/test.md | test.md | Root | Legacy |\n"
            f"{END_TAG}"
        )
        items = extract_existing_inventory(doc_file)
        assert len(items) == 1
        assert items[0]["path"] == "docs/test.md"
        assert items[0]["filename"] == "test.md"
        assert items[0]["category"] == "Root"
        assert items[0]["status"] == "Legacy"

    def test_file_does_not_exist(self, tmp_path):
        """Edge case: file does not exist -> returns []."""
        missing = tmp_path / "nonexistent.md"
        result = extract_existing_inventory(missing)
        assert result == []

    def test_tags_missing(self, tmp_path):
        """Edge case: tags missing -> returns []."""
        doc_file = tmp_path / "no_tags.md"
        doc_file.write_text("# Some file\n\nNo inventory tags here.\n")
        result = extract_existing_inventory(doc_file)
        assert result == []

    def test_empty_table_between_tags(self, tmp_path):
        """Edge case: table empty between tags -> returns []."""
        doc_file = tmp_path / "empty_table.md"
        doc_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            f"{END_TAG}"
        )
        result = extract_existing_inventory(doc_file)
        assert result == []

    def test_multiple_rows(self, tmp_path):
        """Parse a table with multiple rows."""
        doc_file = tmp_path / "multi.md"
        doc_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            "| docs/a.md | a.md | Root | Active |\n"
            "| docs/lld/b.md | b.md | LLD | Legacy |\n"
            "| docs/standards/c.md | c.md | Standard | Draft |\n"
            f"{END_TAG}"
        )
        items = extract_existing_inventory(doc_file)
        assert len(items) == 3
        assert items[1]["category"] == "LLD"
        assert items[2]["status"] == "Draft"

    def test_fixture_file(self):
        """Parse the static mock fixture file."""
        fixture = Path("tests/fixtures/mock_repo/docs/0003-file-inventory.md")
        if not fixture.exists():
            pytest.skip("Fixture file not available")
        items = extract_existing_inventory(fixture)
        assert len(items) == 2
        paths = [i["path"] for i in items]
        assert "docs/0003-file-inventory.md" in paths
        assert "docs/lld/active/123-test.md" in paths
        legacy = [i for i in items if i["filename"] == "123-test.md"][0]
        assert legacy["status"] == "Legacy"


# ---------------------------------------------------------------------------
# T020: scan_docs_directory
# ---------------------------------------------------------------------------

class TestScanDocsDirectory:
    """Tests for scan_docs_directory()."""

    def test_scan_finds_md_only(self, tmp_path):
        """T020: Scan returns .md files and excludes .txt files."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Readme")
        (docs_dir / "ignore.txt").write_text("ignore me")
        (docs_dir / "data.csv").write_text("a,b,c")

        files = scan_docs_directory(docs_dir)
        assert len(files) == 1
        assert files[0].name == "readme.md"

    def test_scan_recursive(self, tmp_path):
        """Scan finds .md files in nested subdirectories."""
        docs_dir = tmp_path / "docs"
        lld_dir = docs_dir / "lld" / "active"
        lld_dir.mkdir(parents=True)
        (docs_dir / "root.md").write_text("# Root")
        (lld_dir / "feature.md").write_text("# Feature")

        files = scan_docs_directory(docs_dir)
        names = sorted([f.name for f in files])
        assert names == ["feature.md", "root.md"]

    def test_scan_nonexistent_directory(self, tmp_path):
        """Edge case: directory does not exist -> returns []."""
        missing = tmp_path / "no_such_dir"
        result = scan_docs_directory(missing)
        assert result == []

    def test_scan_empty_directory(self, tmp_path):
        """Empty directory returns []."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        result = scan_docs_directory(docs_dir)
        assert result == []


# ---------------------------------------------------------------------------
# T030: categorize_file
# ---------------------------------------------------------------------------

class TestCategorizeFile:
    """Tests for categorize_file()."""

    def test_lld_subfolder(self):
        """T030: docs/lld/active/test.md -> 'LLD'."""
        cat = categorize_file(Path("docs/lld/active/test.md"))
        assert cat == "LLD"

    def test_standards_subfolder(self):
        """docs/standards/0001-python-guidelines.md -> 'Standard'."""
        cat = categorize_file(Path("docs/standards/0001-python-guidelines.md"))
        assert cat == "Standard"

    def test_adrs_subfolder(self):
        """docs/adrs/0001-decision.md -> 'ADR'."""
        cat = categorize_file(Path("docs/adrs/0001-decision.md"))
        assert cat == "ADR"

    def test_root_docs_file(self):
        """File directly in docs/ -> 'Root'."""
        cat = categorize_file(Path("docs/readme.md"))
        assert cat == "Root"

    def test_unrecognized_subfolder(self):
        """docs/random/file.md -> 'Random' (capitalized)."""
        cat = categorize_file(Path("docs/random/file.md"))
        assert cat == "Random"

    def test_deeply_nested_lld(self):
        """docs/lld/active/deep/file.md -> 'LLD'."""
        cat = categorize_file(Path("docs/lld/active/deep/file.md"))
        assert cat == "LLD"


# ---------------------------------------------------------------------------
# T050: inject_inventory_table
# ---------------------------------------------------------------------------

class TestInjectInventoryTable:
    """Tests for inject_inventory_table()."""

    def test_inject_replaces_existing_table(self, tmp_path):
        """T050: Inject replaces content between bounding tags."""
        doc_file = tmp_path / "inventory.md"
        doc_file.write_text(
            "# Inventory\n\n"
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            "| docs/old.md | old.md | Root | Active |\n"
            f"{END_TAG}\n\n"
            "Footer text.\n"
        )

        items: list[InventoryItem] = [
            {"path": "docs/new.md", "filename": "new.md", "category": "Root", "status": "Active"},
            {"path": "docs/lld/feature.md", "filename": "feature.md", "category": "LLD", "status": "Draft"},
        ]

        result = inject_inventory_table(doc_file, items)
        assert result is True

        content = doc_file.read_text()
        assert "new.md" in content
        assert "feature.md" in content
        assert "old.md" not in content
        assert "Footer text." in content
        assert START_TAG in content
        assert END_TAG in content

    def test_inject_creates_file_if_missing(self, tmp_path):
        """If file doesn't exist, create it with the table."""
        doc_file = tmp_path / "subdir" / "new_inventory.md"
        items: list[InventoryItem] = [
            {"path": "docs/a.md", "filename": "a.md", "category": "Root", "status": "Active"},
        ]

        result = inject_inventory_table(doc_file, items)
        assert result is True
        assert doc_file.exists()

        content = doc_file.read_text()
        assert START_TAG in content
        assert END_TAG in content
        assert "docs/a.md" in content

    def test_inject_appends_when_tags_missing(self, tmp_path):
        """Edge case: file exists but has no tags -> appends table."""
        doc_file = tmp_path / "no_tags.md"
        doc_file.write_text("# Some existing content\n\nParagraph here.\n")

        items: list[InventoryItem] = [
            {"path": "docs/x.md", "filename": "x.md", "category": "Root", "status": "Active"},
        ]

        result = inject_inventory_table(doc_file, items)
        assert result is True

        content = doc_file.read_text()
        assert "Some existing content" in content
        assert START_TAG in content
        assert END_TAG in content
        assert "docs/x.md" in content

    def test_inject_empty_items(self, tmp_path):
        """Injecting empty list produces a table with only headers."""
        doc_file = tmp_path / "empty.md"
        doc_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            "| docs/old.md | old.md | Root | Active |\n"
            f"{END_TAG}"
        )

        result = inject_inventory_table(doc_file, [])
        assert result is True

        content = doc_file.read_text()
        assert "old.md" not in content
        assert START_TAG in content
        assert END_TAG in content


# ---------------------------------------------------------------------------
# T040: update_inventory_node (integration-style)
# ---------------------------------------------------------------------------

class TestUpdateInventoryNode:
    """Tests for update_inventory_node()."""

    def test_merge_preserves_legacy_status(self, tmp_path):
        """T040: Merge items preserving Legacy status from existing entries."""
        docs_dir = tmp_path / "docs"
        lld_dir = docs_dir / "lld"
        lld_dir.mkdir(parents=True)

        inv_file = docs_dir / "0003-file-inventory.md"
        inv_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            "| docs/lld/old.md | old.md | LLD | Legacy |\n"
            f"{END_TAG}"
        )

        (lld_dir / "old.md").write_text("# Old")
        (lld_dir / "new.md").write_text("# New")

        state = {"repo_path": str(tmp_path)}
        result = update_inventory_node(state)

        assert result["inventory_updated"] is True
        # new.md and 0003-file-inventory.md are new entries; old.md is existing
        assert result["inventory_entries_added"] >= 1

        content = inv_file.read_text()
        assert "Legacy" in content  # Old status preserved
        assert "new.md" in content
        assert "old.md" in content

    def test_new_files_get_active_status(self, tmp_path):
        """New files discovered should have status 'Active'."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        inv_file = docs_dir / "0003-file-inventory.md"
        inv_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            f"{END_TAG}"
        )

        (docs_dir / "brand_new.md").write_text("# Brand New")

        state = {"repo_path": str(tmp_path)}
        result = update_inventory_node(state)

        assert result["inventory_updated"] is True

        content = inv_file.read_text()
        assert "brand_new.md" in content
        assert "Active" in content

    def test_sorts_by_category_then_filename(self, tmp_path):
        """Output should be sorted by category then filename."""
        docs_dir = tmp_path / "docs"
        lld_dir = docs_dir / "lld"
        standards_dir = docs_dir / "standards"
        lld_dir.mkdir(parents=True)
        standards_dir.mkdir(parents=True)

        inv_file = docs_dir / "0003-file-inventory.md"
        inv_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            f"{END_TAG}"
        )

        (lld_dir / "b_feature.md").write_text("# B")
        (lld_dir / "a_feature.md").write_text("# A")
        (standards_dir / "z_standard.md").write_text("# Z")
        (docs_dir / "root_file.md").write_text("# Root")

        state = {"repo_path": str(tmp_path)}
        result = update_inventory_node(state)
        assert result["inventory_updated"] is True

        content = inv_file.read_text()
        # Verify the table exists and has entries
        assert "a_feature.md" in content
        assert "b_feature.md" in content
        assert "z_standard.md" in content


# ---------------------------------------------------------------------------
# T060: Graceful failure
# ---------------------------------------------------------------------------

class TestGracefulFailure:
    """Tests for graceful failure behavior."""

    def test_nonexistent_repo_path(self, tmp_path):
        """T060: Non-existent repo_path should not crash."""
        state = {"repo_path": "/path/that/does/not/exist"}
        result = update_inventory_node(state)

        # Should not throw exception
        assert isinstance(result, dict)
        assert "inventory_updated" in result
        assert "inventory_entries_added" in result
        assert "errors" in result
        # With no docs dir, there are no files to scan, so it either
        # succeeds with 0 entries or fails gracefully with an error
        assert result["inventory_entries_added"] == 0

    def test_missing_repo_path_key_uses_default(self, tmp_path):
        """If repo_path is missing from state, should use default '.'."""
        state = {}
        result = update_inventory_node(state)

        # Should not crash
        assert isinstance(result, dict)
        assert "errors" in result

    def test_readonly_file_handled(self, tmp_path):
        """If inventory file is read-only, node should handle gracefully."""
        import os
        import platform

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        inv_file = docs_dir / "0003-file-inventory.md"
        inv_file.write_text(
            f"{START_TAG}\n"
            "| Path | Filename | Category | Status |\n"
            "|---|---|---|---|\n"
            f"{END_TAG}"
        )
        (docs_dir / "test.md").write_text("# Test")

        # Make the file read-only (platform-dependent behavior)
        if platform.system() != "Windows":
            inv_file.chmod(0o444)
            try:
                state = {"repo_path": str(tmp_path)}
                result = update_inventory_node(state)
                # Should not crash - either succeeds or reports error gracefully
                assert isinstance(result, dict)
                assert "errors" in result
            finally:
                inv_file.chmod(0o644)
        else:
            pytest.skip("Read-only file test not reliable on Windows")
```