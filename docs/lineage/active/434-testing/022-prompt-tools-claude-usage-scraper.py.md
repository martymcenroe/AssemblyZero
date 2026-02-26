# Implementation Request: tools/claude-usage-scraper.py

## Task

Write the complete contents of `tools/claude-usage-scraper.py`.

Change type: Modify
Description: Extract parsing into named functions; add `__main__` guard

## LLD Specification

# Implementation Spec: Add Tests for claude-usage-scraper.py Regex Parsing

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #434 |
| LLD | `docs/lld/active/434-test-claude-usage-scraper-regex.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

Extract inline regex/ANSI parsing logic from `tools/claude-usage-scraper.py` into named, importable functions and add comprehensive unit tests with 35 test scenarios covering happy paths, ANSI-encoded input, edge cases, error handling, regression, and ReDoS resilience.

**Objective:** Make all regex and ANSI parsing logic in the scraper testable via unit tests with ≥95% branch coverage.

**Success Criteria:** All 35 test scenarios pass, scraper behavior unchanged after refactoring, no new dependencies added, all tests run < 2s with no network access.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/scraper/__init__.py` | Add | Package init for fixture directory |
| 2 | `tests/fixtures/scraper/ansi_samples.py` | Add | ANSI-encoded sample strings for parsing tests |
| 3 | `tests/fixtures/scraper/usage_outputs.py` | Add | Sample Claude CLI usage output blocks with expected parsed results |
| 4 | `tests/fixtures/scraper/golden_input.txt` | Add | Fixed input for regression baseline |
| 5 | `tests/fixtures/scraper/golden_output.txt` | Add | Expected output captured from pre-refactor scraper |
| 6 | `tools/claude-usage-scraper.py` | Modify | Extract parsing into named functions; add `__main__` guard |
| 7 | `tests/tools/__init__.py` | Add | Package init for tools test directory |
| 8 | `tests/tools/test_claude_usage_scraper.py` | Add | 35 unit tests for all extracted parsing functions |

**Implementation Order Rationale:** Fixtures first (they have no dependencies). Golden files must be generated before the scraper is modified — specifically, `golden_input.txt` is created at step 4, then the `__main__` guard (Change 5 from Section 6.6) is applied as the minimum-viable modification, then `golden_output.txt` is captured at step 5 using the subprocess method. After golden files are committed, the remaining scraper changes (Changes 1–4 from Section 6.6) are applied. Finally, the test init and test file are added.

## 3. Current State (for Modify/Delete files)

### 3.1 `tools/claude-usage-scraper.py`

**Relevant excerpt — imports and module top** (lines 1–30):

```python
"""
Claude Code Usage Scraper

Automates Claude Code's TUI to extract usage quota data that isn't available
via any programmatic API.

Usage:
  poetry run python tools/claude-usage-scraper.py
  poetry run python tools/claude-usage-scraper.py --log /path/to/usage.log

Output:
  JSON to stdout with session, weekly_all, and weekly_sonnet usage percentages.

References:
  - GitHub Issue #8412: https://github.com/anthropics/claude-code/issues/8412
  - GitHub Issue #5621: https://github.com/anthropics/claude-code/issues/5621
"""

import json

import re

import sys

import time

import queue

import threading

import argparse

from datetime import datetime, timezone

from pathlib import Path
```

**What changes:** Add compiled regex pattern constants after the `from pathlib import Path` import line.

**Relevant excerpt — `strip_ansi` function** (lines ~35-37):

```python
def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
```

**What changes:** Rename to `strip_ansi_codes()` with enhanced compiled regex that also handles cursor movement, DEC private, and charset escape sequences. Keep `strip_ansi` as a backward-compatible alias.

**Relevant excerpt — `PtyReader` class** (lines ~39+):

```python
class PtyReader:

    """Non-blocking PTY reader using a background thread."""

    def __init__(self, pty):
    ...
```

**What changes:** New parsing functions (`parse_token_count`, `parse_cost_value`, `extract_model_name`, `extract_usage_line`, `parse_usage_block`) are inserted between the `strip_ansi`/`strip_ansi_codes` function and the `PtyReader` class definition.

**Relevant excerpt — `parse_usage_data` function** (lines ~67-120, approximate):

```python
def parse_usage_data(raw_output: str) -> dict:
    """Parse usage percentages and reset times from Claude Code /status output."""
    result = {
        "session": None,
        "weekly_all": None,
        "weekly_sonnet": None,
        "reset_time": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    cleaned = strip_ansi(raw_output)

    # Parse usage percentages - patterns like "75.2%" or "0%"
    percent_pattern = r'(\d+(?:\.\d+)?)\s*%'

    # ... inline regex patterns for token counts, costs, model names
    # These are embedded directly in this function body
```

**What changes:** Replace the `strip_ansi(raw_output)` call with `strip_ansi_codes(raw_output)`. Where the function body uses inline regex operations for token counts, costs, or model names, replace those with calls to the newly extracted `parse_token_count()`, `parse_cost_value()`, `extract_model_name()`, `extract_usage_line()`, and/or `parse_usage_block()` functions. The function's return value contract (the `result` dict structure) remains unchanged.

**Relevant excerpt — module-level execution** (bottom of file, lines ~200+):

```python
def main():
    parser = argparse.ArgumentParser(description="Scrape Claude Code usage data")
    parser.add_argument("--log", type=Path, help="Path to NDJSON log file")
    # ... argument parsing and execution

main()
```

**What changes:** Wrap the bare `main()` call in `if __name__ == "__main__":` guard to prevent execution on import.

## 4. Data Structures

### 4.1 UsageRecord

**Definition:**

```python
class UsageRecord(TypedDict):
    """Parsed usage data from a single Claude CLI session line."""
    session_id: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total_cost_usd: float
    model: str
    timestamp: str | None
```

**Concrete Example:**

```json
{
    "session_id": "abc123-def456",
    "input_tokens": 15234,
    "output_tokens": 3421,
    "cache_read_tokens": 8000,
    "cache_write_tokens": 1200,
    "total_cost_usd": 0.0847,
    "model": "claude-sonnet-4-20250514",
    "timestamp": "2026-02-25T14:30:00Z"
}
```

### 4.2 AnsiStripResult

**Definition:**

```python
class AnsiStripResult(TypedDict):
    """Result of stripping ANSI codes from a string."""
    clean_text: str
    had_ansi: bool
```

**Concrete Example:**

```json
{
    "clean_text": "Session usage: 15,234 input / 3,421 output tokens",
    "had_ansi": true
}
```

## 5. Function Specifications

### 5.1 `strip_ansi_codes()`

**File:** `tools/claude-usage-scraper.py`

**Signature:**

```python
def strip_ansi_codes(text: str) -> str:
    """Remove all ANSI escape sequences from text.

    Handles SGR (Select Graphic Rendition), cursor movement,
    and other common terminal escape sequences.
    """
    ...
```

**Input Example:**

```python
text = "\033[32mSession\033[0m: \033[1m\033[34m15,234\033[0m input tokens"
```

**Output Example:**

```python
"Session: 15,234 input tokens"
```

**Edge Cases:**
- Empty string `""` → returns `""`
- No ANSI codes `"plain text"` → returns `"plain text"` unchanged
- Nested ANSI `"\033[1m\033[31mBold Red\033[0m"` → returns `"Bold Red"`
- Cursor movement `"\033[2J\033[HText"` → returns `"Text"`
- Long string `"x" * 15000` → returns same string within < 100ms

### 5.2 `parse_token_count()`

**File:** `tools/claude-usage-scraper.py`

**Signature:**

```python
def parse_token_count(raw: str) -> int:
    """Parse a token count string that may contain commas or whitespace.

    Examples: '1,234' -> 1234, ' 500 ' -> 500, '0' -> 0
    Raises ValueError for non-numeric strings.
    """
    ...
```

**Input Example:**

```python
raw = "1,234,567"
```

**Output Example:**

```python
1234567
```

**Edge Cases:**
- `"0"` → `0`
- `" 500 "` → `500`
- `"abc"` → raises `ValueError("Cannot parse token count from: 'abc'")`
- `""` → raises `ValueError`
- `"1" * 12000 + "abc"` → raises `ValueError` within < 100ms

### 5.3 `parse_cost_value()`

**File:** `tools/claude-usage-scraper.py`

**Signature:**

```python
def parse_cost_value(raw: str) -> float:
    """Parse a cost string like '$0.0042' or '0.0042' into a float.

    Handles optional '$' prefix and whitespace.
    Raises ValueError for unparseable strings.
    """
    ...
```

**Input Example:**

```python
raw = "$0.0842"
```

**Output Example:**

```python
0.0842
```

**Edge Cases:**
- `"0.0042"` (no `$`) → `0.0042`
- `"$0.00"` → `0.0`
- `" $1.23 "` → `1.23`
- `"free"` → raises `ValueError("Cannot parse cost value from: 'free'")`
- `"$" + "9" * 11000` → raises `ValueError` within < 100ms

### 5.4 `extract_usage_line()`

**File:** `tools/claude-usage-scraper.py`

**Signature:**

```python
def extract_usage_line(line: str) -> dict | None:
    """Extract usage data from a single line of Claude CLI output.

    Returns None if the line does not match the expected usage format.
    Returns a dict with keys matching UsageRecord if matched.
    Strips ANSI codes before parsing.
    """
    ...
```

**Input Example:**

```python
line = "abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847"
```

**Output Example:**

```python
{
    "session_id": "abc123",
    "input_tokens": 15234,
    "output_tokens": 3421,
    "cache_read_tokens": 8000,
    "cache_write_tokens": 1200,
    "total_cost_usd": 0.0847,
    "model": "claude-sonnet-4-20250514",
    "timestamp": None,
}
```

**Edge Cases:**
- Non-usage line `"Starting session..."` → `None`
- Truncated/partial line `"abc123  claude-sonnet"` → `None`
- ANSI-wrapped line → strips ANSI first, then parses
- Empty string → `None`

### 5.5 `extract_model_name()`

**File:** `tools/claude-usage-scraper.py`

**Signature:**

```python
def extract_model_name(text: str) -> str | None:
    """Extract the Claude model identifier from output text.

    Handles model strings like 'claude-sonnet-4-20250514',
    'claude-opus-4-20250514', etc.
    """
    ...
```

**Input Example:**

```python
text = "model: claude-sonnet-4-20250514 (default)"
```

**Output Example:**

```python
"claude-sonnet-4-20250514"
```

**Edge Cases:**
- `"no model info here"` → `None`
- Text with two models → returns first match
- `"model: claude-opus-4-20250514"` → `"claude-opus-4-20250514"`
- `"model: claude-haiku-3-20250514"` → `"claude-haiku-3-20250514"`

### 5.6 `parse_usage_block()`

**File:** `tools/claude-usage-scraper.py`

**Signature:**

```python
def parse_usage_block(block: str) -> list[dict]:
    """Parse a multi-line usage output block into structured records.

    Strips ANSI codes first, then extracts all usage lines.
    Non-matching lines are silently skipped.
    """
    ...
```

**Input Example:**

```python
block = """Some header text
abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847
def456  claude-sonnet-4-20250514  22,100 input  5,000 output  10,000 cache read  2,000 cache write  $0.1200
Some footer text"""
```

**Output Example:**

```python
[
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
```

**Edge Cases:**
- Empty string `""` → `[]`
- Single usage line → list with 1 record
- All non-matching lines → `[]`
- Fully ANSI-encoded block → same result as clean block

### 5.7 `make_ansi()` (test helper)

**File:** `tests/tools/test_claude_usage_scraper.py`

**Signature:**

```python
def make_ansi(text: str, code: int = 32) -> str:
    """Wrap text in ANSI escape codes for test fixture generation."""
    ...
```

**Input Example:**

```python
text = "Green text"
code = 32
```

**Output Example:**

```python
"\033[32mGreen text\033[0m"
```

## 6. Change Instructions

### 6.1 `tests/fixtures/scraper/__init__.py` (Add)

**Complete file contents:**

```python
"""Test fixtures for Claude usage scraper tests.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing
"""
```

### 6.2 `tests/fixtures/scraper/ansi_samples.py` (Add)

**Complete file contents:**

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

### 6.3 `tests/fixtures/scraper/usage_outputs.py` (Add)

**Complete file contents:**

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

### 6.4 `tests/fixtures/scraper/golden_input.txt` (Add)

**Complete file contents:**

```
=== Usage Summary ===
abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847
def456  claude-sonnet-4-20250514  22,100 input  5,000 output  10,000 cache read  2,000 cache write  $0.1200
Total: $0.2047
```

### 6.5 `tests/fixtures/scraper/golden_output.txt` (Add)

**CRITICAL: This file MUST be generated BEFORE any refactoring changes beyond the `__main__` guard.** The generation sequence is:

1. First, apply **only** Change 5 from Section 6.6 (the `__main__` guard) to `tools/claude-usage-scraper.py`
2. Then generate the golden output using the subprocess method:

```bash
python tools/claude-usage-scraper.py < tests/fixtures/scraper/golden_input.txt > tests/fixtures/scraper/golden_output.txt
```

3. If the scraper does not support stdin piping (i.e., it uses PTY-based scraping rather than reading from stdin), use this alternative approach to capture the golden output:

```bash
python -c "
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('scraper', 'tools/claude-usage-scraper.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
golden_input = open('tests/fixtures/scraper/golden_input.txt').read()
result = mod.parse_usage_data(golden_input)
print(json.dumps(result, sort_keys=True))
" > tests/fixtures/scraper/golden_output.txt
```

4. Commit both `golden_input.txt` and `golden_output.txt` before proceeding with Changes 1–4.

**Placeholder content** (replace with actual captured output):

```json
{"reset_time": null, "session": null, "timestamp": "2026-02-25T00:00:00+00:00", "weekly_all": null, "weekly_sonnet": null}
```

**IMPORTANT:** The actual golden output must be captured from the current (pre-refactor) scraper's `parse_usage_data()` function. The placeholder above approximates the expected structure but the `timestamp` value will differ. The regression test (T300) normalizes using `json.dumps(sort_keys=True)` for comparison.

### 6.6 `tools/claude-usage-scraper.py` (Modify)

**Change 5 (apply FIRST — before golden file generation):** Add `__main__` guard at bottom of file

Locate the bare `main()` call at the very end of the file and wrap it:

```diff
-main()
+if __name__ == "__main__":
+    main()
```

**After golden files are generated and committed, apply Changes 1–4:**

**Change 1:** Add compiled regex patterns at module level (after the `from pathlib import Path` import, before the `strip_ansi` function)

```diff
 from pathlib import Path

+# Compiled regex patterns for parsing
+_ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9;]*[a-zA-Z]|\x1b\([A-Z]')
+_COST_PATTERN = re.compile(r'^\s*\$?([\d]+\.[\d]+|\d+)\s*$')
+_MODEL_PATTERN = re.compile(r'(claude-(?:sonnet|opus|haiku)-[\w.-]+)')
+_USAGE_LINE_PATTERN = re.compile(
+    r'(\S+)\s+'                           # session_id
+    r'(claude-(?:sonnet|opus|haiku)-[\w.-]+)\s+'  # model
+    r'([\d,]+)\s+input\s+'               # input_tokens
+    r'([\d,]+)\s+output\s+'              # output_tokens
+    r'([\d,]+)\s+cache\s+read\s+'        # cache_read_tokens
+    r'([\d,]+)\s+cache\s+write\s+'       # cache_write_tokens
+    r'\$?([\d.]+)'                        # total_cost_usd
+)
+
+
 def strip_ansi(text: str) -> str:
```

**Change 2:** Replace existing `strip_ansi` function with `strip_ansi_codes` and backward-compatible alias

```diff
-def strip_ansi(text: str) -> str:
-    """Remove ANSI escape sequences from terminal output."""
-    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
+def strip_ansi_codes(text: str) -> str:
+    """Remove all ANSI escape sequences from text.
+
+    Handles SGR (Select Graphic Rendition), cursor movement,
+    and other common terminal escape sequences.
+    """
+    return _ANSI_PATTERN.sub('', text)
+
+
+# Backward-compatible alias
+strip_ansi = strip_ansi_codes
```

**Change 3:** Add new parsing functions after `strip_ansi` alias and before `class PtyReader`

Insert the following block between the `strip_ansi = strip_ansi_codes` alias line and the `class PtyReader:` line:

```python

def parse_token_count(raw: str) -> int:
    """Parse a token count string that may contain commas or whitespace.

    Examples: '1,234' -> 1234, ' 500 ' -> 500, '0' -> 0
    Raises ValueError for non-numeric strings.
    """
    cleaned = raw.strip().replace(',', '')
    if not cleaned or not cleaned.isdigit():
        raise ValueError(f"Cannot parse token count from: {raw!r}")
    return int(cleaned)


def parse_cost_value(raw: str) -> float:
    """Parse a cost string like '$0.0042' or '0.0042' into a float.

    Handles optional '$' prefix and whitespace.
    Raises ValueError for unparseable strings.
    """
    match = _COST_PATTERN.match(raw)
    if not match:
        raise ValueError(f"Cannot parse cost value from: {raw!r}")
    return float(match.group(1))


def extract_model_name(text: str) -> str | None:
    """Extract the Claude model identifier from output text.

    Handles model strings like 'claude-sonnet-4-20250514',
    'claude-opus-4-20250514', etc. Returns first match.
    """
    match = _MODEL_PATTERN.search(text)
    return match.group(1) if match else None


def extract_usage_line(line: str) -> dict | None:
    """Extract usage data from a single line of Claude CLI output.

    Returns None if the line does not match the expected usage format.
    Strips ANSI codes before parsing.
    """
    cleaned = strip_ansi_codes(line)
    match = _USAGE_LINE_PATTERN.search(cleaned)
    if not match:
        return None
    return {
        "session_id": match.group(1),
        "model": match.group(2),
        "input_tokens": parse_token_count(match.group(3)),
        "output_tokens": parse_token_count(match.group(4)),
        "cache_read_tokens": parse_token_count(match.group(5)),
        "cache_write_tokens": parse_token_count(match.group(6)),
        "total_cost_usd": parse_cost_value(match.group(7)),
        "timestamp": None,
    }


def parse_usage_block(block: str) -> list[dict]:
    """Parse a multi-line usage output block into structured records.

    Strips ANSI codes first, then extracts all usage lines.
    Non-matching lines are silently skipped.
    """
    results = []
    for line in block.splitlines():
        record = extract_usage_line(line)
        if record is not None:
            results.append(record)
    return results

```

**Change 4:** Update `parse_usage_data` to use the extracted functions

Inside the `parse_usage_data` function body, replace the `strip_ansi` call with `strip_ansi_codes`. Then, locate any inline regex operations that calculate values such as `result['weekly_all']`, `result['weekly_sonnet']`, or extract token counts, costs, or model names inline, and replace them with calls to the new `parse_token_count()`, `parse_cost_value()`, `extract_model_name()`, `extract_usage_line()`, or `parse_usage_block()` functions as appropriate.

Specifically:

```diff
-    cleaned = strip_ansi(raw_output)
+    cleaned = strip_ansi_codes(raw_output)
```

For any inline `re.search`/`re.findall` calls within `parse_usage_data` that extract token counts (patterns matching `\d[\d,]*`), replace with:

```python
# Before (inline pattern):
#   m = re.search(r'([\d,]+)\s+input', cleaned)
#   if m: input_tokens = int(m.group(1).replace(',', ''))

# After (using extracted function):
#   m = re.search(r'([\d,]+)\s+input', cleaned)
#   if m: input_tokens = parse_token_count(m.group(1))
```

For any inline cost extraction (patterns matching `\$[\d.]+`), replace with:

```python
# Before: cost = float(m.group(1))
# After:  cost = parse_cost_value(m.group(1))
```

For any inline model name extraction, replace with:

```python
# Before: re.search(r'claude-\w+-\d+-\w+', cleaned)
# After:  extract_model_name(cleaned)
```

**Note:** The function's return value contract (`result` dict with keys `session`, `weekly_all`, `weekly_sonnet`, `reset_time`, `timestamp`) MUST remain unchanged. Only the internal implementation of how values are parsed changes.

### 6.7 `tests/tools/__init__.py` (Add)

**Complete file contents:**

```python
"""Tests for tools/ directory.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing
"""
```

### 6.8 `tests/tools/test_claude_usage_scraper.py` (Add)

**Complete file contents:**

```python
"""Unit tests for claude-usage-scraper.py parsing functions.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing

Tests cover: ANSI stripping, token parsing, cost parsing, model extraction,
usage line extraction, full block parsing, regression, import safety,
and ReDoS resilience.
"""

import io
import json
import re
import sys
import time
import socket
import importlib
import importlib.util
from pathlib import Path
from unittest import mock

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import module under test using importlib to handle the hyphenated filename.
# This relies on the __main__ guard being present — importing must not trigger execution.
_scraper_path = Path(__file__).resolve().parents[2] / "tools" / "claude-usage-scraper.py"
_spec = importlib.util.spec_from_file_location("claude_usage_scraper", _scraper_path)
scraper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scraper)

# Import fixtures
from tests.fixtures.scraper import ansi_samples, usage_outputs


# ── Test Helper ──

def make_ansi(text: str, code: int = 32) -> str:
    """Wrap text in ANSI escape codes for test fixture generation."""
    return f"\033[{code}m{text}\033[0m"


# ── T010-T050: TestStripAnsiCodes ──

class TestStripAnsiCodes:
    """Tests for strip_ansi_codes() function."""

    def test_strip_ansi_basic_sgr(self):
        """T010: Removes basic SGR codes like \\033[32m."""
        assert scraper.strip_ansi_codes("\033[32mGreen\033[0m") == "Green"

    def test_strip_ansi_nested(self):
        """T020: Handles overlapping/nested ANSI sequences."""
        assert scraper.strip_ansi_codes("\033[1m\033[31mBold Red\033[0m") == "Bold Red"

    def test_strip_ansi_no_codes(self):
        """T030: Returns input unchanged when no ANSI present."""
        assert scraper.strip_ansi_codes("plain text") == "plain text"

    def test_strip_ansi_empty_string(self):
        """T040: Returns empty string."""
        assert scraper.strip_ansi_codes("") == ""

    def test_strip_ansi_cursor_movement(self):
        """T050: Removes cursor positioning sequences."""
        assert scraper.strip_ansi_codes("\033[2J\033[HText") == "Text"


# ── T060-T100: TestParseTokenCount ──

class TestParseTokenCount:
    """Tests for parse_token_count() function."""

    def test_parse_token_count_simple(self):
        """T060: Simple integer string."""
        assert scraper.parse_token_count("1234") == 1234

    def test_parse_token_count_commas(self):
        """T070: Comma-separated token count."""
        assert scraper.parse_token_count("1,234,567") == 1234567

    def test_parse_token_count_whitespace(self):
        """T080: Token count with leading/trailing whitespace."""
        assert scraper.parse_token_count(" 500 ") == 500

    def test_parse_token_count_zero(self):
        """T090: Zero token count."""
        assert scraper.parse_token_count("0") == 0

    def test_parse_token_count_invalid(self):
        """T100: Non-numeric string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse token count"):
            scraper.parse_token_count("abc")

    @pytest.mark.parametrize("raw,expected", list(usage_outputs.TOKEN_COUNT_CASES.items()))
    def test_parse_token_count_parametrized(self, raw, expected):
        """Parametrized token count cases from fixtures."""
        assert scraper.parse_token_count(raw) == expected

    @pytest.mark.parametrize("raw", usage_outputs.TOKEN_COUNT_ERROR_CASES)
    def test_parse_token_count_error_cases(self, raw):
        """Parametrized error cases from fixtures."""
        with pytest.raises(ValueError):
            scraper.parse_token_count(raw)


# ── T110-T150: TestParseCostValue ──

class TestParseCostValue:
    """Tests for parse_cost_value() function."""

    def test_parse_cost_with_dollar(self):
        """T110: Cost string with $ prefix."""
        assert scraper.parse_cost_value("$0.0042") == pytest.approx(0.0042)

    def test_parse_cost_without_dollar(self):
        """T120: Cost string without $ prefix."""
        assert scraper.parse_cost_value("0.0042") == pytest.approx(0.0042)

    def test_parse_cost_zero(self):
        """T130: Zero cost."""
        assert scraper.parse_cost_value("$0.00") == 0.0

    def test_parse_cost_whitespace(self):
        """T140: Cost with whitespace."""
        assert scraper.parse_cost_value(" $1.23 ") == pytest.approx(1.23)

    def test_parse_cost_invalid(self):
        """T150: Unparseable cost string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse cost value"):
            scraper.parse_cost_value("free")

    @pytest.mark.parametrize("raw,expected", list(usage_outputs.COST_VALUE_CASES.items()))
    def test_parse_cost_parametrized(self, raw, expected):
        """Parametrized cost cases from fixtures."""
        assert scraper.parse_cost_value(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", usage_outputs.COST_VALUE_ERROR_CASES)
    def test_parse_cost_error_cases(self, raw):
        """Parametrized error cases from fixtures."""
        with pytest.raises(ValueError):
            scraper.parse_cost_value(raw)


# ── T160-T190: TestExtractUsageLine ──

class TestExtractUsageLine:
    """Tests for extract_usage_line() function."""

    def test_extract_usage_line_valid(self):
        """T160: Returns complete record from clean usage line."""
        result = scraper.extract_usage_line(usage_outputs.CLEAN_USAGE_LINE)
        assert result is not None
        assert result["session_id"] == "abc123"
        assert result["input_tokens"] == 15234
        assert result["output_tokens"] == 3421
        assert result["cache_read_tokens"] == 8000
        assert result["cache_write_tokens"] == 1200
        assert result["total_cost_usd"] == pytest.approx(0.0847)
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["timestamp"] is None

    def test_extract_usage_line_with_ansi(self):
        """T170: Strips ANSI then parses correctly."""
        result = scraper.extract_usage_line(ansi_samples.ANSI_USAGE_LINE)
        assert result is not None
        assert result["session_id"] == "abc123"
        assert result["input_tokens"] == 15234
        assert result["output_tokens"] == 3421
        assert result["model"] == "claude-sonnet-4-20250514"

    def test_extract_usage_line_no_match(self):
        """T180: Returns None for non-usage lines."""
        assert scraper.extract_usage_line("Starting session...") is None

    def test_extract_usage_line_partial(self):
        """T190: Returns None for truncated lines."""
        assert scraper.extract_usage_line("abc123  claude-sonnet") is None

    @pytest.mark.parametrize("line", usage_outputs.MALFORMED_LINES)
    def test_extract_usage_line_malformed(self, line):
        """All malformed lines return None."""
        assert scraper.extract_usage_line(line) is None


# ── T200-T240: TestExtractModelName ──

class TestExtractModelName:
    """Tests for extract_model_name() function."""

    def test_extract_model_name_sonnet(self):
        """T200: Extracts sonnet model."""
        result = scraper.extract_model_name("model: claude-sonnet-4-20250514")
        assert result == "claude-sonnet-4-20250514"

    def test_extract_model_name_opus(self):
        """T210: Extracts opus model."""
        result = scraper.extract_model_name("model: claude-opus-4-20250514")
        assert result == "claude-opus-4-20250514"

    def test_extract_model_name_haiku(self):
        """T220: Extracts haiku model."""
        result = scraper.extract_model_name("model: claude-haiku-3-20250514")
        assert result == "claude-haiku-3-20250514"

    def test_extract_model_name_none(self):
        """T230: Returns None when no model present."""
        assert scraper.extract_model_name("no model info here") is None

    def test_extract_model_name_multiple(self):
        """T240: Returns first match when multiple present."""
        text = "claude-sonnet-4-20250514 and claude-opus-4-20250514"
        result = scraper.extract_model_name(text)
        assert result == "claude-sonnet-4-20250514"

    @pytest.mark.parametrize(
        "text,expected",
        list(usage_outputs.MODEL_STRINGS.items()),
    )
    def test_extract_model_name_parametrized(self, text, expected):
        """Parametrized model name cases from fixtures."""
        assert scraper.extract_model_name(text) == expected


# ── T250-T290: TestParseUsageBlock ──

class TestParseUsageBlock:
    """Tests for parse_usage_block() function."""

    def test_parse_usage_block_full(self):
        """T250: Parses multi-line block into list of records."""
        results = scraper.parse_usage_block(usage_outputs.FULL_USAGE_BLOCK)
        assert len(results) == 2
        assert results[0]["session_id"] == "abc123"
        assert results[0]["input_tokens"] == 15234
        assert results[1]["session_id"] == "def456"
        assert results[1]["input_tokens"] == 22100

    def test_parse_usage_block_mixed(self):
        """T260: Skips non-usage lines, parses valid ones."""
        results = scraper.parse_usage_block(usage_outputs.MIXED_BLOCK)
        assert len(results) == usage_outputs.MIXED_BLOCK_EXPECTED_COUNT

    def test_parse_usage_block_empty(self):
        """T270: Returns empty list for empty input."""
        assert scraper.parse_usage_block("") == []

    def test_parse_usage_block_ansi_heavy(self):
        """T280: Correctly parses fully ANSI-encoded block."""
        results = scraper.parse_usage_block(ansi_samples.ANSI_FULL_BLOCK)
        assert len(results) == 2
        assert results[0]["session_id"] == "abc123"
        assert results[0]["model"] == "claude-sonnet-4-20250514"
        assert results[1]["session_id"] == "def456"

    def test_parse_usage_block_single_line(self):
        """T290: Handles block with exactly one usage line."""
        results = scraper.parse_usage_block(usage_outputs.CLEAN_USAGE_LINE)
        assert len(results) == 1
        assert results[0]["session_id"] == "abc123"


# ── T300: TestRegression ──

class TestRegression:
    """Regression test comparing output against golden files."""

    def test_scraper_regression_output_unchanged(self):
        """T300: Scraper parse output matches golden file after refactor."""
        golden_input_path = Path(__file__).resolve().parents[1] / "fixtures" / "scraper" / "golden_input.txt"
        golden_output_path = Path(__file__).resolve().parents[1] / "fixtures" / "scraper" / "golden_output.txt"

        if not golden_input_path.exists() or not golden_output_path.exists():
            pytest.skip(
                "Golden files not generated yet. Run: "
                "python tools/claude-usage-scraper.py < tests/fixtures/scraper/golden_input.txt "
                "> tests/fixtures/scraper/golden_output.txt"
            )

        golden_input = golden_input_path.read_text(encoding="utf-8")
        golden_output = golden_output_path.read_text(encoding="utf-8").strip()

        # Run the refactored parse function against the same input
        result = scraper.parse_usage_data(golden_input)

        # Normalize the timestamp field since it changes on each run
        # Both golden and actual should be compared without volatile fields
        expected = json.loads(golden_output)
        result.pop("timestamp", None)
        expected.pop("timestamp", None)

        actual_normalized = json.dumps(result, indent=None, sort_keys=True)
        expected_normalized = json.dumps(expected, indent=None, sort_keys=True)

        assert actual_normalized == expected_normalized, (
            f"Regression detected!\n"
            f"Expected: {expected_normalized}\n"
            f"Actual:   {actual_normalized}"
        )


# ── T310: TestImportSafety ──

class TestImportSafety:
    """Test that importing the module has no side effects."""

    def test_import_no_side_effects(self):
        """T310: Importing module does not execute scraper logic."""
        # Capture stdout during a fresh import
        captured = io.StringIO()
        with mock.patch("sys.stdout", captured):
            # Force re-import
            fresh_spec = importlib.util.spec_from_file_location(
                "claude_usage_scraper_fresh", _scraper_path
            )
            fresh_mod = importlib.util.module_from_spec(fresh_spec)
            fresh_spec.loader.exec_module(fresh_mod)

        output = captured.getvalue()
        # Should produce no output on import
        assert output == "", (
            f"Module produced output on import (side effect detected): {output!r}"
        )


# ── T320-T330: TestRealisticFixtures ──

class TestRealisticFixtures:
    """Tests using realistic CLI fixture data."""

    def test_strip_ansi_with_realistic_cli_output(self):
        """T320: ANSI stripping works on actual Claude CLI fixture data."""
        result = scraper.strip_ansi_codes(ansi_samples.ANSI_USAGE_LINE)
        assert result == ansi_samples.ANSI_USAGE_LINE_EXPECTED_CLEAN

    def test_parse_usage_block_realistic_fixture(self):
        """T330: Full block parse against realistic fixture matches expected records."""
        results = scraper.parse_usage_block(usage_outputs.FULL_USAGE_BLOCK)
        assert len(results) == len(usage_outputs.FULL_USAGE_BLOCK_EXPECTED)

        for actual, expected in zip(results, usage_outputs.FULL_USAGE_BLOCK_EXPECTED):
            assert actual["session_id"] == expected["session_id"]
            assert actual["input_tokens"] == expected["input_tokens"]
            assert actual["output_tokens"] == expected["output_tokens"]
            assert actual["cache_read_tokens"] == expected["cache_read_tokens"]
            assert actual["cache_write_tokens"] == expected["cache_write_tokens"]
            assert actual["total_cost_usd"] == pytest.approx(expected["total_cost_usd"])
            assert actual["model"] == expected["model"]


# ── T340: TestNoNetworkAccess ──

class TestNoNetworkAccess:
    """Verify tests run without network access."""

    def test_no_network_access(self):
        """T340: All parsing functions complete without any socket calls."""
        original_connect = socket.socket.connect
        connect_calls = []

        def mock_connect(self, *args, **kwargs):
            connect_calls.append(args)
            raise ConnectionError("Network access blocked by test")

        with mock.patch.object(socket.socket, "connect", mock_connect):
            # Run all parsing functions
            scraper.strip_ansi_codes("\033[32mtest\033[0m")
            scraper.parse_token_count("1,234")
            scraper.parse_cost_value("$0.01")
            scraper.extract_model_name("claude-sonnet-4-20250514")
            scraper.extract_usage_line(usage_outputs.CLEAN_USAGE_LINE)
            scraper.parse_usage_block(usage_outputs.FULL_USAGE_BLOCK)

        assert len(connect_calls) == 0, (
            f"Network access detected: {len(connect_calls)} socket.connect calls"
        )


# ── T350: TestReDoSResilience ──

class TestReDoSResilience:
    """ReDoS resilience tests with adversarial long strings."""

    TIMEOUT_SECONDS = 0.1  # 100ms budget

    def test_redos_strip_ansi_long_string(self):
        """T350a: strip_ansi_codes completes within timeout on >10k char input."""
        long_input = ansi_samples.LONG_ADVERSARIAL_PLAIN  # "x" * 15000
        start = time.monotonic()
        result = scraper.strip_ansi_codes(long_input)
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"strip_ansi_codes took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )
        # Plain string with no ANSI should return unchanged
        assert result == long_input

    def test_redos_strip_ansi_adversarial_ansi(self):
        """T350b: strip_ansi_codes handles adversarial ANSI-like sequence."""
        long_input = ansi_samples.LONG_ADVERSARIAL_ANSI_LIKE
        start = time.monotonic()
        result = scraper.strip_ansi_codes(long_input)
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"strip_ansi_codes took {elapsed:.3f}s (budget: {self.TIMEOUT_SECONDS}s)"
        )

    def test_redos_parse_token_count_long_string(self):
        """T350c: parse_token_count handles >10k char adversarial input."""
        long_input = ansi_samples.LONG_ADVERSARIAL_TOKEN  # "1" * 12000 + "abc"
        start = time.monotonic()
        with pytest.raises(ValueError):
            scraper.parse_token_count(long_input)
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"parse_token_count took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )

    def test_redos_parse_cost_long_string(self):
        """T350d: parse_cost_value handles >10k char adversarial input."""
        long_input = ansi_samples.LONG_ADVERSARIAL_COST  # "$" + "9" * 11000
        start = time.monotonic()
        # May either parse (as a huge number) or raise ValueError
        try:
            scraper.parse_cost_value(long_input)
        except ValueError:
            pass
        elapsed = time.monotonic() - start

        assert elapsed < self.TIMEOUT_SECONDS, (
            f"parse_cost_value took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )

    def test_redos_extract_usage_line_long_string(self):
        """T350e: extract_usage_line handles >10k char adversarial input."""
        long_input = "x" * 15000
        start = time.monotonic()
        result = scraper.extract_usage_line(long_input)
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed < self.TIMEOUT_SECONDS, (
            f"extract_usage_line took {elapsed:.3f}s on {len(long_input)} chars "
            f"(budget: {self.TIMEOUT_SECONDS}s)"
        )
```

## 7. Pattern References

### 7.1 Existing Test Pattern — Workflow Tests

**File:** `tests/test_integration_workflow.py` (lines 1-80)

```python
# This pattern shows the test file structure used in the project:
# - Module-level imports
# - pytest fixtures
# - Test classes grouped by feature
# - Descriptive test method names
```

**Relevance:** Follow the same test file structure — imports at top, test classes grouped logically, pytest assertions.

### 7.2 Existing CLI Tool Pattern

**File:** `tools/run_audit.py` (lines 1-60)

```python
# This pattern shows how tools/ scripts are structured:
# - Module docstring
# - Imports
# - Functions
# - if __name__ == "__main__": guard
```

**Relevance:** The `__main__` guard pattern we need to add to `claude-usage-scraper.py` should follow this existing convention.

### 7.3 Existing Tool Import Pattern — Hyphenated Filenames

**Note:** `tools/claude-usage-scraper.py` uses a hyphenated filename which cannot be imported with standard `import` syntax. The test file uses `importlib.util.spec_from_file_location()` to handle this:

```python
_scraper_path = Path(__file__).resolve().parents[2] / "tools" / "claude-usage-scraper.py"
_spec = importlib.util.spec_from_file_location("claude_usage_scraper", _scraper_path)
scraper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scraper)
```

**Relevance:** Critical pattern for importing the scraper module in tests. Standard `from tools import claude_usage_scraper` will fail with `SyntaxError` / `ModuleNotFoundError` due to the hyphens. This `importlib` approach is the only correct way to import the module.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `re` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `json` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `sys` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `time` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `argparse` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `datetime`, `timezone` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `pathlib.Path` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `queue` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `threading` | stdlib | `tools/claude-usage-scraper.py` (already imported) |
| `pytest` | dev dependency | `tests/tools/test_claude_usage_scraper.py` |
| `importlib` | stdlib | `tests/tools/test_claude_usage_scraper.py` |
| `importlib.util` | stdlib | `tests/tools/test_claude_usage_scraper.py` |
| `io` | stdlib | `tests/tools/test_claude_usage_scraper.py` |
| `json` | stdlib | `tests/tools/test_claude_usage_scraper.py` |
| `socket` | stdlib | `tests/tools/test_claude_usage_scraper.py` |
| `time` | stdlib | `tests/tools/test_claude_usage_scraper.py` |
| `unittest.mock` | stdlib | `tests/tools/test_claude_usage_scraper.py` |

**New Dependencies:** None — all imports use Python stdlib or existing dev dependencies (pytest).

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `strip_ansi_codes()` | `"\033[32mGreen\033[0m"` | `"Green"` |
| T020 | `strip_ansi_codes()` | `"\033[1m\033[31mBold Red\033[0m"` | `"Bold Red"` |
| T030 | `strip_ansi_codes()` | `"plain text"` | `"plain text"` |
| T040 | `strip_ansi_codes()` | `""` | `""` |
| T050 | `strip_ansi_codes()` | `"\033[2J\033[HText"` | `"Text"` |
| T060 | `parse_token_count()` | `"1234"` | `1234` |
| T070 | `parse_token_count()` | `"1,234,567"` | `1234567` |
| T080 | `parse_token_count()` | `" 500 "` | `500` |
| T090 | `parse_token_count()` | `"0"` | `0` |
| T100 | `parse_token_count()` | `"abc"` | Raises `ValueError` |
| T110 | `parse_cost_value()` | `"$0.0042"` | `0.0042` |
| T120 | `parse_cost_value()` | `"0.0042"` | `0.0042` |
| T130 | `parse_cost_value()` | `"$0.00"` | `0.0` |
| T140 | `parse_cost_value()` | `" $1.23 "` | `1.23` |
| T150 | `parse_cost_value()` | `"free"` | Raises `ValueError` |
| T160 | `extract_usage_line()` | `CLEAN_USAGE_LINE` fixture | `UsageRecord` with `session_id="abc123"`, `input_tokens=15234`, etc. |
| T170 | `extract_usage_line()` | `ANSI_USAGE_LINE` fixture | Same `UsageRecord` as T160 |
| T180 | `extract_usage_line()` | `"Starting session..."` | `None` |
| T190 | `extract_usage_line()` | `"abc123  claude-sonnet"` | `None` |
| T200 | `extract_model_name()` | `"model: claude-sonnet-4-20250514"` | `"claude-sonnet-4-20250514"` |
| T210 | `extract_model_name()` | `"model: claude-opus-4-20250514"` | `"claude-opus-4-20250514"` |
| T220 | `extract_model_name()` | `"model: claude-haiku-3-20250514"` | `"claude-haiku-3-20250514"` |
| T230 | `extract_model_name()` | `"no model info here"` | `None` |
| T240 | `extract_model_name()` | Two model strings in one text | `"claude-sonnet-4-20250514"` (first match) |
| T250 | `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | List of 2 `UsageRecord`s |
| T260 | `parse_usage_block()` | `MIXED_BLOCK` fixture | List of 2 records (skips non-matching) |
| T270 | `parse_usage_block()` | `""` | `[]` |
| T280 | `parse_usage_block()` | `ANSI_FULL_BLOCK` fixture | List of 2 records (same as clean) |
| T290 | `parse_usage_block()` | Single clean usage line | List of 1 record |
| T300 | `parse_usage_data()` | `golden_input.txt` content | Matches `golden_output.txt` (excluding volatile `timestamp` field) |
| T310 | Module import | `importlib.util.spec_from_file_location` + `exec_module` | No stdout output |
| T320 | `strip_ansi_codes()` | `ANSI_USAGE_LINE` fixture | `ANSI_USAGE_LINE_EXPECTED_CLEAN` |
| T330 | `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | `FULL_USAGE_BLOCK_EXPECTED` all fields match |
| T340 | All parsing functions | Various inputs with socket blocked | Zero `socket.connect` calls |
| T350 | All parsing functions | >10k char adversarial strings | Completes < 100ms, correct result |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All extracted parsing functions follow these conventions:
- `strip_ansi_codes()`: Never raises — always returns a string (may return input unchanged)
- `parse_token_count()`: Raises `ValueError` with descriptive message for unparseable input
- `parse_cost_value()`: Raises `ValueError` with descriptive message for unparseable input
- `extract_usage_line()`: Returns `None` for non-matching lines (never raises)
- `extract_model_name()`: Returns `None` when no model found (never raises)
- `parse_usage_block()`: Returns empty list for empty/non-matching input (never raises)

### 10.2 Logging Convention

No logging is added to the extracted functions. They are pure parsing functions with no side effects. The existing scraper's `main()` function handles any user-facing output.

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `_ANSI_PATTERN` | `re.compile(r'\x1b\[[0-9;]*[a-zA-Z]\|\x1b\[\?[0-9;]*[a-zA-Z]\|\x1b\([A-Z]')` | Precompiled for performance; covers SGR, DEC private, and charset sequences |
| `_COST_PATTERN` | `re.compile(r'^\s*\$?([\d]+\.[\d]+\|\d+)\s*$')` | Extracts numeric value from cost strings |
| `_MODEL_PATTERN` | `re.compile(r'(claude-(?:sonnet\|opus\|haiku)-[\w.-]+)')` | Matches all Claude model name variants |
| `_USAGE_LINE_PATTERN` | See Change 1 in Section 6.6 | Matches full usage line format with named capture groups |
| `TIMEOUT_SECONDS` | `0.1` | 100ms ReDoS budget; any regex taking longer indicates backtracking |

### 10.4 Import Mechanism for Hyphenated Filename

The scraper file `claude-usage-scraper.py` uses hyphens in its filename, which is not valid for Python `import` statements. **Do NOT use** `from tools import claude_usage_scraper` — this will fail with `SyntaxError` or `ModuleNotFoundError`. The test file uses `importlib.util.spec_from_file_location()` to load the module by file path:

```python
_scraper_path = Path(__file__).resolve().parents[2] / "tools" / "claude-usage-scraper.py"
_spec = importlib.util.spec_from_file_location("claude_usage_scraper", _scraper_path)
scraper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scraper)
```

This is the standard Python approach for importing modules with non-standard filenames.

### 10.5 Golden File Generation Order (CRITICAL)

**The golden files MUST be generated BEFORE the scraper's parsing logic is changed, otherwise the regression baseline is invalid.**

Mandatory sequencing:

1. **Step 1:** Create `tests/fixtures/scraper/golden_input.txt` with the fixed synthetic input (Section 6.4)
2. **Step 2:** Apply ONLY Change 5 from Section 6.6 — add the `if __name__ == "__main__":` guard. This is the minimum change needed to allow import without side effects, and it does NOT alter parsing behavior.
3. **Step 3:** Generate `golden_output.txt` by running the pre-refactor scraper's `parse_usage_data()` against golden input:
   ```bash
   python -c "
   import importlib.util, json
   spec = importlib.util.spec_from_file_location('scraper', 'tools/claude-usage-scraper.py')
   mod = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(mod)
   golden_input = open('tests/fixtures/scraper/golden_input.txt').read()
   result = mod.parse_usage_data(golden_input)
   print(json.dumps(result, sort_keys=True))
   " > tests/fixtures/scraper/golden_output.txt
   ```
4. **Step 4:** Commit both golden files AND the `__main__` guard change.
5. **Step 5:** Proceed with Changes 1–4 (adding compiled patterns, `strip_ansi_codes`, new functions, updating `parse_usage_data`).

### 10.6 Regex Pattern Design Notes

The `_USAGE_LINE_PATTERN` regex is designed to be non-backtracking:
- Each capture group uses character classes with clear boundaries (e.g., `[\d,]+`, `\S+`)
- Whitespace separators use `\s+` which always matches greedily without alternatives
- No nested quantifiers or overlapping alternatives that could cause exponential backtracking
- The `\S+` for session_id matches to the first whitespace boundary — no ambiguity

### 10.7 Regression Test Timestamp Handling

The `parse_usage_data()` function includes a `timestamp` field set to `datetime.now(timezone.utc).isoformat()`. This value is volatile — it changes on every call. The regression test (T300) strips the `timestamp` field from both the golden output and the actual output before comparison, ensuring the test is deterministic.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3 — `tools/claude-usage-scraper.py` with 4 code excerpts)
- [x] Every data structure has a concrete JSON/YAML example (Section 4 — `UsageRecord`, `AnsiStripResult`)
- [x] Every function has input/output examples with realistic values (Section 5 — all 7 functions)
- [x] Change instructions are diff-level specific (Section 6 — 5 diffs for scraper, complete files for new files)
- [x] Pattern references include file:line and are verified to exist (Section 7 — 3 patterns)
- [x] All imports are listed and verified (Section 8 — all stdlib + pytest)
- [x] Test mapping covers all LLD test scenarios (Section 9 — all 35 test IDs T010-T350)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #434 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #434 |
| Verdict | APPROVED |
| Date | 2026-02-26 |
| Iterations | 1 |
| Finalized | 2026-02-26T01:53:23Z |

### Review Feedback Summary

Approved with suggestions:
*   **Change 4 (Logic Replacement):** While the instruction to replace inline regexes "as appropriate" is acceptable given the context, providing a more explicit directive (e.g., "If `parse_usage_data` contains a loop iterating over lines to find usage data, replace the parsing logic within that loop with a call to `extract_usage_line` or replace the loop entirely with `parse_usage_block`") would slightly reduce implementation risk.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
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
  ... and 14 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  nodes/
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
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
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
#!/usr/bin/env python3
"""
Claude Code Usage Scraper

Automates Claude Code's TUI to extract usage quota data that isn't available
via any programmatic API.

Usage:
  poetry run python tools/claude-usage-scraper.py
  poetry run python tools/claude-usage-scraper.py --log /path/to/usage.log

Output:
  JSON to stdout with session, weekly_all, and weekly_sonnet usage percentages.

References:
  - GitHub Issue #8412: https://github.com/anthropics/claude-code/issues/8412
  - GitHub Issue #5621: https://github.com/anthropics/claude-code/issues/5621
"""
import json
import re
import sys
import time
import queue
import threading
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    import winpty
except ImportError:
    print(json.dumps({
        "status": "error",
        "error": "pywinpty not installed. Run: poetry add pywinpty",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }))
    sys.exit(1)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


class PtyReader:
    """Non-blocking PTY reader using a background thread."""

    def __init__(self, pty):
        self.pty = pty
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._reader_thread, daemon=True)
        self.thread.start()

    def _reader_thread(self):
        """Background thread that continuously reads from PTY."""
        while self.running and self.pty.isalive():
            try:
                chunk = self.pty.read(4096)
                if chunk:
                    self.queue.put(chunk)
            except EOFError:
                break
            except Exception:
                break

    def read(self, timeout: float = 1.0) -> str:
        """Read all available data with timeout."""
        result = ''
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                chunk = self.queue.get(timeout=0.1)
                result += chunk
            except queue.Empty:
                if result:
                    break
        return result

    def stop(self):
        self.running = False


def parse_usage_data(raw_output: str) -> dict:
    """Parse usage percentages and reset times from Claude Code /status output."""
    text = strip_ansi(raw_output)

    result = {
        "session": {"percent_used": None, "resets_at": None},
        "weekly_all": {"percent_used": None, "resets_at": None},
        "weekly_sonnet": {"percent_used": None, "resets_at": None}
    }

    # Session pattern - handles TUI box characters
    session_match = re.search(
        r'Current\s+session[^\d]*(\d+)%\s*used.*?Resets?\s+([^\n\r│]+)',
        text, re.IGNORECASE | re.DOTALL
    )
    if session_match:
        result["session"]["percent_used"] = int(session_match.group(1))
        result["session"]["resets_at"] = session_match.group(2).strip()

    # Weekly all models pattern
    weekly_all_match = re.search(
        r'Current\s+week\s*\(all\s+models?\)[^\d]*(\d+)%\s*used.*?Resets?\s+([^\n\r│]+)',
        text, re.IGNORECASE | re.DOTALL
    )
    if weekly_all_match:
        result["weekly_all"]["percent_used"] = int(weekly_all_match.group(1))
        result["weekly_all"]["resets_at"] = weekly_all_match.group(2).strip()

    # Weekly Sonnet only pattern - captures percentage and optional reset time
    weekly_sonnet_match = re.search(
        r'Current\s+week\s*\(Sonnet\s+only\)[^\d]*(\d+)%\s*used(?:.*?Resets?\s+([^\n\r│]+))?',
        text, re.IGNORECASE | re.DOTALL
    )
    if weekly_sonnet_match:
        result["weekly_sonnet"]["percent_used"] = int(weekly_sonnet_match.group(1))
        # Sonnet reset time may not be shown if 0% - capture if present
        if weekly_sonnet_match.group(2):
            result["weekly_sonnet"]["resets_at"] = weekly_sonnet_match.group(2).strip()

    return result


def scrape_usage(timeout: int = 30) -> dict:
    """
    Spawn Claude Code, navigate to /status Usage tab, and scrape the data.

    Returns dict with usage data or error information.
    """
    output_buffer = ""
    pty_process = None
    reader = None

    try:
        # Spawn Claude Code in a PTY with adequate dimensions
        pty_process = winpty.PtyProcess.spawn(['claude'], dimensions=(50, 150))

        # Create non-blocking reader
        reader = PtyReader(pty_process)

        # Wait for Claude to initialize (takes a few seconds)
        time.sleep(6)
        initial = reader.read(timeout=2.0)
        output_buffer += initial

        if not pty_process.isalive():
            return {
                "status": "error",
                "error": "Claude Code process exited unexpectedly",
                "raw_output": strip_ansi(output_buffer)
            }

        # Type /status command
        pty_process.write('/status')
        time.sleep(1)
        _ = reader.read(timeout=1.0)  # Discard autocomplete output

        # Press Escape to dismiss autocomplete
        pty_process.write('\x1b')
        time.sleep(0.5)
        _ = reader.read(timeout=0.5)

        # Press Enter to execute /status
        pty_process.write('\r')
        time.sleep(3)

        status_output = reader.read(timeout=3.0)
        output_buffer += status_output

        # Now we're on the Status tab. Tab twice to get to Usage tab
        # Status → Config → Usage
        pty_process.write('\t')
        time.sleep(1)
        _ = reader.read(timeout=1.0)

        pty_process.write('\t')
        time.sleep(2)

        usage_output = reader.read(timeout=2.0)
        output_buffer += usage_output

        # Parse the usage data
        usage_data = parse_usage_data(output_buffer)

        # Check if we got any data
        has_data = any(
            usage_data[key]["percent_used"] is not None
            for key in ["session", "weekly_all", "weekly_sonnet"]
        )

        if not has_data:
            return {
                "status": "error",
                "error": "Could not parse usage data from output",
                "raw_output": strip_ansi(output_buffer)[-2000:]
            }

        return {
            "status": "success",
            **usage_data
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "error": "Claude Code not found. Ensure 'claude' is in PATH."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "raw_output": strip_ansi(output_buffer)[-1000:] if output_buffer else None
        }
    finally:
        # Stop the reader thread
        if reader:
            reader.stop()

        # Clean up: exit Claude Code
        if pty_process and pty_process.isalive():
            try:
                pty_process.write('\x1b')  # Escape to close dialog
                time.sleep(0.3)
                pty_process.write('/exit\r')
                time.sleep(0.5)
                if pty_process.isalive():
                    pty_process.terminate()
            except Exception:
                try:
                    pty_process.terminate()
                except Exception:
                    pass


def append_to_log(log_path: Path, data: dict):
    """Append a NDJSON (newline-delimited JSON) log entry.

    Each line is a complete JSON object for easy parsing by log aggregators
    (Splunk, Datadog, etc.) and standard tools like jq.
    """
    # Ensure timestamp is present
    if "timestamp" not in data:
        data["timestamp"] = datetime.now(timezone.utc).isoformat()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Claude Code usage quota data via terminal automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  poetry run python tools/claude-usage-scraper.py
  poetry run python tools/claude-usage-scraper.py --log ~/Projects/claude-usage.log
  poetry run python tools/claude-usage-scraper.py --timeout 45
        """
    )
    parser.add_argument(
        "--log", "-l",
        default=None,
        help="Path to append NDJSON log entries (one JSON object per line)"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress JSON output to stdout (only write to log if specified)"
    )

    args = parser.parse_args()

    # Scrape usage data
    result = scrape_usage(timeout=args.timeout)

    # Add timestamp
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Append to log if specified
    if args.log:
        log_path = Path(args.log).expanduser()
        append_to_log(log_path, result)

    # Output JSON to stdout
    if not args.quiet:
        print(json.dumps(result, indent=2))

    # Exit with error code if scraping failed
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()

```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_434.py
"""Test file for Issue #434.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from tools.claude-usage-scraper import *  # noqa: F401, F403


# Unit Tests
# -----------

def test_t010():
    """
    `strip_ansi_codes()` | `"\033[32mGreen\033[0m"` | `"Green"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t010 works correctly
    assert False, 'TDD RED: test_t010 not implemented'


def test_t020():
    """
    `strip_ansi_codes()` | `"\033[1m\033[31mBold Red\033[0m"` | `"Bold
    Red"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'


def test_t030():
    """
    `strip_ansi_codes()` | `"plain text"` | `"plain text"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t030 works correctly
    assert False, 'TDD RED: test_t030 not implemented'


def test_t040():
    """
    `strip_ansi_codes()` | `""` | `""`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t040 works correctly
    assert False, 'TDD RED: test_t040 not implemented'


def test_t050():
    """
    `strip_ansi_codes()` | `"\033[2J\033[HText"` | `"Text"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t050 works correctly
    assert False, 'TDD RED: test_t050 not implemented'


def test_t060():
    """
    `parse_token_count()` | `"1234"` | `1234`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t060 works correctly
    assert False, 'TDD RED: test_t060 not implemented'


def test_t070():
    """
    `parse_token_count()` | `"1,234,567"` | `1234567`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t070 works correctly
    assert False, 'TDD RED: test_t070 not implemented'


def test_t080():
    """
    `parse_token_count()` | `" 500 "` | `500`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t080 works correctly
    assert False, 'TDD RED: test_t080 not implemented'


def test_t090():
    """
    `parse_token_count()` | `"0"` | `0`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t090 works correctly
    assert False, 'TDD RED: test_t090 not implemented'


def test_t100():
    """
    `parse_token_count()` | `"abc"` | Raises `ValueError`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t100 works correctly
    assert False, 'TDD RED: test_t100 not implemented'


def test_t110():
    """
    `parse_cost_value()` | `"$0.0042"` | `0.0042`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t110 works correctly
    assert False, 'TDD RED: test_t110 not implemented'


def test_t120():
    """
    `parse_cost_value()` | `"0.0042"` | `0.0042`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t120 works correctly
    assert False, 'TDD RED: test_t120 not implemented'


def test_t130():
    """
    `parse_cost_value()` | `"$0.00"` | `0.0`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t130 works correctly
    assert False, 'TDD RED: test_t130 not implemented'


def test_t140():
    """
    `parse_cost_value()` | `" $1.23 "` | `1.23`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t140 works correctly
    assert False, 'TDD RED: test_t140 not implemented'


def test_t150():
    """
    `parse_cost_value()` | `"free"` | Raises `ValueError`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t150 works correctly
    assert False, 'TDD RED: test_t150 not implemented'


def test_t160():
    """
    `extract_usage_line()` | `CLEAN_USAGE_LINE` fixture | `UsageRecord`
    with `session_id="abc123"`, `input_tokens=15234`, etc.
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t160 works correctly
    assert False, 'TDD RED: test_t160 not implemented'


def test_t170():
    """
    `extract_usage_line()` | `ANSI_USAGE_LINE` fixture | Same
    `UsageRecord` as T160
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t170 works correctly
    assert False, 'TDD RED: test_t170 not implemented'


def test_t180():
    """
    `extract_usage_line()` | `"Starting session..."` | `None`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t180 works correctly
    assert False, 'TDD RED: test_t180 not implemented'


def test_t190():
    """
    `extract_usage_line()` | `"abc123 claude-sonnet"` | `None`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t190 works correctly
    assert False, 'TDD RED: test_t190 not implemented'


def test_t200():
    """
    `extract_model_name()` | `"model: claude-sonnet-4-20250514"` |
    `"claude-sonnet-4-20250514"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t200 works correctly
    assert False, 'TDD RED: test_t200 not implemented'


def test_t210():
    """
    `extract_model_name()` | `"model: claude-opus-4-20250514"` |
    `"claude-opus-4-20250514"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t210 works correctly
    assert False, 'TDD RED: test_t210 not implemented'


def test_t220():
    """
    `extract_model_name()` | `"model: claude-haiku-3-20250514"` |
    `"claude-haiku-3-20250514"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t220 works correctly
    assert False, 'TDD RED: test_t220 not implemented'


def test_t230():
    """
    `extract_model_name()` | `"no model info here"` | `None`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t230 works correctly
    assert False, 'TDD RED: test_t230 not implemented'


def test_t240():
    """
    `extract_model_name()` | Two model strings in one text |
    `"claude-sonnet-4-20250514"` (first match)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t240 works correctly
    assert False, 'TDD RED: test_t240 not implemented'


def test_t250():
    """
    `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture | List of 2
    `UsageRecord`s
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t250 works correctly
    assert False, 'TDD RED: test_t250 not implemented'


def test_t260():
    """
    `parse_usage_block()` | `MIXED_BLOCK` fixture | List of 2 records
    (skips non-matching)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t260 works correctly
    assert False, 'TDD RED: test_t260 not implemented'


def test_t270():
    """
    `parse_usage_block()` | `""` | `[]`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t270 works correctly
    assert False, 'TDD RED: test_t270 not implemented'


def test_t280():
    """
    `parse_usage_block()` | `ANSI_FULL_BLOCK` fixture | List of 2 records
    (same as clean)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t280 works correctly
    assert False, 'TDD RED: test_t280 not implemented'


def test_t290():
    """
    `parse_usage_block()` | Single clean usage line | List of 1 record
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t290 works correctly
    assert False, 'TDD RED: test_t290 not implemented'


def test_t300():
    """
    `parse_usage_data()` | `golden_input.txt` content | Matches
    `golden_output.txt` (excluding volatile `timestamp` field)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t300 works correctly
    assert False, 'TDD RED: test_t300 not implemented'


def test_t310():
    """
    Module import | `importlib.util.spec_from_file_location` +
    `exec_module` | No stdout output
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t310 works correctly
    assert False, 'TDD RED: test_t310 not implemented'


def test_t320():
    """
    `strip_ansi_codes()` | `ANSI_USAGE_LINE` fixture |
    `ANSI_USAGE_LINE_EXPECTED_CLEAN`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t320 works correctly
    assert False, 'TDD RED: test_t320 not implemented'


def test_t330():
    """
    `parse_usage_block()` | `FULL_USAGE_BLOCK` fixture |
    `FULL_USAGE_BLOCK_EXPECTED` all fields match
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t330 works correctly
    assert False, 'TDD RED: test_t330 not implemented'


def test_t340():
    """
    All parsing functions | Various inputs with socket blocked | Zero
    `socket.connect` calls
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t340 works correctly
    assert False, 'TDD RED: test_t340 not implemented'


def test_t350():
    """
    All parsing functions | >10k char adversarial strings | Completes <
    100ms, correct result
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t350 works correctly
    assert False, 'TDD RED: test_t350 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### tests/fixtures/scraper/__init__.py (signatures)

```python
"""Test fixtures for Claude usage scraper tests.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing
"""
```

### tests/fixtures/scraper/ansi_samples.py (signatures)

```python
"""ANSI-encoded sample strings for Claude usage scraper parsing tests.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing

These fixtures provide ANSI escape sequence test data for validating
the strip_ansi_codes() function and ANSI-aware parsing pipeline.
"""

BASIC_SGR_GREEN = "\033[32mGreen text\033[0m"

BASIC_SGR_GREEN_EXPECTED = "Green text"

BASIC_SGR_RED = "\033[31mRed text\033[0m"

BASIC_SGR_RED_EXPECTED = "Red text"

BASIC_SGR_BOLD = "\033[1mBold text\033[0m"

BASIC_SGR_BOLD_EXPECTED = "Bold text"

NESTED_BOLD_RED = "\033[1m\033[31mBold Red\033[0m"

NESTED_BOLD_RED_EXPECTED = "Bold Red"

NESTED_MULTI = "\033[1m\033[4m\033[32mBold Underline Green\033[0m"

NESTED_MULTI_EXPECTED = "Bold Underline Green"

CURSOR_CLEAR_SCREEN = "\033[2J\033[HText after clear"

CURSOR_CLEAR_SCREEN_EXPECTED = "Text after clear"

CURSOR_MOVE_UP = "\033[3ALine after move up"

CURSOR_MOVE_UP_EXPECTED = "Line after move up"

CURSOR_POSITION = "\033[10;20HPositioned text"

CURSOR_POSITION_EXPECTED = "Positioned text"

PLAIN_TEXT = "This is plain text with no escape sequences"

PLAIN_TEXT_EXPECTED = "This is plain text with no escape sequences"

EMPTY_STRING = ""

EMPTY_STRING_EXPECTED = ""

ANSI_USAGE_LINE_EXPECTED_CLEAN = (
    "abc123  claude-sonnet-4-20250514  15,234 input  "
    "3,421 output  8,000 cache read  1,200 cache write  $0.0847"
)

LONG_ADVERSARIAL_PLAIN = "x" * 15000

LONG_ADVERSARIAL_ANSI_LIKE = "\033[" + "1;" * 5000 + "m" + "text" + "\033[0m"

LONG_ADVERSARIAL_TOKEN = "1" * 12000 + "abc"

LONG_ADVERSARIAL_COST = "$" + "9" * 11000
```

### tests/fixtures/scraper/usage_outputs.py (signatures)

```python
"""Sample Claude CLI usage output blocks for parsing tests.

Issue #434: Add Tests for claude-usage-scraper.py Regex Parsing

CLI Version: Claude Code CLI (circa 2026-02 output format)
Note: If the Claude CLI output format changes, update these fixtures
and document the new CLI version here.
"""

CLEAN_USAGE_LINE = (
    "abc123  claude-sonnet-4-20250514  15,234 input  "
    "3,421 output  8,000 cache read  1,200 cache write  $0.0847"
)

CLEAN_USAGE_LINE_2 = (
    "def456  claude-sonnet-4-20250514  22,100 input  "
    "5,000 output  10,000 cache read  2,000 cache write  $0.1200"
)

MIXED_BLOCK_EXPECTED_COUNT = 2

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

### tests/fixtures/scraper/golden_input.txt (signatures)

```python
=== Usage Summary ===
abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847
def456  claude-sonnet-4-20250514  22,100 input  5,000 output  10,000 cache read  2,000 cache write  $0.1200
Total: $0.2047
# ... (truncated, syntax error in original)

```

### tests/fixtures/scraper/golden_output.txt (full)

```python
{
  "session": {
    "percent_used": null,
    "resets_at": null
  },
  "weekly_all": {
    "percent_used": null,
    "resets_at": null
  },
  "weekly_sonnet": {
    "percent_used": null,
    "resets_at": null
  }
}
```

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
