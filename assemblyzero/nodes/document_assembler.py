"""Mechanical document assembly utilities.

Issue #607: Mechanical Document Assembly Node
"""
import re

class AssemblyError(Exception):
    """Raised when document assembly fails critical constraints."""
    pass

def strip_hallucinated_headers(content: str, expected_header: str) -> str:
    """
    Removes hallucinated markdown headers from LLM output.
    Handles extra whitespace, multiple # signs, and bold asterisks.
    """
    if not content or not expected_header:
        return content

    # Clean the expected header of any markdown for the regex matching base
    clean_expected = re.sub(r'^#+\s*', '', expected_header).replace('*', '').strip()
    
    # Regex breakdown:
    # ^\s*                - Leading whitespace
    # #*                  - Optional markdown hash symbols
    # \s*                 - Optional whitespace
    # (?:\*\*)?           - Optional bold markdown
    # {clean_expected}    - The actual text (escaped)
    # (?:\*\*)?           - Optional trailing bold markdown
    # \s*                 - Optional trailing whitespace
    # \n*                 - Any trailing newlines
    escaped_text = re.escape(clean_expected)
    pattern = re.compile(
        rf"^\s*#*\s*(?:\*\*)?{escaped_text}(?:\*\*)?\s*\n*",
        re.IGNORECASE
    )
    
    # Strip from the beginning of the string
    cleaned = re.sub(pattern, '', content.lstrip())
    return cleaned.strip()

def assemble_final_document(completed_sections: list[dict]) -> str:
    """Mechanically concatenates headers and cleaned contents."""
    parts = []
    for sec in completed_sections:
        parts.append(f"{sec['header']}\n\n{sec['content']}")
    return "\n\n".join(parts) + "\n"