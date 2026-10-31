"""LLD path extraction and enforcement for implementation workflow.

Issue #188: Enforce LLD-specified file paths during implementation
to prevent Claude from placing files in arbitrary locations.

Extracts file paths from LLD Section 2.1 (Files Changed table),
builds prompt sections listing allowed paths, and detects scaffolded
test files for "DO NOT MODIFY" protection.
"""

import re
from pathlib import Path, PurePosixPath
from typing import TypedDict


class LLDPathSpec(TypedDict):
    """Extracted file path specification from an LLD."""

    implementation_files: list[str]
    test_files: list[str]
    config_files: list[str]
    all_allowed_paths: set[str]
    scaffolded_test_files: set[str]


def parse_files_changed_table(markdown_table: str) -> list[tuple[str, str, str]]:
    """Parse a Files Changed markdown table into structured tuples.

    Expects rows like: | `path/to/file.py` | Add | Description |

    Args:
        markdown_table: Raw markdown table text.

    Returns:
        List of (path, change_type, description) tuples.
    """
    results = []
    lines = markdown_table.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header and separator rows
        cells = [c.strip() for c in line.split("|")]
        # Remove empty first/last from leading/trailing |
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        # Skip separator rows (----)
        if all(set(c) <= set("-: ") for c in cells):
            continue
        # Skip header row
        if cells[0].lower() in ("file", "filename", "path"):
            continue

        path = cells[0].strip("`").strip()
        change_type = cells[1].strip()
        description = cells[2].strip() if len(cells) > 2 else ""

        # Skip empty paths
        if not path or path.lower() == "file":
            continue

        results.append((path, change_type, description))

    return results


def extract_paths_from_lld(lld_content: str) -> LLDPathSpec:
    """Extract all file paths specified in LLD Section 2.1.

    Parses the Files Changed table to find implementation files,
    test files, and config files.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        LLDPathSpec with categorized file paths.

    Content with no Section 2.1 returns an empty spec, quietly, and that is
    the contract rather than a swallowed failure (ADR 0236, #3585). On a real
    implementation run the content is the implementation SPEC, which
    ``load_lld`` stores under ``lld_content``: its files table is
    ``## 2. Files to Implement`` and it has no Section 2.1 by design. The
    implementation node adds every path of that table to the allowed set
    itself, so the empty answer here costs the enforcement nothing, while a
    raise would halt every implementation run.
    """
    spec: LLDPathSpec = {
        "implementation_files": [],
        "test_files": [],
        "config_files": [],
        "all_allowed_paths": set(),
        "scaffolded_test_files": set(),
    }

    # Find Section 2.1 Files Changed
    # Look for the table after "### 2.1" or "## 2.1" header
    section_pattern = re.compile(
        r"#{2,3}\s*2\.1\b.*?\n(.*?)(?=\n#{2,3}\s|\Z)",
        re.DOTALL,
    )
    match = section_pattern.search(lld_content)
    if not match:
        return spec

    section_content = match.group(1)

    # Parse pipe-delimited rows directly from the section.
    # More lenient than requiring a strict table format — handles
    # malformed tables where some rows lack trailing pipes.
    entries = parse_files_changed_table(section_content)

    for path, change_type, description in entries:
        # Normalize path
        normalized = _normalize_path(path)
        if not normalized:
            continue

        spec["all_allowed_paths"].add(normalized)

        # Categorize
        if _is_test_path(normalized):
            spec["test_files"].append(normalized)
        elif _is_config_path(normalized):
            spec["config_files"].append(normalized)
        else:
            spec["implementation_files"].append(normalized)

    return spec


def detect_scaffolded_test_files(
    test_files: list[str], base_path: Path
) -> set[str]:
    """Check which test files already exist on disk (scaffolded).

    Args:
        test_files: List of test file relative paths.
        base_path: Repository root path.

    Returns:
        Set of test file paths that exist on disk.
    """
    scaffolded = set()
    for tf in test_files:
        full_path = base_path / tf
        if full_path.exists():
            scaffolded.add(tf)
    return scaffolded


def build_implementation_prompt_section(path_spec: LLDPathSpec) -> str:
    """Generate the file path enforcement section for the implementation prompt.

    Marks scaffolded test files with 'DO NOT MODIFY' warning.

    Args:
        path_spec: Extracted LLD path specification.

    Returns:
        Markdown prompt section text.
    """
    if not path_spec["all_allowed_paths"]:
        return ""

    lines = [
        "## Required File Paths (from LLD - do not deviate)",
        "",
        "The following paths are specified in the LLD. Write ONLY to these paths:",
        "",
    ]

    # Implementation files
    for path in sorted(path_spec["implementation_files"]):
        lines.append(f"- `{path}`")

    # Test files
    for path in sorted(path_spec["test_files"]):
        if path in path_spec["scaffolded_test_files"]:
            lines.append(f"- `{path}` — **DO NOT MODIFY** (already scaffolded)")
        else:
            lines.append(f"- `{path}`")

    # Config files
    for path in sorted(path_spec["config_files"]):
        lines.append(f"- `{path}`")

    lines.extend([
        "",
        "Any files written to other paths will be rejected.",
        "",
    ])

    return "\n".join(lines)


def _normalize_path(path: str) -> str:
    """Normalize a file path for comparison.

    Removes leading ./ and normalizes separators.

    Args:
        path: Raw path string.

    Returns:
        Normalized path string.
    """
    if not path:
        return ""
    # Use PurePosixPath to normalize
    normalized = str(PurePosixPath(path))
    # Remove leading ./
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_test_path(path: str) -> bool:
    """Check if a path is a test file."""
    parts = PurePosixPath(path).parts
    return any(p in ("tests", "test") for p in parts) or path.startswith("test_")


def _is_config_path(path: str) -> bool:
    """Check if a path is a config file."""
    config_extensions = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".conf"}
    return PurePosixPath(path).suffix in config_extensions
