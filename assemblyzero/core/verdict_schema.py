"""Structured verdict schema for Gemini reviewer responses.

Issue #492: Structured output for verdicts.
Issue #503: Structured two-strike stagnation detection.

Provides a JSON schema that Gemini's response_schema parameter can enforce,
replacing fragile regex-based verdict parsing with structured JSON output.
"""

from difflib import SequenceMatcher

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["APPROVED", "REVISE", "BLOCKED"],
        },
        "summary": {
            "type": "string",
        },
        "blocking_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "issue": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["BLOCKING", "HIGH", "SUGGESTION"],
                    },
                },
                "required": ["section", "issue", "severity"],
            },
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["verdict", "summary"],
}


def parse_structured_verdict(response_text: str) -> dict | None:
    """Parse a structured JSON verdict from reviewer response.

    Attempts to parse the response as JSON matching VERDICT_SCHEMA.
    Returns None if parsing fails (caller should fall back to regex).

    Args:
        response_text: Raw response text from the reviewer.

    Returns:
        Parsed verdict dict with keys: verdict, summary, blocking_issues,
        suggestions. Returns None if response is not valid JSON or
        doesn't contain required fields.
    """
    import json

    if not response_text or not response_text.strip():
        return None

    text = response_text.strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "verdict" in data and "summary" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code fences
    import re

    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict) and "verdict" in data and "summary" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None


def same_blocking_issues(
    current_feedback: str,
    previous_feedback: str,
    similarity_threshold: float = 0.8,
) -> bool:
    """Check if two verdicts raise the same blocking issues.

    Issue #503: Structured two-strike stagnation detection.

    Strategy:
    1. Try structured JSON comparison first (section + issue identity)
    2. Fall back to line-overlap heuristic if either verdict is unstructured

    Args:
        current_feedback: Current verdict text (may be JSON or markdown).
        previous_feedback: Previous verdict text (may be JSON or markdown).
        similarity_threshold: SequenceMatcher ratio for fuzzy match (default 0.8).

    Returns:
        True if the same blocking issues appear in both verdicts (stagnation).
    """
    if not current_feedback or not previous_feedback:
        return False

    current_parsed = parse_structured_verdict(current_feedback)
    previous_parsed = parse_structured_verdict(previous_feedback)

    # Both structured: use section+issue identity comparison
    if current_parsed and previous_parsed:
        return _structured_stagnation(
            current_parsed, previous_parsed, similarity_threshold
        )

    # Fallback: line-overlap heuristic (legacy)
    return _line_overlap_stagnation(current_feedback, previous_feedback)


def _structured_stagnation(
    current: dict, previous: dict, threshold: float
) -> bool:
    """Compare blocking issues structurally.

    Two verdicts are stagnant if >50% of current blocking issues
    match a previous issue by section + fuzzy issue text similarity.
    """
    current_issues = current.get("blocking_issues", [])
    previous_issues = previous.get("blocking_issues", [])

    if not current_issues:
        return False

    matched = 0
    for c_issue in current_issues:
        c_section = c_issue.get("section", "").lower().strip()
        c_text = c_issue.get("issue", "").lower().strip()

        for p_issue in previous_issues:
            p_section = p_issue.get("section", "").lower().strip()
            p_text = p_issue.get("issue", "").lower().strip()

            section_match = (
                c_section == p_section
                or SequenceMatcher(None, c_section, p_section).ratio() >= threshold
            )
            text_match = SequenceMatcher(None, c_text, p_text).ratio() >= threshold

            if section_match and text_match:
                matched += 1
                break

    return matched / len(current_issues) > 0.5


def _line_overlap_stagnation(current: str, previous: str) -> bool:
    """Legacy line-overlap heuristic for unstructured verdicts.

    Issue #486: Original two-strike detection.
    """
    current_lines = {
        line.strip().lower()
        for line in current.splitlines()
        if line.strip() and len(line.strip()) > 10
    }
    previous_lines = {
        line.strip().lower()
        for line in previous.splitlines()
        if line.strip() and len(line.strip()) > 10
    }

    if not current_lines:
        return False

    overlap = current_lines & previous_lines
    return len(overlap) / len(current_lines) > 0.5
