# Implementation Request: tests/unit/test_gate/test_integration.py

## Task

Write the complete contents of `tests/unit/test_gate/test_integration.py`.

Change type: Add
Description: Integration tests for full workflow

## LLD Specification

# Implementation Spec: Hard Gate Wrapper for Skipped Test Enforcement (test-gate.py)

| Field | Value |
|-------|-------|
| Issue | #225 |
| LLD | `docs/lld/active/225-test-gate-hard-enforcement.md` |
| Generated | 2026-02-05 |
| Status | DRAFT |

## 1. Overview

Create a pytest wrapper script (`tools/test-gate.py`) that intercepts pytest output, detects skipped tests, and enforces audit block validation before allowing CI to pass. The wrapper runs pytest as a subprocess, parses verbose output for skips, and cross-references against a SKIPPED TEST AUDIT block in stdout or a `.skip-audit.md` file.

**Objective:** Programmatically enforce skipped test auditing in CI, blocking PRs with unaudited critical skips.

**Success Criteria:** All 9 requirements from LLD Section 3 met; ≥95% test coverage on new code; CI workflow updated to use wrapper.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tools/test_gate/__init__.py` | Add | Package init, version constant |
| 2 | `tools/test_gate/models.py` | Add | Data models (TypedDicts) |
| 3 | `tools/test_gate/parser.py` | Add | Pytest output parsing, subprocess execution |
| 4 | `tools/test_gate/auditor.py` | Add | Audit block detection, validation, matching |
| 5 | `tools/test-gate.py` | Add | CLI entry point |
| 6 | `tests/unit/test_gate/__init__.py` | Add | Test package init |
| 7 | `tests/unit/test_gate/test_parser.py` | Add | Parser unit tests |
| 8 | `tests/unit/test_gate/test_auditor.py` | Add | Auditor unit tests |
| 9 | `tests/unit/test_gate/test_integration.py` | Add | Integration tests for full workflow |
| 10 | `.github/workflows/ci.yml` | Modify | Replace direct pytest with test-gate.py wrapper |

**Implementation Order Rationale:** Models first (no dependencies), then parser (depends on models), then auditor (depends on models), then CLI entry point (depends on all), then tests (depend on implementation), finally CI workflow update (depends on working script).

## 3. Current State (for Modify/Delete files)

### 3.1 `.github/workflows/ci.yml`

**Relevant excerpt** (lines 1–55, complete file):

```yaml
# CI Workflow - Unit tests on every push/PR, integration tests on main
# Issues #325, #116

name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ hashFiles('poetry.lock') }}-v2
          restore-keys: |
            venv-${{ runner.os }}-

      - name: Install dependencies
        run: poetry install --no-interaction --with dev

      - name: Run unit tests with coverage
        run: poetry run pytest tests/unit/ -v --tb=short --cov=assemblyzero --cov-report=term-missing --cov-report=xml:coverage.xml
        env:
          LANGSMITH_TRACING: "false"

      - name: Run integration tests
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: poetry run pytest tests/integration/ -v --tb=short -m integration
        env:
          LANGSMITH_TRACING: "false"
          ASSEMBLYZERO_MOCK_MODE: "1"

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml
          retention-days: 30
```

**What changes:** The `Run unit tests with coverage` step is modified to invoke `tools/test-gate.py` instead of `pytest` directly. The `Run integration tests` step is similarly updated.

## 4. Data Structures

### 4.1 SkippedTest

**Definition:**

```python
class SkippedTest(TypedDict):
    """Represents a single skipped test from pytest output."""
    name: str
    reason: str
    line_number: int
    file_path: str
    is_critical: bool
```

**Concrete Example:**

```json
{
    "name": "tests/unit/test_auth.py::test_oauth_token_refresh",
    "reason": "Requires external OAuth provider",
    "line_number": 42,
    "file_path": "tests/unit/test_auth.py",
    "is_critical": true
}
```

**Second Example (non-critical):**

```json
{
    "name": "tests/unit/test_utils.py::test_deprecated_helper",
    "reason": "Deprecated feature, removal pending #180",
    "line_number": 15,
    "file_path": "tests/unit/test_utils.py",
    "is_critical": false
}
```

### 4.2 AuditEntry

**Definition:**

```python
class AuditEntry(TypedDict):
    """Represents a single entry in the audit block."""
    test_pattern: str
    status: str  # "VERIFIED", "UNVERIFIED", "EXPECTED"
    justification: str
    owner: str
    expires: str | None
```

**Concrete Example:**

```json
{
    "test_pattern": "tests/unit/test_auth.py::test_oauth_token_refresh",
    "status": "VERIFIED",
    "justification": "External OAuth provider not available in CI. Covered by integration tests.",
    "owner": "marty",
    "expires": "2026-06-01"
}
```

**Second Example (glob pattern):**

```json
{
    "test_pattern": "tests/unit/test_utils.py::test_deprecated_*",
    "status": "EXPECTED",
    "justification": "Deprecated features scheduled for removal in v0.3.0",
    "owner": "marty",
    "expires": null
}
```

### 4.3 AuditBlock

**Definition:**

```python
class AuditBlock(TypedDict):
    """Parsed SKIPPED TEST AUDIT block."""
    entries: list[AuditEntry]
    raw_text: str
    source: str  # "stdout" or "file"
```

**Concrete Example:**

```json
{
    "entries": [
        {
            "test_pattern": "tests/unit/test_auth.py::test_oauth_token_refresh",
            "status": "VERIFIED",
            "justification": "External OAuth provider not available in CI",
            "owner": "marty",
            "expires": "2026-06-01"
        }
    ],
    "raw_text": "<!-- SKIPPED TEST AUDIT -->\n| Test | Status | Justification | Owner | Expires |\n...",
    "source": "file"
}
```

### 4.4 GateResult

**Definition:**

```python
class GateResult(TypedDict):
    """Result of running the test gate."""
    passed: bool
    exit_code: int
    skipped_tests: list[SkippedTest]
    audit: AuditBlock | None
    unaudited: list[SkippedTest]
    unverified: list[SkippedTest]
    errors: list[str]
```

**Concrete Example (passing):**

```json
{
    "passed": true,
    "exit_code": 0,
    "skipped_tests": [
        {
            "name": "tests/unit/test_auth.py::test_oauth_token_refresh",
            "reason": "Requires external OAuth provider",
            "line_number": 42,
            "file_path": "tests/unit/test_auth.py",
            "is_critical": true
        }
    ],
    "audit": {
        "entries": [
            {
                "test_pattern": "tests/unit/test_auth.py::test_oauth_token_refresh",
                "status": "VERIFIED",
                "justification": "Covered by integration tests",
                "owner": "marty",
                "expires": null
            }
        ],
        "raw_text": "...",
        "source": "file"
    },
    "unaudited": [],
    "unverified": [],
    "errors": []
}
```

**Concrete Example (failing):**

```json
{
    "passed": false,
    "exit_code": 1,
    "skipped_tests": [
        {
            "name": "tests/unit/test_security.py::test_xss_prevention",
            "reason": "TODO: implement",
            "line_number": 88,
            "file_path": "tests/unit/test_security.py",
            "is_critical": true
        }
    ],
    "audit": null,
    "unaudited": [
        {
            "name": "tests/unit/test_security.py::test_xss_prevention",
            "reason": "TODO: implement",
            "line_number": 88,
            "file_path": "tests/unit/test_security.py",
            "is_critical": true
        }
    ],
    "unverified": [],
    "errors": ["No SKIPPED TEST AUDIT block found. Skipped tests require audit."]
}
```

## 5. Function Specifications

### 5.1 `main()`

**File:** `tools/test-gate.py`

**Signature:**

```python
def main(args: list[str] | None = None) -> int:
    """Main entry point - wraps pytest and enforces skip audit gate."""
    ...
```

**Input Example:**

```python
args = ["tests/unit/", "-v", "--tb=short", "--cov=assemblyzero"]
```

**Output Example:**

```python
0  # pytest passed and all skips audited
```

**Input Example (bypass):**

```python
args = ["tests/unit/", "--skip-gate-bypass", "Emergency hotfix for #500"]
```

**Output Example:**

```python
0  # pytest exit code passed through with WARNING logged
```

**Edge Cases:**
- `args=None` → reads from `sys.argv[1:]`
- `args=[]` → runs pytest with no arguments (just adds `-v`)
- `--skip-gate-bypass` without justification string → prints error, returns 2
- `--skip-gate-bypass ""` → prints error (empty justification), returns 2

### 5.2 `run_pytest()`

**File:** `tools/test_gate/parser.py`

**Signature:**

```python
def run_pytest(args: list[str], timeout: int = 1800) -> tuple[int, str, str]:
    """Execute pytest with given args, return (exit_code, stdout, stderr).
    
    Forwards SIGINT to the subprocess for clean Ctrl+C handling.
    """
    ...
```

**Input Example:**

```python
args = ["tests/unit/", "-v", "--tb=short"]
timeout = 1800
```

**Output Example:**

```python
(0, "===== 42 passed, 3 skipped in 12.5s =====\n...", "")
```

**Edge Cases:**
- Subprocess timeout → returns `(1, "", "pytest timed out after 1800 seconds")`
- `FileNotFoundError` (pytest not installed) → returns `(1, "", "pytest not found: ...")`
- SIGINT received → forwarded to subprocess, subprocess exit code returned

### 5.3 `ensure_verbose_flag()`

**File:** `tools/test_gate/parser.py`

**Signature:**

```python
def ensure_verbose_flag(args: list[str]) -> list[str]:
    """Ensure -v flag is present in args for skip detection. Returns new list (does not mutate input)."""
    ...
```

**Input Example:**

```python
args = ["tests/unit/", "--tb=short"]
```

**Output Example:**

```python
["tests/unit/", "--tb=short", "-v"]
```

**Input Example (already has verbose):**

```python
args = ["tests/unit/", "-vv", "--tb=short"]
```

**Output Example:**

```python
["tests/unit/", "-vv", "--tb=short"]  # unchanged
```

**Edge Cases:**
- `["-v"]` already present → returns copy unchanged
- `["--verbose"]` already present → returns copy unchanged
- `["-vv"]` already present → returns copy unchanged
- `["-vvv"]` already present → returns copy unchanged
- Empty list → returns `["-v"]`

### 5.4 `parse_skipped_tests()`

**File:** `tools/test_gate/parser.py`

**Signature:**

```python
def parse_skipped_tests(output: str) -> list[SkippedTest]:
    """Parse pytest verbose output for skipped test information.
    
    Matches lines like:
      SKIPPED [1] tests/test_foo.py:10: reason here
      tests/test_foo.py::test_bar SKIPPED (reason here)
    """
    ...
```

**Input Example:**

```python
output = """
tests/unit/test_auth.py::test_oauth_token_refresh SKIPPED (Requires external OAuth provider)
tests/unit/test_utils.py::test_deprecated_helper SKIPPED (Deprecated feature)
SKIPPED [1] tests/unit/test_payment.py:55: Payment gateway unavailable
"""
```

**Output Example:**

```python
[
    SkippedTest(
        name="tests/unit/test_auth.py::test_oauth_token_refresh",
        reason="Requires external OAuth provider",
        line_number=0,
        file_path="tests/unit/test_auth.py",
        is_critical=False,
    ),
    SkippedTest(
        name="tests/unit/test_utils.py::test_deprecated_helper",
        reason="Deprecated feature",
        line_number=0,
        file_path="tests/unit/test_utils.py",
        is_critical=False,
    ),
    SkippedTest(
        name="tests/unit/test_payment.py:55",
        reason="Payment gateway unavailable",
        line_number=55,
        file_path="tests/unit/test_payment.py",
        is_critical=False,
    ),
]
```

**Edge Cases:**
- No SKIPPED lines → returns `[]`
- Malformed line → skipped (logged as WARNING), doesn't crash
- Empty output → returns `[]`

### 5.5 `detect_critical_tests()`

**File:** `tools/test_gate/parser.py`

**Signature:**

```python
CRITICAL_KEYWORDS: list[str] = ["security", "auth", "payment", "critical"]

def detect_critical_tests(tests: list[SkippedTest]) -> list[SkippedTest]:
    """Return new list with is_critical set based on naming conventions.
    
    A test is marked critical if any CRITICAL_KEYWORDS appear in the
    test name (case-insensitive). Does not mutate input.
    """
    ...
```

**Input Example:**

```python
tests = [
    {"name": "tests/test_auth.py::test_oauth_refresh", "reason": "...", "line_number": 0, "file_path": "tests/test_auth.py", "is_critical": False},
    {"name": "tests/test_utils.py::test_format_string", "reason": "...", "line_number": 0, "file_path": "tests/test_utils.py", "is_critical": False},
]
```

**Output Example:**

```python
[
    {"name": "tests/test_auth.py::test_oauth_refresh", "reason": "...", "line_number": 0, "file_path": "tests/test_auth.py", "is_critical": True},  # "auth" keyword
    {"name": "tests/test_utils.py::test_format_string", "reason": "...", "line_number": 0, "file_path": "tests/test_utils.py", "is_critical": False},
]
```

**Edge Cases:**
- Empty list → returns `[]`
- Test already has `is_critical=True` → remains `True` (never downgraded)

### 5.6 `find_audit_block()`

**File:** `tools/test_gate/auditor.py`

**Signature:**

```python
def find_audit_block(output: str, audit_file: Path | None = None) -> AuditBlock | None:
    """Locate and parse SKIPPED TEST AUDIT block from output or file.
    
    Search order:
    1. audit_file parameter (if provided)
    2. .skip-audit.md in current directory
    3. stdout output
    
    Returns None if no audit block found.
    """
    ...
```

**Input Example (file):**

```python
output = "... pytest output ..."
audit_file = Path(".skip-audit.md")
```

Where `.skip-audit.md` contains:

```markdown
<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/unit/test_auth.py::test_oauth_token_refresh | VERIFIED | External provider not in CI | marty | 2026-06-01 |
| tests/unit/test_utils.py::test_deprecated_* | EXPECTED | Removal in v0.3.0 | marty | |
<!-- END SKIPPED TEST AUDIT -->
```

**Output Example:**

```python
{
    "entries": [
        {"test_pattern": "tests/unit/test_auth.py::test_oauth_token_refresh", "status": "VERIFIED", "justification": "External provider not in CI", "owner": "marty", "expires": "2026-06-01"},
        {"test_pattern": "tests/unit/test_utils.py::test_deprecated_*", "status": "EXPECTED", "justification": "Removal in v0.3.0", "owner": "marty", "expires": None},
    ],
    "raw_text": "<!-- SKIPPED TEST AUDIT -->\n...\n<!-- END SKIPPED TEST AUDIT -->",
    "source": "file",
}
```

**Edge Cases:**
- `audit_file` provided but doesn't exist → falls through to `.skip-audit.md` and stdout
- No audit block found anywhere → returns `None`
- Malformed audit block (missing closing tag) → logs WARNING, returns `None`

### 5.7 `parse_audit_block()`

**File:** `tools/test_gate/auditor.py`

**Signature:**

```python
def parse_audit_block(raw_block: str, source: str = "unknown") -> AuditBlock:
    """Parse raw audit block text into structured AuditBlock.
    
    Expects markdown table format between sentinel comments.
    """
    ...
```

**Input Example:**

```python
raw_block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | Not in CI | marty | 2026-06-01 |
<!-- END SKIPPED TEST AUDIT -->"""
source = "file"
```

**Output Example:**

```python
{
    "entries": [
        {"test_pattern": "tests/test_auth.py::test_oauth", "status": "VERIFIED", "justification": "Not in CI", "owner": "marty", "expires": "2026-06-01"},
    ],
    "raw_text": "<!-- SKIPPED TEST AUDIT -->...",
    "source": "file",
}
```

**Edge Cases:**
- Empty table (header only, no rows) → returns `AuditBlock` with `entries=[]`
- Extra whitespace in cells → stripped
- Missing `Expires` cell or empty → `expires=None`
- Missing `Owner` cell or empty → `owner=""`

### 5.8 `validate_audit()`

**File:** `tools/test_gate/auditor.py`

**Signature:**

```python
def validate_audit(
    skipped: list[SkippedTest],
    audit: AuditBlock | None,
) -> tuple[list[SkippedTest], list[SkippedTest]]:
    """Validate skipped tests against audit block.
    
    Returns (unaudited_tests, unverified_critical_tests).
    - unaudited: skipped tests with no matching audit entry
    - unverified_critical: critical tests matched to UNVERIFIED entries
    """
    ...
```

**Input Example:**

```python
skipped = [
    {"name": "tests/test_auth.py::test_oauth", "reason": "...", "line_number": 0, "file_path": "tests/test_auth.py", "is_critical": True},
    {"name": "tests/test_utils.py::test_helper", "reason": "...", "line_number": 0, "file_path": "tests/test_utils.py", "is_critical": False},
]
audit = {
    "entries": [
        {"test_pattern": "tests/test_auth.py::test_oauth", "status": "VERIFIED", "justification": "...", "owner": "marty", "expires": None},
    ],
    "raw_text": "...",
    "source": "file",
}
```

**Output Example:**

```python
(
    [{"name": "tests/test_utils.py::test_helper", ...}],  # unaudited
    [],  # no unverified critical
)
```

**Edge Cases:**
- `audit=None` → all skipped tests returned as unaudited, empty unverified list
- All tests matched → `([], [])`
- Critical test with `UNVERIFIED` status → appears in second list

### 5.9 `match_test_to_audit()`

**File:** `tools/test_gate/auditor.py`

**Signature:**

```python
def match_test_to_audit(test: SkippedTest, entry: AuditEntry) -> bool:
    """Check if a test matches an audit entry pattern.
    
    Supports:
    - Exact match: "tests/test_foo.py::test_bar"
    - Glob patterns: "tests/test_foo.py::test_*"
    - Directory patterns: "tests/unit/*"
    """
    ...
```

**Input Example (exact match):**

```python
test = {"name": "tests/test_auth.py::test_oauth", "reason": "...", "line_number": 0, "file_path": "tests/test_auth.py", "is_critical": False}
entry = {"test_pattern": "tests/test_auth.py::test_oauth", "status": "VERIFIED", "justification": "...", "owner": "marty", "expires": None}
```

**Output Example:**

```python
True
```

**Input Example (glob match):**

```python
test = {"name": "tests/test_auth.py::test_oauth_refresh", ...}
entry = {"test_pattern": "tests/test_auth.py::test_oauth_*", ...}
```

**Output Example:**

```python
True
```

**Input Example (no match):**

```python
test = {"name": "tests/test_utils.py::test_format", ...}
entry = {"test_pattern": "tests/test_auth.py::test_*", ...}
```

**Output Example:**

```python
False
```

**Edge Cases:**
- Pattern with `**` → treated as recursive glob
- Pattern is exact test name → exact string match (no glob)
- Empty pattern → never matches

## 6. Change Instructions

### 6.1 `tools/test_gate/__init__.py` (Add)

**Complete file contents:**

```python
"""test_gate - Pytest wrapper for skipped test audit enforcement.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

__version__ = "0.1.0"
```

### 6.2 `tools/test_gate/models.py` (Add)

**Complete file contents:**

```python
"""Data models for the test gate.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from typing import TypedDict


class SkippedTest(TypedDict):
    """Represents a single skipped test from pytest output."""

    name: str  # Full test path (e.g., tests/test_foo.py::test_bar)
    reason: str  # Skip reason from @pytest.mark.skip or skipif
    line_number: int  # Line in test file (0 if unknown)
    file_path: str  # Path to test file
    is_critical: bool  # Inferred from markers or naming


class AuditEntry(TypedDict):
    """Represents a single entry in the audit block."""

    test_pattern: str  # Glob or exact match pattern
    status: str  # "VERIFIED", "UNVERIFIED", or "EXPECTED"
    justification: str  # Why this skip is acceptable
    owner: str  # Who verified (may be empty)
    expires: str | None  # ISO date string or None


class AuditBlock(TypedDict):
    """Parsed SKIPPED TEST AUDIT block."""

    entries: list[AuditEntry]
    raw_text: str  # Original block text for error messages
    source: str  # "stdout" or "file"


class GateResult(TypedDict):
    """Result of running the test gate."""

    passed: bool
    exit_code: int
    skipped_tests: list[SkippedTest]
    audit: AuditBlock | None
    unaudited: list[SkippedTest]  # Skips without matching audit entries
    unverified: list[SkippedTest]  # Critical skips with UNVERIFIED status
    errors: list[str]  # Validation error messages
```

### 6.3 `tools/test_gate/parser.py` (Add)

**Complete file contents:**

```python
"""Pytest output parsing utilities.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from tools.test_gate.models import SkippedTest

# Keywords that indicate a critical test when found in the test name (case-insensitive)
CRITICAL_KEYWORDS: list[str] = ["security", "auth", "payment", "critical"]

# Regex patterns for pytest verbose skip output formats
# Format 1: "tests/test_foo.py::test_bar SKIPPED (reason)"
_PATTERN_INLINE = re.compile(
    r"^([\w/\\.\-]+\.py::[\w\[\]\-]+)\s+SKIPPED\s+\((.+?)\)\s*$",
    re.MULTILINE,
)
# Format 2: "SKIPPED [N] path/file.py:line: reason"
_PATTERN_BLOCK = re.compile(
    r"^SKIPPED\s+\[\d+\]\s+([\w/\\.\-]+\.py):(\d+):\s+(.+?)\s*$",
    re.MULTILINE,
)


def run_pytest(args: list[str], timeout: int = 1800) -> tuple[int, str, str]:
    """Execute pytest with given args, return (exit_code, stdout, stderr).

    Forwards SIGINT to the subprocess for clean Ctrl+C handling.
    Uses subprocess with list args (no shell=True) to prevent injection.
    """
    cmd = [sys.executable, "-m", "pytest"] + args

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Forward SIGINT to subprocess on Unix systems
        original_handler = None
        if hasattr(signal, "SIGINT"):
            def _forward_sigint(signum: int, frame: object) -> None:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)

            original_handler = signal.signal(signal.SIGINT, _forward_sigint)

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return (1, "", f"pytest timed out after {timeout} seconds")
        finally:
            if original_handler is not None:
                signal.signal(signal.SIGINT, original_handler)

        return (proc.returncode, stdout, stderr)

    except FileNotFoundError as exc:
        return (1, "", f"pytest not found: {exc}")


def ensure_verbose_flag(args: list[str]) -> list[str]:
    """Ensure -v flag is present in args for skip detection.

    Returns a new list (does not mutate input). If any verbose flag
    (-v, -vv, -vvv, --verbose) is already present, returns a copy unchanged.
    """
    new_args = list(args)

    for arg in new_args:
        # Check for -v, -vv, -vvv, etc.
        if arg == "--verbose":
            return new_args
        if re.match(r"^-v+$", arg):
            return new_args

    new_args.append("-v")
    return new_args


def parse_skipped_tests(output: str) -> list[SkippedTest]:
    """Parse pytest verbose output for skipped test information.

    Handles two common pytest verbose output formats:
    1. "tests/test_foo.py::test_bar SKIPPED (reason)"
    2. "SKIPPED [N] tests/test_foo.py:line: reason"
    """
    results: list[SkippedTest] = []

    # Pattern 1: inline SKIPPED
    for match in _PATTERN_INLINE.finditer(output):
        test_name = match.group(1)
        reason = match.group(2)
        # Extract file path from test name (before ::)
        file_path = test_name.split("::")[0] if "::" in test_name else test_name
        results.append(
            SkippedTest(
                name=test_name,
                reason=reason,
                line_number=0,
                file_path=file_path,
                is_critical=False,
            )
        )

    # Pattern 2: block SKIPPED
    for match in _PATTERN_BLOCK.finditer(output):
        file_path = match.group(1)
        line_number = int(match.group(2))
        reason = match.group(3)
        test_name = f"{file_path}:{line_number}"
        results.append(
            SkippedTest(
                name=test_name,
                reason=reason,
                line_number=line_number,
                file_path=file_path,
                is_critical=False,
            )
        )

    return results


def detect_critical_tests(tests: list[SkippedTest]) -> list[SkippedTest]:
    """Return new list with is_critical set based on naming conventions.

    A test is marked critical if any CRITICAL_KEYWORDS appear in the
    test name (case-insensitive). Does not mutate input list.
    Tests already marked critical remain critical.
    """
    results: list[SkippedTest] = []
    for test in tests:
        name_lower = test["name"].lower()
        is_critical = test["is_critical"] or any(
            kw in name_lower for kw in CRITICAL_KEYWORDS
        )
        results.append(
            SkippedTest(
                name=test["name"],
                reason=test["reason"],
                line_number=test["line_number"],
                file_path=test["file_path"],
                is_critical=is_critical,
            )
        )
    return results
```

### 6.4 `tools/test_gate/auditor.py` (Add)

**Complete file contents:**

```python
"""Audit block detection and validation.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

from tools.test_gate.models import AuditBlock, AuditEntry, SkippedTest

# Sentinel markers for audit blocks
_AUDIT_START = "<!-- SKIPPED TEST AUDIT -->"
_AUDIT_END = "<!-- END SKIPPED TEST AUDIT -->"

# Regex for parsing a markdown table row (pipe-delimited)
_TABLE_ROW = re.compile(
    r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|$"
)


def find_audit_block(
    output: str, audit_file: Path | None = None
) -> AuditBlock | None:
    """Locate and parse SKIPPED TEST AUDIT block from file or output.

    Search order:
    1. audit_file parameter (if provided and exists)
    2. .skip-audit.md in current directory
    3. stdout output

    Returns None if no audit block found anywhere.
    """
    # 1. Explicit audit file
    if audit_file is not None and audit_file.is_file():
        content = audit_file.read_text(encoding="utf-8")
        block = _extract_audit_text(content)
        if block is not None:
            return parse_audit_block(block, source="file")

    # 2. Default .skip-audit.md
    default_path = Path(".skip-audit.md")
    if default_path.is_file():
        content = default_path.read_text(encoding="utf-8")
        block = _extract_audit_text(content)
        if block is not None:
            return parse_audit_block(block, source="file")

    # 3. stdout
    block = _extract_audit_text(output)
    if block is not None:
        return parse_audit_block(block, source="stdout")

    return None


def _extract_audit_text(text: str) -> str | None:
    """Extract raw audit block text between sentinel markers.

    Returns None if markers not found or block is malformed.
    """
    start_idx = text.find(_AUDIT_START)
    if start_idx == -1:
        return None

    end_idx = text.find(_AUDIT_END, start_idx)
    if end_idx == -1:
        print(
            "WARNING: Found SKIPPED TEST AUDIT start marker but no end marker.",
            file=sys.stderr,
        )
        return None

    return text[start_idx : end_idx + len(_AUDIT_END)]


def parse_audit_block(raw_block: str, source: str = "unknown") -> AuditBlock:
    """Parse raw audit block text into structured AuditBlock.

    Expects markdown table format:
    | Test | Status | Justification | Owner | Expires |
    |------|--------|---------------|-------|---------|
    | pattern | VERIFIED | reason | owner | date |
    """
    entries: list[AuditEntry] = []

    lines = raw_block.strip().splitlines()
    header_seen = False
    separator_seen = False

    for line in lines:
        stripped = line.strip()

        # Skip sentinel markers
        if stripped.startswith("<!--"):
            continue

        # Skip empty lines
        if not stripped:
            continue

        # Detect header row (contains "Test" and "Status")
        if not header_seen and "Test" in stripped and "Status" in stripped:
            header_seen = True
            continue

        # Detect separator row (all dashes and pipes)
        if header_seen and not separator_seen and re.match(r"^[\|\s\-:]+$", stripped):
            separator_seen = True
            continue

        # Parse data rows
        if header_seen and separator_seen:
            match = _TABLE_ROW.match(stripped)
            if match:
                test_pattern = match.group(1).strip()
                status = match.group(2).strip().upper()
                justification = match.group(3).strip()
                owner = match.group(4).strip()
                expires_raw = match.group(5).strip()
                expires = expires_raw if expires_raw else None

                entries.append(
                    AuditEntry(
                        test_pattern=test_pattern,
                        status=status,
                        justification=justification,
                        owner=owner,
                        expires=expires,
                    )
                )

    return AuditBlock(
        entries=entries,
        raw_text=raw_block,
        source=source,
    )


def validate_audit(
    skipped: list[SkippedTest],
    audit: AuditBlock | None,
) -> tuple[list[SkippedTest], list[SkippedTest]]:
    """Validate skipped tests against audit block.

    Returns (unaudited_tests, unverified_critical_tests).
    - unaudited: skipped tests with no matching audit entry
    - unverified_critical: critical tests matched to UNVERIFIED entries
    """
    if audit is None:
        return (list(skipped), [])

    unaudited: list[SkippedTest] = []
    unverified_critical: list[SkippedTest] = []

    for test in skipped:
        matched_entry: AuditEntry | None = None
        for entry in audit["entries"]:
            if match_test_to_audit(test, entry):
                matched_entry = entry
                break

        if matched_entry is None:
            unaudited.append(test)
        elif test["is_critical"] and matched_entry["status"] == "UNVERIFIED":
            unverified_critical.append(test)

    return (unaudited, unverified_critical)


def match_test_to_audit(test: SkippedTest, entry: AuditEntry) -> bool:
    """Check if a test matches an audit entry pattern.

    Supports:
    - Exact match: "tests/test_foo.py::test_bar"
    - Glob patterns with fnmatch: "tests/test_foo.py::test_*"
    - Directory patterns: "tests/unit/*"
    """
    pattern = entry["test_pattern"]
    test_name = test["name"]

    if not pattern:
        return False

    # Exact match first (fast path)
    if test_name == pattern:
        return True

    # Glob match
    return fnmatch.fnmatch(test_name, pattern)
```

### 6.5 `tools/test-gate.py` (Add)

**Complete file contents:**

```python
#!/usr/bin/env python3
"""Pytest wrapper that enforces skipped test auditing.

Issue #225: Hard gate wrapper for skipped test enforcement.

Usage:
    python tools/test-gate.py [pytest-args...] [--audit-file PATH] [--strict] [--skip-gate-bypass "reason"]

Examples:
    python tools/test-gate.py tests/unit/ -v --tb=short
    python tools/test-gate.py tests/ --audit-file .skip-audit.md
    python tools/test-gate.py tests/ --skip-gate-bypass "Emergency hotfix for #500"
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the project root is on sys.path so `tools.test_gate` resolves
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.test_gate.auditor import find_audit_block, validate_audit
from tools.test_gate.parser import (
    detect_critical_tests,
    ensure_verbose_flag,
    parse_skipped_tests,
    run_pytest,
)


def _parse_gate_args(
    args: list[str],
) -> tuple[list[str], Path | None, bool, str | None]:
    """Separate gate-specific flags from pytest args.

    Returns (pytest_args, audit_file, strict, bypass_reason).
    """
    pytest_args: list[str] = []
    audit_file: Path | None = None
    strict: bool = False
    bypass_reason: str | None = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--audit-file":
            if i + 1 < len(args):
                audit_file = Path(args[i + 1])
                i += 2
                continue
            else:
                print("ERROR: --audit-file requires a path argument", file=sys.stderr)
                sys.exit(2)

        elif arg == "--strict":
            strict = True
            i += 1
            continue

        elif arg == "--skip-gate-bypass":
            if i + 1 < len(args):
                bypass_reason = args[i + 1]
                i += 2
                continue
            else:
                print(
                    "ERROR: --skip-gate-bypass requires a justification string",
                    file=sys.stderr,
                )
                sys.exit(2)

        pytest_args.append(arg)
        i += 1

    return (pytest_args, audit_file, strict, bypass_reason)


def main(args: list[str] | None = None) -> int:
    """Main entry point - wraps pytest and enforces skip audit gate."""
    if args is None:
        args = sys.argv[1:]

    pytest_args, audit_file, strict, bypass_reason = _parse_gate_args(list(args))

    # Validate bypass reason if provided
    if bypass_reason is not None:
        if not bypass_reason.strip():
            print(
                "ERROR: --skip-gate-bypass requires a non-empty justification string",
                file=sys.stderr,
            )
            return 2

    # Ensure verbose flag for skip detection
    pytest_args = ensure_verbose_flag(pytest_args)

    # Run pytest
    exit_code, stdout, stderr = run_pytest(pytest_args)

    # Print pytest output through
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)

    # Parse skipped tests
    skipped = parse_skipped_tests(stdout)
    skipped = detect_critical_tests(skipped)

    # If no skips, return pytest exit code directly
    if not skipped:
        return exit_code

    # Handle bypass
    if bypass_reason is not None:
        timestamp = datetime.now(timezone.utc).isoformat()
        print(
            f"\nWARNING: Test gate bypassed at {timestamp}",
            file=sys.stderr,
        )
        print(
            f"WARNING: Bypass reason: {bypass_reason}",
            file=sys.stderr,
        )
        print(
            f"WARNING: {len(skipped)} skipped test(s) were NOT audited",
            file=sys.stderr,
        )
        return exit_code

    # Find audit block
    audit = find_audit_block(stdout, audit_file=audit_file)

    if audit is None:
        print("\n" + "=" * 60, file=sys.stderr)
        print("TEST GATE FAILED: No SKIPPED TEST AUDIT block found", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"\n{len(skipped)} skipped test(s) require an audit block.",
            file=sys.stderr,
        )
        print(
            "\nCreate a .skip-audit.md file with the following format:",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print("  <!-- SKIPPED TEST AUDIT -->", file=sys.stderr)
        print(
            "  | Test | Status | Justification | Owner | Expires |",
            file=sys.stderr,
        )
        print(
            "  |------|--------|---------------|-------|---------|",
            file=sys.stderr,
        )
        for test in skipped:
            print(
                f"  | {test['name']} | VERIFIED | TODO | TODO | |",
                file=sys.stderr,
            )
        print("  <!-- END SKIPPED TEST AUDIT -->", file=sys.stderr)
        print(
            "\nOr use --skip-gate-bypass \"reason\" for emergencies.",
            file=sys.stderr,
        )
        return 1

    # Validate audit
    unaudited, unverified = validate_audit(skipped, audit)

    if unaudited:
        print("\n" + "=" * 60, file=sys.stderr)
        print("TEST GATE FAILED: Unaudited skipped tests", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            f"\n{len(unaudited)} skipped test(s) have no matching audit entry:\n",
            file=sys.stderr,
        )
        for test in unaudited:
            critical_tag = " [CRITICAL]" if test["is_critical"] else ""
            print(
                f"  ✗ {test['name']}{critical_tag}",
                file=sys.stderr,
            )
            print(f"    Reason: {test['reason']}", file=sys.stderr)
        print(
            "\nAdd entries to your audit block for these tests.",
            file=sys.stderr,
        )
        return 1

    if unverified:
        print("\n" + "=" * 60, file=sys.stderr)
        print(
            "TEST GATE FAILED: Unverified critical skipped tests",
            file=sys.stderr,
        )
        print("=" * 60, file=sys.stderr)
        print(
            f"\n{len(unverified)} critical test(s) have UNVERIFIED status:\n",
            file=sys.stderr,
        )
        for test in unverified:
            print(f"  ✗ {test['name']} [CRITICAL]", file=sys.stderr)
            print(f"    Reason: {test['reason']}", file=sys.stderr)
        print(
            "\nChange status to VERIFIED or EXPECTED after review.",
            file=sys.stderr,
        )
        return 1

    # Gate passed
    print(f"\n✓ Test gate passed: {len(skipped)} skip(s) audited", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

### 6.6 `tests/unit/test_gate/__init__.py` (Add)

**Complete file contents:**

```python
"""Test package for tools/test_gate.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""
```

### 6.7 `tests/unit/test_gate/test_parser.py` (Add)

**Complete file contents:**

```python
"""Unit tests for tools/test_gate/parser.py.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.test_gate.models import SkippedTest
from tools.test_gate.parser import (
    CRITICAL_KEYWORDS,
    detect_critical_tests,
    ensure_verbose_flag,
    parse_skipped_tests,
    run_pytest,
)


# --- T025: test_auto_add_verbose_flag ---


class TestEnsureVerboseFlag:
    """Tests for ensure_verbose_flag()."""

    def test_adds_v_when_missing(self) -> None:
        """T025: -v is added when no verbose flag is present."""
        result = ensure_verbose_flag(["tests/unit/", "--tb=short"])
        assert "-v" in result
        assert result == ["tests/unit/", "--tb=short", "-v"]

    def test_does_not_add_when_v_present(self) -> None:
        """Verbose flag already present as -v."""
        result = ensure_verbose_flag(["tests/", "-v"])
        assert result == ["tests/", "-v"]
        assert result.count("-v") == 1

    def test_does_not_add_when_vv_present(self) -> None:
        """Verbose flag already present as -vv."""
        result = ensure_verbose_flag(["-vv", "tests/"])
        assert result == ["-vv", "tests/"]
        assert "-v" not in [a for a in result if a == "-v"]

    def test_does_not_add_when_verbose_present(self) -> None:
        """Verbose flag already present as --verbose."""
        result = ensure_verbose_flag(["--verbose", "tests/"])
        assert result == ["--verbose", "tests/"]

    def test_empty_list_adds_v(self) -> None:
        """Empty args list gets -v added."""
        result = ensure_verbose_flag([])
        assert result == ["-v"]

    def test_does_not_mutate_input(self) -> None:
        """Input list is not mutated."""
        original = ["tests/", "--tb=short"]
        original_copy = list(original)
        ensure_verbose_flag(original)
        assert original == original_copy


# --- T030, T040: test_parse_skipped ---


class TestParseSkippedTests:
    """Tests for parse_skipped_tests()."""

    def test_parse_inline_skip_format(self) -> None:
        """T030: Parse 'test_name SKIPPED (reason)' format."""
        output = "tests/unit/test_auth.py::test_oauth SKIPPED (Requires provider)\n"
        result = parse_skipped_tests(output)
        assert len(result) == 1
        assert result[0]["name"] == "tests/unit/test_auth.py::test_oauth"
        assert result[0]["reason"] == "Requires provider"
        assert result[0]["file_path"] == "tests/unit/test_auth.py"
        assert result[0]["line_number"] == 0
        assert result[0]["is_critical"] is False

    def test_parse_block_skip_format(self) -> None:
        """T030: Parse 'SKIPPED [N] file:line: reason' format."""
        output = "SKIPPED [1] tests/unit/test_payment.py:55: Gateway unavailable\n"
        result = parse_skipped_tests(output)
        assert len(result) == 1
        assert result[0]["file_path"] == "tests/unit/test_payment.py"
        assert result[0]["line_number"] == 55
        assert result[0]["reason"] == "Gateway unavailable"

    def test_parse_multiple_skips(self) -> None:
        """T040: Multiple skipped tests are all captured."""
        output = (
            "tests/test_a.py::test_one SKIPPED (reason one)\n"
            "tests/test_b.py::test_two SKIPPED (reason two)\n"
            "SKIPPED [1] tests/test_c.py:10: reason three\n"
        )
        result = parse_skipped_tests(output)
        assert len(result) == 3

    def test_parse_no_skips(self) -> None:
        """T150: No SKIPPED lines returns empty list."""
        output = "tests/test_a.py::test_one PASSED\n===== 1 passed =====\n"
        result = parse_skipped_tests(output)
        assert result == []

    def test_parse_empty_output(self) -> None:
        """Edge case: empty string returns empty list."""
        assert parse_skipped_tests("") == []

    def test_parse_mixed_output(self) -> None:
        """Mixed passing and skipped output."""
        output = (
            "tests/test_a.py::test_pass PASSED\n"
            "tests/test_a.py::test_skip SKIPPED (some reason)\n"
            "tests/test_a.py::test_fail FAILED\n"
        )
        result = parse_skipped_tests(output)
        assert len(result) == 1
        assert result[0]["name"] == "tests/test_a.py::test_skip"


# --- T050, T060: test_detect_critical ---


class TestDetectCriticalTests:
    """Tests for detect_critical_tests()."""

    def test_detect_by_auth_keyword(self) -> None:
        """T060: 'auth' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_auth.py::test_oauth",
                reason="r",
                line_number=0,
                file_path="tests/test_auth.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_detect_by_security_keyword(self) -> None:
        """T060: 'security' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_security.py::test_xss",
                reason="r",
                line_number=0,
                file_path="tests/test_security.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_detect_by_payment_keyword(self) -> None:
        """T060: 'payment' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_payment.py::test_charge",
                reason="r",
                line_number=0,
                file_path="tests/test_payment.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_detect_by_critical_keyword(self) -> None:
        """T050: 'critical' in name triggers critical."""
        tests = [
            SkippedTest(
                name="tests/test_core.py::test_critical_path",
                reason="r",
                line_number=0,
                file_path="tests/test_core.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_non_critical_unchanged(self) -> None:
        """Non-critical test stays non-critical."""
        tests = [
            SkippedTest(
                name="tests/test_utils.py::test_format",
                reason="r",
                line_number=0,
                file_path="tests/test_utils.py",
                is_critical=False,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is False

    def test_already_critical_stays_critical(self) -> None:
        """Test already marked critical is not downgraded."""
        tests = [
            SkippedTest(
                name="tests/test_utils.py::test_format",
                reason="r",
                line_number=0,
                file_path="tests/test_utils.py",
                is_critical=True,
            )
        ]
        result = detect_critical_tests(tests)
        assert result[0]["is_critical"] is True

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        assert detect_critical_tests([]) == []

    def test_does_not_mutate_input(self) -> None:
        """Input list is not mutated."""
        tests = [
            SkippedTest(
                name="tests/test_auth.py::test_x",
                reason="r",
                line_number=0,
                file_path="tests/test_auth.py",
                is_critical=False,
            )
        ]
        detect_critical_tests(tests)
        assert tests[0]["is_critical"] is False


# --- T010: test_wrapper_passes_through_args ---


class TestRunPytest:
    """Tests for run_pytest()."""

    @patch("tools.test_gate.parser.subprocess.Popen")
    def test_passes_through_args(self, mock_popen: MagicMock) -> None:
        """T010: All pytest args forwarded unchanged to subprocess."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("output", "")
        mock_proc.returncode = 0
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        run_pytest(["tests/unit/", "-v", "-x"])

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        # cmd should be [sys.executable, "-m", "pytest", "tests/unit/", "-v", "-x"]
        assert cmd[2] == "pytest"
        assert "tests/unit/" in cmd
        assert "-v" in cmd
        assert "-x" in cmd

    @patch("tools.test_gate.parser.subprocess.Popen")
    def test_preserves_exit_code(self, mock_popen: MagicMock) -> None:
        """T020: Exit code from pytest is preserved."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = ("", "")
        mock_proc.returncode = 1
        mock_proc.poll.return_value = 1
        mock_popen.return_value = mock_proc

        exit_code, _, _ = run_pytest(["tests/"])
        assert exit_code == 1

    @patch("tools.test_gate.parser.subprocess.Popen")
    def test_timeout_returns_error(self, mock_popen: MagicMock) -> None:
        """Timeout produces exit code 1 and error message."""
        import subprocess as sp

        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = sp.TimeoutExpired(cmd="pytest", timeout=5)
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        exit_code, stdout, stderr = run_pytest(["tests/"], timeout=5)
        assert exit_code == 1
        assert "timed out" in stderr

    @patch(
        "tools.test_gate.parser.subprocess.Popen",
        side_effect=FileNotFoundError("not found"),
    )
    def test_file_not_found_returns_error(self, mock_popen: MagicMock) -> None:
        """Missing pytest returns error."""
        exit_code, stdout, stderr = run_pytest(["tests/"])
        assert exit_code == 1
        assert "not found" in stderr
```

### 6.8 `tests/unit/test_gate/test_auditor.py` (Add)

**Complete file contents:**

```python
"""Unit tests for tools/test_gate/auditor.py.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.test_gate.auditor import (
    find_audit_block,
    match_test_to_audit,
    parse_audit_block,
    validate_audit,
)
from tools.test_gate.models import AuditBlock, AuditEntry, SkippedTest


# --- Sample data ---

SAMPLE_AUDIT_BLOCK = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider not in CI | marty | 2026-06-01 |
| tests/test_utils.py::test_deprecated_* | EXPECTED | Removal in v0.3.0 | marty | |
<!-- END SKIPPED TEST AUDIT -->"""

SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_security.py::test_xss | UNVERIFIED | Needs review | | |
<!-- END SKIPPED TEST AUDIT -->"""


def _make_skipped(
    name: str,
    reason: str = "test reason",
    is_critical: bool = False,
) -> SkippedTest:
    """Helper to create SkippedTest instances."""
    file_path = name.split("::")[0] if "::" in name else name
    return SkippedTest(
        name=name,
        reason=reason,
        line_number=0,
        file_path=file_path,
        is_critical=is_critical,
    )


# --- T070: test_find_audit_stdout ---


class TestFindAuditBlock:
    """Tests for find_audit_block()."""

    def test_find_in_stdout(self) -> None:
        """T070: Audit block found in pytest stdout output."""
        output = f"some output\n{SAMPLE_AUDIT_BLOCK}\nmore output"
        result = find_audit_block(output)
        assert result is not None
        assert result["source"] == "stdout"
        assert len(result["entries"]) == 2

    def test_find_in_file(self, tmp_path: Path) -> None:
        """T080: Audit block found in external file."""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(SAMPLE_AUDIT_BLOCK)

        result = find_audit_block("no audit here", audit_file=audit_file)
        assert result is not None
        assert result["source"] == "file"
        assert len(result["entries"]) == 2

    def test_find_in_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T080: Audit block found in default .skip-audit.md."""
        monkeypatch.chdir(tmp_path)
        default_file = tmp_path / ".skip-audit.md"
        default_file.write_text(SAMPLE_AUDIT_BLOCK)

        result = find_audit_block("no audit here")
        assert result is not None
        assert result["source"] == "file"

    def test_file_takes_priority_over_stdout(self, tmp_path: Path) -> None:
        """Explicit file is checked before stdout."""
        audit_file = tmp_path / "custom-audit.md"
        audit_file.write_text(SAMPLE_AUDIT_BLOCK)

        # stdout also has an audit block but file should win
        result = find_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, audit_file=audit_file
        )
        assert result is not None
        assert result["source"] == "file"
        assert len(result["entries"]) == 2  # from file, not 1 from stdout

    def test_returns_none_when_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No audit block anywhere returns None."""
        monkeypatch.chdir(tmp_path)
        result = find_audit_block("no audit block here")
        assert result is None

    def test_malformed_block_no_end_marker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing end marker returns None with warning."""
        monkeypatch.chdir(tmp_path)
        malformed = "<!-- SKIPPED TEST AUDIT -->\n| Test | Status |\nno end"
        result = find_audit_block(malformed)
        assert result is None

    def test_nonexistent_audit_file_falls_through(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Nonexistent audit file falls through to other sources."""
        monkeypatch.chdir(tmp_path)
        result = find_audit_block(
            SAMPLE_AUDIT_BLOCK,
            audit_file=Path("/nonexistent/path.md"),
        )
        assert result is not None
        assert result["source"] == "stdout"


# --- T090: test_validate_audit_match ---


class TestParseAuditBlock:
    """Tests for parse_audit_block()."""

    def test_parse_standard_block(self) -> None:
        """Parses a well-formed audit block."""
        result = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")
        assert len(result["entries"]) == 2
        assert result["entries"][0]["test_pattern"] == "tests/test_auth.py::test_oauth"
        assert result["entries"][0]["status"] == "VERIFIED"
        assert result["entries"][0]["justification"] == "External provider not in CI"
        assert result["entries"][0]["owner"] == "marty"
        assert result["entries"][0]["expires"] == "2026-06-01"
        assert result["entries"][1]["expires"] is None
        assert result["source"] == "file"

    def test_parse_empty_table(self) -> None:
        """Table with header only returns empty entries."""
        block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
<!-- END SKIPPED TEST AUDIT -->"""
        result = parse_audit_block(block)
        assert result["entries"] == []

    def test_parse_strips_whitespace(self) -> None:
        """Extra whitespace in cells is stripped."""
        block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
|  tests/test_a.py::test_x  |  VERIFIED  |  some reason  |  owner  |  2026-01-01  |
<!-- END SKIPPED TEST AUDIT -->"""
        result = parse_audit_block(block)
        assert result["entries"][0]["test_pattern"] == "tests/test_a.py::test_x"
        assert result["entries"][0]["status"] == "VERIFIED"
        assert result["entries"][0]["owner"] == "owner"


class TestMatchTestToAudit:
    """Tests for match_test_to_audit()."""

    def test_exact_match(self) -> None:
        """T090: Exact test name matches exact pattern."""
        test = _make_skipped("tests/test_auth.py::test_oauth")
        entry = AuditEntry(
            test_pattern="tests/test_auth.py::test_oauth",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True

    def test_glob_match(self) -> None:
        """T090: Glob pattern matches test name."""
        test = _make_skipped("tests/test_utils.py::test_deprecated_helper")
        entry = AuditEntry(
            test_pattern="tests/test_utils.py::test_deprecated_*",
            status="EXPECTED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True

    def test_no_match(self) -> None:
        """Non-matching pattern returns False."""
        test = _make_skipped("tests/test_utils.py::test_format")
        entry = AuditEntry(
            test_pattern="tests/test_auth.py::test_*",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is False

    def test_empty_pattern_no_match(self) -> None:
        """Empty pattern never matches."""
        test = _make_skipped("tests/test_a.py::test_x")
        entry = AuditEntry(
            test_pattern="",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is False

    def test_directory_glob(self) -> None:
        """Directory-level glob pattern."""
        test = _make_skipped("tests/unit/test_auth.py::test_oauth")
        entry = AuditEntry(
            test_pattern="tests/unit/*",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True


# --- T100, T110, T120, T130: validation tests ---


class TestValidateAudit:
    """Tests for validate_audit()."""

    def test_all_audited_passes(self) -> None:
        """T130: All skipped tests have matching audit entries."""
        skipped = [_make_skipped("tests/test_auth.py::test_oauth")]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []

    def test_missing_audit_all_unaudited(self) -> None:
        """T100: No audit block means all tests are unaudited."""
        skipped = [_make_skipped("tests/test_a.py::test_x")]
        unaudited, unverified = validate_audit(skipped, None)
        assert len(unaudited) == 1
        assert unverified == []

    def test_unaudited_test_detected(self) -> None:
        """T110: Test without matching entry is unaudited."""
        skipped = [
            _make_skipped("tests/test_auth.py::test_oauth"),
            _make_skipped("tests/test_new.py::test_something"),  # not in audit
        ]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert len(unaudited) == 1
        assert unaudited[0]["name"] == "tests/test_new.py::test_something"

    def test_unverified_critical_detected(self) -> None:
        """T120: Critical test with UNVERIFIED status is flagged."""
        skipped = [
            _make_skipped(
                "tests/test_security.py::test_xss",
                is_critical=True,
            )
        ]
        audit = parse_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, source="file"
        )

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert len(unverified) == 1
        assert unverified[0]["name"] == "tests/test_security.py::test_xss"

    def test_non_critical_unverified_ok(self) -> None:
        """Non-critical test with UNVERIFIED status passes."""
        skipped = [
            _make_skipped(
                "tests/test_security.py::test_xss",
                is_critical=False,  # not critical
            )
        ]
        audit = parse_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, source="file"
        )

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []

    def test_glob_pattern_covers_test(self) -> None:
        """Glob pattern in audit covers matching tests."""
        skipped = [
            _make_skipped("tests/test_utils.py::test_deprecated_foo"),
            _make_skipped("tests/test_utils.py::test_deprecated_bar"),
        ]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []
```

### 6.9 `tests/unit/test_gate/test_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests for the full test-gate workflow.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.test_gate.models import SkippedTest

# Import the main entry point
import sys
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools import test_gate  # noqa: E402 (ensure package imports work)


# We need to be careful importing test-gate.py since it has a hyphen
# Instead, we test through the module's main function by importing directly
import importlib.util

_GATE_SCRIPT = _PROJECT_ROOT / "tools" / "test-gate.py"


def _load_test_gate_main():
    """Dynamically load test-gate.py and return its main function."""
    spec = importlib.util.spec_from_file_location("test_gate_main", _GATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


PYTEST_OUTPUT_NO_SKIPS = """\
tests/test_a.py::test_one PASSED
tests/test_a.py::test_two PASSED
===== 2 passed in 0.5s =====
"""

PYTEST_OUTPUT_WITH_SKIPS = """\
tests/test_a.py::test_one PASSED
tests/test_auth.py::test_oauth SKIPPED (External provider)
tests/test_utils.py::test_deprecated_helper SKIPPED (Deprecated)
===== 1 passed, 2 skipped in 0.5s =====
"""

PYTEST_OUTPUT_WITH_CRITICAL_SKIP = """\
tests/test_security.py::test_xss_prevention SKIPPED (TODO implement)
===== 1 skipped in 0.1s =====
"""

AUDIT_BLOCK_FOR_SKIPS = """\
<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider | marty | |
| tests/test_utils.py::test_deprecated_* | EXPECTED | Deprecated | marty | |
<!-- END SKIPPED TEST AUDIT -->
"""


class TestIntegrationNoSkips:
    """T150: No skips scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_no_skips_returns_pytest_exit_code(self, mock_run: MagicMock) -> None:
        """T150: Clean test run passes through exit code."""
        mock_run.return_value = (0, PYTEST_OUTPUT_NO_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 0


class TestIntegrationMissingAudit:
    """T100: Missing audit block."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_skips_without_audit_fails(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T100: Skips without audit block returns exit 1."""
        monkeypatch.chdir(tmp_path)  # No .skip-audit.md in tmp_path
        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1


class TestIntegrationWithAudit:
    """T130: All audited scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_all_audited_passes(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T130: All skips audited returns pytest exit code."""
        monkeypatch.chdir(tmp_path)
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(AUDIT_BLOCK_FOR_SKIPS)

        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 0


class TestIntegrationUnaudited:
    """T110: Unaudited test scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_unaudited_test_fails(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T110: Unaudited skip returns exit 1."""
        monkeypatch.chdir(tmp_path)
        # Audit that only covers auth, not utils
        partial_audit = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider | marty | |
<!-- END SKIPPED TEST AUDIT -->"""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(partial_audit)

        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1


class TestIntegrationUnverifiedCritical:
    """T120: Unverified critical test scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_unverified_critical_fails(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T120: Critical test with UNVERIFIED status returns exit 1."""
        monkeypatch.chdir(tmp_path)
        audit = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_security.py::test_xss_prevention | UNVERIFIED | Needs review | | |
<!-- END SKIPPED TEST AUDIT -->"""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(audit)

        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_CRITICAL_SKIP, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1


class TestIntegrationBypass:
    """T140: Bypass flag scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_bypass_logs_and_passes(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """T140: --skip-gate-bypass logs warning and passes through."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/", "--skip-gate-bypass", "Emergency hotfix for #500"])
        assert result == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Emergency hotfix" in captured.err

    @patch("tools.test_gate.parser.run_pytest")
    def test_bypass_empty_reason_fails(
        self, mock_run: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Bypass with empty string is rejected."""
        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/", "--skip-gate-bypass", ""])
        assert result == 2


class TestIntegrationCommonFlags:
    """T160: Common pytest flags work."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_common_flags_preserved(self, mock_run: MagicMock) -> None:
        """T160: Common flags are passed through to pytest."""
        mock_run.return_value = (0, PYTEST_OUTPUT_NO_SKIPS, "")
        main = _load_test_gate_main()

        # These flags should not be consumed by the gate
        result = main([
            "tests/unit/",
            "-v",
            "--tb=short",
            "--cov=assemblyzero",
            "-k", "test_something",
            "-m", "not integration",
        ])
        assert result == 0

        # Verify flags were passed to pytest
        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args
        assert "--tb=short" in call_args
        assert "--cov=assemblyzero" in call_args
        assert "-k" in call_args
        assert "test_something" in call_args


class TestIntegrationExitCodePreservation:
    """T020: Exit code preservation."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_pytest_failure_preserved_when_no_skips(self, mock_run: MagicMock) -> None:
        """T020: Pytest failure exit code preserved when no skips."""
        mock_run.return_value = (1, "FAILED tests/test_a.py::test_one\n", "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1

    @patch("tools.test_gate.parser.run_pytest")
    def test_pytest_failure_preserved_when_gate_passes(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T020: Pytest failure preserved even when gate passes."""
        monkeypatch.chdir(tmp_path)
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(AUDIT_BLOCK_FOR_SKIPS)

        # Pytest returns 1 (some tests failed), but skips are audited
        mock_run.return_value = (1, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1  # pytest exit code, not gate's
```

### 6.10 `.github/workflows/ci.yml` (Modify)

**Change 1:** Modify the "Run unit tests with coverage" step (line ~41)

```diff
       - name: Run unit tests with coverage
-        run: poetry run pytest tests/unit/ -v --tb=short --cov=assemblyzero --cov-report=term-missing --cov-report=xml:coverage.xml
+        run: poetry run python tools/test-gate.py tests/unit/ -v --tb=short --cov=assemblyzero --cov-report=term-missing --cov-report=xml:coverage.xml
         env:
           LANGSMITH_TRACING: "false"
```

**Change 2:** Modify the "Run integration tests" step (line ~47)

```diff
       - name: Run integration tests
         if: github.event_name == 'push' && github.ref == 'refs/heads/main'
-        run: poetry run pytest tests/integration/ -v --tb=short -m integration
+        run: poetry run python tools/test-gate.py tests/integration/ -v --tb=short -m integration
         env:
           LANGSMITH_TRACING: "false"
           ASSEMBLYZERO_MOCK_MODE: "1"
```

## 7. Pattern References

### 7.1 Existing CLI Tool Pattern

**File:** `tools/run_audit.py` (lines 1–60)

Based on the project's existing CLI tools, each tool follows a consistent pattern:
- Module-level docstring with issue reference
- `from __future__ import annotations` import
- A `main()` function as entry point
- `if __name__ == "__main__":` guard calling `main()`
- Uses `sys.exit()` for exit codes

**Relevance:** The `tools/test-gate.py` script follows this same CLI entry point pattern. The `main()` function accepts optional args list (defaulting to `sys.argv[1:]`) and returns an integer exit code.

### 7.2 Existing Test Pattern

**File:** `tests/unit/test_implementation_spec_workflow.py` (lines 1–80)

Tests in this project follow a consistent pattern:
- Module-level docstring with issue reference
- Class-based test organization with descriptive class names
- `@patch` decorators for mocking external calls
- `pytest.fixture` or `tmp_path` for test data
- Test names match `test_<scenario>` pattern

**Relevance:** The test files `test_parser.py`, `test_auditor.py`, and `test_integration.py` follow this same structure with class-based grouping and consistent mock patterns.

### 7.3 Project Path Resolution Pattern

**File:** `tools/run_issue_workflow.py` (lines 1–20)

Existing tools resolve project paths using:

```python
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

**Relevance:** The `tools/test-gate.py` script uses this same pattern to add the project root to `sys.path` so that `tools.test_gate` module imports resolve correctly.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new files |
| `from typing import TypedDict` | stdlib | `models.py` |
| `import re` | stdlib | `parser.py`, `auditor.py` |
| `import subprocess` | stdlib | `parser.py` |
| `import sys` | stdlib | `parser.py`, `auditor.py`, `test-gate.py` |
| `import signal` | stdlib | `parser.py` |
| `import os` | stdlib | `parser.py` |
| `import fnmatch` | stdlib | `auditor.py` |
| `from pathlib import Path` | stdlib | `auditor.py`, `test-gate.py` |
| `from datetime import datetime, timezone` | stdlib | `test-gate.py` |
| `import importlib.util` | stdlib | `test_integration.py` |
| `from unittest.mock import MagicMock, patch` | stdlib | All test files |
| `import pytest` | dev dependency (existing) | All test files |
| `from tools.test_gate.models import SkippedTest` | internal | `parser.py`, test files |
| `from tools.test_gate.models import AuditBlock, AuditEntry` | internal | `auditor.py`, test files |
| `from tools.test_gate.parser import ...` | internal | `test-gate.py`, test files |
| `from tools.test_gate.auditor import ...` | internal | `test-gate.py`, test files |

**New Dependencies:** None — uses stdlib only.

## 9. Test Mapping

| Test ID | Tests Function | File | Input | Expected Output |
|---------|---------------|------|-------|-----------------|
| T010 | `run_pytest()` | `test_parser.py` | `args=["tests/unit/", "-v", "-x"]` | subprocess called with matching args |
| T020 | `run_pytest()` + `main()` | `test_parser.py`, `test_integration.py` | pytest returns 1 | gate returns 1 |
| T025 | `ensure_verbose_flag()` | `test_parser.py` | `args=["tests/", "--tb=short"]` | `[..., "-v"]` appended |
| T030 | `parse_skipped_tests()` | `test_parser.py` | inline SKIPPED output | `SkippedTest` with correct fields |
| T040 | `parse_skipped_tests()` | `test_parser.py` | multiple skipped lines | 3 `SkippedTest` objects |
| T050 | `detect_critical_tests()` | `test_parser.py` | test with "critical" in name | `is_critical=True` |
| T060 | `detect_critical_tests()` | `test_parser.py` | test with "security"/"auth" in name | `is_critical=True` |
| T070 | `find_audit_block()` | `test_auditor.py` | stdout containing audit block | `AuditBlock` with `source="stdout"` |
| T080 | `find_audit_block()` | `test_auditor.py` | `.skip-audit.md` file | `AuditBlock` with `source="file"` |
| T090 | `match_test_to_audit()` | `test_auditor.py` | exact and glob patterns | `True`/`False` matches |
| T100 | `main()` | `test_integration.py` | skips, no audit | exit code 1 |
| T110 | `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | test not in audit | unaudited list populated, exit 1 |
| T120 | `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | critical + UNVERIFIED | unverified list populated, exit 1 |
| T130 | `validate_audit()` + `main()` | `test_auditor.py`, `test_integration.py` | all audited | `([], [])`, exit 0 |
| T140 | `main()` | `test_integration.py` | `--skip-gate-bypass "reason"` | WARNING logged, exit 0 |
| T150 | `main()` | `test_integration.py` | no skipped tests | pytest exit code returned |
| T160 | `main()` | `test_integration.py` | `--cov --tb=short -k name` | all flags passed through |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All errors and warnings are printed to `sys.stderr`. The script distinguishes three exit codes:
- `0`: Gate passed (or no skips found), returns pytest's original exit code
- `1`: Gate failed (missing audit, unaudited tests, or unverified critical tests)
- `2`: Usage error (invalid arguments like empty bypass reason)

When output parsing fails (e.g., unexpected pytest format), the script logs a `WARNING` to stderr and falls through (fail-open), preserving the pytest exit code.

### 10.2 Logging Convention

No logging framework — uses `print()` to stderr for all gate messages:
- Errors: `"TEST GATE FAILED: ..."` with `=` separator lines
- Warnings: `"WARNING: ..."` prefix
- Success: `"✓ Test gate passed: ..."` 

Pytest's own stdout/stderr is passed through unchanged to preserve CI readability.

### 10.3 Constants

| Constant | Value | Rationale | File |
|----------|-------|-----------|------|
| `CRITICAL_KEYWORDS` | `["security", "auth", "payment", "critical"]` | Keywords that indicate critical test paths | `parser.py` |
| `_AUDIT_START` | `"<!-- SKIPPED TEST AUDIT -->"` | Sentinel marker for audit block start | `auditor.py` |
| `_AUDIT_END` | `"<!-- END SKIPPED TEST AUDIT -->"` | Sentinel marker for audit block end | `auditor.py` |
| Default timeout | `1800` (30 minutes) | Maximum pytest execution time before kill | `parser.py` |

### 10.4 Audit Block Format

The canonical audit block format in `.skip-audit.md`:

```markdown
<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/unit/test_auth.py::test_oauth_token_refresh | VERIFIED | External OAuth provider not available in CI. Covered by integration tests. | marty | 2026-06-01 |
| tests/unit/test_utils.py::test_deprecated_* | EXPECTED | Deprecated features scheduled for removal in v0.3.0 | marty | |
<!-- END SKIPPED TEST AUDIT -->
```

Status values:
- `VERIFIED`: Skip has been reviewed and is acceptable
- `EXPECTED`: Skip is a known/expected condition (e.g., platform-specific)
- `UNVERIFIED`: Skip has been noted but not yet reviewed (blocks critical tests)

### 10.5 Dynamic Import for test-gate.py

Since `test-gate.py` contains a hyphen (not valid Python identifier), the integration tests use `importlib.util.spec_from_file_location()` to dynamically load the module. The `_load_test_gate_main()` helper function encapsulates this.

### 10.6 Signal Handling

The `run_pytest()` function installs a temporary SIGINT handler that forwards the signal to the pytest subprocess. The original handler is restored after `proc.communicate()` completes (in a `finally` block) to avoid leaking signal handlers.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — `.github/workflows/ci.yml` complete file shown
- [x] Every data structure has a concrete JSON/YAML example (Section 4) — `SkippedTest`, `AuditEntry`, `AuditBlock`, `GateResult` all have examples
- [x] Every function has input/output examples with realistic values (Section 5) — 9 functions fully specified
- [x] Change instructions are diff-level specific (Section 6) — Full file contents for Add, diff blocks for Modify
- [x] Pattern references include file:line and are verified to exist (Section 7) — 3 pattern references
- [x] All imports are listed and verified (Section 8) — 18 imports mapped
- [x] Test mapping covers all LLD test scenarios (Section 9) — All 16 test IDs covered

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #225 |
| Verdict | DRAFT |
| Date | 2026-02-05 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #225 |
| Verdict | APPROVED |
| Date | 2026-02-24 |
| Iterations | 0 |
| Finalized | 2026-02-24T20:12:13Z |

### Review Feedback Summary

Approved with suggestions:
- **Regex Robustness:** In `tools/test_gate/parser.py`, the `_PATTERN_BLOCK` regex uses `[\w/\\.\-]+` for filenames. While this covers standard codebase conventions, if future tests run on paths with spaces or parentheses, this might fail. This is acceptable for now but something to keep in mind.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_225.py
"""Test file for Issue #225.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest


# Unit Tests
# -----------

def test_id():
    """
    Tests Function | File | Input | Expected Output
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_id works correctly
    assert False, 'TDD RED: test_id not implemented'


def test_t010():
    """
    `run_pytest()` | `test_parser.py` | `args=["tests/unit/", "-v",
    "-x"]` | subprocess called with matching args
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
    `run_pytest()` + `main()` | `test_parser.py`, `test_integration.py` |
    pytest returns 1 | gate returns 1
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t020 works correctly
    assert False, 'TDD RED: test_t020 not implemented'


def test_t025():
    """
    `ensure_verbose_flag()` | `test_parser.py` | `args=["tests/",
    "--tb=short"]` | `[..., "-v"]` appended
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t025 works correctly
    assert False, 'TDD RED: test_t025 not implemented'


def test_t030():
    """
    `parse_skipped_tests()` | `test_parser.py` | inline SKIPPED output |
    `SkippedTest` with correct fields
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
    `parse_skipped_tests()` | `test_parser.py` | multiple skipped lines |
    3 `SkippedTest` objects
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
    `detect_critical_tests()` | `test_parser.py` | test with "critical"
    in name | `is_critical=True`
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
    `detect_critical_tests()` | `test_parser.py` | test with
    "security"/"auth" in name | `is_critical=True`
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
    `find_audit_block()` | `test_auditor.py` | stdout containing audit
    block | `AuditBlock` with `source="stdout"`
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
    `find_audit_block()` | `test_auditor.py` | `.skip-audit.md` file |
    `AuditBlock` with `source="file"`
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
    `match_test_to_audit()` | `test_auditor.py` | exact and glob patterns
    | `True`/`False` matches
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
    `main()` | `test_integration.py` | skips, no audit | exit code 1
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
    `validate_audit()` + `main()` | `test_auditor.py`,
    `test_integration.py` | test not in audit | unaudited list populated,
    exit 1
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
    `validate_audit()` + `main()` | `test_auditor.py`,
    `test_integration.py` | critical + UNVERIFIED | unverified list
    populated, exit 1
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
    `validate_audit()` + `main()` | `test_auditor.py`,
    `test_integration.py` | all audited | `([], [])`, exit 0
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
    `main()` | `test_integration.py` | WARNING logged, exit 0
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
    `main()` | `test_integration.py` | no skipped tests | pytest exit
    code returned
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
    `main()` | `test_integration.py` | all flags passed through
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t160 works correctly
    assert False, 'TDD RED: test_t160 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### tools/test_gate/__init__.py (signatures)

```python
"""test_gate - Pytest wrapper for skipped test audit enforcement.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

__version__ = "0.1.0"
```

### tools/test_gate/models.py (signatures)

```python
"""Data models for the test gate.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from typing import TypedDict

class SkippedTest(TypedDict):

    """Represents a single skipped test from pytest output."""

class AuditEntry(TypedDict):

    """Represents a single entry in the audit block."""

class AuditBlock(TypedDict):

    """Parsed SKIPPED TEST AUDIT block."""

class GateResult(TypedDict):

    """Result of running the test gate."""
```

### tools/test_gate/parser.py (signatures)

```python
"""Pytest output parsing utilities.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import os

import re

import signal

import subprocess

import sys

from typing import TYPE_CHECKING

from tools.test_gate.models import SkippedTest

def run_pytest(args: list[str], timeout: int = 1800) -> tuple[int, str, str]:
    """Execute pytest with given args, return (exit_code, stdout, stderr).

Forwards SIGINT to the subprocess for clean Ctrl+C handling."""
    ...

def ensure_verbose_flag(args: list[str]) -> list[str]:
    """Ensure -v flag is present in args for skip detection.

Returns a new list (does not mutate input). If any verbose flag"""
    ...

def parse_skipped_tests(output: str) -> list[SkippedTest]:
    """Parse pytest verbose output for skipped test information.

Handles two common pytest verbose output formats:"""
    ...

def detect_critical_tests(tests: list[SkippedTest]) -> list[SkippedTest]:
    """Return new list with is_critical set based on naming conventions.

A test is marked critical if any CRITICAL_KEYWORDS appear in the"""
    ...

_PATTERN_INLINE = re.compile(
    r"^([\w/\\.\-]+\.py::[\w\[\]\-]+)\s+SKIPPED\s+\((.+?)\)\s*$",
    re.MULTILINE,
)

_PATTERN_BLOCK = re.compile(
    r"^SKIPPED\s+\[\d+\]\s+([\w/\\.\-]+\.py):(\d+):\s+(.+?)\s*$",
    re.MULTILINE,
)
```

### tools/test_gate/auditor.py (signatures)

```python
"""Audit block detection and validation.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import fnmatch

import re

import sys

from pathlib import Path

from tools.test_gate.models import AuditBlock, AuditEntry, SkippedTest

def find_audit_block(
    output: str, audit_file: Path | None = None
) -> AuditBlock | None:
    """Locate and parse SKIPPED TEST AUDIT block from file or output.

Search order:"""
    ...

def _extract_audit_text(text: str) -> str | None:
    """Extract raw audit block text between sentinel markers.

Returns None if markers not found or block is malformed."""
    ...

def parse_audit_block(raw_block: str, source: str = "unknown") -> AuditBlock:
    """Parse raw audit block text into structured AuditBlock.

Expects markdown table format:"""
    ...

def validate_audit(
    skipped: list[SkippedTest],
    audit: AuditBlock | None,
) -> tuple[list[SkippedTest], list[SkippedTest]]:
    """Validate skipped tests against audit block.

Returns (unaudited_tests, unverified_critical_tests)."""
    ...

def match_test_to_audit(test: SkippedTest, entry: AuditEntry) -> bool:
    """Check if a test matches an audit entry pattern.

Supports:"""
    ...

_AUDIT_START = "<!-- SKIPPED TEST AUDIT -->"

_AUDIT_END = "<!-- END SKIPPED TEST AUDIT -->"

_TABLE_ROW = re.compile(
    r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|$"
)
```

### tools/test-gate.py (signatures)

```python
"""Pytest wrapper that enforces skipped test auditing.

Issue #225: Hard gate wrapper for skipped test enforcement.

Usage:
    python tools/test-gate.py [pytest-args...] [--audit-file PATH] [--strict] [--skip-gate-bypass "reason"]

Examples:
    python tools/test-gate.py tests/unit/ -v --tb=short
    python tools/test-gate.py tests/ --audit-file .skip-audit.md
    python tools/test-gate.py tests/ --skip-gate-bypass "Emergency hotfix for #500"
"""

from __future__ import annotations

import sys

from datetime import datetime, timezone

from pathlib import Path

from tools.test_gate.auditor import find_audit_block, validate_audit

from tools.test_gate.parser import (
    detect_critical_tests,
    ensure_verbose_flag,
    parse_skipped_tests,
    run_pytest,
)

def _parse_gate_args(
    args: list[str],
) -> tuple[list[str], Path | None, bool, str | None]:
    """Separate gate-specific flags from pytest args.

Returns (pytest_args, audit_file, strict, bypass_reason)."""
    ...

def main(args: list[str] | None = None) -> int:
    """Main entry point - wraps pytest and enforces skip audit gate."""
    ...

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

### tests/unit/test_gate/__init__.py (signatures)

```python
"""Test package for tools/test_gate.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""
```

### tests/unit/test_gate/test_parser.py (signatures)

```python
"""Unit tests for tools/test_gate/parser.py.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.test_gate.models import SkippedTest

from tools.test_gate.parser import (
    CRITICAL_KEYWORDS,
    detect_critical_tests,
    ensure_verbose_flag,
    parse_skipped_tests,
    run_pytest,
)

class TestEnsureVerboseFlag:

    """Tests for ensure_verbose_flag()."""

    def test_adds_v_when_missing(self) -> None:
    """T025: -v is added when no verbose flag is present."""
    ...

    def test_does_not_add_when_v_present(self) -> None:
    """Verbose flag already present as -v."""
    ...

    def test_does_not_add_when_vv_present(self) -> None:
    """Verbose flag already present as -vv."""
    ...

    def test_does_not_add_when_verbose_present(self) -> None:
    """Verbose flag already present as --verbose."""
    ...

    def test_empty_list_adds_v(self) -> None:
    """Empty args list gets -v added."""
    ...

    def test_does_not_mutate_input(self) -> None:
    """Input list is not mutated."""
    ...

class TestParseSkippedTests:

    """Tests for parse_skipped_tests()."""

    def test_parse_inline_skip_format(self) -> None:
    """T030: Parse 'test_name SKIPPED (reason)' format."""
    ...

    def test_parse_block_skip_format(self) -> None:
    """T030: Parse 'SKIPPED [N] file:line: reason' format."""
    ...

    def test_parse_multiple_skips(self) -> None:
    """T040: Multiple skipped tests are all captured."""
    ...

    def test_parse_no_skips(self) -> None:
    """T150: No SKIPPED lines returns empty list."""
    ...

    def test_parse_empty_output(self) -> None:
    """Edge case: empty string returns empty list."""
    ...

    def test_parse_mixed_output(self) -> None:
    """Mixed passing and skipped output."""
    ...

class TestDetectCriticalTests:

    """Tests for detect_critical_tests()."""

    def test_detect_by_auth_keyword(self) -> None:
    """T060: 'auth' in name triggers critical."""
    ...

    def test_detect_by_security_keyword(self) -> None:
    """T060: 'security' in name triggers critical."""
    ...

    def test_detect_by_payment_keyword(self) -> None:
    """T060: 'payment' in name triggers critical."""
    ...

    def test_detect_by_critical_keyword(self) -> None:
    """T050: 'critical' in name triggers critical."""
    ...

    def test_non_critical_unchanged(self) -> None:
    """Non-critical test stays non-critical."""
    ...

    def test_already_critical_stays_critical(self) -> None:
    """Test already marked critical is not downgraded."""
    ...

    def test_empty_list(self) -> None:
    """Empty input returns empty output."""
    ...

    def test_does_not_mutate_input(self) -> None:
    """Input list is not mutated."""
    ...

class TestRunPytest:

    """Tests for run_pytest()."""

    def test_passes_through_args(self, mock_popen: MagicMock) -> None:
    """T010: All pytest args forwarded unchanged to subprocess."""
    ...

    def test_preserves_exit_code(self, mock_popen: MagicMock) -> None:
    """T020: Exit code from pytest is preserved."""
    ...

    def test_timeout_returns_error(self, mock_popen: MagicMock) -> None:
    """Timeout produces exit code 1 and error message."""
    ...

    def test_file_not_found_returns_error(self, mock_popen: MagicMock) -> None:
    """Missing pytest returns error."""
    ...
```

### tests/unit/test_gate/test_auditor.py (full)

```python
"""Unit tests for tools/test_gate/auditor.py.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.test_gate.auditor import (
    find_audit_block,
    match_test_to_audit,
    parse_audit_block,
    validate_audit,
)
from tools.test_gate.models import AuditBlock, AuditEntry, SkippedTest


# --- Sample data ---

SAMPLE_AUDIT_BLOCK = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider not in CI | marty | 2026-06-01 |
| tests/test_utils.py::test_deprecated_* | EXPECTED | Removal in v0.3.0 | marty | |
<!-- END SKIPPED TEST AUDIT -->"""

SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_security.py::test_xss | UNVERIFIED | Needs review | | |
<!-- END SKIPPED TEST AUDIT -->"""


def _make_skipped(
    name: str,
    reason: str = "test reason",
    is_critical: bool = False,
) -> SkippedTest:
    """Helper to create SkippedTest instances."""
    file_path = name.split("::")[0] if "::" in name else name
    return SkippedTest(
        name=name,
        reason=reason,
        line_number=0,
        file_path=file_path,
        is_critical=is_critical,
    )


# --- T070: test_find_audit_stdout ---


class TestFindAuditBlock:
    """Tests for find_audit_block()."""

    def test_find_in_stdout(self) -> None:
        """T070: Audit block found in pytest stdout output."""
        output = f"some output\n{SAMPLE_AUDIT_BLOCK}\nmore output"
        result = find_audit_block(output)
        assert result is not None
        assert result["source"] == "stdout"
        assert len(result["entries"]) == 2

    def test_find_in_file(self, tmp_path: Path) -> None:
        """T080: Audit block found in external file."""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(SAMPLE_AUDIT_BLOCK)

        result = find_audit_block("no audit here", audit_file=audit_file)
        assert result is not None
        assert result["source"] == "file"
        assert len(result["entries"]) == 2

    def test_find_in_default_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T080: Audit block found in default .skip-audit.md."""
        monkeypatch.chdir(tmp_path)
        default_file = tmp_path / ".skip-audit.md"
        default_file.write_text(SAMPLE_AUDIT_BLOCK)

        result = find_audit_block("no audit here")
        assert result is not None
        assert result["source"] == "file"

    def test_file_takes_priority_over_stdout(self, tmp_path: Path) -> None:
        """Explicit file is checked before stdout."""
        audit_file = tmp_path / "custom-audit.md"
        audit_file.write_text(SAMPLE_AUDIT_BLOCK)

        # stdout also has an audit block but file should win
        result = find_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, audit_file=audit_file
        )
        assert result is not None
        assert result["source"] == "file"
        assert len(result["entries"]) == 2  # from file, not 1 from stdout

    def test_returns_none_when_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No audit block anywhere returns None."""
        monkeypatch.chdir(tmp_path)
        result = find_audit_block("no audit block here")
        assert result is None

    def test_malformed_block_no_end_marker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing end marker returns None with warning."""
        monkeypatch.chdir(tmp_path)
        malformed = "<!-- SKIPPED TEST AUDIT -->\n| Test | Status |\nno end"
        result = find_audit_block(malformed)
        assert result is None

    def test_nonexistent_audit_file_falls_through(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Nonexistent audit file falls through to other sources."""
        monkeypatch.chdir(tmp_path)
        result = find_audit_block(
            SAMPLE_AUDIT_BLOCK,
            audit_file=Path("/nonexistent/path.md"),
        )
        assert result is not None
        assert result["source"] == "stdout"


# --- T090: test_validate_audit_match ---


class TestParseAuditBlock:
    """Tests for parse_audit_block()."""

    def test_parse_standard_block(self) -> None:
        """Parses a well-formed audit block."""
        result = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")
        assert len(result["entries"]) == 2
        assert result["entries"][0]["test_pattern"] == "tests/test_auth.py::test_oauth"
        assert result["entries"][0]["status"] == "VERIFIED"
        assert result["entries"][0]["justification"] == "External provider not in CI"
        assert result["entries"][0]["owner"] == "marty"
        assert result["entries"][0]["expires"] == "2026-06-01"
        assert result["entries"][1]["expires"] is None
        assert result["source"] == "file"

    def test_parse_empty_table(self) -> None:
        """Table with header only returns empty entries."""
        block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
<!-- END SKIPPED TEST AUDIT -->"""
        result = parse_audit_block(block)
        assert result["entries"] == []

    def test_parse_strips_whitespace(self) -> None:
        """Extra whitespace in cells is stripped."""
        block = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
|  tests/test_a.py::test_x  |  VERIFIED  |  some reason  |  owner  |  2026-01-01  |
<!-- END SKIPPED TEST AUDIT -->"""
        result = parse_audit_block(block)
        assert result["entries"][0]["test_pattern"] == "tests/test_a.py::test_x"
        assert result["entries"][0]["status"] == "VERIFIED"
        assert result["entries"][0]["owner"] == "owner"


class TestMatchTestToAudit:
    """Tests for match_test_to_audit()."""

    def test_exact_match(self) -> None:
        """T090: Exact test name matches exact pattern."""
        test = _make_skipped("tests/test_auth.py::test_oauth")
        entry = AuditEntry(
            test_pattern="tests/test_auth.py::test_oauth",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True

    def test_glob_match(self) -> None:
        """T090: Glob pattern matches test name."""
        test = _make_skipped("tests/test_utils.py::test_deprecated_helper")
        entry = AuditEntry(
            test_pattern="tests/test_utils.py::test_deprecated_*",
            status="EXPECTED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True

    def test_no_match(self) -> None:
        """Non-matching pattern returns False."""
        test = _make_skipped("tests/test_utils.py::test_format")
        entry = AuditEntry(
            test_pattern="tests/test_auth.py::test_*",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is False

    def test_empty_pattern_no_match(self) -> None:
        """Empty pattern never matches."""
        test = _make_skipped("tests/test_a.py::test_x")
        entry = AuditEntry(
            test_pattern="",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is False

    def test_directory_glob(self) -> None:
        """Directory-level glob pattern."""
        test = _make_skipped("tests/unit/test_auth.py::test_oauth")
        entry = AuditEntry(
            test_pattern="tests/unit/*",
            status="VERIFIED",
            justification="r",
            owner="m",
            expires=None,
        )
        assert match_test_to_audit(test, entry) is True


# --- T100, T110, T120, T130: validation tests ---


class TestValidateAudit:
    """Tests for validate_audit()."""

    def test_all_audited_passes(self) -> None:
        """T130: All skipped tests have matching audit entries."""
        skipped = [_make_skipped("tests/test_auth.py::test_oauth")]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []

    def test_missing_audit_all_unaudited(self) -> None:
        """T100: No audit block means all tests are unaudited."""
        skipped = [_make_skipped("tests/test_a.py::test_x")]
        unaudited, unverified = validate_audit(skipped, None)
        assert len(unaudited) == 1
        assert unverified == []

    def test_unaudited_test_detected(self) -> None:
        """T110: Test without matching entry is unaudited."""
        skipped = [
            _make_skipped("tests/test_auth.py::test_oauth"),
            _make_skipped("tests/test_new.py::test_something"),  # not in audit
        ]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert len(unaudited) == 1
        assert unaudited[0]["name"] == "tests/test_new.py::test_something"

    def test_unverified_critical_detected(self) -> None:
        """T120: Critical test with UNVERIFIED status is flagged."""
        skipped = [
            _make_skipped(
                "tests/test_security.py::test_xss",
                is_critical=True,
            )
        ]
        audit = parse_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, source="file"
        )

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert len(unverified) == 1
        assert unverified[0]["name"] == "tests/test_security.py::test_xss"

    def test_non_critical_unverified_ok(self) -> None:
        """Non-critical test with UNVERIFIED status passes."""
        skipped = [
            _make_skipped(
                "tests/test_security.py::test_xss",
                is_critical=False,  # not critical
            )
        ]
        audit = parse_audit_block(
            SAMPLE_AUDIT_BLOCK_WITH_UNVERIFIED, source="file"
        )

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []

    def test_glob_pattern_covers_test(self) -> None:
        """Glob pattern in audit covers matching tests."""
        skipped = [
            _make_skipped("tests/test_utils.py::test_deprecated_foo"),
            _make_skipped("tests/test_utils.py::test_deprecated_bar"),
        ]
        audit = parse_audit_block(SAMPLE_AUDIT_BLOCK, source="file")

        unaudited, unverified = validate_audit(skipped, audit)
        assert unaudited == []
        assert unverified == []
```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the code.

```python
# Your implementation here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the code in a single code block
