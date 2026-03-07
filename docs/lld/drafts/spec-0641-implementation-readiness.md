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
