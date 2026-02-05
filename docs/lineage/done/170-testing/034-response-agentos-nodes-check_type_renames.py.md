```python
"""Check for orphaned type references after class/type renames.

LLD Reference: docs/LLDs/active/170-check-type-renames.md
Issue: #170
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class OrphanedUsage(TypedDict):
    """A single orphaned usage of a removed type."""
    file_path: str
    line_number: int
    line_content: str


class TypeRenameIssue(TypedDict):
    """An issue representing a removed type with orphaned usages."""
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
    """Extract removed type definitions from git diff.
    
    Args:
        diff_content: Unified diff content from git
        
    Returns:
        List of (type_name, source_file) tuples
    """
    removed_types = []
    current_file = None
    
    # Track current file being diffed
    file_pattern = re.compile(r'^---\s+a/(.+\.py)$', re.MULTILINE)
    
    # Patterns for type definitions (only on removed lines starting with -)
    # Class definitions: class ClassName:
    class_pattern = re.compile(r'^-\s*class\s+([A-Z][a-zA-Z0-9_]*)\s*[:\(]')
    # TypedDict assignments: Name = TypedDict(...)
    typeddict_pattern = re.compile(r'^-\s*([A-Z][a-zA-Z0-9_]*)\s*=\s*TypedDict\s*\(')
    # Type aliases: MyType = Union[...] or MyType = list[...]
    type_alias_pattern = re.compile(r'^-\s*([A-Z][a-zA-Z0-9_]*)\s*=\s*(?:Union|Optional|List|Dict|Tuple|Set|Callable|Type)\[')
    
    for line in diff_content.split('\n'):
        # Track which file we're in
        file_match = file_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            continue
        
        if not current_file:
            continue
            
        # Check for removed type definitions
        for pattern in [class_pattern, typeddict_pattern, type_alias_pattern]:
            match = pattern.match(line)
            if match:
                type_name = match.group(1)
                removed_types.append((type_name, current_file))
                break
    
    return removed_types


def find_type_usages(
    type_name: str,
    search_paths: list[Path],
    exclude_patterns: list[str],
    timeout: float = 10.0
) -> list[OrphanedUsage]:
    """Search codebase for usages of a type name.
    
    Args:
        type_name: The type name to search for
        search_paths: Directories to search
        exclude_patterns: Glob patterns to exclude
        timeout: Maximum time for search operation
        
    Returns:
        List of OrphanedUsage objects
        
    Raises:
        subprocess.TimeoutExpired: If grep exceeds timeout
    """
    usages = []
    
    # Build git grep command with shell=False (argument list)
    # Use word boundary matching to avoid partial matches
    cmd = ['git', 'grep', '-n', '--', rf'\b{type_name}\b']
    
    # Add path filters (only .py files)
    cmd.append('*.py')
    
    try:
        # Run git grep with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=search_paths[0] if search_paths else None
        )
        
        # git grep returns 1 when no matches found (not an error)
        if result.returncode not in [0, 1]:
            logger.warning(f"git grep returned {result.returncode}: {result.stderr}")
            return usages
        
        # Parse results
        for line in result.stdout.split('\n'):
            if not line.strip():
                continue
                
            # Format: file:line:content
            parts = line.split(':', 2)
            if len(parts) < 3:
                continue
                
            file_path, line_num, content = parts
            
            # Apply exclude patterns
            should_exclude = False
            for pattern in exclude_patterns:
                if pattern in file_path:
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
            
            usages.append(OrphanedUsage(
                file_path=file_path,
                line_number=int(line_num),
                line_content=content.strip()
            ))
    
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout searching for {type_name}")
        raise
    
    return usages


def format_type_rename_error(issues: list[TypeRenameIssue]) -> str:
    """Format issues into a clear, actionable error message.
    
    Args:
        issues: List of TypeRenameIssue objects
        
    Returns:
        Formatted error message
    """
    lines = [
        "❌ ORPHANED TYPE REFERENCES DETECTED",
        "",
        "The following types were removed/renamed but still have references:",
        ""
    ]
    
    for issue in issues:
        lines.append(f"Type: {issue['old_name']}")
        lines.append(f"Originally defined in: {issue['definition_file']}")
        lines.append(f"Orphaned usages ({len(issue['orphaned_usages'])}):")
        
        for usage in issue['orphaned_usages']:
            lines.append(f"  - {usage['file_path']}:{usage['line_number']}")
            lines.append(f"    {usage['line_content']}")
        
        lines.append("")
    
    lines.append("💡 FIX: Update all references to use the new type name, or remove unused imports.")
    
    return '\n'.join(lines)


def log_scan_summary(removed_types_count: int, files_scanned: int, issues_found: int) -> None:
    """Log summary of scan for debugging and observability.
    
    Args:
        removed_types_count: Number of removed types detected from diff
        files_scanned: Number of files scanned
        issues_found: Number of orphaned usage issues found
    """
    logger.info(f"Type rename check: {removed_types_count} removed types, "
                f"{files_scanned} files scanned, {issues_found} issues found")


def check_type_renames(state: dict, timeout: float = 10.0) -> dict:
    """Pre-commit check for orphaned type references.
    
    Detects removed/renamed class/type definitions from git diff
    and greps codebase for remaining usages.
    
    Args:
        state: Workflow state containing staged changes
        timeout: Maximum execution time in seconds (default: 10.0)
        
    Returns:
        Updated state dict with check results
        
    Raises:
        TimeoutError: If check exceeds timeout limit
    """
    # Get diff content from state
    diff_content = state.get('git_diff', '')
    if not diff_content:
        logger.info("No git diff found, skipping type rename check")
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': []
        }
    
    # Extract removed types from diff
    removed_types = extract_removed_types(diff_content)
    
    if not removed_types:
        logger.info("No removed types detected")
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': []
        }
    
    logger.info(f"Detected {len(removed_types)} removed types from diff")
    
    # Get repository root (assume we're in it)
    repo_root = Path.cwd()
    
    # Exclude patterns
    exclude_patterns = [
        'docs/',
        'lineage/',
        '.md',
        '__pycache__',
        '.pytest_cache'
    ]
    
    # Check each removed type for orphaned usages
    issues = []
    files_scanned = 0
    
    for type_name, definition_file in removed_types:
        try:
            usages = find_type_usages(
                type_name,
                [repo_root],
                exclude_patterns + [definition_file],  # Exclude the definition file itself
                timeout=timeout
            )
            
            # Filter out the definition file from usages
            orphaned_usages = [
                usage for usage in usages
                if definition_file not in usage['file_path']
            ]
            
            if orphaned_usages:
                issues.append(TypeRenameIssue(
                    old_name=type_name,
                    definition_file=definition_file,
                    orphaned_usages=orphaned_usages
                ))
                files_scanned += len(orphaned_usages)
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Type rename check exceeded {timeout}s timeout while checking {type_name}")
    
    # Log summary
    log_scan_summary(len(removed_types), files_scanned, len(issues))
    
    # Return results
    if issues:
        error_message = format_type_rename_error(issues)
        logger.error(error_message)
        
        return {
            **state,
            'type_rename_check_passed': False,
            'type_rename_issues': issues,
            'type_rename_error': error_message
        }
    else:
        logger.info(f"✓ All {len(removed_types)} type renames are clean")
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': []
        }
```
