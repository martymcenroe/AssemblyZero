"""Pre-commit check for orphaned type references.

Detects removed/renamed class/type definitions from git diff
and greps codebase for remaining usages.

Reference: LLD #170
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
    """Issue with a removed/renamed type."""
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
    
    Args:
        diff_content: Git diff output
        
    Returns:
        List of (type_name, source_file) tuples
    """
    removed_types = []
    current_file = None
    
    # Track current file from diff headers
    file_pattern = re.compile(r'^--- a/(.+\.py)$', re.MULTILINE)
    
    # Match removed class definitions
    class_pattern = re.compile(r'^-\s*class\s+(\w+)(?:\(|:)', re.MULTILINE)
    
    # Match removed TypedDict definitions
    typeddict_pattern = re.compile(r'^-\s*(\w+)\s*=\s*TypedDict', re.MULTILINE)
    
    # Match removed type aliases
    type_alias_pattern = re.compile(r'^-\s*(\w+)\s*=\s*(?:Union|Optional|List|Dict|Tuple|Set)', re.MULTILINE)
    
    lines = diff_content.split('\n')
    
    for i, line in enumerate(lines):
        # Track current file
        file_match = file_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            continue
        
        if current_file and line.startswith('-') and not line.startswith('---'):
            # Check for class definitions
            class_match = class_pattern.match(line)
            if class_match:
                type_name = class_match.group(1)
                removed_types.append((type_name, current_file))
                continue
            
            # Check for TypedDict
            typeddict_match = typeddict_pattern.match(line)
            if typeddict_match:
                type_name = typeddict_match.group(1)
                removed_types.append((type_name, current_file))
                continue
            
            # Check for type aliases
            alias_match = type_alias_pattern.match(line)
            if alias_match:
                type_name = alias_match.group(1)
                removed_types.append((type_name, current_file))
    
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
        List of orphaned usages
        
    Raises:
        subprocess.TimeoutExpired: If grep exceeds timeout
    """
    usages = []
    
    for search_path in search_paths:
        try:
            # Build git grep command with shell=False for safety
            cmd = ['git', 'grep', '-n', '-I', '--', type_name]
            
            result = subprocess.run(
                cmd,
                cwd=str(search_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            
            # git grep returns 1 when no matches found, which is not an error
            if result.returncode not in (0, 1):
                continue
            
            # Parse grep output
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                # Parse git grep format: filepath:line_number:content
                parts = line.split(':', 2)
                if len(parts) < 3:
                    continue
                
                file_path, line_num_str, content = parts
                
                # Apply exclusions
                if any(pattern in file_path for pattern in exclude_patterns):
                    continue
                
                # Only include .py files
                if not file_path.endswith('.py'):
                    continue
                
                try:
                    line_number = int(line_num_str)
                except ValueError:
                    continue
                
                usages.append(OrphanedUsage(
                    file_path=file_path,
                    line_number=line_number,
                    line_content=content.strip()
                ))
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Search for '{type_name}' exceeded {timeout}s timeout")
        except Exception as e:
            logger.warning(f"Error searching for {type_name}: {e}")
            continue
    
    return usages


def format_type_rename_error(issues: list[TypeRenameIssue]) -> str:
    """Format issues into a clear, actionable error message.
    
    Args:
        issues: List of type rename issues
        
    Returns:
        Formatted error message
    """
    lines = ["TYPE RENAME CHECK FAILED", ""]
    lines.append("Detected removed/renamed types with orphaned references:")
    lines.append("")
    
    for issue in issues:
        lines.append(f"Type: {issue['old_name']}")
        lines.append(f"Originally defined in: {issue['definition_file']}")
        lines.append(f"Orphaned usages ({len(issue['orphaned_usages'])}):")
        
        for usage in issue['orphaned_usages']:
            lines.append(f"  {usage['file_path']}:{usage['line_number']}")
            lines.append(f"    {usage['line_content']}")
        
        lines.append("")
    
    lines.append("Fix: Update or remove the references listed above.")
    
    return '\n'.join(lines)


def log_scan_summary(removed_types_count: int, files_scanned: int, issues_found: int) -> None:
    """Log summary of scan for debugging and observability.
    
    Args:
        removed_types_count: Number of removed types detected
        files_scanned: Number of files scanned
        issues_found: Number of orphaned usage issues found
    """
    logger.info(f"Type rename check summary:")
    logger.info(f"  - Removed types detected: {removed_types_count}")
    logger.info(f"  - Files scanned: {files_scanned}")
    logger.info(f"  - Orphaned usage issues: {issues_found}")


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
    # Get git diff
    try:
        result = subprocess.run(
            ['git', 'diff', '--staged'],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False
        )
        diff_content = result.stdout
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Git diff exceeded {timeout}s timeout")
    
    # Extract removed types
    removed_types = extract_removed_types(diff_content)
    removed_types_count = len(removed_types)
    
    logger.info(f"Detected {removed_types_count} removed types from diff")
    
    if not removed_types:
        state['type_rename_check_passed'] = True
        state['type_rename_issues'] = []
        log_scan_summary(0, 0, 0)
        return state
    
    # Get repository root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            timeout=5.0,
            shell=False
        )
        repo_root = Path(result.stdout.strip())
    except Exception:
        repo_root = Path.cwd()
    
    # Search for usages
    issues = []
    exclude_patterns = ['docs/', 'lineage/', '.md']
    files_scanned_set = set()
    
    for type_name, definition_file in removed_types:
        # Add definition file to exclusions for this search
        current_exclusions = exclude_patterns + [definition_file]
        
        usages = find_type_usages(
            type_name,
            [repo_root],
            current_exclusions,
            timeout=timeout
        )
        
        # Track scanned files
        for usage in usages:
            files_scanned_set.add(usage['file_path'])
        
        if usages:
            issues.append(TypeRenameIssue(
                old_name=type_name,
                definition_file=definition_file,
                orphaned_usages=usages
            ))
    
    files_scanned = len(files_scanned_set)
    log_scan_summary(removed_types_count, files_scanned, len(issues))
    
    # Update state
    if issues:
        state['type_rename_check_passed'] = False
        state['type_rename_issues'] = issues
        state['error_message'] = format_type_rename_error(issues)
    else:
        state['type_rename_check_passed'] = True
        state['type_rename_issues'] = []
    
    return state