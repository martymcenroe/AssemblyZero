# Implementation Request: assemblyzero/workflows/testing/nodes/implement_code.py

## Task

Write the complete contents of `assemblyzero/workflows/testing/nodes/implement_code.py`.

Change type: Modify
Description: Add `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD` constants; add `select_model_for_file()` routing function; update `call_claude_for_file()` to accept `model` param; update `generate_file_with_retry()` to call routing

## LLD Specification

# Implementation Spec: Route Scaffolding/Boilerplate Files to Haiku

| Field | Value |
|-------|-------|
| Issue | #641 |
| LLD | `docs/lld/active/641-route-scaffolding-boilerplate-files-to-haiku.md` |
| Generated | 2026-03-06 |
| Status | DRAFT |

## 1. Overview

Add model selection routing logic to `implement_code.py` so that simple/boilerplate files (`__init__.py`, `conftest.py`, test scaffolds, and small files under 50 lines) use `claude-3-haiku-20240307` while complex files continue using the configured default (Sonnet). This reduces API spend by an estimated 20–30%.

**Objective:** Route scaffolding/boilerplate file generation to Haiku to cut costs without degrading quality on complex files.

**Success Criteria:** `select_model_for_file()` correctly routes files per the 4 routing rules; `call_claude_for_file()` backward-compatible; all 16 test scenarios pass with ≥95% coverage.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/testing/nodes/implement_code.py` | Modify | Add `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD` constants; add `select_model_for_file()` routing function; update `call_claude_for_file()` to accept `model` param; update `generate_file_with_retry()` to call routing |
| 2 | `tests/unit/test_implement_code_routing.py` | Add | Unit tests for model routing logic (all 16 test scenarios) |

**Implementation Order Rationale:** The production code must exist before tests can import from it. However, per TDD, the test file will be written to exercise the *interface* first (tests will fail), then the production code is implemented to make them pass. Order 1 is listed first because it contains the module-level constants that tests import.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/testing/nodes/implement_code.py`

**Relevant excerpt — Module-level imports and constants** (top of file, lines ~1–50):

```python
"""N4: Implement Code node for TDD Testing Workflow.

Issue #272: File-by-file prompting with mechanical validation.
Issue #309: Add retry logic on validation failure (up to 3 attempts).
Issue #188: LLD path enforcement in prompts and write validation.

Key changes from original:
- Iterate through files_to_modify one at a time (not batch)
- Accumulate context: each file sees LLD + previously completed files
- Mechanical validation: code block exists, not empty, parses
- RETRY on validation failure: up to 3 attempts with error feedback
- WE control the file path, not Claude
- Issue #188: Prompt includes allowed paths; writes validated against LLD
"""

from assemblyzero.utils.shell import run_command

import ast

import os

import re

import random

import shutil

from assemblyzero.core.config import CLAUDE_MODEL

from assemblyzero.core.text_sanitizer import strip_emoji

import subprocess

import sys

from assemblyzero.telemetry import emit

import threading

import time

from pathlib import Path

from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost

from assemblyzero.hooks.file_write_validator import validate_file_write

from assemblyzero.utils.cost_tracker import accumulate_node_cost

from assemblyzero.utils.file_type import get_file_type_info, get_language_tag

from assemblyzero.utils.lld_path_enforcer import (
    build_implementation_prompt_section,
    detect_scaffolded_test_files,
    extract_paths_from_lld,
)

from assemblyzero.workflows.requirements.audit import (
    get_repo_structure,
)

from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)

from assemblyzero.workflows.testing.circuit_breaker import record_iteration_cost

from assemblyzero.workflows.testing.state import TestingWorkflowState
```

**What changes:** Add `import logging` and two new module-level constants (`HAIKU_MODEL`, `SMALL_FILE_LINE_THRESHOLD`) after existing constants. Add a module-level logger instance.

---

**Relevant excerpt — Module-level constants** (bottom of file):

```python
MAX_FILE_RETRIES = 2

LARGE_FILE_LINE_THRESHOLD = 500  # Lines

LARGE_FILE_BYTE_THRESHOLD = 15000  # Bytes (~15KB)

CLI_TIMEOUT = 600  # 10 minutes base for CLI subprocess

SDK_TIMEOUT = 600  # 10 minutes base for SDK API call

CODE_GEN_PROMPT_CAP = 60_000
```

**What changes:** Add `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD` constants alongside these existing constants.

---

**Relevant excerpt — `call_claude_for_file()` current signature:**

```python
def call_claude_for_file(prompt: str, file_path: str = "") -> tuple[str, str]:
    """Call Claude for a single file implementation.

    Issue #447: Added file_path parameter for file-type-aware system prompt."""
    ...
```

**What changes:** Add `model: str | None = None` parameter. When not `None`, use it as the model instead of the default `CLAUDE_MODEL`. The return type stays `tuple[str, str]`.

---

**Relevant excerpt — `generate_file_with_retry()` current signature:**

```python
def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
) -> tuple[str, bool]:
    """Generate code for a single file with retry on validation failure.

    Issue #309: Retry up to max_retries times on API or validation errors,"""
    ...
```

**What changes:** Add `estimated_line_count: int = 0` and `is_test_scaffold: bool = False` parameters. Call `select_model_for_file()` at the top and pass the result to `call_claude_for_file()` via the new `model` parameter.

## 4. Data Structures

### 4.1 Module-Level Constants

**Definition:**

```python
HAIKU_MODEL: str = "claude-3-haiku-20240307"
SMALL_FILE_LINE_THRESHOLD: int = 50
```

**Concrete Example (usage context):**

```json
{
    "HAIKU_MODEL": "claude-3-haiku-20240307",
    "SMALL_FILE_LINE_THRESHOLD": 50,
    "DEFAULT_MODEL_from_config": "claude-sonnet-4-20250514"
}
```

### 4.2 FileRoutingContext (Conceptual — Not a Class)

This is the conceptual data that flows through routing. It is **not** implemented as a class; the values are passed as individual function arguments.

**Definition (conceptual):**

```python
class FileRoutingContext(TypedDict):
    file_path: str
    estimated_line_count: int
    is_test_scaffold: bool
```

**Concrete Example:**

```json
{
    "file_path": "assemblyzero/workflows/testing/nodes/__init__.py",
    "estimated_line_count": 0,
    "is_test_scaffold": false
}
```

```json
{
    "file_path": "tests/unit/test_foo.py",
    "estimated_line_count": 200,
    "is_test_scaffold": true
}
```

```json
{
    "file_path": "assemblyzero/utils/helper.py",
    "estimated_line_count": 35,
    "is_test_scaffold": false
}
```

```json
{
    "file_path": "assemblyzero/core/engine.py",
    "estimated_line_count": 450,
    "is_test_scaffold": false
}
```

## 5. Function Specifications

### 5.1 `select_model_for_file()`

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py`

**Signature:**

```python
def select_model_for_file(
    file_path: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> str:
    """Return the model ID to use for generating the given file.

    Routing rules (evaluated in order):
      1. is_test_scaffold=True  -> HAIKU_MODEL
      2. basename is __init__.py or conftest.py -> HAIKU_MODEL
      3. estimated_line_count > 0 and < SMALL_FILE_LINE_THRESHOLD -> HAIKU_MODEL
      4. Otherwise -> configured default (Sonnet via CLAUDE_MODEL)

    Issue #641: Route scaffolding/boilerplate files to Haiku.
    """
    ...
```

**Input Example 1 (test scaffold):**

```python
file_path = "tests/unit/test_foo.py"
estimated_line_count = 200
is_test_scaffold = True
```

**Output Example 1:**

```python
"claude-3-haiku-20240307"
```

**Input Example 2 (boilerplate filename):**

```python
file_path = "assemblyzero/workflows/testing/nodes/__init__.py"
estimated_line_count = 0
is_test_scaffold = False
```

**Output Example 2:**

```python
"claude-3-haiku-20240307"
```

**Input Example 3 (small file by line count):**

```python
file_path = "assemblyzero/utils/helper.py"
estimated_line_count = 35
is_test_scaffold = False
```

**Output Example 3:**

```python
"claude-3-haiku-20240307"
```

**Input Example 4 (complex file, default routing):**

```python
file_path = "assemblyzero/core/engine.py"
estimated_line_count = 450
is_test_scaffold = False
```

**Output Example 4:**

```python
# Value of CLAUDE_MODEL from assemblyzero.core.config, e.g.:
"claude-sonnet-4-20250514"
```

**Input Example 5 (boundary — exactly 50 lines):**

```python
file_path = "assemblyzero/utils/helper.py"
estimated_line_count = 50
is_test_scaffold = False
```

**Output Example 5:**

```python
# Returns default model — 50 is NOT < 50
"claude-sonnet-4-20250514"
```

**Input Example 6 (negative line count):**

```python
file_path = "assemblyzero/utils/helper.py"
estimated_line_count = -1
is_test_scaffold = False
```

**Output Example 6:**

```python
# Negative treated as unknown; falls through to default
"claude-sonnet-4-20250514"
```

**Edge Cases:**
- `estimated_line_count = 0` -> unknown, skip line-count rule, fall through to default
- `estimated_line_count = -1` -> treated as unknown (same as 0)
- `estimated_line_count = 1` -> routes to Haiku (1 > 0 and 1 < 50)
- `estimated_line_count = 49` -> routes to Haiku (49 > 0 and 49 < 50)
- `estimated_line_count = 50` -> falls through to default (50 is NOT < 50)
- Deeply nested `__init__.py` -> basename match, routes to Haiku
- `conftest.py` in any directory -> basename match, routes to Haiku
- `is_test_scaffold=True` with `conftest.py` -> Haiku (scaffold rule fires first, same result)

### 5.2 `call_claude_for_file()` (Modified)

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py`

**Updated Signature:**

```python
def call_claude_for_file(prompt: str, file_path: str = "", model: str | None = None) -> tuple[str, str]:
    """Call Claude for a single file implementation.

    Issue #447: Added file_path parameter for file-type-aware system prompt.
    Issue #641: Added model parameter for routing to different models.

    Args:
        prompt: The full generation prompt.
        file_path: Path for file-type-aware system prompt.
        model: Override model; if None, uses CLAUDE_MODEL from config.

    Returns:
        Tuple of (response_text, stop_reason).
    """
    ...
```

**Input Example (explicit model):**

```python
prompt = "Generate an __init__.py file..."
file_path = "assemblyzero/__init__.py"
model = "claude-3-haiku-20240307"
```

**Output Example:**

```python
('"""AssemblyZero package."""\n', "end_turn")
```

**Input Example (default model, backward-compatible):**

```python
prompt = "Generate the engine module..."
file_path = "assemblyzero/core/engine.py"
model = None
```

**Output Example:**

```python
('"""Engine module."""\n\nclass Engine:\n    ...', "end_turn")
```

**Edge Cases:**
- `model=None` -> uses `CLAUDE_MODEL` from config (backward-compatible with all existing callers)
- `model=""` -> would be truthy empty string; not expected usage, but would pass empty string to API (API will reject it). This is acceptable — callers should pass `None` for default.

### 5.3 `generate_file_with_retry()` (Modified)

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py`

**Updated Signature:**

```python
def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> tuple[str, bool]:
    """Generate code for a single file with retry on validation failure.

    Issue #309: Retry up to max_retries times on API or validation errors.
    Issue #641: Routes to appropriate model via select_model_for_file().
    """
    ...
```

**Input Example:**

```python
filepath = "tests/__init__.py"
base_prompt = "Generate an empty __init__.py..."
audit_dir = Path("/tmp/audit")
max_retries = 2
pruned_prompt = ""
existing_content = ""
estimated_line_count = 0
is_test_scaffold = False
```

**Output Example:**

```python
('"""Tests package."""\n', True)  # (content, success)
```

**Edge Cases:**
- New parameters have defaults that preserve existing behavior (0 and False)
- All existing callers that don't pass the new parameters continue working unchanged

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/testing/nodes/implement_code.py` (Modify)

**Change 1:** Add `logging` import — insert after existing imports, near `import os`

```diff
 import os
 
 import re
 
 import random
+
+import logging
```

**Change 2:** Add module-level logger and new constants — insert after the existing module-level constants block (after `CODE_GEN_PROMPT_CAP = 60_000`). Place them together as a group.

```diff
 CODE_GEN_PROMPT_CAP = 60_000
+
+# Issue #641: Model routing constants
+logger = logging.getLogger(__name__)
+HAIKU_MODEL = "claude-3-haiku-20240307"
+SMALL_FILE_LINE_THRESHOLD = 50  # Files under this line count route to Haiku
```

**Change 3:** Add `select_model_for_file()` function — insert immediately before the existing `call_claude_for_file()` function definition.

```python
def select_model_for_file(
    file_path: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> str:
    """Return the model ID to use for generating the given file.

    Routing rules (evaluated in order):
      1. is_test_scaffold=True  -> HAIKU_MODEL
      2. basename is __init__.py or conftest.py -> HAIKU_MODEL
      3. estimated_line_count > 0 and < SMALL_FILE_LINE_THRESHOLD -> HAIKU_MODEL
      4. Otherwise -> configured default (Sonnet via CLAUDE_MODEL)

    Issue #641: Route scaffolding/boilerplate files to Haiku.

    Args:
        file_path: Relative or absolute path to the file being generated.
            Only the basename is used for filename-based routing rules.
        estimated_line_count: Expected line count of the generated file.
            Pass 0 (default) when unknown; 0 disables line-count routing.
            Negative values are treated as unknown (same as 0).
        is_test_scaffold: True when this file is being generated as a test
            scaffold by the N2 node; overrides all other routing rules.

    Returns:
        Model identifier string suitable for passing to the Anthropic client.
    """
    basename = Path(file_path).name

    if is_test_scaffold:
        logger.info(
            "Routing %s -> %s (reason: test scaffold)", file_path, HAIKU_MODEL
        )
        return HAIKU_MODEL

    if basename in {"__init__.py", "conftest.py"}:
        logger.info(
            "Routing %s -> %s (reason: boilerplate filename)", file_path, HAIKU_MODEL
        )
        return HAIKU_MODEL

    if estimated_line_count > 0 and estimated_line_count < SMALL_FILE_LINE_THRESHOLD:
        logger.info(
            "Routing %s -> %s (reason: small file, lines=%d)",
            file_path,
            HAIKU_MODEL,
            estimated_line_count,
        )
        return HAIKU_MODEL

    default_model = CLAUDE_MODEL
    logger.info("Routing %s -> %s (reason: default)", file_path, default_model)
    return default_model
```

**Change 4:** Modify `call_claude_for_file()` signature — add `model` parameter

Locate the existing `call_claude_for_file` function definition and modify:

```diff
-def call_claude_for_file(prompt: str, file_path: str = "") -> tuple[str, str]:
+def call_claude_for_file(prompt: str, file_path: str = "", model: str | None = None) -> tuple[str, str]:
     """Call Claude for a single file implementation.
 
-    Issue #447: Added file_path parameter for file-type-aware system prompt."""
+    Issue #447: Added file_path parameter for file-type-aware system prompt.
+    Issue #641: Added model parameter for routing to different models."""
```

**Change 5:** Inside `call_claude_for_file()` body — use the `model` parameter when resolving which model to call.

Find the location in the function body where `CLAUDE_MODEL` is referenced for the API call. Add model resolution logic at the top of the function body:

```diff
+    resolved_model = model if model is not None else CLAUDE_MODEL
```

Then replace all references to `CLAUDE_MODEL` within this function's API call with `resolved_model`. The exact location depends on the function body, but the pattern is:

```diff
-        model=CLAUDE_MODEL,
+        model=resolved_model,
```

If the function uses `CLAUDE_MODEL` in multiple places (e.g., logging, the API call itself), replace all of them with `resolved_model`.

**Change 6:** Modify `generate_file_with_retry()` signature — add routing parameters

```diff
 def generate_file_with_retry(
     filepath: str,
     base_prompt: str,
     audit_dir: Path | None = None,
     max_retries: int = MAX_FILE_RETRIES,
     pruned_prompt: str = "",
     existing_content: str = "",
+    estimated_line_count: int = 0,
+    is_test_scaffold: bool = False,
 ) -> tuple[str, bool]:
     """Generate code for a single file with retry on validation failure.
 
-    Issue #309: Retry up to max_retries times on API or validation errors,"""
+    Issue #309: Retry up to max_retries times on API or validation errors.
+    Issue #641: Routes to appropriate model via select_model_for_file()."""
```

**Change 7:** Inside `generate_file_with_retry()` body — call routing and pass model

Add the routing call at the very beginning of the function body (before the retry loop):

```diff
+    model = select_model_for_file(filepath, estimated_line_count, is_test_scaffold)
```

Then find where `call_claude_for_file()` is invoked inside this function and add the `model=model` keyword argument:

```diff
-            response_text, stop_reason = call_claude_for_file(prompt, filepath)
+            response_text, stop_reason = call_claude_for_file(prompt, filepath, model=model)
```

Note: The exact variable names and call pattern depend on the function body. The key is that every call to `call_claude_for_file` within `generate_file_with_retry` must pass `model=model`. If there are multiple call sites (e.g., initial attempt + retry with modified prompt), all must include the `model` parameter.

### 6.2 `tests/unit/test_implement_code_routing.py` (Add)

**Complete file contents:**

```python
"""Unit tests for Issue #641: Model routing for scaffolding/boilerplate files.

Tests the select_model_for_file() routing function and integration with
call_claude_for_file() and generate_file_with_retry().
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.nodes.implement_code import (
    HAIKU_MODEL,
    SMALL_FILE_LINE_THRESHOLD,
    call_claude_for_file,
    generate_file_with_retry,
    select_model_for_file,
)
from assemblyzero.core.config import CLAUDE_MODEL


# ---------------------------------------------------------------------------
# T010: __init__.py routes to Haiku (REQ-1)
# ---------------------------------------------------------------------------
class TestSelectModelForFile:
    """Tests for select_model_for_file() routing logic."""

    def test_init_py_routes_to_haiku(self):
        """T010: __init__.py in root routes to Haiku."""
        result = select_model_for_file(
            file_path="assemblyzero/__init__.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_conftest_py_routes_to_haiku(self):
        """T020: conftest.py routes to Haiku (REQ-2)."""
        result = select_model_for_file(
            file_path="tests/conftest.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_test_scaffold_routes_to_haiku(self):
        """T030: is_test_scaffold=True overrides everything (REQ-3)."""
        result = select_model_for_file(
            file_path="tests/unit/test_foo.py",
            estimated_line_count=200,
            is_test_scaffold=True,
        )
        assert result == HAIKU_MODEL

    def test_49_line_file_routes_to_haiku(self):
        """T040: 49-line file routes to Haiku (REQ-4)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=49,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_50_line_file_routes_to_default(self):
        """T050: Exactly 50 lines routes to Sonnet — boundary (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=50,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_unknown_size_complex_file_routes_to_default(self):
        """T060/T070: Unknown size (0) complex file routes to Sonnet (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/core/engine.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_deeply_nested_init_py_routes_to_haiku(self):
        """T080: Deeply nested __init__.py routes to Haiku (REQ-1)."""
        result = select_model_for_file(
            file_path="assemblyzero/workflows/testing/nodes/__init__.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_1_line_file_routes_to_haiku(self):
        """T130: 1-line file routes to Haiku — lower boundary (REQ-4)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/tiny.py",
            estimated_line_count=1,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_negative_line_count_routes_to_default(self):
        """T120/T140 partial: Negative line count treated as unknown (REQ-6)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=-1,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_51_line_file_routes_to_default(self):
        """T140: 51-line file routes to Sonnet — just above threshold (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/utils/helper.py",
            estimated_line_count=51,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_200_line_complex_file_routes_to_default(self):
        """Additional: 200-line complex file routes to Sonnet (REQ-5)."""
        result = select_model_for_file(
            file_path="assemblyzero/core/engine.py",
            estimated_line_count=200,
            is_test_scaffold=False,
        )
        assert result == CLAUDE_MODEL

    def test_conftest_deeply_nested_routes_to_haiku(self):
        """Additional: Deeply nested conftest.py routes to Haiku (REQ-2)."""
        result = select_model_for_file(
            file_path="tests/integration/fixtures/conftest.py",
            estimated_line_count=0,
            is_test_scaffold=False,
        )
        assert result == HAIKU_MODEL

    def test_scaffold_overrides_conftest(self):
        """Additional: is_test_scaffold=True with conftest -> Haiku (REQ-3)."""
        result = select_model_for_file(
            file_path="tests/conftest.py",
            estimated_line_count=0,
            is_test_scaffold=True,
        )
        assert result == HAIKU_MODEL

    def test_threshold_constant_is_50(self):
        """Sanity: SMALL_FILE_LINE_THRESHOLD is 50."""
        assert SMALL_FILE_LINE_THRESHOLD == 50


# ---------------------------------------------------------------------------
# T110: Routing log emission (REQ-9)
# ---------------------------------------------------------------------------
class TestSelectModelLogging:
    """Tests that routing decisions are logged at INFO level."""

    def test_routing_logged_with_reason_scaffold(self, caplog):
        """T110a: Scaffold routing logged with reason."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="tests/unit/test_x.py",
                estimated_line_count=0,
                is_test_scaffold=True,
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert "tests/unit/test_x.py" in record.message
        assert HAIKU_MODEL in record.message
        assert "test scaffold" in record.message

    def test_routing_logged_with_reason_boilerplate(self, caplog):
        """T110b: Boilerplate filename routing logged with reason."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="pkg/__init__.py",
                estimated_line_count=0,
                is_test_scaffold=False,
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "boilerplate filename" in record.message
        assert "pkg/__init__.py" in record.message
        assert HAIKU_MODEL in record.message

    def test_routing_logged_with_reason_small_file(self, caplog):
        """T110c: Small file routing logged with reason and line count."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="pkg/small.py",
                estimated_line_count=30,
                is_test_scaffold=False,
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "small file" in record.message
        assert "30" in record.message

    def test_routing_logged_with_reason_default(self, caplog):
        """T110d: Default routing logged with reason."""
        with caplog.at_level(logging.INFO):
            select_model_for_file(
                file_path="pkg/big.py",
                estimated_line_count=500,
                is_test_scaffold=False,
            )
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "default" in record.message
        assert "pkg/big.py" in record.message
        assert CLAUDE_MODEL in record.message


# ---------------------------------------------------------------------------
# T090/T100: call_claude_for_file model parameter (REQ-7)
# ---------------------------------------------------------------------------
class TestCallClaudeForFileModel:
    """Tests for the model parameter on call_claude_for_file()."""

    @patch("assemblyzero.workflows.testing.nodes.implement_code.emit")
    def test_explicit_model_passed_to_api(self, mock_emit):
        """T090: Explicit model is used in the API call (REQ-7).

        We patch the underlying API client to verify the model string
        that gets passed through.
        """
        # This test needs to mock the actual API client used inside
        # call_claude_for_file. The exact mock target depends on the
        # implementation (SDK client or CLI). We patch at the highest
        # level that captures the model parameter.
        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file",
            wraps=None,
        ) as mock_call:
            # Since we're wrapping, we need a different approach.
            # Instead, directly test that the function accepts the param
            # without error by mocking the internals.
            pass

        # Simplified: verify function signature accepts model param
        # Full integration tested in T100
        import inspect
        sig = inspect.signature(call_claude_for_file)
        assert "model" in sig.parameters
        param = sig.parameters["model"]
        assert param.default is None

    @patch("assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file")
    def test_default_model_when_none(self, mock_call):
        """T100: model=None preserves backward compatibility (REQ-7).

        Verified by checking function signature default.
        """
        import inspect
        sig = inspect.signature(call_claude_for_file)
        assert sig.parameters["model"].default is None


# ---------------------------------------------------------------------------
# T100: generate_file_with_retry routing integration (REQ-8)
# ---------------------------------------------------------------------------
class TestGenerateFileWithRetryRouting:
    """Tests that generate_file_with_retry() integrates routing correctly."""

    @patch("assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file")
    @patch("assemblyzero.workflows.testing.nodes.implement_code.select_model_for_file")
    def test_routes_init_py_to_haiku_and_passes_model(
        self, mock_select, mock_call_claude
    ):
        """T110: generate_file_with_retry calls routing and passes model (REQ-8)."""
        mock_select.return_value = HAIKU_MODEL
        mock_call_claude.return_value = ('"""Init."""\n', "end_turn")

        # Mock validate_code_response to always pass
        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.validate_code_response",
            return_value=(True, ""),
        ), patch(
            "assemblyzero.workflows.testing.nodes.implement_code.extract_code_block",
            return_value='"""Init."""\n',
        ):
            result, success = generate_file_with_retry(
                filepath="tests/__init__.py",
                base_prompt="Generate __init__.py",
                estimated_line_count=0,
                is_test_scaffold=False,
            )

        # Verify routing was called with correct args
        mock_select.assert_called_once_with("tests/__init__.py", 0, False)

        # Verify call_claude_for_file received the model
        call_args = mock_call_claude.call_args
        assert call_args is not None
        # model should be passed as keyword argument
        if call_args.kwargs.get("model") is not None:
            assert call_args.kwargs["model"] == HAIKU_MODEL
        else:
            # Or as positional — check the third arg
            assert len(call_args.args) >= 3 or "model" in call_args.kwargs

    @patch("assemblyzero.workflows.testing.nodes.implement_code.call_claude_for_file")
    @patch("assemblyzero.workflows.testing.nodes.implement_code.select_model_for_file")
    def test_passes_scaffold_flag_to_routing(
        self, mock_select, mock_call_claude
    ):
        """generate_file_with_retry passes is_test_scaffold to routing."""
        mock_select.return_value = HAIKU_MODEL
        mock_call_claude.return_value = ("test content", "end_turn")

        with patch(
            "assemblyzero.workflows.testing.nodes.implement_code.validate_code_response",
            return_value=(True, ""),
        ), patch(
            "assemblyzero.workflows.testing.nodes.implement_code.extract_code_block",
            return_value="test content",
        ):
            generate_file_with_retry(
                filepath="tests/unit/test_foo.py",
                base_prompt="Generate test scaffold",
                estimated_line_count=45,
                is_test_scaffold=True,
            )

        mock_select.assert_called_once_with("tests/unit/test_foo.py", 45, True)

    def test_new_params_have_safe_defaults(self):
        """Existing callers without new params still work (signature check)."""
        import inspect
        sig = inspect.signature(generate_file_with_retry)
        params = sig.parameters

        assert "estimated_line_count" in params
        assert params["estimated_line_count"].default == 0

        assert "is_test_scaffold" in params
        assert params["is_test_scaffold"].default is False
```

## 7. Pattern References

### 7.1 Existing Constants Pattern

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py` (bottom of file — module-level constants)

```python
MAX_FILE_RETRIES = 2

LARGE_FILE_LINE_THRESHOLD = 500  # Lines

LARGE_FILE_BYTE_THRESHOLD = 15000  # Bytes (~15KB)

CLI_TIMEOUT = 600  # 10 minutes base for CLI subprocess

SDK_TIMEOUT = 600  # 10 minutes base for SDK API call

CODE_GEN_PROMPT_CAP = 60_000
```

**Relevance:** New constants `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD` follow the same pattern — module-level, UPPER_SNAKE_CASE, with inline comments. Place them in this same constants block.

### 7.2 CLAUDE_MODEL Config Import Pattern

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py` (imports section)

```python
from assemblyzero.core.config import CLAUDE_MODEL
```

**Relevance:** The default model is already imported as `CLAUDE_MODEL`. The `select_model_for_file()` function uses this as its fallback/default model. No new config import needed — just reference `CLAUDE_MODEL` directly.

### 7.3 Existing `call_claude_for_file()` Pattern

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py` (function definition)

```python
def call_claude_for_file(prompt: str, file_path: str = "") -> tuple[str, str]:
    """Call Claude for a single file implementation.

    Issue #447: Added file_path parameter for file-type-aware system prompt."""
    ...
```

**Relevance:** Shows the existing signature pattern. The `model` parameter is added as a third keyword argument with `None` default, following the same optional-parameter-with-default pattern as `file_path=""`. The return type `tuple[str, str]` is unchanged.

### 7.4 Existing `generate_file_with_retry()` Pattern

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py` (function definition)

```python
def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
) -> tuple[str, bool]:
    """Generate code for a single file with retry on validation failure.

    Issue #309: Retry up to max_retries times on API or validation errors,"""
    ...
```

**Relevance:** Shows the existing parameter pattern. New parameters `estimated_line_count` and `is_test_scaffold` are appended at the end with safe defaults, following the same convention of keyword arguments with defaults.

### 7.5 Existing Test Pattern

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1–80)

**Relevance:** Shows the project's test style — `pytest` with `unittest.mock.patch`, class-based grouping, descriptive docstrings. The new test file follows this same pattern.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import logging` | stdlib | `implement_code.py` (new) |
| `from pathlib import Path` | stdlib | `implement_code.py` (already imported) |
| `from assemblyzero.core.config import CLAUDE_MODEL` | internal | `implement_code.py` (already imported) |
| `import inspect` | stdlib | `test_implement_code_routing.py` |
| `import logging` | stdlib | `test_implement_code_routing.py` |
| `from unittest.mock import MagicMock, patch` | stdlib | `test_implement_code_routing.py` |
| `import pytest` | third-party (already installed) | `test_implement_code_routing.py` |
| `from assemblyzero.workflows.testing.nodes.implement_code import (HAIKU_MODEL, SMALL_FILE_LINE_THRESHOLD, select_model_for_file, call_claude_for_file, generate_file_with_retry)` | internal | `test_implement_code_routing.py` |
| `from assemblyzero.core.config import CLAUDE_MODEL` | internal | `test_implement_code_routing.py` |

**New Dependencies:** None. Only `logging` from stdlib is newly imported in the production module.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `select_model_for_file()` | `file_path="assemblyzero/__init__.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL` (`"claude-3-haiku-20240307"`) |
| T020 | `select_model_for_file()` | `file_path="tests/conftest.py", estimated_line_count=0, is_test_scaffold=False` | `HAIKU_MODEL` |
| T030 | `select_model_for_file()` | `file_path="tests/unit/test_foo.py", estimated_line_count=200, is_test_scaffold=True` | `HAIKU_MODEL` |
| T040 | `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=49, is_test_scaffold=False` | `HAIKU_MODEL` |
| T050 | `select_model_for_file()` | `file_path="assemblyzero/utils/helper.py", estimated_line_count=50, is_test_scaffold=False` | `CLAUDE_MODEL` (default) |
| T060 | `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=200, is_test_scaffold=False` | `CLAUDE_MODEL` |
| T070 | `select_model_for_file()` | `file_path="assemblyzero/core/engine.py", estimated_line_count=0, is_test_scaffold=False` | `CLAUDE_MODEL` |
| T080 | `select_model_for_file()` | `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` | `HAIKU_MODEL` |
| T090 | `call_claude_for_file()` | Signature inspection: `model` param exists with default `None` | Parameter present |
| T100 | `call_claude_for_file()` | Signature inspection: `model` default is `None` | Backward-compatible |
| T110 | `generate_file_with_retry()` | `filepath="tests/__init__.py"`, mocked routing/call | `select_model_for_file` called; model passed to `call_claude_for_file` |
| T120 | `select_model_for_file()` | `estimated_line_count=-1` | `CLAUDE_MODEL` |
| T130 | `select_model_for_file()` | `estimated_line_count=1` | `HAIKU_MODEL` |
| T140 | `select_model_for_file()` | `estimated_line_count=51` | `CLAUDE_MODEL` |
| T150 | Coverage check | `pytest --cov --cov-fail-under=95` | Exit code 0 |
| T160 | Regression check | `pytest tests/unit/ -m "not integration"` | Exit code 0 |

## 11. Implementation Notes

### 11.1 Error Handling Convention

The `select_model_for_file()` function does not raise exceptions for any valid input combination. If `file_path` is any string (including empty), it will work — `Path("").name` returns `""`, which won't match any boilerplate filename, so it falls through to default. This is intentional: the routing function should never be a source of errors.

The `call_claude_for_file()` function's existing error handling (whatever exception types it raises today) remains unchanged. The new `model` parameter simply changes which model string is passed to the API.

### 11.2 Logging Convention

Use Python's `logging` module at `INFO` level for routing decisions. The logger is named after the module (`__name__`). Log format: `"Routing {file_path} -> {model} (reason: {reason})"`. This provides:
- Which file triggered the decision
- Which model was selected
- Why that model was selected

Example log output:
```
INFO:assemblyzero.workflows.testing.nodes.implement_code:Routing tests/__init__.py -> claude-3-haiku-20240307 (reason: boilerplate filename)
INFO:assemblyzero.workflows.testing.nodes.implement_code:Routing assemblyzero/core/engine.py -> claude-sonnet-4-20250514 (reason: default)
```

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `HAIKU_MODEL` | `"claude-3-haiku-20240307"` | Cheapest Claude model suitable for boilerplate generation. Model string from Anthropic API docs. |
| `SMALL_FILE_LINE_THRESHOLD` | `50` | Files under 50 lines are simple enough for Haiku. Per LLD issue #641 specification. |

### 11.4 Backward Compatibility

All changes are strictly backward-compatible:

1. **`call_claude_for_file()`**: New `model` parameter defaults to `None`. When `None`, the function resolves to `CLAUDE_MODEL` exactly as before. All existing callers that don't pass `model` continue working unchanged.

2. **`generate_file_with_retry()`**: New `estimated_line_count` and `is_test_scaffold` parameters default to `0` and `False`. When both are default, and the file is not an `__init__.py` or `conftest.py`, the routing returns `CLAUDE_MODEL` — identical to pre-change behavior.

3. **No import changes for callers**: The new function `select_model_for_file()` only needs to be imported by callers that want to use it directly. The automatic routing happens inside `generate_file_with_retry()`.

### 11.5 Important: Discovering the Actual Function Body

The current state excerpt shows only function signatures (the full body is truncated with `...`). The implementer **must read the actual file** to:

1. Find where `CLAUDE_MODEL` is referenced inside `call_claude_for_file()` to know where to insert `resolved_model`.
2. Find where `call_claude_for_file()` is invoked inside `generate_file_with_retry()` to add the `model=model` keyword argument.
3. Determine if there are multiple call paths within `generate_file_with_retry()` (e.g., initial attempt vs retry) that each need the `model` parameter.

The diffs in Section 6 provide the pattern, but exact line numbers will need to be verified against the actual file.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 10)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #641 |
| Verdict | DRAFT |
| Date | 2026-03-06 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #641 |
| Verdict | APPROVED |
| Date | 2026-03-07 |
| Iterations | 0 |
| Finalized | 2026-03-07T02:02:26Z |

### Review Feedback Summary

The Implementation Spec is exceptionally well-crafted, providing explicit line-by-line diffs, concrete input/output examples, and the complete source code for the test file. The step-by-step instructions perfectly align with the provided current state code excerpts, eliminating ambiguity and ensuring a high probability of first-try success for an autonomous AI agent.

## Suggestions
- In Change 5, consider explicitly showing the Anthropic SDK call signature in the diff to ensure the agent replac...


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      docs/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_metrics/
    test_rag/
    test_spelunking/
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
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
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
      runners/
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
  hourglass/
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
"""N4: Implement Code node for TDD Testing Workflow.

Issue #272: File-by-file prompting with mechanical validation.
Issue #309: Add retry logic on validation failure (up to 3 attempts).
Issue #188: LLD path enforcement in prompts and write validation.

Key changes from original:
- Iterate through files_to_modify one at a time (not batch)
- Accumulate context: each file sees LLD + previously completed files
- Mechanical validation: code block exists, not empty, parses
- RETRY on validation failure: up to 3 attempts with error feedback
- WE control the file path, not Claude
- Issue #188: Prompt includes allowed paths; writes validated against LLD
"""

from assemblyzero.utils.shell import run_command
import ast
import os
import re
import random

import logging
import shutil

from assemblyzero.core.config import CLAUDE_MODEL
from assemblyzero.core.text_sanitizer import strip_emoji
import subprocess
import sys
from assemblyzero.telemetry import emit
import threading
import time
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost
from assemblyzero.hooks.file_write_validator import validate_file_write
from assemblyzero.utils.cost_tracker import accumulate_node_cost
from assemblyzero.utils.file_type import get_file_type_info, get_language_tag
from assemblyzero.utils.lld_path_enforcer import (
    build_implementation_prompt_section,
    detect_scaffolded_test_files,
    extract_paths_from_lld,
)
from assemblyzero.workflows.requirements.audit import (
    get_repo_structure,
)
from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.circuit_breaker import record_iteration_cost
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Issue #309: Maximum retry attempts per file
MAX_FILE_RETRIES = 2

# Issue #324: Large file thresholds for diff-based generation
LARGE_FILE_LINE_THRESHOLD = 500  # Lines
LARGE_FILE_BYTE_THRESHOLD = 15000  # Bytes (~15KB)

# Issue #321: Timeout constants
# Issue #373: Increased from 300s — large test file prompts need more time
CLI_TIMEOUT = 600  # 10 minutes base for CLI subprocess
SDK_TIMEOUT = 600  # 10 minutes base for SDK API call

# Issue #644: Prompt size cap for code generation (chars)
CODE_GEN_PROMPT_CAP = 60_000

# Issue #641: Model routing constants
logger = logging.getLogger(__name__)
HAIKU_MODEL = "claude-3-haiku-20240307"
SMALL_FILE_LINE_THRESHOLD = 50  # Files under this line count route to Haiku


class ProgressReporter:
    """Print elapsed time periodically during long operations.

    Issue #267: Prevents the workflow from appearing frozen during
    long Claude API calls. Prints every `interval` seconds.

    Usage:
        with ProgressReporter("Calling Claude", interval=15):
            response = call_claude_for_file(prompt)
    """

    def __init__(self, label: str = "Waiting", interval: int = 15):
        self.label = label
        self.interval = interval
        self._start: float = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        self._start = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        elapsed = int(time.monotonic() - self._start)
        status = "done" if not exc[0] else "error"
        print(f"        {self.label}... {status} ({elapsed}s)")
        return False

    def _run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval)
            if not self._stop_event.is_set():
                elapsed = int(time.monotonic() - self._start)
                print(f"        {self.label}... ({elapsed}s)", flush=True)


class ImplementationError(Exception):
    """Raised when implementation fails mechanically.

    Graph runner should catch this and exit non-zero.
    """
    def __init__(self, filepath: str, reason: str, response_preview: str | None = None):
        self.filepath = filepath
        self.reason = reason
        self.response_preview = response_preview
        super().__init__(f"FATAL: Failed to implement {filepath}: {reason}")


def _find_claude_cli() -> str | None:
    """Find the Claude CLI executable."""
    cli = shutil.which("claude")
    if cli:
        return cli

    npm_paths = [
        Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "claude",
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/c/Users") / os.environ.get("USERNAME", "") / "AppData" / "Roaming" / "npm" / "claude.cmd",
    ]

    for path in npm_paths:
        if path.exists():
            return str(path)

    return None


# =============================================================================
# Mechanical Validation (no LLM judgment)
# =============================================================================

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


def estimate_context_tokens(lld_content: str, completed_files: list[tuple[str, str]]) -> int:
    """Estimate token count for context.

    Uses simple heuristic: ~4 chars per token.
    """
    total_chars = len(lld_content)
    for filepath, content in completed_files:
        total_chars += len(filepath) + len(content) + 50  # 50 for formatting

    return total_chars // 4


def summarize_file_for_context(content: str) -> str:
    """Extract imports and signatures from a Python file for compact context.

    Issue #373: Instead of embedding full file bodies (~20KB+) in accumulated
    context, extract only what subsequent files need: imports, class/function
    signatures, and their docstrings. Reduces context from ~20KB to ~2-3KB.

    Args:
        content: Full Python file content.

    Returns:
        Compact summary with imports and signatures.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If we can't parse it, return first 50 lines as fallback
        lines = content.split("\n")
        return "\n".join(lines[:50]) + "\n# ... (truncated, syntax error in original)\n"

    parts: list[str] = []

    # Extract module docstring
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        docstring = tree.body[0].value.value
        parts.append(f'"""{docstring}"""')

    # Extract all imports
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Get the source lines for this import
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            source_lines = content.split("\n")[start:end]
            parts.append("\n".join(source_lines))

    # Extract class and function signatures
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            parts.append(_summarize_class(node, content))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(_summarize_function(node, content))

    # Extract module-level constants/type aliases (simple assignments)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            source_lines = content.split("\n")[start:end]
            line_text = "\n".join(source_lines)
            # Only include short assignments (constants, not large data structures)
            if len(line_text) < 200:
                parts.append(line_text)

    return "\n\n".join(parts)


def _summarize_function(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> str:
    """Extract function signature and docstring."""
    # Get the def line from source
    start = node.lineno - 1
    source_lines = source.split("\n")

    # Find the end of the signature (the line with the colon)
    sig_lines = []
    for i in range(start, min(start + 10, len(source_lines))):
        sig_lines.append(source_lines[i])
        if source_lines[i].rstrip().endswith(":"):
            break

    sig = "\n".join(sig_lines)

    # Get docstring if present
    docstring = ast.get_docstring(node)
    if docstring:
        # Use only first 3 lines of docstring
        doc_lines = docstring.split("\n")[:3]
        indent = "    "
        sig += f'\n{indent}"""{chr(10).join(doc_lines)}"""'

    sig += "\n    ..."
    return sig


def _summarize_class(node: ast.ClassDef, source: str) -> str:
    """Extract class signature, docstring, and method signatures."""
    source_lines = source.split("\n")
    start = node.lineno - 1

    # Get class def line
    class_lines = []
    for i in range(start, min(start + 5, len(source_lines))):
        class_lines.append(source_lines[i])
        if source_lines[i].rstrip().endswith(":"):
            break

    parts = ["\n".join(class_lines)]

    # Get class docstring
    docstring = ast.get_docstring(node)
    if docstring:
        doc_lines = docstring.split("\n")[:3]
        parts.append(f'    """{chr(10).join(doc_lines)}"""')

    # Get method signatures
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_sig = _summarize_function(item, source)
            parts.append(method_sig)

    return "\n\n".join(parts)


# =============================================================================
# Issue #324: Diff-Based Generation for Large Files
# =============================================================================


def is_large_file(content: str) -> bool:
    """Check if file content exceeds size thresholds.

    Issue #324: Large files (500+ lines OR 15KB+) should use diff mode
    instead of full file regeneration.

    Args:
        content: The file content to check.

    Returns:
        True if file exceeds either threshold.
    """
    if not content:
        return False

    # Check line count (500+ lines = large)
    line_count = len(content.split("\n"))
    if line_count > LARGE_FILE_LINE_THRESHOLD:
        return True

    # Check byte size (15KB+ = large)
    byte_count = len(content.encode("utf-8"))
    if byte_count > LARGE_FILE_BYTE_THRESHOLD:
        return True

    return False


def select_generation_strategy(change_type: str, existing_content: str | None) -> str:
    """Select code generation strategy based on change type and file size.

    Issue #324: Use diff mode for large file modifications.

    Args:
        change_type: "Add", "Modify", or "Delete".
        existing_content: Current file content (None for new files).

    Returns:
        "standard" or "diff".
    """
    # Add and Delete always use standard mode
    if change_type.lower() in ("add", "delete"):
        return "standard"

    # Modify: check file size
    if existing_content and is_large_file(existing_content):
        return "diff"

    return "standard"


def build_diff_prompt(
    lld_content: str,
    existing_content: str,
    test_content: str,
    file_path: str,
) -> str:
    """Build prompt requesting FIND/REPLACE diff format.

    Issue #324: For large files, request targeted changes instead of
    full file regeneration.

    Args:
        lld_content: The LLD specification.
        existing_content: Current file content.
        test_content: Test code that must pass.
        file_path: Path to the file being modified.

    Returns:
        Prompt string for diff-based generation.
    """
    prompt = f"""# Modification Request: {file_path}

## Task

Modify the existing file using FIND/REPLACE blocks. Do NOT output the entire file.

## LLD Specification

{lld_content}

## Current File Content

```python
{existing_content}
```

"""

    if test_content:
        prompt += f"""## Tests That Must Pass

```python
{test_content}
```

"""

    prompt += """

## Previous Attempt Failed (Attempt 2/2)

Your previous response had an error:

```
No code block found in response
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.

## Output Format

Output ONLY the changes using this FIND/REPLACE format:

### CHANGE 1: Brief description of what this change does
FIND:
```python
exact code to find
```

REPLACE WITH:
```python
replacement code
```

### CHANGE 2: Next change description
FIND:
```python
...
```

REPLACE WITH:
```python
...
```

CRITICAL RULES:
1. Do NOT output the entire file - only the FIND/REPLACE blocks
2. Each FIND block must match EXACTLY in the current file
3. Include enough context in FIND to be unambiguous (unique match)
4. Number your changes: CHANGE 1, CHANGE 2, etc.
5. Describe what each change does in the header
"""

    return prompt


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

    # Pattern to match CHANGE headers
    # Matches: ### CHANGE N: description
    change_pattern = re.compile(
        r"###\s*CHANGE\s*\d+\s*:\s*(.+?)(?=\n)",
        re.IGNORECASE
    )

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
        header_marker = sections[i]  # "### CHANGE N:"
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


# =============================================================================
# Prompt Building
# =============================================================================

def build_single_file_prompt(
    filepath: str,
    file_spec: dict,
    lld_content: str,
    completed_files: list[tuple[str, str]],
    repo_root: Path,
    test_content: str = "",
    previous_error: str = "",
    path_enforcement_section: str = "",
    context_content: str = "",
    repo_structure: str = "",
) -> str:
    """Build prompt for a single file with accumulated context.

    Issue #188: Added path_enforcement_section parameter to inject allowed paths.
    Issue #288: Added context_content parameter for injected architectural context.
    Issue #445: Added repo_structure parameter to ground Claude in actual layout.
    """

    change_type = file_spec.get("change_type", "Add")
    description = file_spec.get("description", "")

    prompt = f"""# Implementation Request: {filepath}

## Task

Write the complete contents of `{filepath}`.

Change type: {change_type}
Description: {description}

## LLD Specification

{lld_content}

"""

    # Issue #188: Add path enforcement section
    if path_enforcement_section:
        prompt += path_enforcement_section + "\n"

    # Issue #445: Add repo structure to ground Claude in actual layout
    if repo_structure:
        prompt += f"""## Repository Structure

The actual directory layout of this repository:

```
{repo_structure}
```

Use these real paths — do NOT invent paths that don't exist.

"""

    # Issue #288: Add injected context
    if context_content:
        prompt += f"""## Additional Context

{context_content}

"""

    # Include existing file content if modifying
    if change_type.lower() == "modify":
        existing_path = repo_root / filepath
        if existing_path.exists():
            try:
                existing_content = existing_path.read_text(encoding="utf-8")
                prompt += f"""## Existing File Contents

The file currently contains:

```python
{existing_content}
```

Modify this file according to the LLD specification.

"""
            except Exception:
                pass

    # Include test content if available
    if test_content:
        prompt += f"""## Tests That Must Pass

```python
{test_content}
```

"""

    # Issue #373: Include previously completed files with trimmed context.
    # Only the most recent file (N-1) gets full content for continuity.
    # All earlier files get signature-only summaries to reduce prompt size.
    if completed_files:
        prompt += "## Previously Implemented Files\n\n"
        prompt += "These files have already been implemented. Use them for imports and references:\n\n"
        for idx, (prev_path, prev_content) in enumerate(completed_files):
            is_most_recent = (idx == len(completed_files) - 1)
            if is_most_recent:
                # Most recent file: full content for continuity
                prompt += f"""### {prev_path} (full)

```python
{prev_content}
```

"""
            else:
                # Earlier files: signatures only to save context
                summary = summarize_file_for_context(prev_content)
                prompt += f"""### {prev_path} (signatures)

```python
{summary}
```

"""

    # Include previous error if this is a retry... wait, no retries!
    # Actually we might loop back from green phase failure, so include error context
    if previous_error:
        prompt += f"""## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
{previous_error}
```

Read the error messages carefully and fix the root cause in your implementation.

"""

    # Issue #447: File-type-aware output format
    info = get_file_type_info(filepath)
    tag = info["language_tag"]
    descriptor = info["content_descriptor"]
    block_tag = tag if tag else ""

    prompt += f"""