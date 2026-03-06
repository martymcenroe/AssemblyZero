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

**Success Criteria:** `assemblyzero/core/config.py` and `tools/gemini-rotate.py` default to the new 3.1/4.6 identifiers; backward compatibility mappings are purged; a new model downgrade detection script validates strict 3.1 usage; all unit tests reflect the updated strings; and `docs/runbook.md` is automatically updated with a strict fail-closed operational notice.


## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/config.py` | Modify | Update default models, remove `gemini-3-pro` fallback, add Claude default. |
| 2 | `assemblyzero/core/llm_provider.py` | Modify | Implement `MODEL_MAP`, `get_model_identifier`, and wire helpers into class defaults. |
| 3 | `tools/gemini-rotate.py` | Modify | Update `DEFAULT_MODEL` to `gemini-3.1-pro-preview`. |
| 4 | `tools/gemini-model-check.sh` | Add | Bash script for model downgrade validation (rejects flash/3.0). |
| 5 | `tests/test_assemblyzero_config.py` | Modify | Add/update assertions to check for 3.1 and 4.6 default strings. |
| 6 | `tests/test_gemini_client.py` | Modify | Update model string test parameters to use `3.1-pro-preview`. |
| 7 | `docs/runbook.md` | Modify | Append operations log entry detailing the strict removal of `gemini-3-pro` fallbacks (REQ-6). |

**Implementation Order Rationale:** Constants and core configs (1) must be updated first, followed by providers (2) and CLI tools (3-4), concluding with tests (5-6) to verify the new behaviors. The documentation update (7) acts as the final programmatic step to document the operational shift.


## 3. Current State (for Modify/Delete files)

### [UNCHANGED] 3.1 `assemblyzero/core/config.py`
### [UNCHANGED] 3.2 `assemblyzero/core/llm_provider.py`
### [UNCHANGED] 3.3 `tools/gemini-rotate.py`
### [UNCHANGED] 3.4 `tests/test_assemblyzero_config.py`
### [UNCHANGED] 3.5 `tests/test_gemini_client.py`

### 3.6 `docs/runbook.md`

**File:** `docs/runbook.md`
```markdown
# AssemblyZero Runbook

## Existing Procedures
(Various standard operating procedures)
```


## [UNCHANGED] 4. Data Structures
### [UNCHANGED] 4.1 `MODEL_MAP`

## [UNCHANGED] 5. Function Specifications
### [UNCHANGED] 5.1 `get_model_identifier()`

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

**Change 2:** Update Claude CLI default model to wire in the `get_model_identifier` mapping helper instead of hardcoding.
```diff
 class ClaudeCLIProvider(LLMProvider):
...
-    def __init__(self, model: str = "opus"):
-        self.model = model
+    def __init__(self, model: str = "opus"):
+        self.model = get_model_identifier("claude", model)
```

**Change 3:** Update Anthropic provider default model to wire in the `get_model_identifier` mapping helper instead of hardcoding.
```diff
 class AnthropicProvider(LLMProvider):
...
-    def __init__(self, model: str = "opus"):
-        self.model = model
+    def __init__(self, model: str = "opus"):
+        self.model = get_model_identifier("claude", model)
```

### 6.3 `tools/gemini-rotate.py` (Modify)

**Change 1:** Update `DEFAULT_MODEL` variable.
```diff
 STATE_FILE = Path.home() / ".assemblyzero" / "gemini-rotation-state.json"

-DEFAULT_MODEL = "gemini-3-pro-preview"
+DEFAULT_MODEL = "gemini-3.1-pro-preview"
```

### [UNCHANGED] 6.4 `tools/gemini-model-check.sh` (Add)
### [UNCHANGED] 6.5 `tests/test_assemblyzero_config.py` (Modify)
### [UNCHANGED] 6.6 `tests/test_gemini_client.py` (Modify)

### 6.7 `docs/runbook.md` (Modify)

**Change 1:** Append strict model fail-closed notice to the end of the file to programmatically satisfy REQ-6.
```diff
 # AssemblyZero Runbook
 
 ## Existing Procedures
 (Various standard operating procedures)
+
+## Strict Removal of gemini-3-pro Fallbacks (2026-03)
+Legacy `gemini-3-pro` mappings have been completely purged from fallback configurations to enforce a fail-closed governance posture. If operators observe a sudden spike in 403 (Permission Denied) or 404 (Not Found) errors post-deployment of AssemblyZero, verify that all active GCP/API keys have full allowlist permissions for `gemini-3.1-pro-preview` and `claude-4-6-opus-latest`.
```


## [UNCHANGED] 7. Pattern References
### [UNCHANGED] 7.1 Bash Script Tool Pattern

## [UNCHANGED] 8. Dependencies & Imports
## [UNCHANGED] 9. Placeholder

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
To satisfy REQ-6, an automated append operation is specified in Section 6.7 to modify `docs/runbook.md`. The implementation agent must apply this text change programmatically via file edit, completely replacing the previous requirement for a manual manual update.

### 11.2 File Permissions
Ensure `tools/gemini-model-check.sh` is created with executable permissions (`chmod +x tools/gemini-model-check.sh`) via the implementation agent terminal.

### [UNCHANGED] 11.3 Fail Closed Mentality

### 11.4 Test Environment Isolation
When implementing assertions in `tests/test_assemblyzero_config.py`, ensure that environment variables like `REVIEWER_MODEL` and `DEFAULT_CLAUDE_MODEL` are strictly mocked (e.g., using `unittest.mock.patch.dict(os.environ, {}, clear=True)`) so that local host environment variables do not cause false positives or false negatives when testing default configuration values.