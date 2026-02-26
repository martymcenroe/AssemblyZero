```python
"""ANSI-encoded sample strings for Claude usage scraper parsing tests.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing

These fixtures provide ANSI escape sequence test data for validating
the strip_ansi_codes() function and ANSI-aware parsing pipeline.
"""

# Basic SGR (Select Graphic Rendition) sequences
BASIC_SGR_GREEN = "\033[32mGreen text\033[0m"
BASIC_SGR_GREEN_EXPECTED = "Green text"

BASIC_SGR_RED = "\033[31mRed text\033[0m"
BASIC_SGR_RED_EXPECTED = "Red text"

BASIC_SGR_BOLD = "\033[1mBold text\033[0m"
BASIC_SGR_BOLD_EXPECTED = "Bold text"

# Nested / overlapping ANSI sequences
NESTED_BOLD_RED = "\033[1m\033[31mBold Red\033[0m"
NESTED_BOLD_RED_EXPECTED = "Bold Red"

NESTED_MULTI = "\033[1m\033[4m\033[32mBold Underline Green\033[0m"
NESTED_MULTI_EXPECTED = "Bold Underline Green"

# Cursor movement sequences
CURSOR_CLEAR_SCREEN = "\033[2J\033[HText after clear"
CURSOR_CLEAR_SCREEN_EXPECTED = "Text after clear"

CURSOR_MOVE_UP = "\033[3ALine after move up"
CURSOR_MOVE_UP_EXPECTED = "Line after move up"

CURSOR_POSITION = "\033[10;20HPositioned text"
CURSOR_POSITION_EXPECTED = "Positioned text"

# No ANSI codes
PLAIN_TEXT = "This is plain text with no escape sequences"
PLAIN_TEXT_EXPECTED = "This is plain text with no escape sequences"

# Empty string
EMPTY_STRING = ""
EMPTY_STRING_EXPECTED = ""

# Complex real-world-like ANSI output (simulating Claude CLI)
ANSI_USAGE_LINE = (
    "\033[32mabc123\033[0m  "
    "\033[34mclaude-sonnet-4-20250514\033[0m  "
    "\033[33m15,234\033[0m input  "
    "\033[33m3,421\033[0m output  "
    "\033[36m8,000\033[0m cache read  "
    "\033[36m1,200\033[0m cache write  "
    "\033[1m$0.0847\033[0m"
)
ANSI_USAGE_LINE_EXPECTED_CLEAN = (
    "abc123  claude-sonnet-4-20250514  15,234 input  "
    "3,421 output  8,000 cache read  1,200 cache write  $0.0847"
)

# ANSI-heavy multi-line block
ANSI_FULL_BLOCK = (
    "\033[1m=== Usage Summary ===\033[0m\n"
    "\033[32mabc123\033[0m  \033[34mclaude-sonnet-4-20250514\033[0m  "
    "\033[33m15,234\033[0m input  \033[33m3,421\033[0m output  "
    "\033[36m8,000\033[0m cache read  \033[36m1,200\033[0m cache write  "
    "\033[1m$0.0847\033[0m\n"
    "\033[32mdef456\033[0m  \033[34mclaude-sonnet-4-20250514\033[0m  "
    "\033[33m22,100\033[0m input  \033[33m5,000\033[0m output  "
    "\033[36m10,000\033[0m cache read  \033[36m2,000\033[0m cache write  "
    "\033[1m$0.1200\033[0m\n"
    "\033[2mTotal: $0.2047\033[0m\n"
)

# Long adversarial string for ReDoS testing (>10k chars)
LONG_ADVERSARIAL_PLAIN = "x" * 15000
LONG_ADVERSARIAL_ANSI_LIKE = "\033[" + "1;" * 5000 + "m" + "text" + "\033[0m"
LONG_ADVERSARIAL_TOKEN = "1" * 12000 + "abc"
LONG_ADVERSARIAL_COST = "$" + "9" * 11000
```
