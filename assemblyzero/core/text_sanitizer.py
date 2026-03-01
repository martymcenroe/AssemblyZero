"""Text sanitizer for LLM output — strip emojis that crash Windows cp1252.

Issue #527: Strip emoji from all LLM output.

Windows cp1252 encoding can't handle Unicode emojis (U+1F000+), causing
crashes in CLI output and read_text(). This module provides a single
function to sanitize LLM responses before they reach downstream code.
"""

import re

# Semantic replacements: preserve meaning before stripping
_SEMANTIC_MAP: list[tuple[str, str]] = [
    # Checkmarks / success
    ("\u2705", "[PASS]"),   # white heavy check mark
    ("\u2714", "[PASS]"),   # heavy check mark
    ("\u2611", "[PASS]"),   # ballot box with check
    # Crosses / failure
    ("\u274C", "[FAIL]"),   # cross mark
    ("\u274E", "[FAIL]"),   # cross mark with negative squared
    ("\u2716", "[FAIL]"),   # heavy multiplication x
    ("\u2718", "[FAIL]"),   # heavy ballot x
    # Warnings
    ("\u26A0", "[WARN]"),   # warning sign
    ("\u26A0\uFE0F", "[WARN]"),  # warning sign + variation selector
    # Info / tips
    ("\U0001F4A1", "[TIP]"),   # light bulb
    ("\u2139", "[NOTE]"),      # information source
    ("\u2139\uFE0F", "[NOTE]"),  # information source + variation selector
    # Arrows
    ("\u27A1", "->"),        # black rightwards arrow
    ("\u27A1\uFE0F", "->"),  # + variation selector
    ("\u2B05", "<-"),        # leftwards black arrow
    ("\u2B05\uFE0F", "<-"),  # + variation selector
    ("\u2192", "->"),        # rightwards arrow
    ("\u2190", "<-"),        # leftwards arrow
]

# Regex pattern for emoji Unicode ranges
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # misc symbols and pictographs
    "\U0001F680-\U0001F6FF"  # transport and map
    "\U0001F700-\U0001F77F"  # alchemical symbols
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
    "\U00002600-\U000027BF"  # misc symbols (sun, stars, etc.)
    "\U00002B00-\U00002BFF"  # misc symbols and arrows (includes stars)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero-width joiner
    "\U000020E3"             # combining enclosing keycap
    "\U00002702-\U000027B0"  # dingbats
    "\U0001F1E0-\U0001F1FF"  # flags (regional indicator symbols)
    "]+",
    flags=re.UNICODE,
)

def strip_emoji(text: str | None) -> str:
    """Strip emojis from text, replacing common ones with ASCII equivalents.

    Args:
        text: The text to sanitize. None returns empty string.

    Returns:
        Sanitized text with emojis removed and common symbols replaced.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        return str(text)

    # Step 1: Semantic replacements (longest match first — variation selectors)
    for emoji, replacement in _SEMANTIC_MAP:
        text = text.replace(emoji, replacement)

    # Step 2: Strip remaining emojis
    text = _EMOJI_PATTERN.sub("", text)

    return text
