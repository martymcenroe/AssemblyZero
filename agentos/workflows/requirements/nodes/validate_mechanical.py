"""Mechanical LLD validation node.

Issue #277: Add mechanical validation to catch path errors and section
inconsistencies before Gemini review.

Issue #306: Add title issue number validation to detect mismatches before
human or Gemini review.

Issue #312: Add pattern detection for function references vs approach mitigations
to reduce false positive warnings.

Issue #322: Add explicit check for invalid/missing repo_root, returning blocking
error instead of silent skip.

This node validates LLD content deterministically without LLM calls:
- Mandatory sections exist (2.1, 11, 12)
- File paths are valid (Modify/Delete exist, Add parents exist)
- No placeholder prefixes (src/, lib/, app/) unless they exist
- Definition of Done matches Files Changed
- Risk mitigations trace to functions (warning only, with smart filtering)
- LLD title issue number matches workflow issue number
- Target repo validation (None, empty, non-existent paths are blocking errors)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.state import RequirementsWorkflowState

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

    Args:
        lld_content: The LLD markdown content.

    Returns:
        Tuple of (list of file dicts with path/change_type/description, parse errors).
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
    table_pattern = re.compile(
        r"\|\s*`?([^`|]+?)`?\s*\|\s*(\w+)\s*\|\s*([^|]*)\s*\|",
        re.MULTILINE,
    )

    matches = list(table_pattern.finditer(section_content))

    # Valid change types we expect
    valid_change_types = {"add", "modify", "delete", "create", "update", "remove"}

    # Filter out header rows and invalid entries
    data_rows = []
    for match in matches:
        path = match.group(1).strip()
        change_type = match.group(2).strip()

        # Skip header rows - check for common header text
        path_lower = path.lower()
        change_type_lower = change_type.lower()

        if path_lower in ("file", "---", "-") or "---" in path:
            continue
        if change_type_lower in ("change type", "change", "type", "---", "-"):
            continue

        # Only accept valid change types
        if change_type_lower not in valid_change_types:
            continue

        # Path must look like a file path (contain / or . )
        if "/" not in path and "." not in path and "\\" not in path:
            continue

        data_rows.append(match)

    if not data_rows:
        errors.append(
            ValidationError(
                severity=ValidationSeverity.ERROR,
                section="2.1",
                message="Section 2.1 table malformed or empty - no file entries found",
            )
        )
        return files, errors

    for match in data_rows:
        path = match.group(1).strip()
        change_type = match.group(2).strip()
        description = match.group(3).strip()

        files.append({
            "path": path,
            "change_type": change_type,
            "description": description,
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
    search_dirs = ["tools", "agentos", "scripts", "src", "lib", "tests"]

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

    Args:
        files: List of file dicts with path and change_type.
        repo_root: Path to repository root.

    Returns:
        List of ERRORs for invalid paths.
    """
    errors = []

    for file_info in files:
        path = file_info["path"]
        change_type = file_info["change_type"]
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
            parent_dir = full_path.parent
            if not parent_dir.exists():
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

    Args:
        state: Workflow state with current_draft and target_repo.

    Returns:
        Dict of state updates (validation_errors, validation_warnings, etc.)
    """
    lld_content = state.get("current_draft", "")
    target_repo = state.get("target_repo", "")
    issue_number = state.get("issue_number")

    # Handle empty draft
    if not lld_content or not lld_content.strip():
        return {
            "validation_errors": ["LLD content is empty"],
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

    # Step 3: Parse Section 2.1 Files Changed table
    files, parse_errors = parse_files_changed_table(lld_content)
    all_errors.extend(parse_errors)

    if parse_errors:
        # Can't continue validation without file list
        error_messages = [e.message for e in all_errors]
        return {
            "validation_errors": error_messages,
            "validation_warnings": [],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n" + "\n".join(
                f"  - {msg}" for msg in error_messages
            ),
        }

    # Step 4: Issue #322 - Validate file paths with explicit repo_root check
    # This replaces the old silent skip behavior
    path_errors, path_validation_ran = validate_file_paths_with_repo_check(files, repo_root)
    all_errors.extend(path_errors)

    # If repo_root validation failed, we have a blocking error - return early
    if not path_validation_ran and path_errors:
        error_messages = [e.message for e in all_errors]
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

    # Aggregate results
    error_messages = [e.message for e in all_errors]
    warning_messages = [w.message for w in all_warnings]

    if all_errors:
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