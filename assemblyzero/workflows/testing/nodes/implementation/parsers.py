"""Parsing and validation utilities for code generation responses.

Mechanical validation — no LLM judgment.
"""

import ast
import re

from assemblyzero.telemetry import emit
from assemblyzero.utils.file_type import get_language_tag


def extract_code_block(response: str, file_path: str = "") -> str | None:
    """Extract code block content from response.

    Issue #447: File-type-aware extraction. Prefers blocks matching the
    expected language tag, falls back to any fenced block.

    Args:
        response: Claude's raw response text.
        file_path: File path to determine expected language tag.
            Empty string accepts any fenced block (backward compat).

    Returns:
        The content of the best-matching code block, or None if no valid block found.
        Does NOT trust any file path Claude puts in the response.
    """
    # Issue #310: Use greedy line-anchored pattern to handle nested code blocks correctly.
    # Captures (language_tag, content) pairs.
    pattern = re.compile(r"^```(\w*)\s*\n(.*)^```", re.DOTALL | re.MULTILINE)

    expected_tag = get_language_tag(file_path) if file_path else ""
    best_match: str | None = None
    fallback_match: str | None = None

    for match in pattern.finditer(response):
        tag = match.group(1).lower()
        content = match.group(2).strip()

        # Skip empty blocks
        if not content:
            continue

        # If first line is a # File: comment, strip it (we don't trust it)
        lines = content.split("\n")
        if lines[0].strip().startswith("# File:"):
            content = "\n".join(lines[1:]).strip()

        # Must have actual content
        if not content:
            continue

        # Prefer block matching expected tag
        if expected_tag and tag == expected_tag and best_match is None:
            best_match = content
        elif fallback_match is None:
            fallback_match = content

    return best_match or fallback_match


def validate_code_response(code: str, filepath: str, existing_content: str = "") -> tuple[bool, str]:
    """Mechanically validate code. No LLM judgment.

    Returns (valid, error_message).
    """
    if not code:
        return False, "Code is empty"

    if not code.strip():
        return False, "Code is only whitespace"

    # Minimum line threshold (5 lines for non-trivial files)
    lines = code.strip().split("\n")
    if len(lines) < 5:
        # Issue #473: allow short files for __init__.py, fixtures, configs, data
        short_ok = (
            filepath.endswith("__init__.py")
            or "/fixtures/" in filepath.replace("\\", "/")
            or filepath.endswith((".json", ".yaml", ".yml", ".toml", ".txt", ".csv"))
        )
        if not short_ok and len(lines) < 2:
            return False, f"Code too short ({len(lines)} lines)"

    # Issue #587: Mechanical File Size Safety Gate
    if existing_content:
        existing_lines = existing_content.strip().split("\n")
        # Only apply check if existing file is non-trivial (>10 lines)
        if len(existing_lines) > 10:
            new_lines = len(lines)
            if new_lines < len(existing_lines) * 0.5:
                emit("quality.gate_rejected", repo="", metadata={"filepath": filepath, "type": "size_gate", "error": "drastic_shrink"})
                return False, f"Mechanical Size Gate: File shrank drastically from {len(existing_lines)} lines to {new_lines} lines. You must output the ENTIRE file without using placeholders."

    # Python syntax validation
    if filepath.endswith(".py"):
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"Python syntax error: {e}"

    return True, ""


def detect_summary_response(response: str) -> bool:
    """Detect if Claude gave a summary instead of code.

    Fast rejection before trying to parse.
    """
    blacklist = [
        "here's a summary",
        "here is a summary",
        "i've created",
        "i have created",
        "i've implemented",
        "i have implemented",
        "summary of",
        "the following files",
    ]

    response_lower = response.lower()[:500]  # Only check start

    for phrase in blacklist:
        if phrase in response_lower:
            # Check if there's also a code block (might be legit)
            if "```" not in response[:1000]:
                return True

    return False


def detect_truncation(response: object) -> bool:
    """Detect if response was truncated due to max_tokens.

    Issue #324: Check stop_reason to detect truncation.

    Args:
        response: Claude API response object with stop_reason attribute.

    Returns:
        True if response was truncated.
    """
    stop_reason = getattr(response, "stop_reason", None)
    return stop_reason == "max_tokens"


def parse_diff_response(response: str) -> dict:
    """Parse FIND/REPLACE diff response from Claude.

    Issue #324: Extract change blocks from diff-format response.

    Args:
        response: Claude's response with FIND/REPLACE blocks.

    Returns:
        Dict with keys:
        - success: bool
        - error: str | None
        - changes: list[dict] with keys: description, find_block, replace_block
    """
    changes = []

    # Pattern to match FIND/REPLACE blocks
    # FIND: ```...``` REPLACE WITH: ```...```
    find_replace_pattern = re.compile(
        r"FIND:\s*```\w*\s*\n(.*?)```\s*\n+REPLACE\s+WITH:\s*```\w*\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE
    )

    # Split response into change sections
    sections = re.split(r"(###\s*CHANGE\s*\d+\s*:)", response, flags=re.IGNORECASE)

    # Process pairs: (header_marker, content)
    i = 1  # Skip text before first CHANGE
    while i < len(sections) - 1:
        content = sections[i + 1] if i + 1 < len(sections) else ""

        # Extract description from the content (first line after header)
        desc_match = re.match(r"\s*(.+?)(?=\n)", content)
        description = desc_match.group(1).strip() if desc_match else "Unknown change"

        # Find the FIND/REPLACE block in this section
        fr_match = find_replace_pattern.search(content)

        if not fr_match:
            return {
                "success": False,
                "error": f"CHANGE missing REPLACE WITH section: {description[:50]}",
                "changes": [],
            }

        find_block = fr_match.group(1).strip()
        replace_block = fr_match.group(2).strip()

        changes.append({
            "description": description,
            "find_block": find_block,
            "replace_block": replace_block,
        })

        i += 2

    if not changes:
        return {
            "success": False,
            "error": "No FIND/REPLACE changes found in response",
            "changes": [],
        }

    return {
        "success": True,
        "error": None,
        "changes": changes,
    }


def apply_diff_changes(
    content: str,
    changes: list[dict],
) -> tuple[str, list[str]]:
    """Apply FIND/REPLACE changes to file content.

    Issue #324: Apply each change sequentially, with error detection.

    Args:
        content: Original file content.
        changes: List of change dicts with find_block/replace_block.

    Returns:
        Tuple of (modified_content, error_list).
    """
    errors = []
    result = content

    for change in changes:
        find_block = change.get("find_block", "")
        replace_block = change.get("replace_block", "")
        description = change.get("description", "")

        if not find_block:
            errors.append(f"Empty FIND block for change: {description}")
            continue

        # Count occurrences
        count = result.count(find_block)

        if count == 0:
            # Try whitespace-normalized matching
            normalized_result = _normalize_whitespace(result)
            normalized_find = _normalize_whitespace(find_block)

            if normalized_find in normalized_result:
                # Found with normalization - but we can't reliably replace
                # so we report a whitespace-specific error
                errors.append(
                    f"FIND block has whitespace mismatch for: {description[:50]}. "
                    f"Exact match not found but similar code exists."
                )
            else:
                errors.append(f"FIND block not found in file: {description[:50]}")
            continue

        if count > 1:
            errors.append(
                f"Ambiguous FIND block (matches {count} locations): {description[:50]}"
            )
            continue

        # Single match - safe to replace
        result = result.replace(find_block, replace_block, 1)

    return result, errors


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for fuzzy matching.

    Collapses multiple spaces and normalizes indentation.
    """
    # Replace tabs with spaces
    text = text.replace("\t", "    ")
    # Collapse multiple spaces (but preserve newlines)
    lines = text.split("\n")
    normalized_lines = []
    for line in lines:
        # Strip trailing whitespace, normalize internal spaces
        line = line.rstrip()
        normalized_lines.append(line)
    return "\n".join(normalized_lines)
