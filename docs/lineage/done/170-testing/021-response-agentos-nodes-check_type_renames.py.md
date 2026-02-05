```python
"""Workflow node for detecting orphaned type/class references after renames.

Related: Issue #170 - Add pre-commit check for type/class renames that miss usages
LLD: docs/LLDs/active/170-type-rename-check.md
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class OrphanedUsage(TypedDict):
    """A single orphaned reference to a removed type."""

    file_path: str
    line_number: int
    line_content: str


class TypeRenameIssue(TypedDict):
    """Issue representing a removed type with orphaned references."""

    old_name: str
    definition_file: str
    orphaned_usages: list[OrphanedUsage]


class TypeRenameCheckResult(TypedDict):
    """Result of the type rename check."""

    passed: bool
    issues: list[TypeRenameIssue]
    checked_types: list[str]
    files_scanned: int
    removed_types_count: int


def extract_removed_types(diff_content: str) -> list[tuple[str, str]]:
    """
    Parse git diff to find removed class/type definitions.

    Returns list of (type_name, source_file) tuples.

    Args:
        diff_content: Git diff output in unified format

    Returns:
        List of (type_name, file_path) tuples for removed types
    """
    removed_types: list[tuple[str, str]] = []
    current_file: str | None = None

    # Pattern to match diff file headers
    file_header_pattern = re.compile(r"^diff --git a/(.*\.py) b/.*\.py")
    # Alternative file header pattern
    alt_file_header_pattern = re.compile(r"^\-\-\- a/(.*\.py)")

    # Patterns for type definitions (only in removed lines starting with -)
    class_pattern = re.compile(r"^-\s*class\s+(\w+)[\(:]")
    typeddict_pattern = re.compile(r"^-\s*(\w+)\s*=\s*TypedDict\(")
    type_alias_pattern = re.compile(r"^-\s*(\w+)\s*=\s*(?:Union|Optional|List|Dict|Tuple|Type)\[")

    for line in diff_content.splitlines():
        # Track current file
        file_match = file_header_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            continue

        # Alternative file header
        alt_file_match = alt_file_header_pattern.match(line)
        if alt_file_match:
            current_file = alt_file_match.group(1)
            continue

        if not current_file:
            continue

        # Check for removed type definitions
        if class_match := class_pattern.match(line):
            removed_types.append((class_match.group(1), current_file))
        elif typeddict_match := typeddict_pattern.match(line):
            removed_types.append((typeddict_match.group(1), current_file))
        elif type_alias_match := type_alias_pattern.match(line):
            removed_types.append((type_alias_match.group(1), current_file))

    return removed_types


def find_type_usages(
    type_name: str,
    search_paths: list[Path],
    exclude_patterns: list[str],
    timeout: float = 10.0,
) -> list[OrphanedUsage]:
    """
    Search codebase for usages of a type name.

    Excludes docs, lineage, and other non-source directories.
    Uses subprocess with shell=False for safety.

    Args:
        type_name: The type name to search for
        search_paths: Directories to search
        exclude_patterns: Glob patterns to exclude
        timeout: Maximum time for search operation

    Returns:
        List of OrphanedUsage dictionaries

    Raises:
        subprocess.TimeoutExpired: If grep exceeds timeout
    """
    usages: list[OrphanedUsage] = []

    # Build git grep command with exclusions
    cmd = ["git", "grep", "-n", "-F", type_name]

    # Add path filters for .py files only
    for search_path in search_paths:
        cmd.append(f"{search_path}/*.py")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit (no matches)
        )

        # git grep exits with 1 if no matches found, which is fine
        if result.returncode not in (0, 1):
            logger.warning(f"git grep returned unexpected code {result.returncode}")
            return usages

        # Parse output: file:line:content
        for line in result.stdout.splitlines():
            if not line:
                continue

            # Split on first two colons only
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue

            file_path, line_num_str, content = parts

            # Apply exclusions
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern.startswith("*"):
                    # Extension pattern like *.md
                    if file_path.endswith(pattern[1:]):
                        should_exclude = True
                        break
                elif "/" in pattern or "\\" in pattern:
                    # Directory pattern like docs/ or lineage/
                    normalized_pattern = pattern.replace("\\", "/").rstrip("/")
                    normalized_path = file_path.replace("\\", "/")
                    if normalized_pattern in normalized_path:
                        should_exclude = True
                        break

            if should_exclude:
                continue

            try:
                line_number = int(line_num_str)
            except ValueError:
                continue

            usages.append(
                OrphanedUsage(
                    file_path=file_path,
                    line_number=line_number,
                    line_content=content.strip(),
                )
            )

    except subprocess.TimeoutExpired as e:
        logger.error(f"git grep timed out after {timeout}s searching for {type_name}")
        raise TimeoutError(
            f"Type usage search timed out after {timeout}s for type '{type_name}'"
        ) from e

    return usages


def format_type_rename_error(issues: list[TypeRenameIssue]) -> str:
    """
    Format issues into a clear, actionable error message.

    Args:
        issues: List of TypeRenameIssue dictionaries

    Returns:
        Formatted error message with file:line references
    """
    lines = [
        "TYPE RENAME CHECK FAILED",
        "",
        "Detected removed types with orphaned references:",
        "",
    ]

    for issue in issues:
        lines.append(f"Type: {issue['old_name']}")
        lines.append(f"  Originally defined in: {issue['definition_file']}")
        lines.append(f"  Orphaned usages ({len(issue['orphaned_usages'])}):")

        for usage in issue["orphaned_usages"]:
            lines.append(
                f"    - {usage['file_path']}:{usage['line_number']}: {usage['line_content']}"
            )

        lines.append("")

    lines.extend(
        [
            "ACTION REQUIRED:",
            "1. Update all references to use the new type name, or",
            "2. Remove the references if they're no longer needed, or",
            "3. Restore the old type definition if the rename was unintended",
            "",
        ]
    )

    return "\n".join(lines)


def log_scan_summary(
    removed_types_count: int, files_scanned: int, issues_found: int
) -> None:
    """
    Log summary of scan for debugging and observability.

    Args:
        removed_types_count: Number of removed types detected from diff
        files_scanned: Number of files scanned
        issues_found: Number of orphaned usage issues found
    """
    logger.info(
        f"Type rename check: {removed_types_count} removed types, "
        f"{files_scanned} files scanned, {issues_found} issues found"
    )


def check_type_renames(state: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    """
    Pre-commit check for orphaned type references.

    Detects removed/renamed class/type definitions from git diff
    and greps codebase for remaining usages.

    Args:
        state: Workflow state containing staged changes
        timeout: Maximum execution time in seconds (default: 10.0)

    Returns:
        Updated state with check results

    Raises:
        TimeoutError: If check exceeds timeout limit
    """
    # Get staged diff
    diff_content = state.get("diff_content", "")
    if not diff_content:
        # Try to get diff from git
        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True,
            )
            diff_content = result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to get git diff: {e}")
            state["type_rename_check_passed"] = False
            state["type_rename_error"] = "Failed to retrieve git diff"
            return state

    # Extract removed types
    removed_types = extract_removed_types(diff_content)
    removed_types_count = len(removed_types)

    if not removed_types:
        # No types removed, check passes
        logger.info("Type rename check: no removed types detected")
        state["type_rename_check_passed"] = True
        state["type_rename_issues"] = []
        return state

    logger.info(f"Detected {removed_types_count} removed types from diff")

    # Search for orphaned usages
    issues: list[TypeRenameIssue] = []
    checked_types: list[str] = []

    # Get repository root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error(f"Failed to get repo root: {e}")
        state["type_rename_check_passed"] = False
        state["type_rename_error"] = "Failed to determine repository root"
        return state

    # Define exclusion patterns
    exclude_patterns = [
        "docs/",
        "lineage/",
        "*.md",
        ".git/",
        "__pycache__/",
        ".pytest_cache/",
    ]

    # Search paths (all Python files in repo, will be filtered by git grep)
    search_paths = [Path(".")]

    files_scanned = 0
    for type_name, definition_file in removed_types:
        checked_types.append(type_name)

        try:
            usages = find_type_usages(
                type_name, search_paths, exclude_patterns, timeout=timeout
            )
        except TimeoutError:
            # Log and continue with partial results
            logger.warning(f"Timeout searching for {type_name}, continuing with partial results")
            continue

        # Filter out usages in the definition file itself (the removal)
        filtered_usages = [
            usage for usage in usages if usage["file_path"] != definition_file
        ]

        files_scanned += len({usage["file_path"] for usage in filtered_usages})

        if filtered_usages:
            issues.append(
                TypeRenameIssue(
                    old_name=type_name,
                    definition_file=definition_file,
                    orphaned_usages=filtered_usages,
                )
            )

    # Log summary
    log_scan_summary(removed_types_count, files_scanned, len(issues))

    # Update state
    if issues:
        state["type_rename_check_passed"] = False
        state["type_rename_issues"] = issues
        state["type_rename_error"] = format_type_rename_error(issues)
    else:
        state["type_rename_check_passed"] = True
        state["type_rename_issues"] = []

    return state
```
