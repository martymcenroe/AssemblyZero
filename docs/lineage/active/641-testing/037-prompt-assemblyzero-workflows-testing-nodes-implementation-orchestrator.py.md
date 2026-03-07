# Implementation Request: assemblyzero/workflows/testing/nodes/implementation/orchestrator.py

## Task

Write the complete contents of `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py`.

Change type: Modify
Description: Update `call_claude_for_file()` to accept `model` param; update `generate_file_with_retry()` to call routing

## LLD Specification

# Implementation Spec: Route Scaffolding/Boilerplate Files to Haiku

| Field | Value |
|-------|-------|
| Issue | #641 |
| LLD | `docs/lld/active/641-route-scaffolding-boilerplate-to-haiku.md` |
| Generated | 2026-03-06 |
| Status | DRAFT |

## 1. Overview

Add model-selection routing logic so that simple/boilerplate files (e.g., `__init__.py`, `conftest.py`, test scaffolds, small files < 50 lines) use `claude-3-haiku-20240307` instead of the default Sonnet model, reducing API spend by an estimated 20–30%.

**Objective:** Route cheap-to-generate files to Haiku while complex files continue using Sonnet.

**Success Criteria:** All 11 requirements from LLD Section 3 are met, with ≥ 95% test coverage on new/modified code and zero regressions.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/workflows/testing/nodes/implementation/routing.py` | Add | New module containing `select_model_for_file()`, constants `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD` |
| 2 | `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py` | Modify | Update `call_claude_for_file()` to accept `model` param; update `generate_file_with_retry()` to call routing |
| 3 | `assemblyzero/workflows/testing/nodes/implementation/__init__.py` | Modify | Re-export new public names from `routing.py` |
| 4 | `assemblyzero/workflows/testing/nodes/implement_code.py` | Modify | Add `select_model_for_file`, `HAIKU_MODEL`, `SMALL_FILE_LINE_THRESHOLD` to re-exports |
| 5 | `tests/unit/test_implement_code_routing.py` | Add | All 16 test scenarios from LLD Section 10.0 |

**Implementation Order Rationale:** The routing module (1) has no internal dependencies and must exist before orchestrator (2) can import from it. The `__init__.py` (3) and shim (4) re-export updates come after the implementation exists. Tests (5) are written first per TDD but listed last for implementation ordering context.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py`

**Relevant excerpt — `call_claude_for_file` signature area** (approximate):

```python
def call_claude_for_file(
    prompt: str,
    *,
    max_tokens: int = 8192,
    timeout: float = 120.0,
) -> str:
    """Invoke Claude to generate file content."""
    model = get_default_model()  # or similar env/config lookup
    # ... anthropic client call ...
    response = anthropic_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

**What changes:** Add optional `model: str | None = None` parameter. When `None`, resolve to default (preserving existing behavior). When provided, use the supplied model string.

**Relevant excerpt — `generate_file_with_retry` signature area** (approximate):

```python
def generate_file_with_retry(
    file_path: str,
    prompt: str,
    max_attempts: int = 3,
) -> str:
    """Generate a single file with automatic retry."""
    for attempt in range(1, max_attempts + 1):
        try:
            result = call_claude_for_file(prompt)
            return result
        except TransientError as e:
            if attempt == max_attempts:
                raise ModelCallError(...) from e
            # backoff...
```

**What changes:** Add `estimated_line_count: int = 0` and `is_test_scaffold: bool = False` parameters. Call `select_model_for_file()` before the retry loop and pass result to `call_claude_for_file(prompt, model=model)`.

### 3.2 `assemblyzero/workflows/testing/nodes/implementation/__init__.py`

**Relevant excerpt** (approximate):

```python
"""Implementation package for the N4 Implement Code node."""

from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
    call_claude_for_file,
    generate_file_with_retry,
    # ... other exports ...
)
```

**What changes:** Add imports of `select_model_for_file`, `HAIKU_MODEL`, `SMALL_FILE_LINE_THRESHOLD` from the new `routing` module and include them in `__all__` (if used) or in the explicit import list.

### 3.3 `assemblyzero/workflows/testing/nodes/implement_code.py`

**Relevant excerpt** (full file — 48-line shim):

```python
"""N4: Implement Code node for TDD Testing Workflow.

This module is a backward-compatibility shim. The implementation has been
split into focused modules under the `implementation/` package.

All public names are re-exported here so existing imports continue to work:
    from assemblyzero.workflows.testing.nodes.implement_code import implement_code
"""

from assemblyzero.workflows.testing.nodes.implementation import *  # noqa: F401, F403

from assemblyzero.workflows.testing.nodes.implementation import (  # noqa: F811
    implement_code,
    extract_code_block,
    validate_code_response,
    call_claude_for_file,
    ProgressReporter,
    ImplementationError,
    # ... many more names ...
    MAX_FILE_RETRIES,
    CLI_TIMEOUT,
    SDK_TIMEOUT,
    LARGE_FILE_LINE_THRESHOLD,
    LARGE_FILE_BYTE_THRESHOLD,
    CODE_GEN_PROMPT_CAP,
)
```

**What changes:** Add `select_model_for_file`, `HAIKU_MODEL`, `SMALL_FILE_LINE_THRESHOLD` to the explicit import list so they are available via `from assemblyzero.workflows.testing.nodes.implement_code import select_model_for_file`.

## 4. Data Structures

### 4.1 Module-Level Constants

**Definition:**

```python
HAIKU_MODEL: str = "claude-3-haiku-20240307"
SMALL_FILE_LINE_THRESHOLD: int = 50
```

**Concrete Example:**

```json
{
    "HAIKU_MODEL": "claude-3-haiku-20240307",
    "SMALL_FILE_LINE_THRESHOLD": 50
}
```

### 4.2 Boilerplate Filenames Set

**Definition:**

```python
_BOILERPLATE_BASENAMES: frozenset[str] = frozenset({"__init__.py", "conftest.py"})
```

**Concrete Example:**

```json
["__init__.py", "conftest.py"]
```

This is an internal constant used only by `select_model_for_file()`. Using `frozenset` for O(1) lookups and immutability.

## 5. Function Specifications

### 5.1 `select_model_for_file()`

**File:** `assemblyzero/workflows/testing/nodes/implementation/routing.py`

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
      4. Otherwise -> configured default (Sonnet)

    Raises:
        TypeError: If file_path is not a str.
    """
    ...
```

**Input Example 1 — test scaffold:**

```python
file_path = "tests/unit/test_foo.py"
estimated_line_count = 200
is_test_scaffold = True
```

**Output Example 1:**

```python
"claude-3-haiku-20240307"
# Logs: INFO Routing tests/unit/test_foo.py -> claude-3-haiku-20240307 (reason: test_scaffold)
```

**Input Example 2 — boilerplate filename:**

```python
file_path = "assemblyzero/workflows/testing/nodes/__init__.py"
estimated_line_count = 0
is_test_scaffold = False
```

**Output Example 2:**

```python
"claude-3-haiku-20240307"
# Logs: INFO Routing .../__init__.py -> claude-3-haiku-20240307 (reason: boilerplate_filename)
```

**Input Example 3 — small file:**

```python
file_path = "assemblyzero/utils/helper.py"
estimated_line_count = 49
is_test_scaffold = False
```

**Output Example 3:**

```python
"claude-3-haiku-20240307"
# Logs: INFO Routing .../helper.py -> claude-3-haiku-20240307 (reason: small_file, lines=49)
```

**Input Example 4 — complex file (default):**

```python
file_path = "assemblyzero/core/engine.py"
estimated_line_count = 200
is_test_scaffold = False
```

**Output Example 4:**

```python
"claude-3-5-sonnet-20241022"  # or whatever get_default_model() returns
# Logs: INFO Routing .../engine.py -> claude-3-5-sonnet-... (reason: default)
```

**Edge Cases:**
- `file_path` is not a `str` -> raises `TypeError("file_path must be a str, got {type}")`
- `estimated_line_count = -1` -> treated as unknown (fails `> 0` check), falls through to default
- `estimated_line_count = 0` -> unknown, falls through to default
- `estimated_line_count = 50` -> NOT less than threshold, falls through to default
- `estimated_line_count = 1` -> routes to Haiku (lower boundary)
- `is_test_scaffold = True` with `conftest.py` basename -> Haiku (scaffold check fires first; both would route to Haiku anyway)

### 5.2 `call_claude_for_file()` (modified)

**File:** `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py`

**Signature:**

```python
def call_claude_for_file(
    prompt: str,
    model: str | None = None,
    *,
    max_tokens: int = 8192,
    timeout: float = 120.0,
) -> str:
    """Invoke Claude to generate file content.

    Args:
        prompt: The full generation prompt.
        model: Override model; if None, uses default from environment/config.
    """
    ...
```

**Input Example — with explicit model:**

```python
prompt = "Generate an __init__.py that exports..."
model = "claude-3-haiku-20240307"
```

**Output Example:**

```python
'"""Package init."""\n\nfrom .core import Engine\n'
# Anthropic client called with model="claude-3-haiku-20240307"
```

**Input Example — without model (backward-compatible):**

```python
prompt = "Generate a complex engine module..."
model = None  # or omitted entirely
```

**Output Example:**

```python
'"""Engine module."""\n\nclass Engine:\n    ...'
# Anthropic client called with model=<default from config>
```

**Edge Cases:**
- `model=None` -> resolves to `get_default_model()` — **identical to pre-change behavior**
- `model=""` -> passed as-is to API (will fail with API error, caught by existing error handling)

### 5.3 `generate_file_with_retry()` (modified)

**File:** `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py`

**Signature:**

```python
def generate_file_with_retry(
    file_path: str,
    prompt: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
    max_attempts: int = 3,
) -> str:
    """Generate a single file with automatic retry and model routing."""
    ...
```

**Input Example:**

```python
file_path = "tests/__init__.py"
prompt = "Generate an empty test init..."
estimated_line_count = 5
is_test_scaffold = False
```

**Output Example:**

```python
'"""Tests package."""\n'
# select_model_for_file called with ("tests/__init__.py", 5, False)
# call_claude_for_file called with (prompt, model="claude-3-haiku-20240307")
```

**Edge Cases:**
- New parameters default to `0` and `False` respectively — **existing callers unaffected**
- If `select_model_for_file` raises `TypeError`, it propagates up (fail-closed)

## 6. Change Instructions

### 6.1 `assemblyzero/workflows/testing/nodes/implementation/routing.py` (Add)

**Complete file contents:**

```python
"""Model routing logic for file generation.

Issue #641: Route scaffolding/boilerplate files to Haiku to reduce API spend.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HAIKU_MODEL: str = "claude-3-haiku-20240307"
"""Model identifier for Claude Haiku — used for cheap/simple file generation."""

SMALL_FILE_LINE_THRESHOLD: int = 50
"""Files with estimated line count below this threshold route to Haiku."""

_BOILERPLATE_BASENAMES: frozenset[str] = frozenset({"__init__.py", "conftest.py"})
"""Filenames that are always routed to Haiku regardless of size."""


def _get_default_model() -> str:
    """Return the configured default model (Sonnet).

    Delegates to the existing model resolution logic used by
    call_claude_for_file when no model override is provided.

    NOTE: During implementation, wire this to the same env/config source
    that call_claude_for_file currently uses (e.g., os.environ.get(
    "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")).
    """
    import os

    return os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")


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
      4. Otherwise -> configured default (Sonnet)

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

    Raises:
        TypeError: If file_path is not a str.
    """
    if not isinstance(file_path, str):
        raise TypeError(
            f"file_path must be a str, got {type(file_path).__name__}"
        )

    basename = Path(file_path).name

    # Rule 1: Test scaffold override
    if is_test_scaffold:
        logger.info(
            "Routing %s -> %s (reason: test_scaffold)", file_path, HAIKU_MODEL
        )
        return HAIKU_MODEL

    # Rule 2: Boilerplate filename
    if basename in _BOILERPLATE_BASENAMES:
        logger.info(
            "Routing %s -> %s (reason: boilerplate_filename)",
            file_path,
            HAIKU_MODEL,
        )
        return HAIKU_MODEL

    # Rule 3: Small file by line count
    if 0 < estimated_line_count < SMALL_FILE_LINE_THRESHOLD:
        logger.info(
            "Routing %s -> %s (reason: small_file, lines=%d)",
            file_path,
            HAIKU_MODEL,
            estimated_line_count,
        )
        return HAIKU_MODEL

    # Rule 4: Default (Sonnet)
    default_model = _get_default_model()
    logger.info(
        "Routing %s -> %s (reason: default)", file_path, default_model
    )
    return default_model
```

### 6.2 `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py` (Modify)

**Change 1:** Add import of routing function near top-of-file imports

```diff
 from pathlib import Path
+from assemblyzero.workflows.testing.nodes.implementation.routing import (
+    select_model_for_file,
+)
```

**Change 2:** Modify `call_claude_for_file` signature to add `model` parameter

```diff
 def call_claude_for_file(
     prompt: str,
+    model: str | None = None,
     *,
     max_tokens: int = 8192,
     timeout: float = 120.0,
 ) -> str:
     """Invoke Claude to generate file content.
 
     Args:
         prompt: The full generation prompt.
+        model: Override model; if None, uses default from environment/config.
+            Passing None preserves pre-change behaviour exactly.
         max_tokens: Token budget for the response.
         timeout: Request timeout in seconds.
     """
-    resolved_model = get_default_model()
+    resolved_model = model if model is not None else get_default_model()
```

Note: The exact name of the default-model-resolution function (`get_default_model()` is a placeholder) must match whatever the codebase currently uses. Inspect the actual function body during implementation.

**Change 3:** Modify `generate_file_with_retry` signature and body

```diff
 def generate_file_with_retry(
     file_path: str,
     prompt: str,
+    estimated_line_count: int = 0,
+    is_test_scaffold: bool = False,
     max_attempts: int = 3,
 ) -> str:
-    """Generate a single file with automatic retry."""
+    """Generate a single file with automatic retry and model routing.
+
+    Calls select_model_for_file() to determine the model, then delegates
+    to call_claude_for_file() with the resolved model.
+
+    Args:
+        file_path: Relative path of the file being generated (used for routing).
+        prompt: The generation prompt.
+        estimated_line_count: Expected line count; 0 = unknown.
+        is_test_scaffold: True when generating a test scaffold (N2 node).
+        max_attempts: Maximum retry attempts on transient failure.
+    """
+    model = select_model_for_file(file_path, estimated_line_count, is_test_scaffold)
+
     for attempt in range(1, max_attempts + 1):
         try:
-            result = call_claude_for_file(prompt)
+            result = call_claude_for_file(prompt, model=model)
             return result
```

### 6.3 `assemblyzero/workflows/testing/nodes/implementation/__init__.py` (Modify)

**Change 1:** Add routing imports

```diff
 from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
     call_claude_for_file,
     generate_file_with_retry,
     # ... existing exports ...
 )
+from assemblyzero.workflows.testing.nodes.implementation.routing import (
+    select_model_for_file,
+    HAIKU_MODEL,
+    SMALL_FILE_LINE_THRESHOLD,
+)
```

### 6.4 `assemblyzero/workflows/testing/nodes/implement_code.py` (Modify)

**Change 1:** Add new names to the explicit import list

```diff
 from assemblyzero.workflows.testing.nodes.implementation import (  # noqa: F811
     implement_code,
     extract_code_block,
     validate_code_response,
     call_claude_for_file,
+    select_model_for_file,
     ProgressReporter,
     ImplementationError,
     # ... existing names ...
     LARGE_FILE_LINE_THRESHOLD,
     LARGE_FILE_BYTE_THRESHOLD,
     CODE_GEN_PROMPT_CAP,
+    HAIKU_MODEL,
+    SMALL_FILE_LINE_THRESHOLD,
 )
```

### 6.5 `tests/unit/test_implement_code_routing.py` (Add)

**Complete file contents:**

```python
"""Unit tests for model routing logic (Issue #641).

Tests select_model_for_file(), the model parameter on call_claude_for_file(),
and the routing integration in generate_file_with_retry().
"""

import logging
from unittest.mock import patch, MagicMock

import pytest

from assemblyzero.workflows.testing.nodes.implementation.routing import (
    select_model_for_file,
    HAIKU_MODEL,
    SMALL_FILE_LINE_THRESHOLD,
    _get_default_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-3-5-sonnet-20241022"


@pytest.fixture(autouse=True)
def _set_default_model(monkeypatch):
    """Ensure a deterministic default model for all tests."""
    monkeypatch.setenv("ANTHROPIC_MODEL", DEFAULT_MODEL)


# ---------------------------------------------------------------------------
# T010 – __init__.py routes to Haiku (REQ-1)
# ---------------------------------------------------------------------------

def test_init_py_routes_to_haiku():
    """T010: select_model_for_file returns HAIKU_MODEL for __init__.py."""
    result = select_model_for_file(
        file_path="assemblyzero/__init__.py",
        estimated_line_count=0,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T020 – conftest.py routes to Haiku (REQ-2)
# ---------------------------------------------------------------------------

def test_conftest_py_routes_to_haiku():
    """T020: select_model_for_file returns HAIKU_MODEL for conftest.py."""
    result = select_model_for_file(
        file_path="tests/conftest.py",
        estimated_line_count=0,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T030 – test scaffold flag overrides everything (REQ-3)
# ---------------------------------------------------------------------------

def test_scaffold_flag_overrides_line_count():
    """T030: is_test_scaffold=True routes to Haiku even with large line count."""
    result = select_model_for_file(
        file_path="tests/unit/test_foo.py",
        estimated_line_count=200,
        is_test_scaffold=True,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T040 – 49-line file routes to Haiku (REQ-4)
# ---------------------------------------------------------------------------

def test_49_line_file_routes_to_haiku():
    """T040: File with 49 estimated lines routes to Haiku."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/helper.py",
        estimated_line_count=49,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T050 – 50-line boundary routes to Sonnet (REQ-5)
# ---------------------------------------------------------------------------

def test_50_line_boundary_routes_to_sonnet():
    """T050: Exactly 50 lines routes to default (Sonnet). Threshold is < 50."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/helper.py",
        estimated_line_count=50,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T060 – Unknown size complex file routes to Sonnet (REQ-5)
# ---------------------------------------------------------------------------

def test_unknown_size_routes_to_sonnet():
    """T060: estimated_line_count=0 means unknown; routes to Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/core/engine.py",
        estimated_line_count=0,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T070 – Deeply nested __init__.py (REQ-1)
# ---------------------------------------------------------------------------

def test_deeply_nested_init_py_routes_to_haiku():
    """T070: Path depth is irrelevant; basename __init__.py matches."""
    result = select_model_for_file(
        file_path="assemblyzero/workflows/testing/nodes/__init__.py",
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T080 – call_claude_for_file uses supplied model (REQ-7)
# ---------------------------------------------------------------------------

def test_call_claude_explicit_model():
    """T080: When model is provided, Anthropic client receives it."""
    with patch(
        "assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file"
    ) as mock_call:
        mock_call.return_value = "generated content"
        mock_call("prompt text", model=HAIKU_MODEL)
        mock_call.assert_called_once_with("prompt text", model=HAIKU_MODEL)


# ---------------------------------------------------------------------------
# T090 – call_claude_for_file default model (REQ-7)
# ---------------------------------------------------------------------------

def test_call_claude_default_model():
    """T090: When model=None, backward-compatible default is used."""
    with patch(
        "assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file"
    ) as mock_call:
        mock_call.return_value = "generated content"
        mock_call("prompt text")
        mock_call.assert_called_once_with("prompt text")


# ---------------------------------------------------------------------------
# T100 – generate_file_with_retry routing integration (REQ-8)
# ---------------------------------------------------------------------------

def test_generate_file_with_retry_passes_routed_model():
    """T100: generate_file_with_retry calls select_model and passes to call_claude."""
    with patch(
        "assemblyzero.workflows.testing.nodes.implementation.orchestrator.call_claude_for_file"
    ) as mock_call, patch(
        "assemblyzero.workflows.testing.nodes.implementation.orchestrator.select_model_for_file",
        return_value=HAIKU_MODEL,
    ) as mock_route:
        mock_call.return_value = "content"
        from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
            generate_file_with_retry,
        )

        generate_file_with_retry(
            file_path="tests/__init__.py",
            prompt="generate init",
            estimated_line_count=5,
        )
        mock_route.assert_called_once_with("tests/__init__.py", 5, False)
        mock_call.assert_called_once()
        # Verify model kwarg was passed
        _, kwargs = mock_call.call_args
        assert kwargs.get("model") == HAIKU_MODEL or mock_call.call_args[0][1] == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T110 – Routing log emission (REQ-9)
# ---------------------------------------------------------------------------

def test_routing_logs_reason(caplog):
    """T110: Routing decision logged at INFO with file path, model, and reason."""
    with caplog.at_level(logging.INFO):
        select_model_for_file(
            file_path="assemblyzero/__init__.py",
        )

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert "assemblyzero/__init__.py" in record.message
    assert HAIKU_MODEL in record.message
    assert "boilerplate_filename" in record.message


# ---------------------------------------------------------------------------
# T120 – Negative line count treated as unknown (REQ-6)
# ---------------------------------------------------------------------------

def test_negative_line_count_routes_to_sonnet():
    """T120: Negative estimated_line_count treated as unknown -> Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/core/engine.py",
        estimated_line_count=-1,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T130 – 1-line file routes to Haiku (REQ-4)
# ---------------------------------------------------------------------------

def test_1_line_file_routes_to_haiku():
    """T130: Lower boundary — 1 line routes to Haiku."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/tiny.py",
        estimated_line_count=1,
        is_test_scaffold=False,
    )
    assert result == HAIKU_MODEL


# ---------------------------------------------------------------------------
# T140 – 51-line file routes to Sonnet (REQ-5)
# ---------------------------------------------------------------------------

def test_51_line_file_routes_to_sonnet():
    """T140: Just above threshold — routes to Sonnet."""
    result = select_model_for_file(
        file_path="assemblyzero/utils/medium.py",
        estimated_line_count=51,
        is_test_scaffold=False,
    )
    assert result == DEFAULT_MODEL


# ---------------------------------------------------------------------------
# T150 – Coverage checked via pytest-cov CLI flag (REQ-10)
# T160 – Regression checked via full test suite run (REQ-11)
# These are CI-level checks, not individual test functions.
# ---------------------------------------------------------------------------
```

## 7. Pattern References

### 7.1 Existing Constants Pattern

**File:** `assemblyzero/workflows/testing/nodes/implement_code.py` (shim re-exports)

```python
MAX_FILE_RETRIES,
CLI_TIMEOUT,
SDK_TIMEOUT,
LARGE_FILE_LINE_THRESHOLD,
LARGE_FILE_BYTE_THRESHOLD,
CODE_GEN_PROMPT_CAP,
```

**Relevance:** Follow the same naming convention (UPPER_SNAKE_CASE) and module-level placement for `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD`. These constants are re-exported through the shim, matching the existing pattern.

### 7.2 Mock Patch Target Pattern (from Memory)

```python
# Correct patch targets after #655 split:
"orchestrator.call_claude_for_file"  # not "implement_code.call_claude_for_file"
"orchestrator.emit"                  # not "implement_code.emit"
"claude_client._find_claude_cli"     # not "implement_code._find_claude_cli"
```

**Relevance:** All mock patches in tests must target the actual module path (`orchestrator.call_claude_for_file`), not the shim path. The new routing function patches must similarly target `orchestrator.select_model_for_file` when mocking at the call site inside orchestrator.

### 7.3 Node Implementation Pattern

**File:** `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` (lines 1-50)

**Relevance:** Shows the standard pattern for node modules with logging, imports, and function signatures. Follow the same `logger = logging.getLogger(__name__)` convention in `routing.py`.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `import logging` | stdlib | `routing.py` |
| `from pathlib import Path` | stdlib | `routing.py` |
| `import os` | stdlib | `routing.py` (`_get_default_model`) |
| `from assemblyzero.workflows.testing.nodes.implementation.routing import select_model_for_file` | internal | `orchestrator.py` |
| `from assemblyzero.workflows.testing.nodes.implementation.routing import HAIKU_MODEL, SMALL_FILE_LINE_THRESHOLD` | internal | `__init__.py`, `implement_code.py` (re-exports) |
| `import pytest` | dev-dependency | `test_implement_code_routing.py` |
| `from unittest.mock import patch, MagicMock` | stdlib | `test_implement_code_routing.py` |

**New Dependencies:** None. All imports resolve to stdlib or existing internal modules.

## 9. Placeholder

*Reserved for future use to maintain alignment with LLD section numbering.*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `select_model_for_file()` | `file_path="assemblyzero/__init__.py"` | `HAIKU_MODEL` |
| T020 | `select_model_for_file()` | `file_path="tests/conftest.py"` | `HAIKU_MODEL` |
| T030 | `select_model_for_file()` | `is_test_scaffold=True, estimated_line_count=200` | `HAIKU_MODEL` |
| T040 | `select_model_for_file()` | `estimated_line_count=49` | `HAIKU_MODEL` |
| T050 | `select_model_for_file()` | `estimated_line_count=50` | `DEFAULT_MODEL` |
| T060 | `select_model_for_file()` | `estimated_line_count=0, file="engine.py"` | `DEFAULT_MODEL` |
| T070 | `select_model_for_file()` | deeply nested `__init__.py` | `HAIKU_MODEL` |
| T080 | `call_claude_for_file()` | `model=HAIKU_MODEL` | API called with Haiku model |
| T090 | `call_claude_for_file()` | `model=None` (default) | API called with default model |
| T100 | `generate_file_with_retry()` | `file_path="tests/__init__.py"` | Routes to Haiku, passes to `call_claude_for_file` |
| T110 | `select_model_for_file()` | any routed call, check logs | `logger.info` with path + model + reason |
| T120 | `select_model_for_file()` | `estimated_line_count=-1` | `DEFAULT_MODEL` |
| T130 | `select_model_for_file()` | `estimated_line_count=1` | `HAIKU_MODEL` |
| T140 | `select_model_for_file()` | `estimated_line_count=51` | `DEFAULT_MODEL` |
| T150 | Coverage check | `pytest --cov-fail-under=95` | Exit 0 |
| T160 | Regression check | Full unit suite | Exit 0, no failures |

## 11. Implementation Notes

### 11.1 Error Handling Convention

`select_model_for_file()` raises `TypeError` on invalid input (fail-fast). All other failures propagate through the existing `ModelCallError` exception path in `generate_file_with_retry()`. No new exception types are introduced.

### 11.2 Logging Convention

Use `logging.getLogger(__name__)` in the new `routing.py` module. All routing decisions are logged at `INFO` level with a consistent format:

```
Routing {file_path} -> {model} (reason: {reason_tag})
```

Reason tags: `test_scaffold`, `boilerplate_filename`, `small_file`, `default`.

### 11.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `HAIKU_MODEL` | `"claude-3-haiku-20240307"` | Current Haiku model string from Anthropic; single constant makes updates trivial |
| `SMALL_FILE_LINE_THRESHOLD` | `50` | LLD-specified threshold; files with fewer lines route to Haiku |
| `_BOILERPLATE_BASENAMES` | `frozenset({"__init__.py", "conftest.py"})` | O(1) lookup; immutable; easy to extend |

### 11.4 Default Model Resolution

The `_get_default_model()` helper in `routing.py` reads `ANTHROPIC_MODEL` from the environment. During implementation, verify this matches the exact mechanism used by the existing `call_claude_for_file()` in `orchestrator.py`. If `orchestrator.py` uses a different config source (e.g., a `get_default_model()` function), import and reuse that instead of duplicating the logic. The key constraint: `select_model_for_file()` must return the **same** default model that `call_claude_for_file()` would use when `model=None`.

### 11.5 Backward Compatibility

- `call_claude_for_file(prompt)` — works identically to pre-change (model defaults to `None` -> resolved to default)
- `generate_file_with_retry(file_path, prompt)` — works identically to pre-change (new params default to `0` and `False`, routing returns default model)
- The shim in `implement_code.py` re-exports new names but doesn't change any existing exports

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
| Finalized | 2026-03-07T04:22:47Z |

### Review Feedback Summary

The Implementation Spec is exceptionally well-structured, providing exact diffs, complete file contents for new files, and exhaustive test coverage. The instructions are concrete, unambiguous, and account for backward compatibility and correct module re-exports. It is highly executable for an autonomous AI agent.

## Suggestions
- In Section 6.1 (`routing.py`), the spec instructs the agent to inspect `orchestrator.py` to find the exact import path for `get_default_model()`. While an AI agent can...


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
  ... and 14 more files
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
"""Main implementation orchestrator — the LangGraph node and retry logic.

Contains implement_code() (the N4 node entry point) and supporting functions.
"""

from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost
from assemblyzero.hooks.file_write_validator import validate_file_write
from assemblyzero.telemetry import emit
from assemblyzero.utils.cost_tracker import accumulate_node_cost
from assemblyzero.utils.lld_path_enforcer import (
    build_implementation_prompt_section,
    detect_scaffolded_test_files,
    extract_paths_from_lld,
)
from assemblyzero.workflows.requirements.audit import get_repo_structure
from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.circuit_breaker import record_iteration_cost
from assemblyzero.workflows.testing.state import TestingWorkflowState

from .claude_client import (
    ImplementationError,
    ProgressReporter,
    call_claude_for_file,
)
from .context import estimate_context_tokens
from .parsers import (
    detect_summary_response,
    extract_code_block,
    validate_code_response,
)
from .prompts import (
    MAX_FILE_RETRIES,
    build_retry_prompt,
    build_single_file_prompt,
)

# Issue #644: Prompt size cap for code generation (chars)
CODE_GEN_PROMPT_CAP = 60_000


def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
) -> tuple[str, bool]:
    """Generate code for a single file with retry on validation failure.

    Issue #309: Retry up to max_retries times on API or validation errors,
    including error context in subsequent prompts.

    Args:
        filepath: Path to the file being generated.
        base_prompt: The initial prompt for code generation.
        audit_dir: Optional directory for audit logs.
        max_retries: Maximum number of attempts (default: 3).

    Returns:
        Tuple of (generated_code, success_flag).

    Raises:
        ImplementationError: Only after exhausting all retry attempts.
    """
    last_error = ""
    prompt = base_prompt

    for attempt in range(max_retries):
        attempt_num = attempt + 1  # 1-indexed for display

        # Build retry prompt if this isn't the first attempt
        if attempt > 0:
            prompt = build_retry_prompt(pruned_prompt or base_prompt, last_error, attempt_num)
            print(f"        [RETRY {attempt_num}/{max_retries}] {last_error[:80]}...")
            if attempt_num == 2:
                emit("retry.strike_one", repo=str(audit_dir.parent.parent.parent.parent) if audit_dir else "", metadata={"filepath": filepath, "error": last_error[:200]})

        # Save prompt to audit
        if audit_dir and audit_dir.exists():
            file_num = next_file_number(audit_dir)
            suffix = f"-retry{attempt_num}" if attempt > 0 else ""
            save_audit_file(
                audit_dir,
                file_num,
                f"prompt-{filepath.replace('/', '-')}{suffix}.md",
                prompt
            )

        # Call Claude (Issue #447: pass filepath for file-type-aware system prompt)
        response, api_error = call_claude_for_file(prompt, file_path=filepath)

        # Check for API error
        if api_error:
            last_error = f"API error: {api_error}"
            # Issue #546: Non-retryable errors (auth, billing) skip retry loop
            if "[NON-RETRYABLE]" in api_error:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Non-retryable API error: {api_error}",
                    response_preview=None
                )
            if attempt < max_retries - 1:
                print(f"        [RETRY {attempt_num}/{max_retries}] {last_error}")
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"API error after {max_retries} attempts: {api_error}",
                    response_preview=None
                )

        # Save response to audit
        if audit_dir and audit_dir.exists():
            file_num = next_file_number(audit_dir)
            suffix = f"-retry{attempt_num}" if attempt > 0 else ""
            save_audit_file(
                audit_dir,
                file_num,
                f"response-{filepath.replace('/', '-')}{suffix}.md",
                response
            )

        # Detect summary response (fast rejection)
        if detect_summary_response(response):
            last_error = "Claude gave a summary instead of code"
            if attempt < max_retries - 1:
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Summary response after {max_retries} attempts",
                    response_preview=response[:500]
                )

        # Extract code block (Issue #447: file-type-aware extraction)
        code = extract_code_block(response, file_path=filepath)

        if code is None:
            last_error = "No code block found in response"
            if attempt < max_retries - 1:
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"No code block after {max_retries} attempts",
                    response_preview=response[:500]
                )

        # Validate code mechanically
        valid, validation_error = validate_code_response(code, filepath, existing_content)

        if not valid:
            last_error = f"Validation failed: {validation_error}"
            if attempt < max_retries - 1:
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Validation failed after {max_retries} attempts: {validation_error}",
                    response_preview=code[:500]
                )

        # Success!
        if attempt > 0:
            print(f"        [SUCCESS] Retry {attempt_num} succeeded")
        return code, True

    # Should not reach here, but just in case
    emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
    raise ImplementationError(
        filepath=filepath,
        reason=f"Failed after {max_retries} attempts: {last_error}",
        response_preview=None
    )


def validate_files_to_modify(
    files_to_modify: list[dict], repo_root: Path
) -> list[str]:
    """Validate that LLD file paths match the real repository structure.

    Issue #445: Pre-flight check before calling Claude — catches stale LLD
    paths immediately so we don't waste tokens on invalid paths.

    Rules:
    - Modify/Delete: file must exist on disk (hard fail)
    - Add: auto-create parent directory if missing (Issue #468)

    Args:
        files_to_modify: List of file spec dicts with 'path' and 'change_type'.
        repo_root: Path to the repository root.

    Returns:
        List of error strings. Empty list means all paths valid.
    """
    errors: list[str] = []

    for file_spec in files_to_modify:
        file_path = file_spec.get("path", "")
        change_type = file_spec.get("change_type", "Add")
        full_path = repo_root / file_path

        if change_type.lower() in ("modify", "delete"):
            if not full_path.exists():
                errors.append(
                    f"{change_type} target does not exist: {file_path}"
                )
        elif change_type.lower() == "add":
            # Issue #468: auto-create parent dirs for new files
            if not full_path.parent.exists():
                full_path.parent.mkdir(parents=True, exist_ok=True)

    return errors


def implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """N4: Generate implementation code file-by-file.

    Issue #272: File-by-file prompting with mechanical validation.
    """
    iteration_count = state.get("iteration_count", 0)
    gate_log(f"[N4] Implementing code file-by-file (iteration {iteration_count})...")

    if state.get("mock_mode"):
        return _mock_implement_code(state)

    # Issue #511: Cost tracking — note: call_claude_for_file() bypasses
    # provider abstraction (uses subprocess/SDK directly), so
    # get_cumulative_cost() may not capture all costs here yet.
    cost_before = get_cumulative_cost()

    # Track estimated token cost for this iteration
    estimated_tokens_used = record_iteration_cost(state)

    # Get required state
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    lld_content = state.get("lld_content", "")
    files_to_modify = state.get("files_to_modify", [])
    test_files = state.get("test_files", [])
    green_phase_output = state.get("green_phase_output", "")
    # Issue #498: Prefer structured failure summaries over raw pytest output
    test_failure_summary = state.get("test_failure_summary", "")
    e2e_failure_summary = state.get("e2e_failure_summary", "")
    audit_dir = Path(state.get("audit_dir", ""))

    if not files_to_modify:
        print("    [ERROR] No files_to_modify in state - LLD Section 2.1 not parsed?")
        return {
            "error_message": "Implementation failed: No files to implement - check LLD Section 2.1",
            "implementation_files": [],
        }

    # Issue #445: Pre-flight path validation — catch stale LLD paths before
    # calling Claude. Zero tokens wasted on bad paths.
    path_errors = validate_files_to_modify(files_to_modify, repo_root)
    if path_errors:
        for err in path_errors:
            print(f"    [GUARD] {err}")
        repo_tree = get_repo_structure(repo_root, max_depth=3)
        print(f"\n    Actual repository structure:\n{repo_tree}")
        return {
            "error_message": (
                f"GUARD: {len(path_errors)} file path(s) in LLD do not match "
                f"the repository structure. Errors:\n"
                + "\n".join(f"  - {e}" for e in path_errors)
            ),
            "implementation_files": [],
        }

    # Read test content for context
    test_content = ""
    for tf in test_files:
        tf_path = Path(tf)
        if tf_path.exists():
            try:
                test_content += f"# From {tf}\n"
                test_content += tf_path.read_text(encoding="utf-8")
                test_content += "\n\n"
            except Exception:
                pass

    # Limit files to prevent runaway
    files_to_modify = files_to_modify[:50]

    print(f"    Files to implement: {len(files_to_modify)}")
    for f in files_to_modify:
        print(f"      - {f['path']} ({f.get('change_type', 'Add')})")

    # Issue #188: Extract allowed paths from LLD and build prompt section
    path_spec = extract_paths_from_lld(lld_content)
    path_spec["scaffolded_test_files"] = detect_scaffolded_test_files(
        path_spec["test_files"], repo_root,
    )
    # Also add files_to_modify paths (from state) to allowed set
    for f in files_to_modify:
        path_spec["all_allowed_paths"].add(f["path"])
    path_enforcement_section = build_implementation_prompt_section(path_spec)
    if path_enforcement_section:
        print(f"    Path enforcement: {len(path_spec['all_allowed_paths'])} allowed paths")

    # Issue #445: Get repo structure once for prompt grounding
    repo_structure = get_repo_structure(repo_root, max_depth=3)

    # Accumulated context
    completed_files: list[tuple[str, str]] = []
    written_paths: list[str] = []

    for i, file_spec in enumerate(files_to_modify):
        filepath = file_spec["path"]
        change_type = file_spec.get("change_type", "Add")

        existing_content = ""
        target_path = repo_root / filepath
        if change_type.lower() == "modify" and target_path.exists():
            try:
                existing_content = target_path.read_text(encoding="utf-8")
            except Exception:
                pass

        print(f"\n    [{i+1}/{len(files_to_modify)}] {filepath} ({change_type})...")

        # Skip delete operations
        if change_type.lower() == "delete":
            target = repo_root / filepath
            if target.exists():
                target.unlink()
                print(f"        Deleted")
            continue

        # Handle empty placeholder files (e.g. .gitkeep) without calling Claude
        placeholder_names = {".gitkeep", ".gitignore_placeholder", ".keep"}
        if Path(filepath).name in placeholder_names:
            target_path = repo_root / filepath
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("", encoding="utf-8")
            print(f"        Written (placeholder): {target_path}")
            completed_files.append((filepath, ""))
            written_paths.append(str(target_path))
            continue

        # Issue #549: Fast-path for trivial data files — skip Claude entirely
        _trivial_extensions = (".json", ".yaml", ".yml", ".toml", ".txt", ".csv")
        _fname = Path(filepath).name
        _desc = file_spec.get("description", "")
        if (
            (_fname == "__init__.py" or filepath.endswith(_trivial_extensions))
            and change_type.lower() == "add"
            and len(_desc) < 50
        ):
            # __init__.py -> empty; data files -> use description as content
            content = "" if _fname == "__init__.py" else _desc
            target_path = repo_root / filepath
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content + "\n" if content else "", encoding="utf-8")
            print(f"        Written (fast-path): {target_path}")
            completed_files.append((filepath, content))
            written_paths.append(str(target_path))
            continue

        # Issue #547: Skip-on-resume — don't re-call Claude for files already on disk
        target_path = repo_root / filepath
        if change_type.lower() == "add" and target_path.exists() and target_path.stat().st_size > 0:
            existing_content = target_path.read_text(encoding="utf-8")
            print(f"        Skipped (already exists): {target_path}")
            completed_files.append((filepath, existing_content))
            written_paths.append(str(target_path))
            continue

        # Validate change type
        if change_type.lower() == "modify" and not target_path.exists():
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                reason=f"File marked as 'Modify' but does not exist at {target_path}",
                response_preview=None
            )
        if change_type.lower() == "add" and not target_path.parent.exists():
            # Create parent directories for new files
            target_path.parent.mkdir(parents=True, exist_ok=True)

        # Check context size
        token_estimate = estimate_context_tokens(lld_content, completed_files)
        if token_estimate > 180000:
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                reason=f"Context too large ({token_estimate} tokens > 180K limit)",
                response_preview=None
            )
        if token_estimate > 150000:
            print(f"        [WARN] Context approaching limit ({token_estimate} tokens)")

        # Issue #188: Validate file path against LLD
        if path_spec["all_allowed_paths"]:
            validation = validate_file_write(filepath, path_spec["all_allowed_paths"])
            if not validation["allowed"]:
                print(f"        [PATH] REJECTED: {validation['reason']}")
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Path not in LLD: {validation['reason']}",
                    response_preview=None,
                )

        # Build prompt for this single file
        prompt = build_single_file_prompt(
            filepath=filepath,
            file_spec=file_spec,
            lld_content=lld_content,
            completed_files=completed_files,
            repo_root=repo_root,
            test_content=test_content,
            # Issue #498: Use structured failure summary (targeted) over raw output (noisy)
            previous_error=(test_failure_summary or e2e_failure_summary or green_phase_output)
            if iteration_count > 0 else "",
            path_enforcement_section=path_enforcement_section,
            context_content=state.get("context_content", ""),
            repo_structure=repo_structure,
        )

        # Issue #588: Pruned prompt for retries (no completed_files context)
        pruned_prompt = build_single_file_prompt(
            filepath=filepath,
            file_spec=file_spec,
            lld_content=lld_content,
            completed_files=[],  # <-- PRUNED
            repo_root=repo_root,
            test_content=test_content,
            previous_error=(test_failure_summary or e2e_failure_summary or green_phase_output)
            if iteration_count > 0 else "",
            path_enforcement_section=path_enforcement_section,
            context_content=state.get("context_content", ""),
            repo_structure=repo_structure,
        )

        # Issue #644: Enforce prompt size cap — use pruned prompt if full exceeds cap
        if len(prompt) > CODE_GEN_PROMPT_CAP:
            print(f"        [PRUNE] Prompt {len(prompt):,} -> {len(pruned_prompt):,} chars (cap: {CODE_GEN_PROMPT_CAP:,})")
            prompt = pruned_prompt

        # Call Claude with retry logic (Issue #309)
        # Issue #267: Progress feedback during long API calls
        with ProgressReporter("Calling Claude", interval=15):
            code, success = generate_file_with_retry(
                filepath=filepath,
                base_prompt=prompt,
                audit_dir=audit_dir if audit_dir.exists() else None,
                max_retries=MAX_FILE_RETRIES,
                pruned_prompt=pruned_prompt,
                existing_content=existing_content,
            )
        # Note: generate_file_with_retry raises ImplementationError on failure,
        # so if we get here, code is valid

        # Write file (atomic: write to temp, then rename)
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            temp_path.write_text(code, encoding="utf-8")
            temp_path.replace(target_path)
        except Exception as e:
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                reason=f"Failed to write file: {e}",
                response_preview=None
            )

        print(f"        Written: {target_path}")

        # Add to accumulated context
        completed_files.append((filepath, code))
        written_paths.append(str(target_path))

    print(f"\n    Implementation complete: {len(written_paths)} files written")

    # Issue #460: Update test_files to point to real test files written by N4,
    # replacing the scaffold stubs that N2 created.
    issue_number = state.get("issue_number", 0)
    real_test_files = [
        p for p in written_paths
        if "/tests/" in p.replace("\\", "/")
        and Path(p).name.startswith("test_")
        and p.endswith(".py")
    ]

    if real_test_files:
        # Delete the scaffold file — it only has `assert False` stubs
        scaffold_path = repo_root / "tests" / f"test_issue_{issue_number}.py"
        if scaffold_path.exists():
            scaffold_path.unlink()
            print(f"    Deleted scaffold: {scaffold_path}")

    # Log to audit
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="implementation_generated",
        details={
            "files": written_paths,
            "iteration": iteration_count,
            "method": "file-by-file",
        },
    )

    # Issue #511: Accumulate per-node cost
    node_cost_usd = get_cumulative_cost() - cost_before
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "implement_code", node_cost_usd,
    )

    return {
        "implementation_files": written_paths,
        "completed_files": completed_files,
        "estimated_tokens_used": estimated_tokens_used,
        "error_message": "",
        "test_files": real_test_files if real_test_files else state.get("test_files", []),
        "node_costs": node_costs,  # Issue #511
    }


def _mock_implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    issue_number = state.get("issue_number", 42)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    mock_content = f'''"""Mock implementation for Issue #{issue_number}."""

def example_function():
    """Example function."""
    return True
'''

    impl_path = repo_root / "assemblyzero" / f"issue_{issue_number}_impl.py"
    impl_path.parent.mkdir(parents=True, exist_ok=True)
    impl_path.write_text(mock_content, encoding="utf-8")

    print(f"    [MOCK] Generated: {impl_path}")

    return {
        "implementation_files": [str(impl_path)],
        "completed_files": [("assemblyzero/issue_{issue_number}_impl.py", mock_content)],
        "error_message": "",
        "test_files": state.get("test_files", []),
    }

```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_641.py
"""Test file for Issue #641.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Integration/E2E fixtures
@pytest.fixture
def test_client():
    """Test client for API calls."""
    # TODO: Implement test client
    yield None


# Unit Tests
# -----------

def test_id():
    """
    Test Description | Expected Behavior | Status
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
    `select_model_for_file` routes `__init__.py` to Haiku | Returns
    `HAIKU_MODEL` | RED
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
    `select_model_for_file` routes `conftest.py` to Haiku | Returns
    `HAIKU_MODEL` | RED
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
    `select_model_for_file` routes test scaffold to Haiku | Returns
    `HAIKU_MODEL` when `is_test_scaffold=True` | RED
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
    `select_model_for_file` routes 49-line file to Haiku | Returns
    `HAIKU_MODEL` | RED
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
    `select_model_for_file` routes 50-line file to Sonnet | Returns
    default model | RED
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
    `select_model_for_file` routes unknown-size complex file to Sonnet |
    Returns default model when `estimated_line_count=0` | RED
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
    `select_model_for_file` routes deeply nested `__init__.py` to Haiku |
    Path depth irrelevant; basename match wins | RED
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
    `call_claude_for_file` uses supplied model when provided | Anthropic
    client called with correct model string | RED
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
    `call_claude_for_file` uses default model when `model=None` |
    Existing behaviour preserved | RED
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
    `generate_file_with_retry` passes routed model to
    `call_claude_for_file` | Integration of routing -> call | RED
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
    Routing decision logged at INFO level with reason | Logger called
    with file path, model name, and reason | RED
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
    Negative line count treated as unknown | Returns `DEFAULT_MODEL` when
    `estimated_line_count=-1` | RED
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
    Returns `HAIKU_MODEL` for lower boundary | RED
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
    Returns `DEFAULT_MODEL` just above threshold | RED
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
    Coverage ≥ 95% on new/modified code | `pytest-cov` report shows ≥ 95%
    line coverage | RED
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
    No regressions in existing unit test suite | All pre-existing tests
    pass after change | RED
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t160 works correctly
    assert False, 'TDD RED: test_t160 not implemented'


def test_010():
    """
    `__init__.py` in root (REQ-1) | Auto |
    `file_path="assemblyzero/__init__.py"`, `estimated_line_count=0`,
    `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result ==
    HAIKU_MODEL`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_010 works correctly
    assert False, 'TDD RED: test_010 not implemented'


def test_020():
    """
    `conftest.py` in tests root (REQ-2) | Auto |
    `file_path="tests/conftest.py"`, `estimated_line_count=0`,
    `is_test_scaffold=False` | `HAIKU_MODEL` | `assert result ==
    HAIKU_MODEL`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_020 works correctly
    assert False, 'TDD RED: test_020 not implemented'


def test_030():
    """
    Test scaffold flag overrides line count (REQ-3) | Auto |
    `file_path="tests/unit/test_foo.py"`, `estimated_line_count=200`,
    `is_test_scaffold=True` | `HAIKU_MODEL` | Flag overrides line count
    and filen
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_030 works correctly
    assert False, 'TDD RED: test_030 not implemented'


def test_040():
    """
    Auto | `file_path="assemblyzero/utils/helper.py"`,
    `estimated_line_count=49`, `is_test_scaffold=False` | `HAIKU_MODEL` |
    `assert result == HAIKU_MODEL`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_040 works correctly
    assert False, 'TDD RED: test_040 not implemented'


def test_050():
    """
    Auto | `file_path="assemblyzero/utils/helper.py"`,
    `estimated_line_count=50`, `is_test_scaffold=False` | `DEFAULT_MODEL`
    | Exactly 50 lines goes to Sonnet (threshold is `< 50`)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_050 works correctly
    assert False, 'TDD RED: test_050 not implemented'


def test_060():
    """
    200-line complex file (REQ-5) | Auto |
    `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=200`,
    `is_test_scaffold=False` | `DEFAULT_MODEL` | `assert result ==
    DEFAULT_MODEL`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_060 works correctly
    assert False, 'TDD RED: test_060 not implemented'


def test_070():
    """
    Unknown size complex file (REQ-5) | Auto |
    `file_path="assemblyzero/core/engine.py"`, `estimated_line_count=0`,
    `is_test_scaffold=False` | `DEFAULT_MODEL` | `0` means unknown; don't
    route to Haiku
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_070 works correctly
    assert False, 'TDD RED: test_070 not implemented'


def test_080():
    """
    Deeply nested `__init__.py` (REQ-1) | Auto |
    `file_path="assemblyzero/workflows/testing/nodes/__init__.py"` |
    `HAIKU_MODEL` | Basename match regardless of depth
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_080 works correctly
    assert False, 'TDD RED: test_080 not implemented'


def test_090(mock_external_service):
    """
    `call_claude_for_file` explicit model (REQ-7) | Auto |
    `model="claude-3-haiku-20240307"`, mock client | Anthropic client
    receives `model="claude-3-haiku-20240307"` | Mock assert called with
    correct mo
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_090 works correctly
    assert False, 'TDD RED: test_090 not implemented'


def test_100(mock_external_service):
    """
    `call_claude_for_file` default model (REQ-7) | Auto | `model=None`,
    mock client | Anthropic client receives configured default |
    Backward-compatible path
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_100 works correctly
    assert False, 'TDD RED: test_100 not implemented'


def test_120(mock_external_service):
    """
    Routing log emission includes reason (REQ-9) | Auto | Any routed
    call, mock logger | `logger.info` called with file path, model name,
    and reason string | `mock_logger.info.assert_called_once()` and re
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_120 works correctly
    assert False, 'TDD RED: test_120 not implemented'


def test_130():
    """
    Auto | `estimated_line_count=1` | `HAIKU_MODEL` | Lower boundary
    check
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_130 works correctly
    assert False, 'TDD RED: test_130 not implemented'


def test_140():
    """
    Negative line count treated as unknown (REQ-6) | Auto |
    `estimated_line_count=-1` | `DEFAULT_MODEL` | Defensive: negative =
    unknown, no Haiku routing
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_140 works correctly
    assert False, 'TDD RED: test_140 not implemented'


def test_150():
    """
    Coverage ≥ 95% on new/modified code (REQ-10) | Auto | Run `pytest
    --cov=assemblyzero/workflows/testing/nodes/implement_code
    --cov-report=term-missing` | Coverage report shows ≥ 95% line coverage
    | CI
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_150 works correctly
    assert False, 'TDD RED: test_150 not implemented'


def test_160():
    """
    No regressions in existing unit test suite (REQ-11) | Auto | Run
    `pytest tests/unit/ -m "not integration and not e2e and not
    adversarial"` | All pre-existing tests pass | Exit code 0; zero
    failures, z
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_160 works correctly
    assert False, 'TDD RED: test_160 not implemented'



# Integration Tests
# -----------------

@pytest.mark.integration
def test_110(test_client, mock_external_service):
    """
    `generate_file_with_retry` routing integration (REQ-8) | Auto |
    `file_path="tests/__init__.py"`, mock `call_claude_for_file` |
    `call_claude_for_file` called with `model=HAIKU_MODEL` | End-to-end
    routi
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_110 works correctly
    assert False, 'TDD RED: test_110 not implemented'




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
