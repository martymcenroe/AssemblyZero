```python
"""LangGraph workflow node for detecting orphaned type references.

Issue: #170
LLD: docs/LLDs/active/170-check-type-renames.md

This node detects when a class/type is renamed in staged changes and verifies
all usages are updated, preventing broken imports.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class OrphanedUsage(TypedDict):
    """Location of an orphaned type reference."""
    file_path: str
    line_number: int
    line_content: str


class TypeRenameIssue(TypedDict):
    """Issue representing a removed type with orphaned references."""
    old_name: str
    definition_file: str
    orphaned_usages: list[OrphanedUsage]


class TypeRenameCheckResult(TypedDict):
    """Result of type rename check."""
    passed: bool
    issues: list[TypeRenameIssue]
    checked_types: list[str]
    files_scanned: int
    removed_types_count: int


def extract_removed_types(diff_content: str) -> list[tuple[str, str]]:
    """Parse git diff to find removed class/type definitions.
    
    Detects:
    - class ClassName:
    - TypeName = TypedDict(...)
    - TypeName: TypeAlias = ...
    - TypeName = Union[...]
    
    Args:
        diff_content: Unified diff output from git
        
    Returns:
        List of (type_name, source_file) tuples
    """
    removed_types = []
    current_file = None
    
    # Pattern for diff file headers
    file_pattern = re.compile(r'^diff --git a/(.*\.py) b/')
    
    # Patterns for type definitions (only removed lines)
    class_pattern = re.compile(r'^-\s*class\s+(\w+)(?:\(|:)')
    typeddict_pattern = re.compile(r'^-\s*(\w+)\s*=\s*TypedDict\(')
    type_alias_pattern = re.compile(r'^-\s*(\w+)\s*(?::\s*TypeAlias)?\s*=\s*(?:Union|Optional|Literal|dict|list|tuple|set)')
    
    for line in diff_content.split('\n'):
        # Track current file being diffed
        file_match = file_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            continue
            
        if not current_file:
            continue
            
        # Check for removed class definitions
        class_match = class_pattern.match(line)
        if class_match:
            type_name = class_match.group(1)
            removed_types.append((type_name, current_file))
            continue
            
        # Check for removed TypedDict
        typeddict_match = typeddict_pattern.match(line)
        if typeddict_match:
            type_name = typeddict_match.group(1)
            removed_types.append((type_name, current_file))
            continue
            
        # Check for removed type aliases
        type_alias_match = type_alias_pattern.match(line)
        if type_alias_match:
            type_name = type_alias_match.group(1)
            removed_types.append((type_name, current_file))
            continue
    
    return removed_types


def find_type_usages(
    type_name: str,
    search_paths: list[Path],
    exclude_patterns: list[str],
    timeout: float = 10.0
) -> list[OrphanedUsage]:
    """Search codebase for usages of a type name.
    
    Uses git grep for fast, index-aware searching.
    Excludes docs, lineage, and other non-source directories.
    
    Args:
        type_name: The type name to search for
        search_paths: Directories to search (must be within git repo)
        exclude_patterns: Glob patterns to exclude
        timeout: Maximum time for search operation
        
    Returns:
        List of orphaned usages found
        
    Raises:
        subprocess.TimeoutExpired: If grep exceeds timeout
    """
    usages = []
    
    # Build git grep command with shell=False for safety
    # Search for word boundaries to avoid partial matches
    cmd = [
        'git', 'grep',
        '-n',  # Show line numbers
        '-w',  # Match whole words only
        '--',  # Separate patterns from paths
        type_name
    ]
    
    # Add search paths
    for path in search_paths:
        cmd.append(str(path))
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=search_paths[0].parent if search_paths else None
        )
        
        # git grep returns 1 if no matches (not an error)
        if result.returncode not in (0, 1):
            logger.warning(f"git grep failed with code {result.returncode}: {result.stderr}")
            return usages
            
        # Parse output: file:line:content
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
                
            parts = line.split(':', 2)
            if len(parts) < 3:
                continue
                
            file_path, line_num_str, content = parts
            
            # Apply exclusion patterns
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in file_path:
                    should_exclude = True
                    break
                    
            if should_exclude:
                continue
            
            # Only include .py files
            if not file_path.endswith('.py'):
                continue
                
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue
                
            usages.append(OrphanedUsage(
                file_path=file_path,
                line_number=line_num,
                line_content=content.strip()
            ))
            
    except subprocess.TimeoutExpired:
        logger.error(f"Search for '{type_name}' exceeded {timeout}s timeout")
        raise TimeoutError(f"Type usage search exceeded {timeout}s timeout")
        
    return usages


def format_type_rename_error(issues: list[TypeRenameIssue]) -> str:
    """Format issues into a clear, actionable error message.
    
    Args:
        issues: List of detected issues
        
    Returns:
        Formatted error message with file locations and fix guidance
    """
    lines = [
        "TYPE RENAME CHECK FAILED",
        "=" * 60,
        "",
        "The following types were removed but still have references:",
        ""
    ]
    
    for issue in issues:
        lines.append(f"Type: {issue['old_name']}")
        lines.append(f"Removed from: {issue['definition_file']}")
        lines.append(f"Orphaned usages ({len(issue['orphaned_usages'])}):")
        lines.append("")
        
        for usage in issue['orphaned_usages']:
            lines.append(f"  {usage['file_path']}:{usage['line_number']}")
            lines.append(f"    {usage['line_content']}")
            lines.append("")
        
        lines.append("-" * 60)
        lines.append("")
    
    lines.extend([
        "To fix:",
        "1. Update all orphaned references to use the new type name",
        "2. Or add the old type as an alias for backward compatibility",
        "3. Or remove the type from imports where it's no longer needed",
        ""
    ])
    
    return "\n".join(lines)


def log_scan_summary(removed_types_count: int, files_scanned: int, issues_found: int) -> None:
    """Log summary of scan for debugging and observability.
    
    Args:
        removed_types_count: Number of removed types detected from diff
        files_scanned: Number of files scanned for usages
        issues_found: Number of orphaned usage issues found
    """
    logger.info(
        f"Type rename check summary: "
        f"{removed_types_count} removed types, "
        f"{files_scanned} files scanned, "
        f"{issues_found} orphaned usage issues found"
    )


def check_type_renames(state: dict, timeout: float = 10.0) -> dict:
    """Pre-commit check for orphaned type references.
    
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
    logger.info("Starting type rename check")
    
    # Get staged diff
    try:
        result = subprocess.run(
            ['git', 'diff', '--staged'],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        diff_content = result.stdout
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Getting git diff exceeded {timeout}s timeout")
    
    # Extract removed types
    removed_types = extract_removed_types(diff_content)
    removed_types_count = len(removed_types)
    
    logger.info(f"Detected {removed_types_count} removed types from diff")
    
    if not removed_types:
        logger.info("No removed types found, check passed")
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': []
        }
    
    # Get repository root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Getting repo root exceeded {timeout}s timeout")
    
    # Search for usages
    issues = []
    exclude_patterns = ['docs/', 'lineage/', '.md']
    
    for type_name, definition_file in removed_types:
        logger.debug(f"Searching for usages of '{type_name}'")
        
        # Search entire repo
        usages = find_type_usages(
            type_name,
            [repo_root],
            exclude_patterns + [definition_file],  # Exclude definition file itself
            timeout=timeout
        )
        
        if usages:
            issues.append(TypeRenameIssue(
                old_name=type_name,
                definition_file=definition_file,
                orphaned_usages=usages
            ))
    
    # Count files scanned (approximate from git ls-files)
    try:
        result = subprocess.run(
            ['git', 'ls-files', '*.py'],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_root
        )
        files_scanned = len(result.stdout.strip().split('\n'))
    except subprocess.TimeoutExpired:
        files_scanned = 0  # Unknown
    
    log_scan_summary(removed_types_count, files_scanned, len(issues))
    
    if issues:
        error_message = format_type_rename_error(issues)
        logger.error(f"Type rename check failed:\n{error_message}")
        
        return {
            **state,
            'type_rename_check_passed': False,
            'type_rename_issues': issues,
            'error_message': error_message
        }
    
    logger.info("Type rename check passed")
    return {
        **state,
        'type_rename_check_passed': True,
        'type_rename_issues': []
    }
```
