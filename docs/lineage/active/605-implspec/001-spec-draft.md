# Implementation Spec: 605 - Feature: Systemic Model Version Refresh (Gemini 3.1 & Claude 4.6+)

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #605 |
| LLD | `docs/lld/active/605-model-refresh.md` |
| Generated | 2026-02-04 |
| Status | APPROVED |

## 1. Overview

**Objective:** Refresh all hardcoded model identifiers across the codebase to `gemini-3.1-pro-preview`, `claude-4-6-opus-latest`, and `claude-4-6-sonnet-latest`, while strictly removing legacy `gemini-3-pro` fallbacks.

**Success Criteria:** `assemblyzero/core/config.py` and `tools/gemini-rotate.py` default to the new 3.1/4.6 identifiers; backward compatibility mappings are purged; a new model downgrade detection script validates strict 3.1 usage; all unit tests reflect the updated strings.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/config.py` | Modify | Update default models, remove `gemini-3-pro` fallback, add Claude default. |
| 2 | `assemblyzero/core/llm_provider.py` | Modify | Implement `MODEL_MAP`, `get_model_identifier`, update class defaults. |
| 3 | `tools/gemini-rotate.py` | Modify | Update `DEFAULT_MODEL` to `gemini-3.1-pro-preview`. |
| 4 | `tools/gemini-model-check.sh` | Add | Bash script for model downgrade validation (rejects flash/3.0). |
| 5 | `tests/test_assemblyzero_config.py` | Modify | Add/update assertions to check for 3.1 and 4.6 default strings. |
| 6 | `tests/test_gemini_client.py` | Modify | Update model string test parameters to use `3.1-pro-preview`. |

**Implementation Order Rationale:** Constants and core configs (1) must be updated first, followed by providers (2) and CLI tools (3-4), concluding with tests (5-6) to verify the new behaviors.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/core/config.py`

**Relevant excerpt** (lines 10-14):
```python
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gemini-3.1-pro-preview")

REVIEWER_MODEL_FALLBACKS = ["gemini-3-pro-preview"]
```

**What changes:** Remove `gemini-3-pro-preview` from `REVIEWER_MODEL_FALLBACKS` to ensure a fail-closed posture. Add `DEFAULT_CLAUDE_MODEL` constant.

### 3.2 `assemblyzero/core/llm_provider.py`

**Relevant excerpt** (lines 142-154, 182-194):
```python
class ClaudeCLIProvider(LLMProvider):

    """Claude provider using claude -p CLI (Max subscription).

Uses the user's logged-in Claude Code session, which works with"""

    def __init__(self, model: str = "opus"):
    """Initialize Claude CLI provider.
```
```python
class AnthropicProvider(LLMProvider):

    """Anthropic API provider for direct Claude API calls.

Issue #395: Provides direct API access with proper token tracking,"""

    def __init__(self, model: str = "opus"):
    """Initialize Anthropic API provider.
```

**What changes:** Update default `model` kwargs to the new exact strings. Add the global `MODEL_MAP` dictionary and `get_model_identifier` function.

### 3.3 `tools/gemini-rotate.py`

**Relevant excerpt** (lines 120-123):
```python
STATE_FILE = Path.home() / ".assemblyzero" / "gemini-rotation-state.json"

DEFAULT_MODEL = "gemini-3-pro-preview"
```

**What changes:** Update `DEFAULT_MODEL` from `gemini-3-pro-preview` to `gemini-3.1-pro-preview`.

### 3.4 `tests/test_assemblyzero_config.py`

**Relevant excerpt** (lines 20-25):
```python
class TestAssemblyZeroConfig:

    """Test suite for AssemblyZeroConfig."""

    def test_loads_defaults_when_no_file(self, tmp_path):
    """Config uses defaults when file doesn't exist."""
```

**What changes:** Inject specific assertions into config test to verify `gemini-3.1-pro-preview` and `claude-4-6-opus-latest` are correctly loaded/exported.

### 3.5 `tests/test_gemini_client.py`

**Relevant excerpt** (lines 35-49):
```python
class TestGeminiClientModelValidation:

    """Tests for model validation in GeminiClient."""

    def test_130_forbidden_model_rejected_flash(self):
    """Test that Flash model is rejected at initialization."""
    ...

    def test_130_forbidden_model_rejected_lite(self):
    """Test that Lite model is rejected at initialization."""
    ...

    def test_valid_pro_model_accepted(self, temp_credentials_file, temp_state_file):
    """Test that Pro model is accepted."""
    ...
```

**What changes:** Ensure assertions in `test_valid_pro_model_accepted` explicitly check for `gemini-3.1-pro-preview` instead of any generic/legacy `gemini-3-pro` identifiers. Add test coverage ensuring `gemini-3-pro` raises an exception if validation is strict.

## 4. Data Structures

### 4.1 `MODEL_MAP`

**Definition:**
```python
MODEL_MAP: dict[str, str] = {
    "gemini-pro": str,
    "claude-opus": str,
    "claude-sonnet": str
}
```

**Concrete Example:**
```json
{
    "gemini-pro": "gemini-3.1-pro-preview",
    "claude-opus": "claude-4-6-opus-latest",
    "claude-sonnet": "claude-4-6-sonnet-latest"
}
```

## 5. Function Specifications

### 5.1 `get_model_identifier()`

**File:** `assemblyzero/core/llm_provider.py`

**Signature:**
```python
def get_model_identifier(model_family: str, version: str = "latest") -> str:
    """Returns the canonical exact model string for the given family/version."""
    ...
```

**Input Example:**
```python
model_family = "gemini"
version = "pro"
```

**Output Example:**
```python
"gemini-3.1-pro-preview"
```

**Edge Cases:**
- Unrecognized `model_family` -> defaults to returning exactly what was passed.
- If user requests legacy `gemini-3-pro` explicitly -> returns `"gemini-3.1-pro-preview"`.

### 5.2 `check_model_downgrade()`

**File:** `tools/gemini-model-check.sh`

**Signature:**
```bash
# function check_model_downgrade(requested_model, actual_model)
# Note: Implemented as a top-level bash script accepting 2 arguments
```

**Input Example:**
```bash
./tools/gemini-model-check.sh "gemini-3.1-pro" "gemini-2.0-flash"
```

**Output Example:**
```bash
ERROR: Model downgrade detected. Strict fail-closed triggered. Actual model 'gemini-2.0-flash' does not match required prefix 'gemini-3.1-pro'.
# Exits with code 1
```

## 6. Change Instructions

### 6.1 `assemblyzero/core/config.py` (Modify)

**Change 1:** Add Claude default and strip Gemini fallbacks.
```diff
 REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gemini-3.1-pro-preview")

-REVIEWER_MODEL_FALLBACKS = ["gemini-3-pro-preview"]
+REVIEWER_MODEL_FALLBACKS = []
+
+DEFAULT_CLAUDE_MODEL = os.environ.get("DEFAULT_CLAUDE_MODEL", "claude-4-6-opus-latest")
```

### 6.2 `assemblyzero/core/llm_provider.py` (Modify)

**Change 1:** Add `MODEL_MAP` and helper function near the top (after imports).
```diff
 from assemblyzero.core.text_sanitizer import strip_emoji
+
+MODEL_MAP = {
+    "gemini-pro": "gemini-3.1-pro-preview",
+    "claude-opus": "claude-4-6-opus-latest",
+    "claude-sonnet": "claude-4-6-sonnet-latest",
+}
+
+def get_model_identifier(model_family: str, version: str = "latest") -> str:
+    """Returns the canonical exact model string for the given family/version."""
+    key = f"{model_family}-{version}"
+    if key in MODEL_MAP:
+        return MODEL_MAP[key]
+    # Fail-closed upgrade for legacy gemini mappings
+    if "gemini" in model_family and "3" in version and "pro" in version:
+        return MODEL_MAP["gemini-pro"]
+    return key
```

**Change 2:** Update Claude CLI default model.
```diff
 class ClaudeCLIProvider(LLMProvider):
...
-    def __init__(self, model: str = "opus"):
+    def __init__(self, model: str = "claude-4-6-opus-latest"):
```

**Change 3:** Update Anthropic provider default model.
```diff
 class AnthropicProvider(LLMProvider):
...
-    def __init__(self, model: str = "opus"):
+    def __init__(self, model: str = "claude-4-6-opus-latest"):
```

### 6.3 `tools/gemini-rotate.py` (Modify)

**Change 1:** Update `DEFAULT_MODEL` variable.
```diff
 STATE_FILE = Path.home() / ".assemblyzero" / "gemini-rotation-state.json"

-DEFAULT_MODEL = "gemini-3-pro-preview"
+DEFAULT_MODEL = "gemini-3.1-pro-preview"
```

### 6.4 `tools/gemini-model-check.sh` (Add)

**Complete file contents:**
```bash
#!/usr/bin/env bash
# tools/gemini-model-check.sh
# Validates model identifiers to prevent silent downgrades.
# Usage: ./gemini-model-check.sh <requested_model> <actual_model>

REQUESTED_MODEL=${1:-"gemini-3.1-pro-preview"}
ACTUAL_MODEL=$2

if [ -z "$ACTUAL_MODEL" ]; then
    echo "ERROR: actual_model parameter missing."
    exit 1
fi

# Reject any flash or 3.0 models immediately
if [[ "$ACTUAL_MODEL" == *"flash"* ]] || [[ "$ACTUAL_MODEL" == *"3.0"* ]]; then
    echo "ERROR: Model downgrade detected. Strict fail-closed triggered. Actual model '$ACTUAL_MODEL' does not match required 'gemini-3.1-pro' prefix."
    exit 1
fi

# Require 3.1 prefix
if [[ "$ACTUAL_MODEL" != *"gemini-3.1"* ]]; then
    echo "ERROR: Fail-closed governance violation. Model must be part of the gemini-3.1 lineage."
    exit 1
fi

echo "SUCCESS: Model $ACTUAL_MODEL verified against 3.1 strict constraints."
exit 0
```
*(Make sure to apply `chmod +x` to this file during implementation).*

### 6.5 `tests/test_assemblyzero_config.py` (Modify)

**Change 1:** Add test logic for default model exports.
```diff
     def test_loads_defaults_when_no_file(self, tmp_path):
     """Config uses defaults when file doesn't exist."""
+        from assemblyzero.core.config import REVIEWER_MODEL, DEFAULT_CLAUDE_MODEL, REVIEWER_MODEL_FALLBACKS
+        assert REVIEWER_MODEL == "gemini-3.1-pro-preview"
+        assert DEFAULT_CLAUDE_MODEL == "claude-4-6-opus-latest"
+        assert REVIEWER_MODEL_FALLBACKS == []
```

### 6.6 `tests/test_gemini_client.py` (Modify)

**Change 1:** Update assertions for `3.1-pro-preview` in `test_valid_pro_model_accepted`.
```diff
     def test_valid_pro_model_accepted(self, temp_credentials_file, temp_state_file):
     """Test that Pro model is accepted."""
-        client = GeminiClient(model="gemini-3-pro")
-        assert client.model == "gemini-3-pro"
+        client = GeminiClient(model="gemini-3.1-pro-preview")
+        assert client.model == "gemini-3.1-pro-preview"
```

## 7. Pattern References

### 7.1 Bash Script Tool Pattern
**File:** `tools/run_audit.py` (lines 1-15)
**Relevance:** Demonstrates standalone script patterns in the `tools/` directory. The newly added `gemini-model-check.sh` adheres to this by remaining independent and handling strict arguments.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `os` | stdlib | `assemblyzero/core/config.py` (existing) |

**New Dependencies:** None

## 9. Placeholder

*(Empty section as per template structure)*

## 10. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| 010 | `config.py` exports | `import config` | `REVIEWER_MODEL == "gemini-3.1-pro-preview"` |
| 020 | `MODEL_MAP` behavior | `get_model_identifier("gemini", "pro")` | `"gemini-3.1-pro-preview"` |
| 030 | `gemini-rotate.py` | Run without `--model` | Defaults to `gemini-3.1-pro-preview` |
| 040 | `gemini-model-check.sh` | `"gemini-3.1" "gemini-3.0-pro"` | Exit 1 (Downgrade detected) |
| 040 | `gemini-model-check.sh` | `"gemini-3.1" "gemini-3.1-pro-preview"` | Exit 0 (Success) |

## 11. Implementation Notes

### 11.1 Runbook Entry requirement (REQ-6)
To satisfy REQ-6, ensure a manual update to `docs/runbook.md` (or equivalent operations log) is added detailing:
> **Strict Removal of gemini-3-pro Fallbacks (2026-03)**
> Legacy `gemini-3-pro` mappings have been completely purged from fallback configurations to enforce a fail-closed governance posture. If operators observe a sudden spike in 403 (Permission Denied) or 404 (Not Found) errors post-deployment of AssemblyZero, verify that all active GCP/API keys have full allowlist permissions for `gemini-3.1-pro-preview` and `claude-4-6-opus-latest`.

### 11.2 File Permissions
Ensure `tools/gemini-model-check.sh` is created with executable permissions (`chmod +x tools/gemini-model-check.sh`) via the implementation agent terminal.

### 11.3 Fail Closed Mentality
Do **not** add try/except blocks to catch missing models in `get_model_identifier`. The API call must physically fail with an HTTP 400/404 if the credential does not support `3.1-pro-preview` to trigger strict alert thresholds.