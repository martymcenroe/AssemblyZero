```python
"""Check for orphaned type references after class/type renames.

This node detects when a class or type definition is removed/renamed in a git diff
and verifies that all usages in the codebase have been updated accordingly.

Related: Issue #170
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class OrphanedUsage(TypedDict):
    """A reference to a removed type that wasn't updated."""
    file_path: str
    line_number: int
    line_content: str


class TypeRenameIssue(TypedDict):
    """Information about a type rename issue."""
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
    """Parse git diff to find removed class/type definitions.
    
    Returns list of (type_name, source_file) tuples.
    """
    removed_types: list[tuple[str, str]] = []
    current_file = None
    
    for line in diff_content.split('\n'):
        # Track current file being diffed
        if line.startswith('--- a/'):
            current_file = line[6:]
            # Only process .py files
            if not current_file.endswith('.py'):
                current_file = None
        elif line.startswith('+++ b/'):
            # Update to new filename for renames
            new_file = line[6:]
            if new_file.endswith('.py'):
                current_file = new_file
            else:
                current_file = None
        
        # Skip if not in a Python file
        if not current_file:
            continue
        
        # Look for removed lines with type definitions
        if not line.startswith('-'):
            continue
        
        # Remove the '-' prefix
        content = line[1:]
        
        # Pattern 1: class ClassName:
        class_match = re.match(r'^class\s+(\w+)(?:\(|:)', content.strip())
        if class_match:
            type_name = class_match.group(1)
            removed_types.append((type_name, current_file))
            continue
        
        # Pattern 2: TypeName = TypedDict(...)
        typeddict_match = re.match(r'^(\w+)\s*=\s*TypedDict\(', content.strip())
        if typeddict_match:
            type_name = typeddict_match.group(1)
            removed_types.append((type_name, current_file))
            continue
        
        # Pattern 3: Type aliases (TypeName = Union[...], TypeName = Optional[...], etc.)
        type_alias_match = re.match(r'^(\w+)\s*=\s*(?:Union|Optional|dict|list|tuple|Callable)', content.strip())
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
    
    Uses git grep for fast searching with shell=False for safety.
    """
    usages: list[OrphanedUsage] = []
    
    for search_path in search_paths:
        try:
            # Build git grep command with explicit arguments (shell=False)
            # Search for word boundaries to avoid partial matches
            cmd = [
                'git', 'grep',
                '-n',  # Show line numbers
                '-w',  # Word boundaries
                '--',  # Separator before pattern
                type_name,
                # Search only .py files
                '*.py',
            ]
            
            result = subprocess.run(
                cmd,
                cwd=str(search_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            
            # git grep returns 1 when no matches found, 0 when matches found
            if result.returncode not in (0, 1):
                logger.warning(f"git grep failed with code {result.returncode}: {result.stderr}")
                continue
            
            # Parse output: "filepath:line_number:line_content"
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split(':', 2)
                if len(parts) < 3:
                    continue
                
                file_path, line_num_str, line_content = parts
                
                # Apply exclusions
                should_exclude = False
                for pattern in exclude_patterns:
                    # Simple glob-like matching
                    if pattern.endswith('/'):
                        # Directory exclusion
                        if file_path.startswith(pattern) or f'/{pattern}' in file_path:
                            should_exclude = True
                            break
                    elif pattern.startswith('*.'):
                        # Extension exclusion
                        if file_path.endswith(pattern[1:]):
                            should_exclude = True
                            break
                    else:
                        # Exact match or substring
                        if pattern in file_path:
                            should_exclude = True
                            break
                
                if should_exclude:
                    continue
                
                try:
                    line_number = int(line_num_str)
                except ValueError:
                    continue
                
                usages.append(OrphanedUsage(
                    file_path=file_path,
                    line_number=line_number,
                    line_content=line_content.strip(),
                ))
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Search for type '{type_name}' exceeded {timeout}s timeout")
        except Exception as e:
            logger.error(f"Error searching for type '{type_name}': {e}")
    
    return usages


def format_type_rename_error(issues: list[TypeRenameIssue]) -> str:
    """Format issues into a clear, actionable error message."""
    lines = [
        "❌ Type rename check FAILED: Orphaned type references detected",
        "",
        "The following types were removed/renamed but still have references in the codebase:",
        "",
    ]
    
    for issue in issues:
        lines.append(f"Type: {issue['old_name']}")
        lines.append(f"  Originally defined in: {issue['definition_file']}")
        lines.append(f"  Orphaned usages ({len(issue['orphaned_usages'])}):")
        
        for usage in issue['orphaned_usages']:
            lines.append(f"    - {usage['file_path']}:{usage['line_number']}")
            lines.append(f"      {usage['line_content']}")
        
        lines.append("")
    
    lines.append("Fix: Update or remove these references before committing.")
    
    return '\n'.join(lines)


def log_scan_summary(removed_types_count: int, files_scanned: int, issues_found: int) -> None:
    """Log summary of scan for debugging and observability."""
    logger.info(
        f"Type rename check summary: "
        f"detected {removed_types_count} removed types, "
        f"scanned {files_scanned} files, "
        f"found {issues_found} orphaned usage issues"
    )


def check_type_renames(state: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    """Pre-commit check for orphaned type references.
    
    Detects removed/renamed class/type definitions from git diff
    and greps codebase for remaining usages.
    
    Args:
        state: Workflow state containing staged changes
        timeout: Maximum execution time in seconds (default: 10.0)
    
    Raises:
        TimeoutError: If check exceeds timeout limit
    """
    # Get diff from state
    diff_content = state.get('diff', '')
    if not diff_content:
        # No diff to check
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': [],
        }
    
    # Extract removed types from diff
    removed_types = extract_removed_types(diff_content)
    
    if not removed_types:
        # No removed types detected
        logger.info("Type rename check: no removed types detected")
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': [],
        }
    
    logger.info(f"Detected {len(removed_types)} removed types from diff")
    
    # Get repository root from state or default to current directory
    repo_root = Path(state.get('repo_root', '.')).resolve()
    
    # Exclusion patterns
    exclude_patterns = [
        'docs/',
        'lineage/',
        '*.md',
    ]
    
    # Check each removed type for orphaned usages
    issues: list[TypeRenameIssue] = []
    total_files_scanned = 0
    
    for type_name, definition_file in removed_types:
        # Also exclude the definition file itself (for type alias detection)
        current_excludes = exclude_patterns + [definition_file]
        
        try:
            usages = find_type_usages(
                type_name=type_name,
                search_paths=[repo_root],
                exclude_patterns=current_excludes,
                timeout=timeout,
            )
            
            if usages:
                issues.append(TypeRenameIssue(
                    old_name=type_name,
                    definition_file=definition_file,
                    orphaned_usages=usages,
                ))
            
            # Rough estimate of files scanned (count usages as proxy)
            total_files_scanned += len(usages)
        
        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Error checking type '{type_name}': {e}")
    
    # Log summary
    log_scan_summary(
        removed_types_count=len(removed_types),
        files_scanned=total_files_scanned,
        issues_found=len(issues),
    )
    
    # Build result
    if issues:
        error_message = format_type_rename_error(issues)
        logger.error(error_message)
        
        return {
            **state,
            'type_rename_check_passed': False,
            'type_rename_issues': issues,
            'error_message': error_message,
        }
    else:
        logger.info("Type rename check: all usages updated correctly")
        return {
            **state,
            'type_rename_check_passed': True,
            'type_rename_issues': [],
        }
```
