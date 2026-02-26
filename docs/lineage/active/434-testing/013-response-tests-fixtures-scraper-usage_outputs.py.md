

```python
"""Sample Claude CLI usage output blocks for parsing tests.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing

CLI Version: Claude Code CLI (circa 2026-02 output format)
Note: If the Claude CLI output format changes, update these fixtures
and document the new CLI version here.
"""

# Single clean usage line (no ANSI codes)
CLEAN_USAGE_LINE = (
    "abc123  claude-sonnet-4-20250514  15,234 input  "
    "3,421 output  8,000 cache read  1,200 cache write  $0.0847"
)

CLEAN_USAGE_LINE_EXPECTED = {
    "session_id": "abc123",
    "input_tokens": 15234,
    "output_tokens": 3421,
    "cache_read_tokens": 8000,
    "cache_write_tokens": 1200,
    "total_cost_usd": 0.0847,
    "model": "claude-sonnet-4-20250514",
    "timestamp": None,
}

# Second usage line for multi-line block tests
CLEAN_USAGE_LINE_2 = (
    "def456  claude-sonnet-4-20250514  22,100 input  "
    "5,000 output  10,000 cache read  2,000 cache write  $0.1200"
)

CLEAN_USAGE_LINE_2_EXPECTED = {
    "session_id": "def456",
    "input_tokens": 22100,
    "output_tokens": 5000,
    "cache_read_tokens": 10000,
    "cache_write_tokens": 2000,
    "total_cost_usd": 0.12,
    "model": "claude-sonnet-4-20250514",
    "timestamp": None,
}

# Multi-line usage block (realistic CLI output)
FULL_USAGE_BLOCK = """=== Usage Summary ===
abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847
def456  claude-sonnet-4-20250514  22,100 input  5,000 output  10,000 cache read  2,000 cache write  $0.1200
Total: $0.2047
"""

FULL_USAGE_BLOCK_EXPECTED = [
    {
        "session_id": "abc123",
        "input_tokens": 15234,
        "output_tokens": 3421,
        "cache_read_tokens": 8000,
        "cache_write_tokens": 1200,
        "total_cost_usd": 0.0847,
        "model": "claude-sonnet-4-20250514",
        "timestamp": None,
    },
    {
        "session_id": "def456",
        "input_tokens": 22100,
        "output_tokens": 5000,
        "cache_read_tokens": 10000,
        "cache_write_tokens": 2000,
        "total_cost_usd": 0.12,
        "model": "claude-sonnet-4-20250514",
        "timestamp": None,
    },
]

# Mixed block (valid + invalid lines)
MIXED_BLOCK = """Starting Claude Code session...
abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847
Some informational log line here
def456  claude-sonnet-4-20250514  22,100 input  5,000 output  10,000 cache read  2,000 cache write  $0.1200
Error: connection timeout (ignored)
"""

MIXED_BLOCK_EXPECTED_COUNT = 2

# Malformed / non-matching lines
MALFORMED_LINES = [
    "Starting session...",
    "Error: connection refused",
    "",
    "   ",
    "Usage: 75%",
    "abc123  claude-sonnet",  # Truncated
    "total tokens: lots",
    "cost: free",
]

# Model name test strings
MODEL_STRINGS = {
    "model: claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    "model: claude-opus-4-20250514": "claude-opus-4-20250514",
    "model: claude-haiku-3-20250514": "claude-haiku-3-20250514",
    "no model info here": None,
    "claude-sonnet-4-20250514 and claude-opus-4-20250514": "claude-sonnet-4-20250514",  # First match
}

# Token count edge cases
TOKEN_COUNT_CASES = {
    "1234": 1234,
    "1,234,567": 1234567,
    " 500 ": 500,
    "0": 0,
    "100,000": 100000,
}

TOKEN_COUNT_ERROR_CASES = [
    "abc",
    "",
    "12.34",
    "one thousand",
]

# Cost value edge cases
COST_VALUE_CASES = {
    "$0.0042": 0.0042,
    "0.0042": 0.0042,
    "$0.00": 0.0,
    " $1.23 ": 1.23,
    "$100.50": 100.50,
    "0.00": 0.0,
}

COST_VALUE_ERROR_CASES = [
    "free",
    "",
    "abc",
    "$$1.00",
]
```
