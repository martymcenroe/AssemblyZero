"""Inventory-as-Code Node for LangGraph.

Issue #599: Automatically discovers .md files and updates docs/0003-file-inventory.md.
"""

from pathlib import Path
from typing import Any

from assemblyzero.utils.markdown_inventory import (
    InventoryItem,
    extract_existing_inventory,
    categorize_file,
    inject_inventory_table,
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
        # Fallback to local '.' if repo_path not strictly provided in state
        repo_path_str = state.get("repo_path", ".")
        repo_path = Path(repo_path_str)
        docs_dir = repo_path / "docs"
        inventory_file = docs_dir / "0003-file-inventory.md"

        existing_items = extract_existing_inventory(inventory_file)
        existing_map = {item["path"]: item for item in existing_items}

        md_files = scan_docs_directory(docs_dir)

        updated_items: list[InventoryItem] = []
        entries_added = 0

        for file_path in md_files:
            # Use posix paths for consistency in markdown output
            rel_path = file_path.relative_to(repo_path).as_posix()

            if rel_path in existing_map:
                updated_items.append(existing_map[rel_path])
            else:
                updated_items.append({
                    "path": rel_path,
                    "filename": file_path.name,
                    "category": categorize_file(
                        file_path.relative_to(repo_path)
                    ),
                    "status": "Active",
                })
                entries_added += 1

        # Sort by Category, then Filename
        updated_items.sort(key=lambda x: (x["category"], x["filename"]))

        inject_inventory_table(inventory_file, updated_items)

        print(
            f"[Inventory] Updated successfully. Added {entries_added} new entries."
        )
        return {
            "inventory_updated": True,
            "inventory_entries_added": entries_added,
            "errors": [],
        }

    except Exception as e:
        error_msg = f"Failed to update inventory: {str(e)}"
        print(f"[Inventory] ERROR - {error_msg}")
        return {
            "inventory_updated": False,
            "inventory_entries_added": 0,
            "errors": [error_msg],
        }