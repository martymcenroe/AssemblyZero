"""N0: Load LLD node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD → Implementation Spec)

Reads the approved LLD file and extracts:
- Full LLD content (raw markdown)
- Files to modify from Section 2.1 table
- Validates LLD has APPROVED status

This node populates:
- lld_content: Raw LLD markdown
- files_to_modify: List[FileToModify] parsed from Section 2.1
- error_message: "" on success, error text on failure
"""

import re
from pathlib import Path
from typing import Any

from assemblyzero.workflows.implementation_spec.state import (
    FileToModify,
    ImplementationSpecState,
)


# LLD directories relative to repo root
LLD_ACTIVE_DIR = Path("docs/lld/active")
LLD_DONE_DIR = Path("docs/lld/done")
LLD_DRAFTS_DIR = Path("docs/lld/drafts")


def find_lld_path(issue_number: int, repo_root: Path) -> Path | None:
    """Find the LLD file for an issue number.

    Searches docs/lld/active/ and docs/lld/done/ with multiple naming
    patterns in priority order.

    Args:
        issue_number: GitHub issue number.
        repo_root: Repository root path.

    Returns:
        Path to LLD file if found, None otherwise.
    """
    # Search directories in priority order: active first, then done
    search_dirs = [
        repo_root / LLD_ACTIVE_DIR,
        repo_root / LLD_DONE_DIR,
    ]

    # Search patterns in priority order
    patterns = [
        f"LLD-{issue_number:03d}.md",       # LLD-304.md
        f"LLD-{issue_number:03d}-*.md",      # LLD-304-desc.md
        f"LLD-{issue_number}.md",            # LLD-304.md (unpadded)
        f"LLD-{issue_number}-*.md",          # LLD-304-desc.md
    ]

    for lld_dir in search_dirs:
        if not lld_dir.exists():
            continue

        for pattern in patterns:
            matches = list(lld_dir.glob(pattern))
            if matches:
                # Return most recently modified if multiple
                if len(matches) > 1:
                    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return matches[0]

    return None


def parse_files_to_modify(lld_content: str) -> list[FileToModify]:
    """Extract files from LLD Section 2.1 table.

    Parses the "Files Changed" table to extract file paths, change types,
    and descriptions. Normalizes change types to "Add", "Modify", or "Delete".

    Handles table format:
        | File | Change Type | Description |
        |------|-------------|-------------|
        | `path/to/file.py` | Add | Description text |

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of FileToModify dicts with path, change_type, description,
        and current_content (always None at this stage).
    """
    files: list[FileToModify] = []

    # Find Section 2.1 Files Changed table
    table_pattern = re.compile(
        r"###?\s*2\.1[^\n]*Files Changed[^\n]*\n"  # Section header
        r"\n*"                                       # Optional blank lines
        r"\|[^\n]+\n"                                # Table header row
        r"\|[-|\s]+\n"                               # Separator row
        r"((?:\|[^\n]+\n)+)",                        # Table body rows
        re.IGNORECASE,
    )

    match = table_pattern.search(lld_content)
    if not match:
        return files

    table_rows = match.group(1)

    # Parse each row: | `path` | ChangeType | Description |
    row_pattern = re.compile(
        r"\|\s*`?([^`|]+)`?\s*\|\s*([^|]+)\s*\|\s*([^|]*)\|"
    )

    for row_match in row_pattern.finditer(table_rows):
        path = row_match.group(1).strip()
        raw_change_type = row_match.group(2).strip()
        description = row_match.group(3).strip()

        # Skip header-like rows
        if path.lower() in ("file", "path", "filename"):
            continue

        # Normalize change type (Issue #334 pattern)
        change_type = _normalize_change_type(raw_change_type)

        # Skip directory entries (e.g., "Add (Directory)")
        if "(directory)" in raw_change_type.lower():
            continue

        files.append(FileToModify(
            path=path,
            change_type=change_type,
            description=description,
            current_content=None,
        ))

    return files


def _normalize_change_type(raw: str) -> str:
    """Normalize a change type string to Add, Modify, or Delete.

    Handles variations like "Add (Directory)", "Modify", "modify", etc.

    Args:
        raw: Raw change type string from LLD table.

    Returns:
        Normalized change type: "Add", "Modify", or "Delete".
    """
    cleaned = raw.strip().lower()

    # Remove parenthetical notes like "(Directory)"
    cleaned = re.sub(r"\s*\(.*?\)", "", cleaned).strip()

    if cleaned in ("add", "new", "create"):
        return "Add"
    elif cleaned in ("modify", "update", "change", "edit"):
        return "Modify"
    elif cleaned in ("delete", "remove"):
        return "Delete"

    # Default to Add for unknown types
    return "Add"


def _check_approved_status(lld_content: str) -> bool:
    """Check if the LLD has an APPROVED status marker.

    Looks for approval markers in common locations:
    - Status field: "* **Status:** Approved ..."
    - Final Status: "**Final Status:** APPROVED"
    - Review Log: "APPROVED" in appendix

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        True if LLD appears to be approved, False otherwise.
    """
    content_upper = lld_content.upper()

    # Check for explicit status markers
    status_patterns = [
        r"\*\s*\*\*Status:\*\*\s*Approved",
        r"\*\*Final\s+Status:\*\*\s*APPROVED",
        r"Verdict\s*\|\s*Key\s*Issue.*?APPROVED",
    ]

    for pattern in status_patterns:
        if re.search(pattern, lld_content, re.IGNORECASE):
            return True

    # Fallback: look for "APPROVED" anywhere in the document
    return "APPROVED" in content_upper


def load_lld(state: ImplementationSpecState) -> dict[str, Any]:
    """N0: Load and parse the approved LLD file.

    Issue #304: Implementation Readiness Review Workflow

    Steps:
    1. Resolve LLD file path (explicit path or auto-discovery)
    2. Read LLD content from disk
    3. Validate LLD has APPROVED status
    4. Parse Section 2.1 to extract files to modify
    5. Return state updates with loaded content

    Args:
        state: Current workflow state. Requires:
            - issue_number: GitHub issue number
            - lld_path: Explicit path to LLD (optional if repo_root set)
            - repo_root: Repository root for auto-discovery

    Returns:
        Dict with state field updates:
        - lld_content: Raw LLD markdown
        - lld_path: Resolved path to LLD file
        - files_to_modify: List[FileToModify] from Section 2.1
        - error_message: "" on success, error text on failure
    """
    issue_number = state.get("issue_number", 0)

    if not issue_number:
        return {"error_message": "No issue number provided"}

    print(f"\n[N0] Loading LLD for issue #{issue_number}...")

    # Resolve LLD file path
    lld_path_str = state.get("lld_path", "")
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else Path.cwd()

    if lld_path_str:
        lld_path_obj = Path(lld_path_str)
    else:
        lld_path_obj = find_lld_path(issue_number, repo_root)

    # --------------------------------------------------------------------------
    # GUARD: LLD file must exist
    # --------------------------------------------------------------------------
    if not lld_path_obj or not lld_path_obj.exists():
        expected = repo_root / LLD_ACTIVE_DIR / f"LLD-{issue_number:03d}.md"
        print("    [GUARD] BLOCKED: LLD file not found")
        return {
            "error_message": (
                f"LLD not found for issue #{issue_number}. "
                f"Expected at: {expected}"
            )
        }
    # --------------------------------------------------------------------------

    print(f"    LLD path: {lld_path_obj}")

    # Read LLD content
    try:
        lld_content = lld_path_obj.read_text(encoding="utf-8")
    except OSError as e:
        return {"error_message": f"Failed to read LLD: {e}"}

    # --------------------------------------------------------------------------
    # GUARD: LLD content must be non-trivial
    # --------------------------------------------------------------------------
    if not lld_content or len(lld_content) < 100:
        print(f"    [GUARD] BLOCKED: LLD content too short ({len(lld_content)} chars)")
        return {"error_message": "GUARD: LLD content too short"}
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # GUARD: LLD must have APPROVED status
    # --------------------------------------------------------------------------
    if not _check_approved_status(lld_content):
        print("    [GUARD] BLOCKED: LLD is not approved")
        return {
            "error_message": (
                f"LLD for issue #{issue_number} is not approved. "
                "Only approved LLDs can be used to generate Implementation Specs."
            )
        }
    # --------------------------------------------------------------------------

    print("    LLD status: APPROVED")

    # Parse files to modify from Section 2.1
    files_to_modify = parse_files_to_modify(lld_content)
    print(f"    Found {len(files_to_modify)} files to modify")

    if not files_to_modify:
        print("    [GUARD] WARNING: No files found in Section 2.1 table")

    # Log file breakdown by change type
    add_count = sum(1 for f in files_to_modify if f["change_type"] == "Add")
    modify_count = sum(1 for f in files_to_modify if f["change_type"] == "Modify")
    delete_count = sum(1 for f in files_to_modify if f["change_type"] == "Delete")
    print(f"    Breakdown: {add_count} Add, {modify_count} Modify, {delete_count} Delete")

    return {
        "lld_path": str(lld_path_obj),
        "lld_content": lld_content,
        "files_to_modify": files_to_modify,
        "error_message": "",
    }