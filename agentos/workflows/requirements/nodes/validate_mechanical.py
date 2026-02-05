"""Mechanical LLD validation node.

Issue #277: Add mechanical validation to catch path errors and section
inconsistencies before Gemini review.

This node validates LLD content deterministically without LLM calls:
- Mandatory sections exist (2.1, 11, 12)
- File paths are valid (Modify/Delete exist, Add parents exist)
- No placeholder prefixes (src/, lib/, app/) unless they exist
- Definition of Done matches Files Changed
- Risk mitigations trace to functions (warning only)
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.state import RequirementsWorkflowState


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

    Args:
        mitigations: List of mitigation text strings.
        functions: List of function names.

    Returns:
        List of WARNINGs for untraced mitigations.
    """
    warnings = []

    # Normalize function names for matching
    normalized_functions = [f.lower() for f in functions]

    for mitigation in mitigations:
        keywords = extract_keywords(mitigation)

        # Check if any keyword matches any function name (substring match)
        found_match = False
        for keyword in keywords:
            for func in normalized_functions:
                if keyword in func or func in keyword:
                    found_match = True
                    break
            if found_match:
                break

        if not found_match and keywords:
            warnings.append(
                ValidationError(
                    severity=ValidationSeverity.WARNING,
                    section="11",
                    message=f"Risk mitigation has no matching function: '{mitigation[:50]}...'",
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

    Args:
        state: Workflow state with current_draft and target_repo.

    Returns:
        Dict of state updates (validation_errors, validation_warnings, etc.)
    """
    lld_content = state.get("current_draft", "")
    target_repo = state.get("target_repo", "")

    # Handle empty draft
    if not lld_content or not lld_content.strip():
        return {
            "validation_errors": ["LLD content is empty"],
            "validation_warnings": [],
            "lld_status": "BLOCKED",
            "error_message": "MECHANICAL VALIDATION FAILED:\n  - LLD content is empty",
        }

    # Get repo root for path validation
    repo_root = Path(target_repo) if target_repo else None

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

    # Step 2: Parse Section 2.1 Files Changed table
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

    # Step 3: Validate file paths (only if we have repo_root)
    if repo_root and repo_root.exists():
        path_errors = validate_file_paths(files, repo_root)
        all_errors.extend(path_errors)

        # Step 4: Detect placeholder prefixes
        placeholder_errors = detect_placeholder_prefixes(files, repo_root)
        all_errors.extend(placeholder_errors)

    # Step 5: Cross-reference DoD with Files Changed
    xref_errors = cross_reference_sections(lld_content, files)
    all_errors.extend(xref_errors)

    # Step 6: Trace risk mitigations (warnings only)
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
