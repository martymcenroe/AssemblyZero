# Implementation Request: assemblyzero/workflows/requirements/nodes/validate_mechanical.py

## Task

Write the complete contents of `assemblyzero/workflows/requirements/nodes/validate_mechanical.py`.

Change type: Modify
Description: Integration

## LLD Specification

# Implementation Spec: 0600 - AST-Based Import Sentinel

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #600 |
| LLD | `docs/lld/active/LLD-600.md` |
| Generated | 2026-03-05 |
| Status | APPROVED |

## 1. Overview
Catch missing imports early.

## 2. Files to Implement
| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/utils/ast_sentinel.py` | Add | AST logic |
| 2 | `tests/unit/test_ast_sentinel.py` | Add | Tests |
| 3 | `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | Modify | Integration |

## 3. Requirements
1. The system MUST parse Python files using `ast.parse`.
2. The system MUST detect undefined symbols in the Load context.
3. The system MUST handle nested scopes, including functions and classes.
4. The system MUST prohibit star imports (e.g., `from module import *`).
5. The system MUST support `# sentinel: disable-line` to bypass specific lines.

## 4. Data Structures
None.

## 5. Function Specifications
`analyze_file(path)`

## 6. Change Instructions
### 6.1 `assemblyzero/utils/ast_sentinel.py` (Add)
```python
import ast
import builtins
# ... implementation ...
```

## 7. Pattern References
None.

## 8. Dependencies & Imports
| Import | Source |
|--------|--------|
| `ast` | stdlib |

## 9. Test Mapping
| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Happy path valid analysis (REQ-1) | Success |
| T020 | Missing import detected (REQ-2) | Error |
| T030 | Nested scope valid (REQ-3) | Success |
| T040 | Star import blocked (REQ-4) | Error |
| T050 | Disable line respected (REQ-5) | Success |

## 10. Implementation Notes
None.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
"""Mechanical LLD validation node.

Issue #277: Add mechanical validation to catch path errors and section
inconsistencies before Gemini review.

Issue #306: Add title issue number validation to detect mismatches before
human or Gemini review.

Issue #312: Add pattern detection for function references vs approach mitigations
to reduce false positive warnings.

Issue #322: Add explicit check for invalid/missing repo_root, returning blocking
error instead of silent skip.

Issue #334: Normalize change types with parenthetical suffixes (e.g., "Add (Directory)")
and save validation errors to lineage for audit trail.

Issue #600: Integrate AST-based import sentinel to catch missing imports in
existing Python files referenced by the LLD before Gemini review.

This node validates LLD content deterministically without LLM calls:
- Mandatory sections exist (2.1, 11, 12)
- File paths are valid (Modify/Delete exist, Add parents exist)
- No placeholder prefixes (src/, lib/, app/) unless they exist
- Definition of Done matches Files Changed
- Risk mitigations trace to functions (warning only, with smart filtering)
- LLD title issue number matches workflow issue number
- Target repo validation (None, empty, non-existent paths are blocking errors)
- Change type normalization (handles parenthetical suffixes like "Add (Directory)")
- AST-based import sentinel on existing Python files (warning only)
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from assemblyzero.utils.ast_sentinel import analyze_file as ast_analyze_file
from assemblyzero.workflows.requirements.state import RequirementsWorkflowState

logger = logging.getLogger(__name__)

# =============================================================================
# Data Structures
# =============================================================================


class ValidationSeverity(Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Blocks workflow
    WARNING = "warning"  # Logged but does not block


@dataclass
class ValidationError:
    """A validation issue found in the LLD."""

    severity: ValidationSeverity
    section: str
    message: str
    file_path: str | None = None


# =============================================================================
# Constants
# =============================================================================

# Section headers that must be present
# Note: 2.1 is h3 (###), but 11 and 12 are h2 (##) in the LLD template
MANDATORY_SECTIONS = ["### 2.1", "## 11", "## 12"]

# Common placeholder prefixes that often indicate hallucinated paths
PLACEHOLDER_PREFIXES = ["src", "lib", "app"]

# Stopwords to filter from keyword extraction
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "if", "when", "where",
    "how", "what", "which", "who", "whom", "why", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "not",
    "only", "same", "so", "than", "too", "very", "just", "also", "any",
}

# Issue #312: Patterns for detecting explicit function references
# Examples:
# - `function_name` (backticks around identifier)
# - function_name() (parentheses after identifier)
# - "in function_name" or "via function_name"
FUNCTION_REFERENCE_PATTERNS = [
    re.compile(r'`([a-zA-Z_][a-zA-Z0-9_]*)`', re.IGNORECASE),  # `func_name`
    re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)', re.IGNORECASE),  # func_name()
    re.compile(r'\bin\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', re.IGNORECASE),  # in func_name
    re.compile(r'\bvia\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', re.IGNORECASE),  # via func_name
]

# Issue #312: Patterns for detecting approach-style mitigations
# Examples:
# - O(n), O(1), O(log n) (algorithmic complexity)
# - UTF-8, encoding, codec (encoding practices)
# - opt-in, default unchanged, explicitly (configuration practices)
APPROACH_MITIGATION_PATTERNS = [
    re.compile(r'O\([^)]+\)', re.IGNORECASE),  # O(n), O(1), O(log n)
    re.compile(r'\b(UTF-8|encoding|codec)\b', re.IGNORECASE),  # Encoding references
    re.compile(r'\b(opt-in|default\s+unchanged|explicitly)\b', re.IGNORECASE),  # Practices
]

# Issue #306: Pattern for extracting issue number from LLD title
# Supports: hyphen (-), en-dash (–), em-dash (—)
# Handles leading zeros: # 099 - Feature or # 99 - Feature
TITLE_ISSUE_NUMBER_PATTERN = re.compile(
    r'^#\s+0*(\d+)\s+[-–—]',  # Matches "# 0099 -" or "# 99 –" or "# 99 —"
    re.MULTILINE
)


# =============================================================================
# Issue #334: Change Type Normalization Functions
# =============================================================================


def normalize_change_type(raw_change_type: str) -> tuple[str, bool]:
    """Normalize change types with parenthetical suffixes.
    
    Issue #334: Handles change types like "Add (Directory)" by extracting
    the base type and setting an is_directory flag.
    
    Args:
        raw_change_type: Raw change type string (e.g., "Add (Directory)", "Modify")
        
    Returns:
        Tuple of (normalized_type, is_directory)
        e.g., "Add (Directory)" -> ("add", True)
             "Modify" -> ("modify", False)
    """
    if not raw_change_type:
        return ("", False)
    
    # Strip whitespace
    cleaned = raw_change_type.strip()
    
    # Check for parenthetical suffix
    is_directory = False
    if "(" in cleaned:
        # Split on opening parenthesis
        parts = cleaned.split("(", 1)
        base_type = parts[0].strip()
        
        # Check if the parenthetical contains "directory"
        if len(parts) > 1:
            parenthetical = parts[1].lower()
            is_directory = "directory" in parenthetical
    else:
        base_type = cleaned
    
    # Normalize to lowercase
    normalized_type = base_type.lower().strip()
    
    return (normalized_type, is_directory)


def save_validation_errors_to_lineage(
    errors: list[str],
    lineage_path: Path,
    draft_number: int
) -> Path:
    """Save validation errors to lineage folder for audit trail.
    
    Issue #334: Creates a markdown file in the lineage folder documenting
    all validation errors for a specific draft iteration.
    
    Args:
        errors: List of validation error messages
        lineage_path: Path to the lineage folder
        draft_number: The draft iteration number
        
    Returns:
        Path to the saved error file
    """
    # Sanitize draft number to prevent path traversal
    safe_draft_number = abs(int(draft_number))
    
    # Create lineage directory if it doesn't exist
    lineage_path = Path(lineage_path).resolve()
    lineage_path.mkdir(parents=True, exist_ok=True)
    
    # Create error file path
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    error_filename = f"validation-errors-draft{safe_draft_number:03d}-{timestamp}.md"
    error_file_path = lineage_path / error_filename
    
    # Build markdown content
    content_lines = [
        f"# Validation Errors - Draft {safe_draft_number}",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Draft Number:** {safe_draft_number}",
        f"**Error Count:** {len(errors)}",
        "",
        "## Errors",
        "",
    ]
    
    for i, error in enumerate(errors, 1):
        # Escape special characters to prevent log injection
        escaped_error = error.replace("<", "&lt;").replace(">", "&gt;")
        content_lines.append(f"{i}. {escaped_error}")
    
    content_lines.append("")
    
    # Write to file
    error_file_path.write_text("\n".join(content_lines), encoding="utf-8")
    
    logger.info(f"Saved validation errors to: {error_file_path}")
    
    return error_file_path


def validate_directory_creation_order(
    changes: list[dict]
) -> list[str]:
    """Validate that directory entries appear before files that depend on them.
    
    Issue #334: Checks that when a directory is declared with "Add (Directory)",
    any files within that directory can use it as a valid parent.
    
    Args:
        changes: List of FileChange dicts with path, change_type, and is_directory
        
    Returns:
        List of error messages if validation fails
    """
    errors = []
    
    # Track directories that will be created
    directories_to_create: set[str] = set()
    
    # First pass: collect all directories that will be created
    for change in changes:
        if change.get("is_directory", False) and change.get("change_type", "").lower() == "add":
            path = change.get("path", "").replace("\\", "/").rstrip("/")
            directories_to_create.add(path)
    
    # Second pass: check file order (files should come after their parent directories)
    seen_directories: set[str] = set()
    
    for change in changes:
        path = change.get("path", "").replace("\\", "/")
        is_directory = change.get("is_directory", False)
        change_type = change.get("change_type", "").lower()
        
        if is_directory and change_type == "add":
            seen_directories.add(path.rstrip("/"))
        elif change_type == "add" and not is_directory:
            # Check if parent directory is in directories_to_create but not yet seen
            parent = str(Path(path).parent).replace("\\", "/")
            
            if parent in directories_to_create and parent not in seen_directories:
                errors.append(
                    f"File '{path}' depends on directory '{parent}' which appears later in the table. "
                    "Reorder entries so directories come before their contents."
                )
    
    return errors


def print_validation_errors(
    errors: list[str],
    max_display: int = 5
) -> None:
    """Print validation errors to console with truncation for readability.
    
    Issue #334: Provides user-visible feedback about validation failures
    with reasonable truncation for large error lists.
    
    Args:
        errors: List of validation error messages
        max_display: Maximum number of errors to display before truncation
    """
    if not errors:
        return
    
    print("\n[ERROR] MECHANICAL VALIDATION FAILED:")
    print("=" * 50)
    
    # Display up to max_display errors
    displayed = errors[:max_display]
    for i, error in enumerate(displayed, 1):
        # Escape special characters for safe console output
        safe_error = error.replace("<", "&lt;").replace(">", "&gt;")
        print(f"  {i}. {safe_error}")
    
    # Show count of remaining errors
    remaining = len(errors) - max_display
    if remaining > 0:
        print(f"\n  ... and {remaining} more error(s)")
    
    print("=" * 50)
    print()


# =============================================================================
# Issue #322: Repo Root Validation Functions
# =============================================================================


def validate_repo_root(repo_root: Path | None) -> tuple[bool, str | None]:
    """Validate that repo_root is valid and exists.
    
    Issue #322: Explicit check for invalid/missing repo_root.
    
    Returns:
        tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    # Check for None
    if repo_root is None:
        return (False, "Cannot validate file paths: target_repo not specified")
    
    # Check for empty string (Path("") becomes "." in pathlib - current directory)
    repo_str = str(repo_root)
    if not repo_str or repo_str.strip() == "" or repo_str == ".":
        return (False, "Cannot validate file paths: target_repo not specified (empty value)")
    
    # Check if path exists on filesystem
    if not repo_root.exists():
        return (False, f"Cannot validate file paths: target_repo '{repo_root}' does not exist")
    
    return (True, None)


def validate_file_paths_with_repo_check(
    files: list[dict],
    repo_root: Path | None
) -> tuple[list[ValidationError], bool]:
    """Validate file paths against repo, with explicit repo validation.
    
    Issue #322: Explicit check for invalid/missing repo_root before path validation.
    Issue #334: Supports is_directory flag for directory entries.
    
    Returns:
        tuple of (errors, was_validated)
        - errors: List of validation errors (may include blocking repo error)
        - was_validated: Whether path validation actually ran
    """
    errors: list[ValidationError] = []
    
    # First validate repo_root
    is_valid, error_message = validate_repo_root(repo_root)
    
    if not is_valid:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.ERROR,
                section="2.1",
                message=error_message,
            )
        )
        return (errors, False)
    
    # repo_root is valid, proceed with file path validation
    path_errors = validate_file_paths(files, repo_root)
    errors.extend(path_errors)
    
    return (errors, True)


# =============================================================================
# Issue #312: Pattern Detection Functions
# =============================================================================


def contains_explicit_function_reference(mitigation_text: str) -> tuple[bool, list[str]]:
    """Check if mitigation contains explicit function reference syntax.
    
    Returns tuple of (has_reference, matched_references).
    True if text contains backticks around identifier or parentheses after identifier.
    
    Note: Returns the actual matched references for prioritization logic.
    
    Args:
        mitigation_text: The mitigation text to check.
        
    Returns:
        Tuple of (has_reference, list of matched function names).
    """
    matched_functions = []
    
    for pattern in FUNCTION_REFERENCE_PATTERNS:
        matches = pattern.findall(mitigation_text)
        matched_functions.extend(matches)
    
    return (len(matched_functions) > 0, matched_functions)


def is_approach_mitigation(mitigation_text: str) -> tuple[bool, list[str]]:
    """Check if mitigation describes an approach rather than function.
    
    Returns tuple of (is_approach, matched_patterns).
    True if text describes algorithmic complexity, encoding practices,
    configuration flags, or other coding practices.
    
    Args:
        mitigation_text: The mitigation text to check.
        
    Returns:
        Tuple of (is_approach, list of matched pattern descriptions).
    """
    matched_patterns = []
    
    for pattern in APPROACH_MITIGATION_PATTERNS:
        if pattern.search(mitigation_text):
            matched_patterns.append(pattern.pattern)
    
    return (len(matched_patterns) > 0, matched_patterns)


def should_warn_missing_function(
    mitigation_text: str,
    matched_functions: list[str],
) -> bool:
    """Determine if missing function match warrants a warning.
    
    Logic (addressing G3 mixed content issue):
    1. If mitigation contains explicit function reference (backticks/parens):
       - Extract the specific referenced function names
       - If ANY referenced function is NOT in matched_functions, WARN
       - Approach patterns do NOT suppress warnings for explicit references
    2. If mitigation has NO explicit function reference:
       - If it matches approach patterns, SKIP warning
       - Otherwise, SKIP warning (plain description)
    
    This ensures explicit function references ALWAYS trigger warnings if unmatched,
    even when approach patterns are also present (mixed content case).
    
    Args:
        mitigation_text: The mitigation text.
        matched_functions: List of function names found in Section 2.4.
        
    Returns:
        True if a warning should be emitted, False otherwise.
    """
    has_ref, referenced_funcs = contains_explicit_function_reference(mitigation_text)
    
    if has_ref:
        # Explicit function reference present - check if ANY referenced function is missing
        normalized_matched = [f.lower() for f in matched_functions]
        
        for ref_func in referenced_funcs:
            ref_func_lower = ref_func.lower()
            # Check if this referenced function is in the matched list
            found = any(
                ref_func_lower in matched_func or matched_func in ref_func_lower
                for matched_func in normalized_matched
            )
            if not found:
                # At least one explicit reference is unmatched - warn
                return True
        
        # All explicit references matched - no warning
        return False
    
    # No explicit function reference - check if it's approach-style
    is_approach, _ = is_approach_mitigation(mitigation_text)
    
    # If approach-style or plain description, don't warn
    return False


def log_skipped_mitigation(mitigation_text: str, matched_patterns: list[str]) -> None:
    """Log skipped approach-style mitigation at DEBUG level for traceability.
    
    Called when a mitigation is classified as approach-style and warning is skipped.
    Logs the mitigation text and which patterns matched for debugging purposes.
    
    Args:
        mitigation_text: The mitigation text that was skipped.
        matched_patterns: List of pattern descriptions that matched.
    """
    logger.debug(
        f"Skipped approach-style mitigation: '{mitigation_text[:80]}...' "
        f"(matched patterns: {', '.join(matched_patterns)})"
    )


# =============================================================================
# Issue #306: Title Issue Number Validation
# =============================================================================


def extract_title_issue_number(content: str) -> int | None:
    """Extract issue number from LLD title line.
    
    Handles:
        - Standard format: # 306 - Feature: Title
        - Leading zeros: # 099 - Feature: Title
        - Various dashes: hyphen (-), en-dash (–), em-dash (—)
        
    Args:
        content: Full LLD markdown content
        
    Returns:
        Extracted issue number as int, or None if not found/parseable.
    """
    match = TITLE_ISSUE_NUMBER_PATTERN.search(content)
    if not match:
        return None
    
    try:
        # Group 1 is the number without leading zeros
        return int(match.group(1))
    except (ValueError, IndexError):
        return None


def validate_title_issue_number(content: str, issue_number: int) -> list[ValidationError]:
    """Verify the LLD title contains the correct issue number.
    
    Args:
        content: Full LLD markdown content
        issue_number: Expected issue number from workflow context
        
    Returns:
        List of ValidationError dicts. Empty if valid.
    """
    errors = []
    
    # Check if H1 heading exists
    h1_match = re.search(r'^#\s+', content, re.MULTILINE)
    if not h1_match:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.WARNING,
                section="Title",
                message="No H1 title found in LLD",
            )
        )
        return errors
    
    # Extract issue number from title
    extracted_number = extract_title_issue_number(content)
    
    if extracted_number is None:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.WARNING,
                section="Title",
                message="Could not extract issue number from title",
            )
        )
        return errors
    
    # Compare extracted number with expected number
    if extracted_number != issue_number:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.ERROR,
                section="Title",
                message=f"Title issue number ({extracted_number}) doesn't match workflow issue ({issue_number})",
            )
        )
    
    return errors


# =============================================================================
# Validation Functions
# =============================================================================


def validate_mandatory_sections(lld_content: str) -> list[ValidationError]:
    """Verify that all mandatory LLD sections exist.

    Args:
        lld_content: The LLD markdown content.

    Returns:
        List of ERRORs for any missing mandatory section.
    """
    errors = []

    for section in MANDATORY_SECTIONS:
        if section not in lld_content:
            # Extract section number for clearer message
            section_num = section.replace("### ", "")
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.ERROR,
                    section=section_num,
                    message=f"Critical: Section {section_num} missing from LLD",
                )
            )

    return errors


def parse_files_changed_table(lld_content: str) -> tuple[list[dict], list[ValidationError]]:
    """Extract file entries from Section 2.1 table.
    
    Issue #334: Now normalizes change types and sets is_directory flag.

    Args:
        lld_content: The LLD markdown content.

    Returns:
        Tuple of (list of file dicts with path/change_type/description/is_directory, parse errors).
    """
    files = []
    errors = []

    # Find Section 2.1
    section_match = re.search(
        r"###\s*2\.1[^\n]*\n(.*?)(?=###|\Z)",
        lld_content,
        re.DOTALL,
    )

    if not section_match:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.ERROR,
                section="2.1",
                message="Section 2.1 not found or malformed",
            )
        )
        return files, errors

    section_content = section_match.group(1)

    # Find markdown table rows (| file | type | description |)
    # Table format: | `path` | Type | Description |
    # Allow for variations: with/without backticks, varying whitespace
    # Issue #334: Updated pattern to capture change types with parenthetical suffixes
    table_pattern = re.compile(
        r"\|\s*`?([^`|]+?)`?\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\s*\|",
        re.MULTILINE,
    )

    matches = list(table_pattern.finditer(section_content))

    # Valid base change types we expect (after normalization)
    valid_change_types = {"add", "modify", "delete", "create", "update", "remove"}

    # Filter out header rows and invalid entries
    data_rows = []
    for match in matches:
        path = match.group(1).strip()
        raw_change_type = match.group(2).strip()

        # Skip header rows - check for common header text
        path_lower = path.lower()
        raw_change_type_lower = raw_change_type.lower()

        if path_lower in ("file", "---", "-") or "---" in path:
            continue
        if raw_change_type_lower in ("change type", "change", "type", "---", "-"):
            continue

        # Issue #334: Normalize the change type
        normalized_type, is_directory = normalize_change_type(raw_change_type)

        # Only accept valid base change types
        if normalized_type not in valid_change_types:
            continue

        # Path must look like a file path (contain / or . ) OR be a directory
        if "/" not in path and "." not in path and "\\" not in path:
            # Allow paths without extensions if marked as directory
            if not is_directory:
                continue

        data_rows.append((match, normalized_type, is_directory))

    if not data_rows:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.ERROR,
                section="2.1",
                message="Section 2.1 table malformed or empty - no file entries found",
            )
        )
        return files, errors

    for match, normalized_type, is_directory in data_rows:
        path = match.group(1).strip()
        description = match.group(3).strip()

        files.append({
            "path": path,
            "change_type": normalized_type.capitalize(),  # Store as "Add", "Modify", etc.
            "description": description,
            "is_directory": is_directory,
        })

    return files, errors


def find_similar_files(filename: str, repo_root: Path, max_results: int = 3) -> list[str]:
    """Find files with similar names in the repository.

    Issue #300: Help drafter fix invalid paths by suggesting alternatives.

    Args:
        filename: The filename to search for (e.g., "new_repo_setup.py").
        repo_root: Path to repository root.
        max_results: Maximum number of suggestions to return.

    Returns:
        List of relative paths to similar files.
    """
    suggestions = []

    # Normalize filename: convert underscores to hyphens and vice versa
    base_name = Path(filename).stem  # e.g., "new_repo_setup"
    extension = Path(filename).suffix  # e.g., ".py"

    # Generate variants to search for
    variants = {
        base_name,
        base_name.replace("_", "-"),  # new_repo_setup -> new-repo-setup
        base_name.replace("-", "_"),  # new-repo-setup -> new_repo_setup
    }

    # Search common code directories (limit depth to avoid slowness)
    search_dirs = ["tools", "assemblyzero", "scripts", "src", "lib", "tests"]

    for search_dir in search_dirs:
        dir_path = repo_root / search_dir
        if not dir_path.exists():
            continue

        # Use glob to find matching files (limit depth)
        for pattern_base in variants:
            pattern = f"**/{pattern_base}{extension}"
            try:
                for match in dir_path.glob(pattern):
                    if match.is_file():
                        rel_path = str(match.relative_to(repo_root)).replace("\\", "/")
                        if rel_path not in suggestions:
                            suggestions.append(rel_path)
                            if len(suggestions) >= max_results:
                                return suggestions
            except (OSError, ValueError):
                continue

    return suggestions


def validate_file_paths(
    files: list[dict],
    repo_root: Path,
) -> list[ValidationError]:
    """Check that Modify/Delete files exist, Add files have valid parents.

    Issue #300: Include file path suggestions when files don't exist.
    Issue #334: Track directories that will be created for parent validation.

    Args:
        files: List of file dicts with path, change_type, and is_directory.
        repo_root: Path to repository root.

    Returns:
        List of ERRORs for invalid paths.
    """
    errors = []
    
    # Issue #334: Track directories that will be created by "Add (Directory)" entries
    directories_to_create: set[str] = set()
    
    # First pass: collect all directories that will be created
    # Issue #388: Also collect parent directories implied by Add file entries
    for file_info in files:
        if file_info.get("change_type") != "Add":
            continue

        if file_info.get("is_directory", False):
            # Explicit directory creation
            dir_path = file_info["path"].replace("\\", "/").rstrip("/")
            directories_to_create.add(dir_path)
            # Also add all parent paths that this directory implies
            parts = dir_path.split("/")
            for i in range(1, len(parts)):
                parent = "/".join(parts[:i])
                if parent:
                    directories_to_create.add(parent)
        else:
            # Issue #388: Add file entries imply their parent directories
            # e.g., "new_package/module.py" implies "new_package/" exists
            parent_path = str(Path(file_info["path"]).parent).replace("\\", "/")
            if parent_path and parent_path != ".":
                directories_to_create.add(parent_path)
                # Also add ancestor directories
                parts = parent_path.split("/")
                for i in range(1, len(parts)):
                    ancestor = "/".join(parts[:i])
                    if ancestor:
                        directories_to_create.add(ancestor)

    for file_info in files:
        path = file_info["path"]
        change_type = file_info["change_type"]
        is_directory = file_info.get("is_directory", False)
        full_path = repo_root / path

        if change_type in ("Modify", "Delete"):
            if not full_path.exists():
                # Issue #300: Find similar files to suggest
                filename = Path(path).name
                suggestions = find_similar_files(filename, repo_root)

                if suggestions:
                    suggestion_text = ", ".join(f"`{s}`" for s in suggestions)
                    message = (
                        f"File marked {change_type} but does not exist: {path}. "
                        f"Did you mean: {suggestion_text}?"
                    )
                else:
                    message = f"File marked {change_type} but does not exist: {path}"

                errors.append(
                    ValidationError(
                        severity=ValidationSeverity.ERROR,
                        section="2.1",
                        message=message,
                        file_path=path,
                    )
                )
        elif change_type == "Add":
            # Issue #334: For directories, check parent of directory
            # For files, check parent directory exists or will be created
            if is_directory:
                # For directory creation, check parent exists or will be created
                parent_dir = Path(path).parent
                parent_str = str(parent_dir).replace("\\", "/")
                full_parent = repo_root / parent_dir
                
                if parent_str and parent_str != ".":
                    if not full_parent.exists() and parent_str not in directories_to_create:
                        errors.append(
                            ValidationError(
                                severity=ValidationSeverity.ERROR,
                                section="2.1",
                                message=f"Parent directory does not exist for Add directory: {path}",
                                file_path=path,
                            )
                        )
            else:
                # For file creation, check parent exists or will be created
                parent_dir = full_path.parent
                parent_rel = str(Path(path).parent).replace("\\", "/")
                
                if not parent_dir.exists() and parent_rel not in directories_to_create:
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.ERROR,
                            section="2.1",
                            message=f"Parent directory does not exist for Add file: {path}",
                            file_path=path,
                        )
                    )

    return errors


def detect_placeholder_prefixes(
    files: list[dict],
    repo_root: Path,
) -> list[ValidationError]:
    """Flag paths using src/, lib/, app/ when those directories don't exist.

    Args:
        files: List of file dicts with path.
        repo_root: Path to repository root.

    Returns:
        List of ERRORs for placeholder prefixes without matching directories.
    """
    errors = []

    for file_info in files:
        path = file_info["path"]
        parts = path.replace("\\", "/").split("/")

        if parts:
            prefix = parts[0]
            if prefix in PLACEHOLDER_PREFIXES:
                prefix_path = repo_root / prefix
                if not prefix_path.exists():
                    errors.append(
                        ValidationError(
                            severity=ValidationSeverity.ERROR,
                            section="2.1",
                            message=f"Path uses '{prefix}/' but that directory doesn't exist in repo: {path}",
                            file_path=path,
                        )
                    )

    return errors


def extract_files_from_section(lld_content: str, section_header: str) -> set[str]:
    """Extract file paths mentioned in a specific section.

    Looks for paths in backticks or common path patterns.

    Args:
        lld_content: The LLD markdown content.
        section_header: The section header to search (e.g., "## 12").

    Returns:
        Set of file paths mentioned in the section.
    """
    files = set()

    # Find the section (stop at next ## or ### heading, or end of string)
    pattern = rf"{re.escape(section_header)}[^\n]*\n(.*?)(?=##|\Z)"
    section_match = re.search(pattern, lld_content, re.DOTALL)

    if not section_match:
        return files

    section_content = section_match.group(1)

    # Extract paths in backticks
    backtick_paths = re.findall(r"`([^`]+\.[a-zA-Z]+)`", section_content)
    files.update(backtick_paths)

    # Also look for paths without backticks that look like file paths
    # Pattern: word/word/word.ext
    bare_paths = re.findall(r"[\w\-]+(?:/[\w\-]+)+\.\w+", section_content)
    files.update(bare_paths)

    return files


def cross_reference_sections(
    lld_content: str,
    files_changed: list[dict],
) -> list[ValidationError]:
    """Verify files in Definition of Done appear in Files Changed.

    Args:
        lld_content: The LLD markdown content.
        files_changed: List of file dicts from Section 2.1.

    Returns:
        List of ERRORs for mismatched references.
    """
    errors = []

    # Get files mentioned in Section 12 (Definition of Done, uses ## heading)
    dod_files = extract_files_from_section(lld_content, "## 12")

    # Get files from Section 2.1
    fc_files = {f["path"] for f in files_changed}

    # Find files in DoD but not in Files Changed
    missing = dod_files - fc_files

    for file_path in missing:
        # Only report if it looks like a real path (has directory structure)
        if "/" in file_path or "\\" in file_path:
            errors.append(
                ValidationError(
                    severity=ValidationSeverity.ERROR,
                    section="12",
                    message=f"Section 12 references file not in Section 2.1: {file_path}",
                    file_path=file_path,
                )
            )

    return errors


def extract_mitigations_from_risks(lld_content: str) -> list[str]:
    """Parse Section 11 Risks table to extract mitigation text.

    Args:
        lld_content: The LLD markdown content.

    Returns:
        List of mitigation text strings.
    """
    mitigations = []

    # Find Section 11 (uses ## heading in LLD template)
    section_match = re.search(
        r"##\s*11[^\n]*\n(.*?)(?=##|\Z)",
        lld_content,
        re.DOTALL,
    )

    if not section_match:
        return mitigations

    section_content = section_match.group(1)

    # Find table rows - mitigation is typically the last column
    # Pattern: | Risk | Impact | Likelihood | Mitigation |
    # or: | Risk | Impact | Mitigation |
    table_pattern = re.compile(
        r"\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*([^|]+)\s*\|",
        re.MULTILINE,
    )

    for match in table_pattern.finditer(section_content):
        mitigation = match.group(1).strip()
        # Skip header rows and separators
        if mitigation and mitigation.lower() not in ("mitigation", "---", "-"):
            if "---" not in mitigation:
                mitigations.append(mitigation)

    return mitigations


def extract_function_names(lld_content: str) -> list[str]:
    """Parse Section 2.4 to extract function/method names.

    Args:
        lld_content: The LLD markdown content.

    Returns:
        List of function names found in code blocks.
    """
    functions = []

    # Find Section 2.4
    section_match = re.search(
        r"###\s*2\.4[^\n]*\n(.*?)(?=###|\Z)",
        lld_content,
        re.DOTALL,
    )

    if not section_match:
        return functions

    section_content = section_match.group(1)

    # Find function definitions in code blocks
    # Pattern: def function_name( or async def function_name(
    func_pattern = re.compile(r"(?:async\s+)?def\s+(\w+)\s*\(")

    for match in func_pattern.finditer(section_content):
        functions.append(match.group(1))

    return functions


def extract_keywords(text: str) -> list[str]:
    """Extract significant keywords from mitigation text.

    Args:
        text: Text to extract keywords from.

    Returns:
        List of lowercase keywords with stopwords filtered.
    """
    if not text:
        return []

    # Tokenize: split on non-alphanumeric
    tokens = re.findall(r"\w+", text.lower())

    # Filter stopwords and short tokens
    keywords = [t for t in tokens if t not in STOPWORDS and len(t) > 2]

    return keywords


def trace_mitigations_to_functions(
    mitigations: list[str],
    functions: list[str],
) -> list[ValidationError]:
    """Check that each mitigation has at least one related function.

    Issue #312: Smart filtering to reduce false positives for approach-style mitigations.

    Args:
        mitigations: List of mitigation text strings.
        functions: List of function names.

    Returns:
        List of WARNINGs for untraced mitigations (filtered by approach detection).
    """
    warnings = []

    # Normalize function names for matching
    normalized_functions = [f.lower() for f in functions]

    for mitigation in mitigations:
        keywords = extract_keywords(mitigation)

        # Check if any keyword matches any function name (substring match)
        matched_functions = []
        for keyword in keywords:
            for func in normalized_functions:
                if keyword in func or func in keyword:
                    matched_functions.append(func)

        # Issue #312: Use smart filtering to decide whether to warn
        if not matched_functions:
            # No function match - check if we should warn
            if should_warn_missing_function(mitigation, matched_functions):
                warnings.append(
                    ValidationError(
                        severity=ValidationSeverity.WARNING,
                        section="11",
                        message=f"Risk mitigation has no matching function: '{mitigation[:50]}...'",
                    )
                )
            else:
                # Check if it's approach-style and log for debugging
                is_approach, matched_patterns = is_approach_mitigation(mitigation)
                if is_approach:
                    log_skipped_mitigation(mitigation, matched_patterns)
                else:
                    # Plain description - also log at DEBUG
                    logger.debug(
                        f"Skipped plain description mitigation: '{mitigation[:80]}...'"
                    )

    return warnings


# =============================================================================
# Issue #600: AST Import Sentinel Integration
# =============================================================================


def run_ast_sentinel_on_modify_files(
    files: list[dict],
    repo_root: Path,
) -> list[ValidationError]:
    """Run AST-based import sentinel on existing Python files marked Modify.

    Issue #600: Catches missing imports in files that already exist on disk.
    Only runs on .py files with change_type "Modify" (files that must exist).
    Returns warnings (not errors) since sentinel findings are advisory and
    should not block the LLD workflow.

    Args:
        files: List of file dicts with path and change_type.
        repo_root: Path to repository root.

    Returns:
        List of WARNING-severity ValidationErrors for sentinel findings.
    """
    warnings: list[ValidationError] = []

    for file_info in files:
        # Only check existing Python files marked Modify
        if file_info.get("change_type") != "Modify":
            continue

        path = file_info["path"]
        if not path.endswith(".py"):
            continue

        full_path = repo_root / path
        if not full_path.exists():
            # validate_file_paths already handles missing Modify files
            continue

        try:
            result = ast_analyze_file(full_path)
        except Exception as e:
            logger.debug(f"AST sentinel failed on {path}: {e}")
            continue

        if not result.ok:
            for err in result.errors:
                warnings.append(
                    ValidationError(
                        severity=ValidationSeverity.WARNING,
                        section="2.1",
                        message=(
                            f"AST sentinel: {path} line {err.line} — "
                            f"symbol '{err.name}' may not be imported"
                        ),
                        file_path=path,
                    )
                )

    return warnings


# =============================================================================
# Main Validation Node
# =============================================================================


def validate_lld_mechanical(state: Dict[str, Any]) -> Dict[str, Any]:
    """Mechanical validation of LLD content.

    Issue #277: Validates LLD structure and paths without LLM calls.
    Fails hard on errors, warns on suspicious patterns.

    Issue #294: Returns only state updates (not full state) for proper
    LangGraph merge behavior, ensuring validation_errors persist.

    Issue #306: Validates LLD title issue number matches workflow issue number.

    Issue #312: Smart filtering for approach-style mitigations to reduce
    false positive warnings.

    Issue #322: Explicit check for invalid/missing repo_root, returning
    blocking error instead of silent skip.

    Issue #334: Normalize change types with parenthetical suffixes and
    save validation errors to lineage for audit trail.

    Issue #600: Run AST-based import sentinel on existing Python files
    to catch missing imports early (warnings only).

    Args:
        state: Workflow state with current_draft and target_repo.

    Returns:
        Dict of state updates (validation_errors, validation_warnings, etc.)
    """
    lld_content = state.get("current_draft", "")
    target_repo = state.get("target_repo", "")
    issue_number = state.get("issue_number")
    lineage_path = state.get("lineage_path")
    draft_number = state.get("draft_number", 1)

    # Handle empty draft
    if not lld_content or not lld_content.strip():
        error_messages = ["LLD content is empty"]
        
        # Issue #334: Save errors to lineage if path provided
        if lineage_path:
            try:
                save_validation_errors_to_lineage(error_messages, Path(lineage_path), draft_number)
            except Exception as e:
                logger.warning(f"Failed to save validation errors to lineage: {e}")
        
        # Issue #334: Print errors to console
        print_validation_errors(error_messages)
        
        return {
            "validation_errors": error_messages,
            "validation_warnings": [],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n  - LLD content is empty",
        }

    # Issue #322: Get repo root for path validation with explicit validation
    # Convert to Path if non-empty, otherwise None
    if target_repo and str(target_repo).strip():
        repo_root = Path(target_repo)
    else:
        repo_root = None

    all_errors: list[ValidationError] = []
    all_warnings: list[ValidationError] = []

    # Step 1: Validate mandatory sections (fail fast)
    section_errors = validate_mandatory_sections(lld_content)
    if section_errors:
        all_errors.extend(section_errors)
        # Fail fast on missing sections - can't validate further
        error_messages = [e.message for e in all_errors]
        
        # Issue #334: Save errors to lineage
        if lineage_path:
            try:
                save_validation_errors_to_lineage(error_messages, Path(lineage_path), draft_number)
            except Exception as e:
                logger.warning(f"Failed to save validation errors to lineage: {e}")
        
        # Issue #334: Print errors to console
        print_validation_errors(error_messages)
        
        return {
            "validation_errors": error_messages,
            "validation_warnings": [],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n" + "\n".join(
                f"  - {msg}" for msg in error_messages
            ),
        }

    # Step 2: Validate title issue number (Issue #306)
    if issue_number is not None:
        title_errors = validate_title_issue_number(lld_content, issue_number)
        for error in title_errors:
            if error.severity == ValidationSeverity.ERROR:
                all_errors.append(error)
            else:
                all_warnings.append(error)

    # Step 3: Parse Section 2.1 Files Changed table (now with normalization)
    files, parse_errors = parse_files_changed_table(lld_content)
    all_errors.extend(parse_errors)

    if parse_errors:
        # Can't continue validation without file list
        error_messages = [e.message for e in all_errors]
        
        # Issue #334: Save errors to lineage
        if lineage_path:
            try:
                save_validation_errors_to_lineage(error_messages, Path(lineage_path), draft_number)
            except Exception as e:
                logger.warning(f"Failed to save validation errors to lineage: {e}")
        
        # Issue #334: Print errors to console
        print_validation_errors(error_messages)
        
        return {
            "validation_errors": error_messages,
            "validation_warnings": [],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n" + "\n".join(
                f"  - {msg}" for msg in error_messages
            ),
        }

    # Step 3.5: Issue #334 - Validate directory creation order
    order_errors = validate_directory_creation_order(files)
    for error_msg in order_errors:
        all_errors.append(
            ValidationError(
                severity=ValidationSeverity.ERROR,
                section="2.1",
                message=error_msg,
            )
        )

    # Step 4: Issue #322 - Validate file paths with explicit repo_root check
    # This replaces the old silent skip behavior
    path_errors, path_validation_ran = validate_file_paths_with_repo_check(files, repo_root)
    all_errors.extend(path_errors)

    # If repo_root validation failed, we have a blocking error - return early
    if not path_validation_ran and path_errors:
        error_messages = [e.message for e in all_errors]
        
        # Issue #334: Save errors to lineage
        if lineage_path:
            try:
                save_validation_errors_to_lineage(error_messages, Path(lineage_path), draft_number)
            except Exception as e:
                logger.warning(f"Failed to save validation errors to lineage: {e}")
        
        # Issue #334: Print errors to console
        print_validation_errors(error_messages)
        
        return {
            "validation_errors": error_messages,
            "validation_warnings": [],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n" + "\n".join(
                f"  - {msg}" for msg in error_messages
            ),
        }

    # Step 5: Detect placeholder prefixes (only if repo_root is valid)
    if path_validation_ran and repo_root:
        placeholder_errors = detect_placeholder_prefixes(files, repo_root)
        all_errors.extend(placeholder_errors)

    # Step 6: Cross-reference DoD with Files Changed
    xref_errors = cross_reference_sections(lld_content, files)
    all_errors.extend(xref_errors)

    # Step 7: Trace risk mitigations (warnings only, with Issue #312 smart filtering)
    mitigations = extract_mitigations_from_risks(lld_content)
    functions = extract_function_names(lld_content)
    mitigation_warnings = trace_mitigations_to_functions(mitigations, functions)
    all_warnings.extend(mitigation_warnings)

    # Step 8: Issue #600 - Run AST sentinel on existing Modify Python files
    if path_validation_ran and repo_root:
        sentinel_warnings = run_ast_sentinel_on_modify_files(files, repo_root)
        all_warnings.extend(sentinel_warnings)

    # Aggregate results
    error_messages = [e.message for e in all_errors]
    warning_messages = [w.message for w in all_warnings]

    if all_errors:
        # Issue #334: Save errors to lineage
        if lineage_path:
            try:
                save_validation_errors_to_lineage(error_messages, Path(lineage_path), draft_number)
            except Exception as e:
                logger.warning(f"Failed to save validation errors to lineage: {e}")
        
        # Issue #334: Print errors to console
        print_validation_errors(error_messages)
        
        return {
            "validation_errors": error_messages,
            "validation_warnings": warning_messages,
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n" + "\n".join(
                f"  - {msg}" for msg in error_messages
            ),
        }

    # Log warnings but don't block
    if warning_messages:
        print("MECHANICAL VALIDATION WARNINGS:")
        for msg in warning_messages:
            print(f"  - {msg}")

    # Validation passed - return updates without error
    # Issue #302: Explicitly set lld_status to clear any previous BLOCKED status
    # (e.g., from a Gemini verdict). This prevents the router from thinking
    # validation failed when it actually passed.
    return {
        "validation_errors": [],
        "validation_warnings": warning_messages,
        "lld_status": "PENDING",  # Clear BLOCKED status from previous Gemini verdicts
        "error_message": "",
    }
```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-608\tests\unit\test_ast_sentinel.py
"""Unit tests for AST Sentinel logic (Issue #600)."""

from __future__ import annotations

import sys
import textwrap
from io import StringIO
from unittest.mock import patch
from pathlib import Path

import pytest

from assemblyzero.utils.ast_sentinel import (
    SentinelError,
    SentinelResult,
    SymbolSentinel,
    analyze_file,
    analyze_source,
    main,
)

def _analyze(code: str) -> SentinelResult:
    return analyze_source(textwrap.dedent(code))

def _error_names(result: SentinelResult) -> list[str]:
    return [e.name for e in result.errors]

class TestHappyPath:
    def test_010_import_and_use(self):
        result = _analyze("""\
            import os
            os.path.join("a", "b")
        """)
        assert result.ok

    def test_010_from_import(self):
        result = _analyze("""\
            from os.path import join
            join("a", "b")
        """)
        assert result.ok

    def test_010_aliased_import(self):
        result = _analyze("""\
            import numpy as np
            np.array([1, 2, 3])
        """)
        assert result.ok

class TestMissingImport:
    def test_020_missing_import(self):
        result = _analyze("json.dumps({})")
        assert not result.ok
        assert "json" in _error_names(result)

class TestLocalScope:
    def test_050_function_args(self):
        result = _analyze("""\
            def foo(a):
                return a
        """)
        assert result.ok

class TestComprehensions:
    def test_060_list_comp(self):
        result = _analyze("[x for x in [1,2]]")
        assert result.ok

class TestWalrus:
    def test_070_walrus(self):
        result = _analyze("if (x := 10): print(x)")
        assert result.ok

class TestStarImports:
    def test_080_star_import(self):
        result = _analyze("from typing import *")
        assert not result.ok
        assert "*" in _error_names(result)

class TestTypeChecking:
    def test_100_type_checking(self):
        result = _analyze("""\
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import os
            def foo():
                print(os.path)
        """)
        assert result.ok

class TestExtraCoverage:
    def test_async_function(self):
        result = _analyze("async def foo(x): return x")
        assert result.ok

    def test_function_annotations(self):
        result = _analyze("def foo(x: int) -> str: return str(x)")
        assert result.ok

    def test_match_statement(self):
        # Point and x are undefined
        result = _analyze("""\
            match x:
                case [1, y]: print(y)
                case Point(px, py): print(px)
        """)
        assert "x" in _error_names(result)
        assert "Point" in _error_names(result)

    def test_except_handler(self):
        result = _analyze("""\
            try: pass
            except Exception as e: print(e)
        """)
        assert result.ok

    def test_cli_main(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("print(undefined_var)", encoding="utf-8")
        assert main([str(f)]) == 1
        
        f2 = tmp_path / "good.py"
        f2.write_text("x = 1; print(x)", encoding="utf-8")
        assert main([str(f2)]) == 0

    def test_analyze_file_io_error(self):
        result = analyze_file("non_existent_file_999.py")
        assert not result.ok
        assert result.errors[0].name == "<io>"

    def test_syntax_error(self):
        result = _analyze("if x:")
        assert not result.ok
        assert result.errors[0].name == "<syntax>"
        
    def test_async_for_with(self):
        # y and ctx are undefined
        result = _analyze("""\
            async def foo():
                async for x in y: pass
                async with ctx as z: pass
        """)
        assert "y" in _error_names(result)
        assert "ctx" in _error_names(result)

    def test_global_nonlocal(self):
        result = _analyze("""\
            x = 1
            def foo():
                global x
                print(x)
        """)
        assert result.ok



```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### assemblyzero/utils/ast_sentinel.py (signatures)

```python
"""AST-based Import Sentinel for detecting lingering symbols.

Issue #600: Detect missing imports and undefined variables before execution
using static AST analysis.

Provides:
- SymbolSentinel: AST NodeVisitor that tracks scopes and detects undefined names.
- SentinelError: Structured error for undefined symbol usage.
- analyze_source: Analyze a source string for undefined symbols.
- analyze_file: Analyze a file path for undefined symbols.
"""

from __future__ import annotations

import ast

import builtins

import logging

import sys

from dataclasses import dataclass, field

from pathlib import Path

from typing import TYPE_CHECKING

class SentinelError:

    """A single undefined-symbol error found by the sentinel."""

    def __str__(self) -> str:
    ...

class SentinelResult:

    """Result of analyzing a source file."""

    def ok(self) -> bool:
    ...

    def format_errors(self) -> str:
    """Format all errors for stderr output."""
    ...

class SymbolSentinel(ast.NodeVisitor):

    """AST visitor that tracks symbol definitions across scopes.

Maintains a scope stack to detect uses of undefined names."""

    def __init__(self, source_lines: list[str] | None = None) -> None:
    ...

    def _current_scope(self) -> set[str]:
    ...

    def _define(self, name: str) -> None:
    """Register a name in the current scope."""
    ...

    def _is_defined(self, name: str) -> bool:
    """Check if a name is defined in any enclosing scope, builtins, or implicit globals."""
    ...

    def _push_scope(self) -> None:
    ...

    def _pop_scope(self) -> None:
    ...

    def _is_disabled(self, line: int) -> bool:
    """Check if a line has a sentinel: disable-line comment."""
    ...

    def visit_Import(self, node: ast.Import) -> None:
    ...

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
    ...

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
    ...

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
    ...

    def _visit_function_body(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
    """Push scope, register args, visit body, pop scope."""
    ...

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
    ...

    def _visit_comprehension(self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp) -> None:
    """Handle comprehensions with their own scope."""
    ...

    def visit_ListComp(self, node: ast.ListComp) -> None:
    ...

    def visit_SetComp(self, node: ast.SetComp) -> None:
    ...

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
    ...

    def visit_DictComp(self, node: ast.DictComp) -> None:
    ...

    def _visit_target(self, target: ast.AST) -> None:
    """Register names from assignment targets (handles tuples, stars, etc.)."""
    ...

    def visit_Assign(self, node: ast.Assign) -> None:
    ...

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
    ...

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
    ...

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
    """Walrus operator := defines in enclosing scope."""
    ...

    def visit_Global(self, node: ast.Global) -> None:
    ...

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
    ...

    def visit_For(self, node: ast.For) -> None:
    ...

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
    ...

    def visit_With(self, node: ast.With) -> None:
    ...

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
    ...

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
    ...

    def visit_If(self, node: ast.If) -> None:
    """Handle if TYPE_CHECKING blocks."""
    ...

    def _is_type_checking_guard(self, test: ast.AST) -> bool:
    """Check if a test node is `TYPE_CHECKING`."""
    ...

    def visit_Name(self, node: ast.Name) -> None:
    ...

    def visit_Attribute(self, node: ast.Attribute) -> None:
    """Visit attribute access — only check the root object."""
    ...

    def visit_Match(self, node: ast.Match) -> None:
    ...

    def _visit_pattern(self, pattern: ast.AST) -> None:
    """Register names from match patterns."""
    ...

def analyze_source(source: str, filename: str = "<string>") -> SentinelResult:
    """Analyze a source string for undefined symbols.

Args:"""
    ...

def analyze_file(path: str | Path) -> SentinelResult:
    """Analyze a file for undefined symbols.

Args:"""
    ...

def main(argv: list[str] | None = None) -> int:
    """CLI entry point: analyze files and report errors to stderr.

Returns 1 if any errors found, 0 otherwise."""
    ...

logger = logging.getLogger(__name__)

DISABLE_COMMENT = "sentinel: disable-line"
```

### tests/unit/test_ast_sentinel.py (full)

```python
"""Unit tests for AST Sentinel logic (Issue #600)."""

from __future__ import annotations

import sys
import textwrap
from io import StringIO
from unittest.mock import patch
from pathlib import Path

import pytest

from assemblyzero.utils.ast_sentinel import (
    SentinelError,
    SentinelResult,
    SymbolSentinel,
    analyze_file,
    analyze_source,
    main,
)

def _analyze(code: str) -> SentinelResult:
    return analyze_source(textwrap.dedent(code))

def _error_names(result: SentinelResult) -> list[str]:
    return [e.name for e in result.errors]

class TestHappyPath:
    def test_010_import_and_use(self):
        result = _analyze("""\
            import os
            os.path.join("a", "b")
        """)
        assert result.ok

    def test_010_from_import(self):
        result = _analyze("""\
            from os.path import join
            join("a", "b")
        """)
        assert result.ok

    def test_010_aliased_import(self):
        result = _analyze("""\
            import numpy as np
            np.array([1, 2, 3])
        """)
        assert result.ok

class TestMissingImport:
    def test_020_missing_import(self):
        result = _analyze("json.dumps({})")
        assert not result.ok
        assert "json" in _error_names(result)

class TestLocalScope:
    def test_050_function_args(self):
        result = _analyze("""\
            def foo(a):
                return a
        """)
        assert result.ok

class TestComprehensions:
    def test_060_list_comp(self):
        result = _analyze("[x for x in [1,2]]")
        assert result.ok

class TestWalrus:
    def test_070_walrus(self):
        result = _analyze("if (x := 10): print(x)")
        assert result.ok

class TestStarImports:
    def test_080_star_import(self):
        result = _analyze("from typing import *")
        assert not result.ok
        assert "*" in _error_names(result)

class TestTypeChecking:
    def test_100_type_checking(self):
        result = _analyze("""\
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import os
            def foo():
                print(os.path)
        """)
        assert result.ok

class TestExtraCoverage:
    def test_async_function(self):
        result = _analyze("async def foo(x): return x")
        assert result.ok

    def test_function_annotations(self):
        result = _analyze("def foo(x: int) -> str: return str(x)")
        assert result.ok

    def test_match_statement(self):
        # Point and x are undefined
        result = _analyze("""\
            match x:
                case [1, y]: print(y)
                case Point(px, py): print(px)
        """)
        assert "x" in _error_names(result)
        assert "Point" in _error_names(result)

    def test_except_handler(self):
        result = _analyze("""\
            try: pass
            except Exception as e: print(e)
        """)
        assert result.ok

    def test_cli_main(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("print(undefined_var)", encoding="utf-8")
        assert main([str(f)]) == 1
        
        f2 = tmp_path / "good.py"
        f2.write_text("x = 1; print(x)", encoding="utf-8")
        assert main([str(f2)]) == 0

    def test_analyze_file_io_error(self):
        result = analyze_file("non_existent_file_999.py")
        assert not result.ok
        assert result.errors[0].name == "<io>"

    def test_syntax_error(self):
        result = _analyze("if x:")
        assert not result.ok
        assert result.errors[0].name == "<syntax>"
        
    def test_async_for_with(self):
        # y and ctx are undefined
        result = _analyze("""\
            async def foo():
                async for x in y: pass
                async with ctx as z: pass
        """)
        assert "y" in _error_names(result)
        assert "ctx" in _error_names(result)

    def test_global_nonlocal(self):
        result = _analyze("""\
            x = 1
            def foo():
                global x
                print(x)
        """)
        assert result.ok

```

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero-608
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 18 items

tests/unit/test_ast_sentinel.py::TestHappyPath::test_010_import_and_use PASSED [  5%]
tests/unit/test_ast_sentinel.py::TestHappyPath::test_010_from_import PASSED [ 11%]
tests/unit/test_ast_sentinel.py::TestHappyPath::test_010_aliased_import PASSED [ 16%]
tests/unit/test_ast_sentinel.py::TestMissingImport::test_020_missing_import PASSED [ 22%]
tests/unit/test_ast_sentinel.py::TestLocalScope::test_050_function_args PASSED [ 27%]
tests/unit/test_ast_sentinel.py::TestComprehensions::test_060_list_comp PASSED [ 33%]
tests/unit/test_ast_sentinel.py::TestWalrus::test_070_walrus PASSED      [ 38%]
tests/unit/test_ast_sentinel.py::TestStarImports::test_080_star_import PASSED [ 44%]
tests/unit/test_ast_sentinel.py::TestTypeChecking::test_100_type_checking PASSED [ 50%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_async_function PASSED [ 55%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_function_annotations PASSED [ 61%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_match_statement PASSED [ 66%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_except_handler PASSED [ 72%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_cli_main PASSED [ 77%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_analyze_file_io_error PASSED [ 83%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_syntax_error PASSED [ 88%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_async_for_with PASSED [ 94%]
tests/unit/test_ast_sentinel.py::TestExtraCoverage::test_global_nonlocal PASSED [100%]
ERROR: Coverage failure: total of 76 is less than fail-under=95


============================== warnings summary ===============================
tests/unit/test_ast_sentinel.py::TestHappyPath::test_010_import_and_use
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\google\genai\types.py:43: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

tests/unit/test_ast_sentinel.py::TestHappyPath::test_010_import_and_use
  C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Lib\site-packages\langchain_core\_api\deprecation.py:25: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
    from pydantic.v1.fields import FieldInfo as FieldInfoV1

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                 Stmts   Miss  Cover   Missing
------------------------------------------------------------------
assemblyzero\utils\ast_sentinel.py     317     76    76%   122, 130-135, 170, 174, 176-177, 183, 185, 200, 202, 213-225, 241, 247, 251-252, 262, 265, 268, 276-280, 290-294, 297-298, 315-317, 322-327, 335, 340-345, 383, 390, 397-398, 400, 424, 433, 437-442, 447-448, 454, 456-457, 532
------------------------------------------------------------------
TOTAL                                  317     76    76%
FAIL Required test coverage of 95% not reached. Total coverage: 76.03%
======================= 18 passed, 2 warnings in 1.07s ========================


```

Read the error messages carefully and fix the root cause in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
