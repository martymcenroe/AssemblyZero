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