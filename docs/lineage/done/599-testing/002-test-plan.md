# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `extract_existing_inventory()` | Markdown file path with table | `[{"path": "...", "status": "Legacy", ...}]`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `scan_docs_directory()` | `tmp_path / "docs"` containing `.txt` and `.md` | List excluding `.txt` files

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `categorize_file()` | `Path("docs/lld/active/test.md")` | `"LLD"`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_inventory_node()` | Directory with 1 legacy file + 1 new file | Merges lists, preserving `"Legacy"`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `inject_inventory_table()` | Valid `InventoryItem` list | Markdown file contains new HTML bound table

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `update_inventory_node()` | `state={"repo_path": "/invalid"}` | `{"errors": [], "inventory_entries_added": 0}` (Clean completion)

