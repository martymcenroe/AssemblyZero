"""Structured verdict schema for Gemini reviewer responses.

Issue #492: Structured output for verdicts.

Provides a JSON schema that Gemini's response_schema parameter can enforce,
replacing fragile regex-based verdict parsing with structured JSON output.
"""

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
