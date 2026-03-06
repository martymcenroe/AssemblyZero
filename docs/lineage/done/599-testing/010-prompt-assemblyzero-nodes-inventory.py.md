# Implementation Request: assemblyzero/nodes/inventory.py

## Task

Write the complete contents of `assemblyzero/nodes/inventory.py`.

Change type: Add
Description: LangGraph node orchestrating discovery and utilizing the utils.

## LLD Specification

# Implementation Spec: Feature: Inventory-as-Code Node

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #599 |
| LLD | `docs/lld/active/599-inventory-as-code-node.md` |
| Generated | 2026-03-06 |
| Status | APPROVED |

## 1. Overview

Automate the "Inventory Rule" by adding a mechanical node that scans `docs/`, categorizes `.md` files, and updates `0003-file-inventory.md` at the end of every workflow.

**Objective:** Automatically maintain an accurate, categorized markdown table of all documentation files without overwriting human-modified statuses.

**Success Criteria:** Detects all nested `.md` files in `docs/`, correctly maps subdirectories to categories, preserves manual status changes, and safely updates the markdown file between bounding comments. Must fail open (not crash the workflow) if file errors occur.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/markdown_inventory.py` | Add | Standalone parsing and formatting logic for the inventory table. |
| 2 | `assemblyzero/nodes/inventory.py` | Add | LangGraph node orchestrating discovery and utilizing the utils. |
| 3 | `tests/fixtures/mock_repo/docs/0003-file-inventory.md` | Add | Static mock data for unit tests. |
| 4 | `tests/unit/test_inventory_node.py` | Add | Test suite covering both utils and the node itself. |

**Implementation Order Rationale:** The utility functions (`markdown_inventory.py`) have no dependencies and contain the core complex logic (regex/parsing). The LangGraph node (`inventory.py`) relies on these utilities. Mock fixtures must exist before the unit tests can be written and verified.

## 3. Current State (for Modify/Delete files)

### 3.1 N/A (All Files are Additions)

**Relevant excerpt**: N/A

**What changes:** No existing files are being modified or deleted. All files listed in Section 2 are new additions.

## 4. Data Structures

### 4.1 InventoryItem

**Definition:**

```python
class InventoryItem(TypedDict):
    path: str
    filename: str
    category: str
    status: str
```

**Concrete Example:**

```json
{
    "path": "docs/lld/active/599-inventory-as-code-node.md",
    "filename": "599-inventory-as-code-node.md",
    "category": "LLD",
    "status": "Active"
}
```

### 4.2 InventoryState

**Definition:**

```python
class InventoryState(TypedDict, total=False):
    inventory_updated: bool
    inventory_entries_added: int
    errors: list[str]
```

**Concrete Example:**

```json
{
    "inventory_updated": true,
    "inventory_entries_added": 2,
    "errors": []
}
```

## 5. Function Specifications

### 5.1 `extract_existing_inventory()`

**File:** `assemblyzero/utils/markdown_inventory.py`

**Signature:**

```python
def extract_existing_inventory(filepath: Path) -> list[InventoryItem]:
    """Parses the existing markdown table between bounding tags to retain statuses."""
    ...
```

**Input Example:**

```python
filepath = Path("docs/0003-file-inventory.md")
```

**Output Example:**

```python
[
    {
        "path": "docs/lld/123-old-feature.md",
        "filename": "123-old-feature.md",
        "category": "LLD",
        "status": "Legacy"
    }
]
```

**Edge Cases:**
- File does not exist -> returns `[]`
- Tags missing -> returns `[]`
- Table empty between tags -> returns `[]`

### 5.2 `inject_inventory_table()`

**File:** `assemblyzero/utils/markdown_inventory.py`

**Signature:**

```python
def inject_inventory_table(filepath: Path, items: list[InventoryItem]) -> bool:
    """Writes the updated table back to the file between bounding tags."""
    ...
```

**Input Example:**

```python
filepath = Path("docs/0003-file-inventory.md")
items = [
    {
        "path": "docs/lld/599-inventory.md",
        "filename": "599-inventory.md",
        "category": "LLD",
        "status": "Active"
    }
]
```

**Output Example:**

```python
True  # Returns boolean indicating success
```

**Edge Cases:**
- File is read-only -> raises `PermissionError` (handled by node)
- File exists but missing bounding tags -> appends table and tags to EOF.

### 5.3 `categorize_file()`

**File:** `assemblyzero/utils/markdown_inventory.py`

**Signature:**

```python
def categorize_file(filepath: Path) -> str:
    """Categorizes a file based on its directory path relative to docs/."""
    ...
```

**Input Example:**

```python
filepath = Path("docs/standards/0001-python-guidelines.md")
```

**Output Example:**

```python
"Standard"
```

**Edge Cases:**
- File directly in `docs/` -> returns `"Root"`
- Unrecognized subfolder (e.g., `docs/random/file.md`) -> returns `"Random"` (Capitalized subfolder name)

### 5.4 `scan_docs_directory()`

**File:** `assemblyzero/nodes/inventory.py`

**Signature:**

```python
def scan_docs_directory(docs_dir: Path) -> list[Path]:
    """Returns a list of all .md files in the docs directory."""
    ...
```

**Input Example:**

```python
docs_dir = Path("docs")
```

**Output Example:**

```python
[
    Path("docs/0003-file-inventory.md"),
    Path("docs/lld/active/599-inventory.md")
]
```

**Edge Cases:**
- Directory does not exist -> returns `[]`

### 5.5 `update_inventory_node()`

**File:** `assemblyzero/nodes/inventory.py`

**Signature:**

```python
def update_inventory_node(state: dict) -> dict:
    """LangGraph node execution: orchestrates the scan, diff, and update process."""
    ...
```

**Input Example:**

```python
state = {
    "issue_number": 599,
    "repo_path": "/path/to/repo"
}
```

**Output Example:**

```python
{
    "inventory_updated": True,
    "inventory_entries_added": 1,
    "errors": []
}
```

**Edge Cases:**
- Cannot write to inventory file -> returns `{"inventory_updated": False, "inventory_entries_added": 0, "errors": ["Permission denied writing to inventory."]}` (Fail Open)

## 6. Change Instructions

### 6.1 `assemblyzero/utils/markdown_inventory.py` (Add)

**Complete file contents:**

```python
"""Markdown inventory parsing and writing utilities.

Issue #599: Inventory-as-Code Node
"""

import re
from pathlib import Path
from typing import TypedDict, List

class InventoryItem(TypedDict):
    path: str
    filename: str
    category: str
    status: str

START_TAG = "<!-- INVENTORY_START -->"
END_TAG = "<!-- INVENTORY_END -->"

def extract_existing_inventory(filepath: Path) -> list[InventoryItem]:
    """Parses the existing markdown table between bounding tags to retain statuses."""
    if not filepath.exists():
        return []
    
    content = filepath.read_text(encoding="utf-8")
    pattern = re.compile(rf"{START_TAG}\n(.*?)\n{END_TAG}", re.DOTALL)
    match = pattern.search(content)
    
    if not match:
        return []
        
    table_content = match.group(1).strip().split("\n")
    items = []
    
    # Skip header (0) and separator (1)
    for line in table_content[2:]:
        if not line.strip() or not line.startswith("|"):
            continue
            
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5:  # First empty, Path, Filename, Category, Status, Last empty
            items.append({
                "path": parts[1],
                "filename": parts[2],
                "category": parts[3],
                "status": parts[4]
            })
            
    return items

def categorize_file(filepath: Path) -> str:
    """Categorizes a file based on its directory path relative to docs/."""
    # Assuming path is relative, e.g., 'docs/lld/active/file.md' or 'docs/file.md'
    parts = filepath.parts
    if "docs" in parts:
        docs_idx = parts.index("docs")
        # If it's directly in docs/
        if len(parts) - docs_idx == 2:
            return "Root"
        # Return capitalized name of the first subfolder inside docs/
        if len(parts) - docs_idx > 2:
            subfolder = parts[docs_idx + 1]
            if subfolder.lower() == "lld":
                return "LLD"
            if subfolder.lower() == "adrs":
                return "ADR"
            if subfolder.lower() == "standards":
                return "Standard"
            return subfolder.capitalize()
    return "Uncategorized"

def inject_inventory_table(filepath: Path, items: list[InventoryItem]) -> bool:
    """Writes the updated table back to the file between bounding tags."""
    table_lines = [
        START_TAG,
        "| Path | Filename | Category | Status |",
        "|---|---|---|---|",
    ]
    
    for item in items:
        table_lines.append(f"| {item['path']} | {item['filename']} | {item['category']} | {item['status']} |")
        
    table_lines.append(END_TAG)
    new_table_str = "\n".join(table_lines)
    
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(f"# Documentation Inventory\n\n{new_table_str}\n", encoding="utf-8")
        return True
        
    content = filepath.read_text(encoding="utf-8")
    pattern = re.compile(rf"{START_TAG}.*?{END_TAG}", re.DOTALL)
    
    if pattern.search(content):
        new_content = pattern.sub(new_table_str, content)
    else:
        new_content = content.rstrip() + f"\n\n{new_table_str}\n"
        
    filepath.write_text(new_content, encoding="utf-8")
    return True
```

### 6.2 `assemblyzero/nodes/inventory.py` (Add)

**Complete file contents:**

```python
"""Inventory-as-Code Node for LangGraph.

Issue #599: Automatically discovers .md files and updates docs/0003-file-inventory.md.
"""

from pathlib import Path
from typing import Any

from assemblyzero.utils.markdown_inventory import (
    InventoryItem,
    extract_existing_inventory,
    categorize_file,
    inject_inventory_table
)

def scan_docs_directory(docs_dir: Path) -> list[Path]:
    """Returns a list of all .md files in the docs directory."""
    if not docs_dir.exists() or not docs_dir.is_dir():
        return []
    return list(docs_dir.rglob("*.md"))

def update_inventory_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node execution: orchestrates the scan, diff, and update process."""
    print("[Inventory] Starting documentation inventory scan...")
    
    try:
        # Resolve target repo docs path
        # Fallback to local 'docs' if repo_path not strictly provided in state for standalone testing
        repo_path_str = state.get("repo_path", ".")
        docs_dir = Path(repo_path_str) / "docs"
        inventory_file = docs_dir / "0003-file-inventory.md"
        
        existing_items = extract_existing_inventory(inventory_file)
        existing_map = {item["path"]: item for item in existing_items}
        
        md_files = scan_docs_directory(docs_dir)
        
        updated_items: list[InventoryItem] = []
        entries_added = 0
        
        for file_path in md_files:
            # Use posix paths for consistency in markdown output
            rel_path = file_path.relative_to(Path(repo_path_str)).as_posix()
            
            if rel_path in existing_map:
                updated_items.append(existing_map[rel_path])
            else:
                updated_items.append({
                    "path": rel_path,
                    "filename": file_path.name,
                    "category": categorize_file(file_path.relative_to(Path(repo_path_str))),
                    "status": "Active"
                })
                entries_added += 1
                
        # Sort by Category, then Filename
        updated_items.sort(key=lambda x: (x["category"], x["filename"]))
        
        inject_inventory_table(inventory_file, updated_items)
        
        print(f"[Inventory] Updated successfully. Added {entries_added} new entries.")
        return {
            "inventory_updated": True,
            "inventory_entries_added": entries_added,
            "errors": []
        }
        
    except Exception as e:
        error_msg = f"Failed to update inventory: {str(e)}"
        print(f"[Inventory] ERROR - {error_msg}")
        return {
            "inventory_updated": False,
            "inventory_entries_added": 0,
            "errors": [error_msg]
        }
```

### 6.3 `tests/fixtures/mock_repo/docs/0003-file-inventory.md` (Add)

**Complete file contents:**

```markdown
# Documentation Inventory

This file is automatically updated by the Inventory-as-Code node.

<!-- INVENTORY_START -->
| Path | Filename | Category | Status |
|---|---|---|---|
| docs/0003-file-inventory.md | 0003-file-inventory.md | Root | Active |
| docs/lld/active/123-test.md | 123-test.md | LLD | Legacy |
<!-- INVENTORY_END -->

Do not modify the tags above.
```

### 6.4 `tests/unit/test_inventory_node.py` (Add)

**Complete file contents:**

```python
"""Unit tests for the Inventory-as-Code Node."""

import pytest
from pathlib import Path
from assemblyzero.utils.markdown_inventory import (
    extract_existing_inventory,
    categorize_file,
    inject_inventory_table
)
from assemblyzero.nodes.inventory import update_inventory_node, scan_docs_directory

def test_extract_existing_inventory(tmp_path):
    # T010: Parse existing table
    doc_file = tmp_path / "0003-file-inventory.md"
    doc_file.write_text(
        "<!-- INVENTORY_START -->\n"
        "| Path | Filename | Category | Status |\n"
        "|---|---|---|---|\n"
        "| docs/test.md | test.md | Root | Legacy |\n"
        "<!-- INVENTORY_END -->"
    )
    items = extract_existing_inventory(doc_file)
    assert len(items) == 1
    assert items[0]["path"] == "docs/test.md"
    assert items[0]["status"] == "Legacy"

def test_scan_directory_and_categorize(tmp_path):
    # T020 & T030: Scan and categorize
    docs_dir = tmp_path / "docs"
    lld_dir = docs_dir / "lld" / "active"
    lld_dir.mkdir(parents=True)
    
    (lld_dir / "test.md").write_text("# Test LLD")
    (docs_dir / "ignore.txt").write_text("ignore")
    
    files = scan_docs_directory(docs_dir)
    assert len(files) == 1
    assert files[0].name == "test.md"
    
    cat = categorize_file(Path("docs/lld/active/test.md"))
    assert cat == "LLD"

def test_update_inventory_node_integration(tmp_path):
    # T040 & T050: Merge items and inject safely
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    inv_file = docs_dir / "0003-file-inventory.md"
    inv_file.write_text(
        "<!-- INVENTORY_START -->\n"
        "| Path | Filename | Category | Status |\n"
        "|---|---|---|---|\n"
        "| docs/lld/old.md | old.md | LLD | Legacy |\n"
        "<!-- INVENTORY_END -->"
    )
    
    lld_dir = docs_dir / "lld"
    lld_dir.mkdir()
    (lld_dir / "new.md").write_text("# New")
    (lld_dir / "old.md").write_text("# Old")
    
    state = {"repo_path": str(tmp_path)}
    result = update_inventory_node(state)
    
    assert result["inventory_updated"] is True
    assert result["inventory_entries_added"] == 2 # 0003 and new.md
    
    content = inv_file.read_text()
    assert "Legacy" in content  # Original status preserved
    assert "new.md" in content

def test_graceful_failure(tmp_path):
    # T060: Graceful failure missing dir
    state = {"repo_path": "/path/that/does/not/exist"}
    result = update_inventory_node(state)
    
    # Should not throw exception, just update state cleanly
    assert result["inventory_updated"] is True
    assert result["inventory_entries_added"] == 0
```

## 7. Pattern References

### 7.1 LangGraph Node Stateless Pattern

**File:** `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1-50`

```python
def analyze_codebase(state: dict[str, Any]) -> dict[str, Any]:
    """Existing standard node pattern returning a state dict delta."""
    try:
        # logic
        return {"some_key": "success", "errors": []}
    except Exception as e:
        return {"some_key": "fail", "errors": [str(e)]}
```

**Relevance:** The implementation of `update_inventory_node` exactly mirrors this core standard for LangGraph nodes in AssemblyZero: wrap the core logic in a generic `try/except`, log to standard output with a component prefix `[NodeName]`, and return a delta `dict` appending to the `errors` list rather than raising an execution-halting exception.

### 7.2 Safe Mock Filesystem Testing

**File:** `tests/e2e/test_lld_workflow_mock.py:1-80`

```python
# Utilizing tmp_path fixture from pytest
def test_workflow_execution(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()
    # execution logic bounds isolated to tmp directory
```

**Relevance:** The testing architecture for the node uses pytest's built-in `tmp_path` fixture to dynamically scaffold nested `docs/` hierarchies to test the regex extraction and file injection without relying exclusively on static fixtures.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import re` | stdlib | `markdown_inventory.py` |
| `from pathlib import Path` | stdlib | All files |
| `from typing import TypedDict, List, Any` | stdlib | `markdown_inventory.py`, `inventory.py` |
| `import pytest` | standard deps | `test_inventory_node.py` |

**New Dependencies:** None (Relies entirely on standard library and existing Pytest).

## 9. Placeholder

*Reserved for future use.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `extract_existing_inventory()` | Markdown file path with table | `[{"path": "...", "status": "Legacy", ...}]` |
| T020 | `scan_docs_directory()` | `tmp_path / "docs"` containing `.txt` and `.md` | List excluding `.txt` files |
| T030 | `categorize_file()` | `Path("docs/lld/active/test.md")` | `"LLD"` |
| T040 | `update_inventory_node()` | Directory with 1 legacy file + 1 new file | Merges lists, preserving `"Legacy"` |
| T050 | `inject_inventory_table()` | Valid `InventoryItem` list | Markdown file contains new HTML bound table |
| T060 | `update_inventory_node()` | `state={"repo_path": "/invalid"}` | `{"errors": [], "inventory_entries_added": 0}` (Clean completion) |

## 11. Implementation Notes

### 11.1 Error Handling Convention

Fail Open Policy: The `update_inventory_node` MUST NOT halt the overall workflow if an issue occurs (e.g., file locks, regex parse failures of weirdly formatted old files). It uses a wide `except Exception` catch to log the error to the state `errors` list and returns cleanly so the parent graph continues.

### 11.2 Logging Convention

Standard `print` prefixes are required for observability in standard-out workflow runners.
`print("[Inventory] Starting documentation inventory scan...")`

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `START_TAG` | `<!-- INVENTORY_START -->` | Used for safe replacement via regex |
| `END_TAG` | `<!-- INVENTORY_END -->` | Used for safe replacement via regex |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 - Declared explicit N/A for Add-only PRs)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #599 |
| Verdict | APPROVED |
| Date | 2026-03-06 |
| Iterations | 1 |
| Finalized | 2026-03-06T10:00:00Z |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #599 |
| Verdict | APPROVED |
| Date | 2026-03-06 |
| Iterations | 0 |
| Finalized | 2026-03-06T13:58:00Z |

### Review Feedback Summary

The Implementation Spec is exceptionally detailed, providing complete and concrete code for all required files, including utilities, LangGraph nodes, and unit tests. The inclusion of full file contents, clear data structures with JSON examples, and robust error handling ensures an autonomous AI agent can implement this with a very high success rate.

## Suggestions
- The type hint `list[InventoryItem]` is used in several signatures. Ensure the project is running on Python 3.9+, otherwise use `Li...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      docs/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
      nodes/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-599\tests\test_issue_599.py
"""Test file for Issue #599.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.utils.markdown_inventory import *  # noqa: F401, F403


# Unit Tests
# -----------

def test_t010():
    """
    `extract_existing_inventory()` | Markdown file path with table |
    `[{"path": "...", "status": "Legacy", ...}]`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020():
    """
    `scan_docs_directory()` | `tmp_path / "docs"` containing `.txt` and
    `.md` | List excluding `.txt` files
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'


def test_t030():
    """
    `categorize_file()` | `Path("docs/lld/active/test.md")` | `"LLD"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t030 works correctly
    assert False, 'TDD RED: test_t030 not implemented'


def test_t040():
    """
    `update_inventory_node()` | Directory with 1 legacy file + 1 new file
    | Merges lists, preserving `"Legacy"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040 works correctly
    assert False, 'TDD RED: test_t040 not implemented'


def test_t050():
    """
    `inject_inventory_table()` | Valid `InventoryItem` list | Markdown
    file contains new HTML bound table
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050 works correctly
    assert False, 'TDD RED: test_t050 not implemented'


def test_t060():
    """
    `update_inventory_node()` | `state={"repo_path": "/invalid"}` |
    `{"errors": [], "inventory_entries_added": 0}` (Clean completion)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t060 works correctly
    assert False, 'TDD RED: test_t060 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/utils/markdown_inventory.py (full)

```python
"""Markdown inventory parsing and writing utilities.

Issue #599: Inventory-as-Code Node
"""

import re
from pathlib import Path
from typing import TypedDict


class InventoryItem(TypedDict):
    path: str
    filename: str
    category: str
    status: str


START_TAG = "<!-- INVENTORY_START -->"
END_TAG = "<!-- INVENTORY_END -->"


def extract_existing_inventory(filepath: Path) -> list[InventoryItem]:
    """Parses the existing markdown table between bounding tags to retain statuses."""
    if not filepath.exists():
        return []

    content = filepath.read_text(encoding="utf-8")
    pattern = re.compile(rf"{re.escape(START_TAG)}\n(.*?)\n{re.escape(END_TAG)}", re.DOTALL)
    match = pattern.search(content)

    if not match:
        return []

    table_content = match.group(1).strip().split("\n")
    items: list[InventoryItem] = []

    # Skip header (0) and separator (1)
    for line in table_content[2:]:
        if not line.strip() or not line.startswith("|"):
            continue

        parts = [p.strip() for p in line.split("|")]
        # Split on | gives: ['', 'Path', 'Filename', 'Category', 'Status', '']
        if len(parts) >= 5:
            items.append({
                "path": parts[1],
                "filename": parts[2],
                "category": parts[3],
                "status": parts[4],
            })

    return items


def categorize_file(filepath: Path) -> str:
    """Categorizes a file based on its directory path relative to docs/.

    Expects a path relative to the repo root, e.g. 'docs/lld/active/file.md'.
    """
    parts = filepath.parts
    if "docs" in parts:
        docs_idx = parts.index("docs")
        # If it's directly in docs/
        if len(parts) - docs_idx == 2:
            return "Root"
        # Return categorized name of the first subfolder inside docs/
        if len(parts) - docs_idx > 2:
            subfolder = parts[docs_idx + 1]
            if subfolder.lower() == "lld":
                return "LLD"
            if subfolder.lower() == "adrs":
                return "ADR"
            if subfolder.lower() == "standards":
                return "Standard"
            return subfolder.capitalize()
    return "Uncategorized"


def inject_inventory_table(filepath: Path, items: list[InventoryItem]) -> bool:
    """Writes the updated table back to the file between bounding tags."""
    table_lines = [
        START_TAG,
        "| Path | Filename | Category | Status |",
        "|---|---|---|---|",
    ]

    for item in items:
        table_lines.append(
            f"| {item['path']} | {item['filename']} | {item['category']} | {item['status']} |"
        )

    table_lines.append(END_TAG)
    new_table_str = "\n".join(table_lines)

    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(
            f"# Documentation Inventory\n\n{new_table_str}\n", encoding="utf-8"
        )
        return True

    content = filepath.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(START_TAG)}.*?{re.escape(END_TAG)}", re.DOTALL
    )

    if pattern.search(content):
        new_content = pattern.sub(new_table_str, content)
    else:
        new_content = content.rstrip() + f"\n\n{new_table_str}\n"

    filepath.write_text(new_content, encoding="utf-8")
    return True
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
