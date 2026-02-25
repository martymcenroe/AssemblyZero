# Implementation Request: assemblyzero/telemetry/cascade_events.py

## Task

Write the complete contents of `assemblyzero/telemetry/cascade_events.py`.

Change type: Add
Description: Structured JSONL logging for cascade events

## LLD Specification

# Implementation Spec: Auto-Approve Safety — Prevent Cascading Task Execution

| Field | Value |
|-------|-------|
| Issue | #358 |
| LLD | `docs/lld/active/358-cascade-prevention.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

Implement a cascade detection system that prevents AI models from auto-approving through multiple tasks without human review. The system uses regex-based pattern detection on model output, integrated as a Claude Code PostToolUse hook, with JSONL telemetry and a CLAUDE.md behavioral rule as defense-in-depth.

**Objective:** Detect "should I continue?" patterns in model output and block auto-approval on those prompts.

**Success Criteria:** ≥95% recall on known cascade scenarios, <2% false positive rate on legitimate permission prompts, <5ms detection latency, all detections logged as structured JSONL events.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/cascade_samples.json` | Add | Test fixture data — cascade and non-cascade sample outputs |
| 2 | `assemblyzero/hooks/cascade_patterns.py` | Add | Pattern definitions — regex and semantic patterns |
| 3 | `assemblyzero/hooks/cascade_detector.py` | Add | Core pattern detection engine |
| 4 | `assemblyzero/hooks/cascade_action.py` | Add | Action handlers — block, log, alert |
| 5 | `assemblyzero/telemetry/cascade_events.py` | Add | Structured JSONL logging for cascade events |
| 6 | `assemblyzero/hooks/__init__.py` | Modify | Export cascade detector |
| 7 | `assemblyzero/telemetry/__init__.py` | Modify | Export cascade event logger |
| 8 | `data/unleashed/cascade_block_patterns.json` | Add | User-editable blocklist patterns |
| 9 | `.claude/hooks/post_output_cascade_check.py` | Add | Claude Code PostToolUse hook entry point |
| 10 | `CLAUDE.md` | Modify | Add cascade prevention rule |
| 11 | `tests/unit/test_cascade_detector.py` | Add | Unit tests for pattern detection |
| 12 | `tests/unit/test_cascade_action.py` | Add | Unit tests for action handlers |
| 13 | `tests/unit/test_cascade_events.py` | Add | Unit tests for telemetry logging |
| 14 | `tests/integration/test_cascade_hook_integration.py` | Add | Integration tests for full hook pipeline |

**Implementation Order Rationale:** Fixtures first (TDD), then patterns (no dependencies), then detector (depends on patterns), then action (depends on detector), then telemetry (depends on action), then wire up exports, config, hook, CLAUDE.md rule, and finally tests. Tests are listed last in order but written first per TDD requirement.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/hooks/__init__.py`

**Relevant excerpt** (entire file):

```python
"""Hooks for workflow validation and enforcement."""
```

**What changes:** Add imports for `cascade_detector`, `cascade_patterns`, and `cascade_action` modules. Export key functions: `detect_cascade_risk`, `handle_cascade_detection`, `load_default_patterns`.

### 3.2 `assemblyzero/telemetry/__init__.py`

**Relevant excerpt** (entire file):

```python
"""AssemblyZero telemetry — structured event emission.

Fire-and-forget telemetry that never raises, never blocks tool execution.
Events go to DynamoDB with local JSONL fallback when offline.

Usage:
    from assemblyzero.telemetry import emit, track_tool

    # Direct event emission
    emit("workflow.start", repo="AssemblyZero", metadata={"issue": 42})

    # Context manager for tool tracking
    with track_tool("run_audit", repo="AssemblyZero"):
        do_work()  # emits tool.start, tool.complete (or tool.error)

Kill switch: set ASSEMBLYZERO_TELEMETRY=0 to disable all emission.
"""

from assemblyzero.telemetry.emitter import emit, flush, track_tool

__all__ = ["emit", "flush", "track_tool"]
```

**What changes:** Add imports for `cascade_events` module functions. Add `log_cascade_event`, `create_cascade_event`, `get_cascade_stats` to `__all__`.

### 3.3 `CLAUDE.md`

**Relevant excerpt** (entire file):

```markdown
# CLAUDE.md - AssemblyZero

Universal rules are in `C:\Users\mcwiz\Projects\CLAUDE.md` (auto-loaded for all projects).

AssemblyZero is the canonical source for core rules, tools, and workflow.

## Key Files

- `WORKFLOW.md` — Development workflow gates (worktrees, reviews, reports)
- `tools/` — Shared tooling (merge, batch-workflow, gemini-model-check)
- `docs/standards/` — Engineering standards (0001–0999)

## Merging PRs

NEVER use `gh pr merge` directly. Always follow the post-merge cleanup in WORKFLOW.md:

```bash
# 1. Merge (squash)
gh pr merge {NUMBER} --squash --repo martymcenroe/AssemblyZero

# 2. Archive lineage
poetry run python tools/archive_worktree_lineage.py --worktree ../AssemblyZero-{ID} --issue {ID}

# 3. Remove worktree (clean ephemeral files first, never --force)
git worktree remove ../AssemblyZero-{ID}

# 4. Delete local branch
git branch -d {BRANCH}

# 5. Pull merged changes
git checkout main && git pull
```

Skipping post-merge cleanup leaves orphaned worktrees and stale branches.
```

**What changes:** Add a new `## Cascade Prevention (Task Completion Behavior)` section after the `## Merging PRs` section. The rule instructs models to ask open-ended questions after task completion and explicitly forbids numbered yes/no options for next-step decisions.

## 4. Data Structures

### 4.1 CascadeRiskLevel

**Definition:**

```python
from enum import Enum

class CascadeRiskLevel(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

**Concrete Example:**

```json
"high"
```

### 4.2 CascadePattern

**Definition:**

```python
class CascadePattern(TypedDict):
    id: str
    category: Literal["continuation_offer", "numbered_choice", "task_completion_pivot", "scope_expansion"]
    regex: str
    description: str
    risk_weight: float
    examples: list[str]
```

**Concrete Example:**

```json
{
    "id": "CP-001",
    "category": "continuation_offer",
    "regex": "(?i)should I (continue|proceed|start|begin|move on)",
    "description": "Detects 'Should I continue/proceed/start' offers",
    "risk_weight": 0.7,
    "examples": [
        "Should I continue with the next issue?",
        "Should I proceed to implement the remaining tests?"
    ]
}
```

### 4.3 CascadeDetectionResult

**Definition:**

```python
class CascadeDetectionResult(TypedDict):
    detected: bool
    risk_level: CascadeRiskLevel
    matched_patterns: list[str]
    matched_text: str
    recommended_action: Literal["allow", "block_and_prompt", "block_and_alert"]
    confidence: float
```

**Concrete Example (cascade detected):**

```json
{
    "detected": true,
    "risk_level": "high",
    "matched_patterns": ["CP-001", "CP-020"],
    "matched_text": "I've fixed issue #42. Should I continue with issue #43?",
    "recommended_action": "block_and_prompt",
    "confidence": 0.85
}
```

**Concrete Example (no cascade):**

```json
{
    "detected": false,
    "risk_level": "none",
    "matched_patterns": [],
    "matched_text": "",
    "recommended_action": "allow",
    "confidence": 0.0
}
```

### 4.4 CascadeEvent

**Definition:**

```python
class CascadeEvent(TypedDict):
    timestamp: str
    event_type: Literal["cascade_risk"]
    risk_level: str
    action_taken: str
    matched_patterns: list[str]
    model_output_snippet: str
    session_id: str
    auto_approve_blocked: bool
```

**Concrete Example:**

```json
{
    "timestamp": "2026-02-25T14:32:07.123456+00:00",
    "event_type": "cascade_risk",
    "risk_level": "high",
    "action_taken": "blocked",
    "matched_patterns": ["CP-001", "CP-020"],
    "model_output_snippet": "I've fixed issue #42. Should I continue with issue #43? 1. Yes 2. No, stop here. This was a particularly tricky bug involving the state machine tr",
    "session_id": "sess_abc123def456",
    "auto_approve_blocked": true
}
```

### 4.5 CascadeBlockPatternsConfig

**Definition:**

```python
class CascadeBlockPatternsConfig(TypedDict):
    version: str
    enabled: bool
    patterns: list[CascadePattern]
    risk_threshold: float
    alert_on_block: bool
    log_all_checks: bool
```

**Concrete Example:**

```json
{
    "version": "1.0",
    "enabled": true,
    "patterns": [
        {
            "id": "CP-100",
            "category": "continuation_offer",
            "regex": "(?i)want me to (tackle|handle|address) the next",
            "description": "Custom pattern for 'want me to tackle the next' phrasing",
            "risk_weight": 0.7,
            "examples": ["Want me to tackle the next issue?"]
        }
    ],
    "risk_threshold": 0.6,
    "alert_on_block": true,
    "log_all_checks": false
}
```

### 4.6 Test Fixture: cascade_samples.json

**Concrete Example (partial):**

```json
{
    "cascade_samples": [
        {
            "id": "S001",
            "text": "Great, issue #42 is fixed! Should I continue with issue #43?",
            "expected_detected": true,
            "expected_min_risk": "high",
            "category": "continuation_offer"
        },
        {
            "id": "S002",
            "text": "Done! What's next?\n1. Yes, start issue #44\n2. No, stop here",
            "expected_detected": true,
            "expected_min_risk": "critical",
            "category": "numbered_choice_with_completion"
        },
        {
            "id": "S003",
            "text": "I've completed the refactor. Now let me also update the tests for the new module.",
            "expected_detected": true,
            "expected_min_risk": "high",
            "category": "task_completion_pivot"
        },
        {
            "id": "S004",
            "text": "While I'm at it, I could also fix the related CSS issue in the sidebar.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion"
        },
        {
            "id": "S005",
            "text": "I solved issue 1. Should I do issue 2?\n1. Yes\n2. No",
            "expected_detected": true,
            "expected_min_risk": "critical",
            "category": "gemini_style_cascade"
        }
    ],
    "permission_prompt_samples": [
        {
            "id": "P001",
            "text": "Allow bash command: git push origin main? (y/n)",
            "expected_detected": false,
            "category": "bash_permission"
        },
        {
            "id": "P002",
            "text": "Allow file write: /src/main.py? (y/n)",
            "expected_detected": false,
            "category": "file_write_permission"
        },
        {
            "id": "P003",
            "text": "Allow Read tool to read file: src/config.json?",
            "expected_detected": false,
            "category": "read_permission"
        }
    ],
    "non_cascade_samples": [
        {
            "id": "N001",
            "text": "def should_i_continue(): return True",
            "expected_detected": false,
            "category": "code_with_keyword"
        },
        {
            "id": "N002",
            "text": "Should I use async or sync for this function?",
            "expected_detected": false,
            "category": "legitimate_technical_question"
        },
        {
            "id": "N003",
            "text": "The implementation looks correct. Here's the summary of changes made:\n- Fixed the parser\n- Updated tests\n- Added docs",
            "expected_detected": false,
            "category": "clean_completion"
        },
        {
            "id": "N004",
            "text": "",
            "expected_detected": false,
            "category": "empty_input"
        },
        {
            "id": "N005",
            "text": "Should I format this differently? The current approach uses tabs.",
            "expected_detected": false,
            "category": "legitimate_question_with_keyword"
        }
    ],
    "edge_case_samples": [
        {
            "id": "E001",
            "text": "I've updated the code. Should I also add type hints? The current functions lack proper typing.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "subtle_scope_expansion"
        },
        {
            "id": "E002",
            "text": "That's done. Next steps could include:\n1. Adding more tests\n2. Updating docs\n3. Deploying\n\nWhich would you prefer?",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "soft_numbered_options"
        },
        {
            "id": "E003",
            "text": "I also noticed some lint warnings — should I fix those too?\n1. Yes\n2. No",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion_with_numbered"
        }
    ]
}
```

## 5. Function Specifications

### 5.1 `detect_cascade_risk()`

**File:** `assemblyzero/hooks/cascade_detector.py`

**Signature:**

```python
def detect_cascade_risk(
    model_output: str,
    patterns: list[CascadePattern] | None = None,
    risk_threshold: float = 0.6,
) -> CascadeDetectionResult:
    """Analyze model output text for cascade-risk patterns."""
    ...
```

**Input Example:**

```python
model_output = "I've fixed issue #42. Should I continue with issue #43?"
patterns = None  # Uses defaults
risk_threshold = 0.6
```

**Output Example:**

```python
{
    "detected": True,
    "risk_level": CascadeRiskLevel.HIGH,
    "matched_patterns": ["CP-001", "CP-020"],
    "matched_text": "Should I continue with issue #43?",
    "recommended_action": "block_and_prompt",
    "confidence": 0.85,
}
```

**Edge Cases:**
- Empty string `""` → `{"detected": False, "risk_level": CascadeRiskLevel.NONE, "matched_patterns": [], "matched_text": "", "recommended_action": "allow", "confidence": 0.0}`
- `None` input → same as empty string (guard at top of function)
- Input > 10,000 chars → truncated to first 10,000 before scanning
- Permission prompt → short-circuits to `{"detected": False, "recommended_action": "allow"}` via `is_permission_prompt()`

### 5.2 `compute_risk_score()`

**File:** `assemblyzero/hooks/cascade_detector.py`

**Signature:**

```python
def compute_risk_score(
    matched_patterns: list[tuple[CascadePattern, re.Match]],
) -> tuple[float, CascadeRiskLevel]:
    """Compute composite risk score from matched patterns."""
    ...
```

**Input Example:**

```python
matched_patterns = [
    ({"id": "CP-001", "category": "continuation_offer", "risk_weight": 0.7, ...}, <re.Match>),
    ({"id": "CP-020", "category": "task_completion_pivot", "risk_weight": 0.8, ...}, <re.Match>),
    ({"id": "CP-010", "category": "numbered_choice", "risk_weight": 0.5, ...}, <re.Match>),
]
```

**Output Example:**

```python
(1.0, CascadeRiskLevel.CRITICAL)
# Score = max(continuation: 0.7) + max(pivot: 0.8) + max(numbered: 0.5) = 2.0 → capped at 1.0
```

**Edge Cases:**
- Empty list → `(0.0, CascadeRiskLevel.NONE)`
- Single weak match `[({weight: 0.2}, match)]` → `(0.2, CascadeRiskLevel.NONE)` (below 0.3)
- Multiple patterns same category → takes max weight, not sum: `[({cat: "co", w: 0.7}, m), ({cat: "co", w: 0.5}, m)]` → score 0.7, not 1.2

### 5.3 `is_permission_prompt()`

**File:** `assemblyzero/hooks/cascade_detector.py`

**Signature:**

```python
def is_permission_prompt(text: str) -> bool:
    """Distinguish genuine permission prompts from cascade offers."""
    ...
```

**Input Example (True):**

```python
text = "Allow bash command: git push origin main? (y/n)"
# Returns True
```

**Input Example (True):**

```python
text = "Allow file write: /src/main.py? (y/n)"
# Returns True
```

**Input Example (False):**

```python
text = "Should I continue with the next issue?"
# Returns False
```

**Edge Cases:**
- `"Allow Read tool to read file: src/config.json?"` → `True`
- `"I allow you to continue"` → `False` (not a permission prompt structure)
- `""` → `False`

### 5.4 `load_default_patterns()`

**File:** `assemblyzero/hooks/cascade_patterns.py`

**Signature:**

```python
def load_default_patterns() -> list[CascadePattern]:
    """Load the built-in cascade detection patterns."""
    ...
```

**Input Example:** (no args)

**Output Example:**

```python
[
    {
        "id": "CP-001",
        "category": "continuation_offer",
        "regex": r"(?i)should I (continue|proceed|start|begin|move on)",
        "description": "Detects 'Should I continue/proceed/start' offers",
        "risk_weight": 0.7,
        "examples": ["Should I continue with the next issue?"],
    },
    # ... 14+ more patterns
]
# Returns list of 15+ CascadePattern dicts
```

**Edge Cases:** None — always returns the same hardcoded list.

### 5.5 `load_user_patterns()`

**File:** `assemblyzero/hooks/cascade_patterns.py`

**Signature:**

```python
def load_user_patterns(
    config_path: str | Path | None = None,
) -> list[CascadePattern]:
    """Load user-defined patterns from cascade_block_patterns.json."""
    ...
```

**Input Example:**

```python
config_path = "data/unleashed/cascade_block_patterns.json"
```

**Output Example (valid config):**

```python
[
    {
        "id": "CP-100",
        "category": "continuation_offer",
        "regex": r"(?i)want me to (tackle|handle|address) the next",
        "description": "Custom pattern for 'want me to tackle the next' phrasing",
        "risk_weight": 0.7,
        "examples": ["Want me to tackle the next issue?"],
    }
]
```

**Edge Cases:**
- `config_path=None` → uses default `data/unleashed/cascade_block_patterns.json`
- File not found → returns empty list (logged as warning)
- Invalid JSON → returns empty list (logged as warning, triggers REQ-8 fallback)
- Config with `enabled: false` → returns empty list

### 5.6 `merge_patterns()`

**File:** `assemblyzero/hooks/cascade_patterns.py`

**Signature:**

```python
def merge_patterns(
    defaults: list[CascadePattern],
    overrides: list[CascadePattern],
) -> list[CascadePattern]:
    """Merge two pattern lists, with overrides taking precedence by ID."""
    ...
```

**Input Example:**

```python
defaults = [
    {"id": "CP-001", "category": "continuation_offer", "regex": r"(?i)should I (continue|proceed)", "risk_weight": 0.7, ...},
    {"id": "CP-010", "category": "numbered_choice", "regex": r"...", "risk_weight": 0.5, ...},
]
overrides = [
    {"id": "CP-001", "category": "continuation_offer", "regex": r"(?i)should I (continue|proceed|go on)", "risk_weight": 0.8, ...},
    {"id": "CP-100", "category": "scope_expansion", "regex": r"...", "risk_weight": 0.6, ...},
]
```

**Output Example:**

```python
[
    {"id": "CP-001", "regex": r"(?i)should I (continue|proceed|go on)", "risk_weight": 0.8, ...},  # Override
    {"id": "CP-010", "regex": r"...", "risk_weight": 0.5, ...},  # Default preserved
    {"id": "CP-100", "regex": r"...", "risk_weight": 0.6, ...},  # New from override
]
```

**Edge Cases:**
- Empty overrides → returns copy of defaults
- Empty defaults → returns copy of overrides
- Both empty → returns empty list

### 5.7 `handle_cascade_detection()`

**File:** `assemblyzero/hooks/cascade_action.py`

**Signature:**

```python
def handle_cascade_detection(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    alert_enabled: bool = True,
) -> bool:
    """Execute the recommended action from a cascade detection."""
    ...
```

**Input Example (block):**

```python
result = {
    "detected": True,
    "risk_level": CascadeRiskLevel.HIGH,
    "matched_patterns": ["CP-001", "CP-020"],
    "matched_text": "Should I continue with issue #43?",
    "recommended_action": "block_and_prompt",
    "confidence": 0.85,
}
session_id = "sess_abc123def456"
model_output = "I've fixed issue #42. Should I continue with issue #43?"
alert_enabled = True
```

**Output Example:** `False` (auto-approve blocked)

**Input Example (allow):**

```python
result = {
    "detected": False,
    "risk_level": CascadeRiskLevel.NONE,
    "matched_patterns": [],
    "matched_text": "",
    "recommended_action": "allow",
    "confidence": 0.0,
}
```

**Output Example:** `True` (auto-approve may proceed)

**Edge Cases:**
- `recommended_action == "block_and_alert"` with `alert_enabled=False` → still returns `False` (blocked), but skips alert formatting
- Telemetry logging failure → caught internally, does not affect return value

### 5.8 `format_block_message()`

**File:** `assemblyzero/hooks/cascade_action.py`

**Signature:**

```python
def format_block_message(
    result: CascadeDetectionResult,
) -> str:
    """Format a human-readable message explaining why auto-approve was blocked."""
    ...
```

**Input Example:**

```python
result = {
    "detected": True,
    "risk_level": CascadeRiskLevel.HIGH,
    "matched_patterns": ["CP-001", "CP-020"],
    "matched_text": "Should I continue with issue #43?",
    "recommended_action": "block_and_prompt",
    "confidence": 0.85,
}
```

**Output Example:**

```
⚠️  CASCADE DETECTED — Auto-approve blocked
Risk Level: HIGH (confidence: 0.85)
Matched Patterns: CP-001 (continuation_offer), CP-020 (task_completion_pivot)
Trigger: "Should I continue with issue #43?"

The AI is offering to continue to the next task. Please provide manual input.
Type your response to decide what happens next.
```

**Edge Cases:**
- `matched_text` longer than 100 chars → truncated with `...`
- Empty `matched_patterns` (shouldn't happen if detected=True, but guard) → shows "unknown"

### 5.9 `log_cascade_event()`

**File:** `assemblyzero/telemetry/cascade_events.py`

**Signature:**

```python
def log_cascade_event(
    event: CascadeEvent,
    log_path: str | Path | None = None,
) -> None:
    """Append a cascade_risk event to the telemetry log."""
    ...
```

**Input Example:**

```python
event = {
    "timestamp": "2026-02-25T14:32:07.123456+00:00",
    "event_type": "cascade_risk",
    "risk_level": "high",
    "action_taken": "blocked",
    "matched_patterns": ["CP-001", "CP-020"],
    "model_output_snippet": "I've fixed issue #42. Should I continue with issue #43?",
    "session_id": "sess_abc123def456",
    "auto_approve_blocked": True,
}
log_path = "tmp/cascade-events.jsonl"
```

**Output Example:** None (side effect: appends one JSON line to file)

**Written line:**
```json
{"timestamp":"2026-02-25T14:32:07.123456+00:00","event_type":"cascade_risk","risk_level":"high","action_taken":"blocked","matched_patterns":["CP-001","CP-020"],"model_output_snippet":"I've fixed issue #42. Should I continue with issue #43?","session_id":"sess_abc123def456","auto_approve_blocked":true}
```

**Edge Cases:**
- `log_path=None` → uses `tmp/cascade-events.jsonl`
- Parent directory doesn't exist → creates it with `Path.mkdir(parents=True, exist_ok=True)`
- File I/O error → caught, logged to stderr, does not raise

### 5.10 `create_cascade_event()`

**File:** `assemblyzero/telemetry/cascade_events.py`

**Signature:**

```python
def create_cascade_event(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    action_taken: str,
) -> CascadeEvent:
    """Create a CascadeEvent from a detection result."""
    ...
```

**Input Example:**

```python
result = {
    "detected": True,
    "risk_level": CascadeRiskLevel.HIGH,
    "matched_patterns": ["CP-001", "CP-020"],
    "matched_text": "Should I continue...",
    "recommended_action": "block_and_prompt",
    "confidence": 0.85,
}
session_id = "sess_abc123"
model_output = "I've fixed issue #42. Should I continue with issue #43? " + "x" * 500
action_taken = "blocked"
```

**Output Example:**

```python
{
    "timestamp": "2026-02-25T14:32:07.123456+00:00",  # datetime.now(timezone.utc).isoformat()
    "event_type": "cascade_risk",
    "risk_level": "high",
    "action_taken": "blocked",
    "matched_patterns": ["CP-001", "CP-020"],
    "model_output_snippet": "I've fixed issue #42. Should I continue with issue #43? xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # truncated to 200 chars
    "session_id": "sess_abc123",
    "auto_approve_blocked": True,
}
```

**Edge Cases:**
- `model_output` ≤ 200 chars → used as-is
- `model_output` > 200 chars → truncated to 200 chars (no ellipsis in data, just truncation)
- `risk_level` is enum → converted to `.value` string

### 5.11 `get_cascade_stats()`

**File:** `assemblyzero/telemetry/cascade_events.py`

**Signature:**

```python
def get_cascade_stats(
    log_path: str | Path | None = None,
    since_hours: int = 24,
) -> dict[str, int]:
    """Retrieve cascade detection statistics from the event log."""
    ...
```

**Input Example:**

```python
log_path = "tmp/cascade-events.jsonl"
since_hours = 24
```

**Output Example:**

```python
{"total_checks": 47, "detections": 5, "blocks": 4, "allowed": 43}
```

**Edge Cases:**
- File doesn't exist → `{"total_checks": 0, "detections": 0, "blocks": 0, "allowed": 0}`
- Corrupt JSONL line → skip line, continue parsing
- `since_hours=0` → return all events regardless of time

### 5.12 `main()` (Hook entry point)

**File:** `.claude/hooks/post_output_cascade_check.py`

**Signature:**

```python
def main() -> None:
    """Claude Code PostToolUse hook entry point."""
    ...
```

**Input:** Model output text from stdin (Claude Code hook contract)

**Output:** `sys.exit(0)` for allow, `sys.exit(2)` for block

**Edge Cases:**
- Empty stdin → `exit(0)` (allow)
- Unhandled exception → `exit(0)` (fail open for hook crash, logged to stderr)
- Import error (module not found) → `exit(0)` with stderr warning

### 5.13 `validate_claude_md_cascade_rule()` (Test utility)

**File:** `tests/integration/test_cascade_hook_integration.py` (as test helper function)

**Signature:**

```python
def validate_claude_md_cascade_rule(
    claude_md_path: str | Path,
) -> dict[str, bool]:
    """Validate that CLAUDE.md contains the required cascade prevention rule."""
    ...
```

**Input Example:**

```python
claude_md_path = "CLAUDE.md"
```

**Output Example (passing):**

```python
{
    "rule_present": True,
    "contains_open_ended": True,
    "forbids_numbered_options": True,
    "section_correct": True,
}
```

**Output Example (failing — rule missing):**

```python
{
    "rule_present": False,
    "contains_open_ended": False,
    "forbids_numbered_options": False,
    "section_correct": False,
}
```

**Edge Cases:**
- File not found → all `False`
- Rule present but missing open-ended phrasing → `rule_present=True`, `contains_open_ended=False`

## 6. Change Instructions

### 6.1 `tests/fixtures/cascade_samples.json` (Add)

**Complete file contents:**

```json
{
    "cascade_samples": [
        {
            "id": "S001",
            "text": "Great, issue #42 is fixed! Should I continue with issue #43?",
            "expected_detected": true,
            "expected_min_risk": "high",
            "category": "continuation_offer"
        },
        {
            "id": "S002",
            "text": "Done! What's next?\n1. Yes, start issue #44\n2. No, stop here",
            "expected_detected": true,
            "expected_min_risk": "critical",
            "category": "numbered_choice_with_completion"
        },
        {
            "id": "S003",
            "text": "I've completed the refactor. Now let me also update the tests for the new module.",
            "expected_detected": true,
            "expected_min_risk": "high",
            "category": "task_completion_pivot"
        },
        {
            "id": "S004",
            "text": "While I'm at it, I could also fix the related CSS issue in the sidebar.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion"
        },
        {
            "id": "S005",
            "text": "I solved issue 1. Should I do issue 2?\n1. Yes\n2. No",
            "expected_detected": true,
            "expected_min_risk": "critical",
            "category": "gemini_style_cascade"
        },
        {
            "id": "S006",
            "text": "Do you want me to proceed with the next task?",
            "expected_detected": true,
            "expected_min_risk": "low",
            "category": "continuation_offer_single"
        },
        {
            "id": "S007",
            "text": "Shall I begin the refactoring of the auth module?",
            "expected_detected": true,
            "expected_min_risk": "low",
            "category": "continuation_offer_single"
        },
        {
            "id": "S008",
            "text": "Would you like me to start implementing issue #44?",
            "expected_detected": true,
            "expected_min_risk": "low",
            "category": "continuation_offer_single"
        },
        {
            "id": "S009",
            "text": "That's fixed. Should I also update the documentation?\n1. Yes, update docs\n2. No, that's enough",
            "expected_detected": true,
            "expected_min_risk": "critical",
            "category": "completion_pivot_with_numbered"
        },
        {
            "id": "S010",
            "text": "I've finished the migration. Now let me handle the next batch of files.",
            "expected_detected": true,
            "expected_min_risk": "high",
            "category": "task_completion_pivot"
        },
        {
            "id": "S011",
            "text": "There are also some type errors — should I fix those too?",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion"
        },
        {
            "id": "S012",
            "text": "I additionally noticed a performance issue — want me to address it?",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion"
        },
        {
            "id": "S013",
            "text": "Ready to move on to the testing phase?",
            "expected_detected": true,
            "expected_min_risk": "low",
            "category": "continuation_offer_single"
        },
        {
            "id": "S014",
            "text": "Task #5 is complete. Next up is task #6 which involves updating the API endpoints.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "task_completion_pivot"
        },
        {
            "id": "S015",
            "text": "While I'm here, I should additionally clean up the unused imports across the codebase.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion"
        }
    ],
    "permission_prompt_samples": [
        {
            "id": "P001",
            "text": "Allow bash command: git push origin main? (y/n)",
            "expected_detected": false,
            "category": "bash_permission"
        },
        {
            "id": "P002",
            "text": "Allow file write: /src/main.py? (y/n)",
            "expected_detected": false,
            "category": "file_write_permission"
        },
        {
            "id": "P003",
            "text": "Allow Read tool to read file: src/config.json?",
            "expected_detected": false,
            "category": "read_permission"
        },
        {
            "id": "P004",
            "text": "Allow bash command: poetry run pytest tests/ -v? (y/n)",
            "expected_detected": false,
            "category": "bash_permission"
        },
        {
            "id": "P005",
            "text": "Allow Write tool to write to: assemblyzero/hooks/cascade_detector.py?",
            "expected_detected": false,
            "category": "write_permission"
        },
        {
            "id": "P006",
            "text": "Allow ListDirectory tool to list: /src/?",
            "expected_detected": false,
            "category": "list_permission"
        },
        {
            "id": "P007",
            "text": "Allow bash command: rm -rf build/? (y/n)",
            "expected_detected": false,
            "category": "bash_permission"
        },
        {
            "id": "P008",
            "text": "Allow Grep tool to search for: import cascade? (y/n)",
            "expected_detected": false,
            "category": "grep_permission"
        },
        {
            "id": "P009",
            "text": "Allow WebSearch tool? (y/n)",
            "expected_detected": false,
            "category": "web_permission"
        },
        {
            "id": "P010",
            "text": "Allow Edit tool to edit: CLAUDE.md?",
            "expected_detected": false,
            "category": "edit_permission"
        }
    ],
    "non_cascade_samples": [
        {
            "id": "N001",
            "text": "def should_i_continue(): return True",
            "expected_detected": false,
            "category": "code_with_keyword"
        },
        {
            "id": "N002",
            "text": "Should I use async or sync for this function?",
            "expected_detected": false,
            "category": "legitimate_technical_question"
        },
        {
            "id": "N003",
            "text": "The implementation looks correct. Here's the summary of changes made:\n- Fixed the parser\n- Updated tests\n- Added docs",
            "expected_detected": false,
            "category": "clean_completion"
        },
        {
            "id": "N004",
            "text": "",
            "expected_detected": false,
            "category": "empty_input"
        },
        {
            "id": "N005",
            "text": "Should I format this differently? The current approach uses tabs.",
            "expected_detected": false,
            "category": "legitimate_question_with_keyword"
        }
    ],
    "edge_case_samples": [
        {
            "id": "E001",
            "text": "I've updated the code. Should I also add type hints? The current functions lack proper typing.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "subtle_scope_expansion"
        },
        {
            "id": "E002",
            "text": "That's done. Next steps could include:\n1. Adding more tests\n2. Updating docs\n3. Deploying\n\nWhich would you prefer?",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "soft_numbered_options"
        },
        {
            "id": "E003",
            "text": "I also noticed some warnings — should I fix those too?\n1. Yes\n2. No",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion_with_numbered"
        },
        {
            "id": "E004",
            "text": "There is another issue related to the database schema — should I investigate?",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "scope_expansion_there_is"
        },
        {
            "id": "E005",
            "text": "Bug #99 resolved. Now for the next one — issue #100 involves the payment gateway.",
            "expected_detected": true,
            "expected_min_risk": "medium",
            "category": "completion_then_next"
        }
    ]
}
```

### 6.2 `assemblyzero/hooks/cascade_patterns.py` (Add)

**Complete file contents:**

```python
"""Cascade detection pattern definitions.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Contains regex patterns for detecting cascade-risk scenarios in model output.
Patterns are organized by category and scored by risk weight.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Literal, TypedDict

logger = logging.getLogger(__name__)

# Default config file location relative to project root
_DEFAULT_CONFIG_PATH = Path("data/unleashed/cascade_block_patterns.json")


class CascadePattern(TypedDict):
    """A single pattern definition for cascade detection."""

    id: str
    category: Literal[
        "continuation_offer",
        "numbered_choice",
        "task_completion_pivot",
        "scope_expansion",
    ]
    regex: str
    description: str
    risk_weight: float
    examples: list[str]


def load_default_patterns() -> list[CascadePattern]:
    """Load the built-in cascade detection patterns.

    Returns the hardcoded baseline pattern set derived from 3 months
    of production cascade incidents. These patterns catch common
    cascade scenarios across Claude and Gemini model outputs.

    Returns:
        List of CascadePattern definitions (15+ patterns).
    """
    return [
        # ── continuation_offer ──
        {
            "id": "CP-001",
            "category": "continuation_offer",
            "regex": r"(?i)\bshould I (continue|proceed|start|begin|move on)\b",
            "description": "Detects 'Should I continue/proceed/start' offers",
            "risk_weight": 0.7,
            "examples": ["Should I continue with the next issue?"],
        },
        {
            "id": "CP-002",
            "category": "continuation_offer",
            "regex": r"(?i)\bdo you want me to (continue|proceed|start|begin)\b",
            "description": "Detects 'Do you want me to continue' offers",
            "risk_weight": 0.7,
            "examples": ["Do you want me to proceed?"],
        },
        {
            "id": "CP-003",
            "category": "continuation_offer",
            "regex": r"(?i)\bshall I (continue|proceed|start|begin|move on)\b",
            "description": "Detects 'Shall I continue/start' offers",
            "risk_weight": 0.7,
            "examples": ["Shall I begin the next task?"],
        },
        {
            "id": "CP-004",
            "category": "continuation_offer",
            "regex": r"(?i)\bwould you like me to (continue|proceed|start|begin)\b",
            "description": "Detects 'Would you like me to continue' offers",
            "risk_weight": 0.7,
            "examples": ["Would you like me to start issue #44?"],
        },
        {
            "id": "CP-005",
            "category": "continuation_offer",
            "regex": r"(?i)\bready to (continue|proceed|start|begin|move on)\b",
            "description": "Detects 'Ready to continue/move on' offers",
            "risk_weight": 0.5,
            "examples": ["Ready to move on to the next one?"],
        },
        # ── numbered_choice ──
        {
            "id": "CP-010",
            "category": "numbered_choice",
            "regex": r"(?mi)^\s*1[.\)]\s*(yes|continue|proceed|go ahead)",
            "description": "Detects '1. Yes/Continue' numbered option",
            "risk_weight": 0.5,
            "examples": ["1. Yes, continue"],
        },
        {
            "id": "CP-011",
            "category": "numbered_choice",
            "regex": r"(?mi)^\s*2[.\)]\s*(no|stop|wait|hold)",
            "description": "Detects '2. No/Stop' numbered option",
            "risk_weight": 0.5,
            "examples": ["2. No, stop here"],
        },
        {
            "id": "CP-012",
            "category": "numbered_choice",
            "regex": r"(?is)(which option|choose|select).{0,30}\n\s*1[.\)].{0,50}\n\s*2[.\)]",
            "description": "Detects 'Choose: 1. X  2. Y' structured options",
            "risk_weight": 0.4,
            "examples": ["Choose:\n1. Option A\n2. Option B"],
        },
        # ── task_completion_pivot ──
        {
            "id": "CP-020",
            "category": "task_completion_pivot",
            "regex": r"(?i)I('ve| have) (finished|completed|fixed|solved|done).{0,80}(should I|shall I|want me to|let me)",
            "description": "Detects 'I finished X. Should I do Y?' pivot",
            "risk_weight": 0.8,
            "examples": ["I've finished issue 42. Should I start 43?"],
        },
        {
            "id": "CP-021",
            "category": "task_completion_pivot",
            "regex": r"(?i)(that's|that is) (done|complete|fixed|finished).{0,80}(should|shall|want|would|let me|next)",
            "description": "Detects 'That's done. What next?' pivot",
            "risk_weight": 0.7,
            "examples": ["That's done. What should I tackle next?"],
        },
        {
            "id": "CP-022",
            "category": "task_completion_pivot",
            "regex": r"(?i)(task|issue|bug|feature).{0,30}(complete|done|fixed|resolved).{0,80}(next|now|also|another)",
            "description": "Detects 'Issue resolved. Now for the next' pivot",
            "risk_weight": 0.6,
            "examples": ["Issue #42 resolved. Now for the next one."],
        },
        {
            "id": "CP-023",
            "category": "task_completion_pivot",
            "regex": r"(?i)I('ve| have) (finished|completed|fixed|solved|done).{0,80}(now let me|let me also|let me now)",
            "description": "Detects 'I finished X. Now let me do Y' self-directed pivot",
            "risk_weight": 0.8,
            "examples": ["I've completed the refactor. Now let me also update the tests."],
        },
        # ── scope_expansion ──
        {
            "id": "CP-030",
            "category": "scope_expansion",
            "regex": r"(?i)while I'm (at it|here),? I (could|should|can|might) (also|additionally)",
            "description": "Detects 'While I'm at it, I could also' expansion",
            "risk_weight": 0.6,
            "examples": ["While I'm at it, I could also refactor the auth module."],
        },
        {
            "id": "CP-031",
            "category": "scope_expansion",
            "regex": r"(?i)I (also|additionally) noticed.{0,80}(should I|want me to|shall I)",
            "description": "Detects 'I also noticed — should I fix it?' expansion",
            "risk_weight": 0.6,
            "examples": ["I also noticed a bug — should I fix it?"],
        },
        {
            "id": "CP-032",
            "category": "scope_expansion",
            "regex": r"(?i)there (are|is) (also|another|more|additional).{0,80}(should I|want me to|shall I)",
            "description": "Detects 'There are also X — should I?' expansion",
            "risk_weight": 0.5,
            "examples": ["There are also some lint warnings — should I fix those?"],
        },
    ]


def load_user_patterns(
    config_path: str | Path | None = None,
) -> list[CascadePattern]:
    """Load user-defined patterns from cascade_block_patterns.json.

    Merges with defaults. User patterns can override built-in patterns
    by using the same pattern ID.

    Args:
        config_path: Path to user config. If None, uses default location
                     at data/unleashed/cascade_block_patterns.json.

    Returns:
        Merged list of patterns (user overrides take precedence).
        Returns empty list if file not found or invalid.
    """
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.debug("User pattern config not found at %s", config_path)
        return []

    try:
        raw = config_path.read_text(encoding="utf-8")
        config = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to load user cascade patterns from %s: %s", config_path, exc
        )
        return []

    if not isinstance(config, dict):
        logger.warning("Invalid cascade pattern config format at %s", config_path)
        return []

    if not config.get("enabled", True):
        logger.debug("User cascade patterns disabled in config")
        return []

    patterns = config.get("patterns", [])
    if not isinstance(patterns, list):
        logger.warning("Invalid patterns field in %s", config_path)
        return []

    # Validate each pattern has required fields
    valid_patterns: list[CascadePattern] = []
    required_keys = {"id", "category", "regex", "description", "risk_weight"}
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        if not required_keys.issubset(pattern.keys()):
            logger.warning("Skipping invalid pattern (missing keys): %s", pattern.get("id", "unknown"))
            continue
        # Validate regex compiles
        try:
            re.compile(pattern["regex"])
        except re.error as exc:
            logger.warning("Skipping pattern %s with invalid regex: %s", pattern["id"], exc)
            continue
        # Set defaults for optional fields
        if "examples" not in pattern:
            pattern["examples"] = []
        valid_patterns.append(pattern)  # type: ignore[arg-type]

    return valid_patterns


def merge_patterns(
    defaults: list[CascadePattern],
    overrides: list[CascadePattern],
) -> list[CascadePattern]:
    """Merge two pattern lists, with overrides taking precedence by ID.

    Args:
        defaults: Base pattern list.
        overrides: Override patterns (same ID replaces default).

    Returns:
        Merged pattern list preserving order (defaults first, then new overrides).
    """
    override_map: dict[str, CascadePattern] = {p["id"]: p for p in overrides}
    override_ids_used: set[str] = set()

    merged: list[CascadePattern] = []
    for default in defaults:
        if default["id"] in override_map:
            merged.append(override_map[default["id"]])
            override_ids_used.add(default["id"])
        else:
            merged.append(default)

    # Append any override patterns with new IDs (not in defaults)
    for override in overrides:
        if override["id"] not in override_ids_used:
            merged.append(override)

    return merged
```

### 6.3 `assemblyzero/hooks/cascade_detector.py` (Add)

**Complete file contents:**

```python
"""Core cascade detection engine.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Analyzes model output text for cascade-risk patterns using multi-category
weighted regex scoring.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, TypedDict

from assemblyzero.hooks.cascade_patterns import (
    CascadePattern,
    load_default_patterns,
    load_user_patterns,
    merge_patterns,
)

# Maximum input length to prevent performance issues
MAX_INPUT_LENGTH = 10_000


class CascadeRiskLevel(Enum):
    """Severity of detected cascade risk."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CascadeDetectionResult(TypedDict):
    """Result from analyzing a model output block."""

    detected: bool
    risk_level: CascadeRiskLevel
    matched_patterns: list[str]
    matched_text: str
    recommended_action: Literal["allow", "block_and_prompt", "block_and_alert"]
    confidence: float


# Pre-compiled permission prompt patterns
_PERMISSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)^allow (bash|file write|read|write|edit|listdirectory|grep|websearch)\b"),
    re.compile(r"(?i)^allow \w+ tool\b"),
    re.compile(r"(?i)allow (bash command|file write|file read):"),
    re.compile(r"(?i)\(y/n\)\s*$"),
]


def detect_cascade_risk(
    model_output: str,
    patterns: list[CascadePattern] | None = None,
    risk_threshold: float = 0.6,
) -> CascadeDetectionResult:
    """Analyze model output text for cascade-risk patterns.

    Scans the output against all registered patterns, calculates a
    composite risk score, and returns a detection result with
    recommended action.

    Args:
        model_output: The raw text output from the AI model.
        patterns: Optional override patterns. If None, loads from
                  default pattern set merged with user patterns.
        risk_threshold: Minimum composite score (0.0-1.0) to
                       trigger a block recommendation.

    Returns:
        CascadeDetectionResult with detection status and recommended action.
    """
    # Guard: empty/None input
    if not model_output:
        return _make_allow_result()

    # Truncate to max length for performance
    text = model_output[:MAX_INPUT_LENGTH]

    # Short-circuit: don't block permission prompts
    if is_permission_prompt(text):
        return _make_allow_result()

    # Load patterns
    if patterns is None:
        defaults = load_default_patterns()
        user = load_user_patterns()
        patterns = merge_patterns(defaults, user)

    # Compile and match patterns
    matched: list[tuple[CascadePattern, re.Match[str]]] = []
    for pattern in patterns:
        try:
            compiled = re.compile(pattern["regex"])
            match = compiled.search(text)
            if match:
                matched.append((pattern, match))
        except re.error:
            # Skip invalid patterns silently
            continue

    # Compute risk score
    score, risk_level = compute_risk_score(matched)

    # Determine action based on risk level
    if risk_level in (CascadeRiskLevel.NONE, CascadeRiskLevel.LOW):
        recommended_action: Literal["allow", "block_and_prompt", "block_and_alert"] = "allow"
    elif risk_level == CascadeRiskLevel.MEDIUM:
        recommended_action = "block_and_prompt"
    else:  # HIGH or CRITICAL
        recommended_action = "block_and_alert"

    # Apply threshold override: if score is below threshold, allow
    if score < risk_threshold and recommended_action != "allow":
        recommended_action = "allow"
        risk_level = CascadeRiskLevel.LOW if score >= 0.3 else CascadeRiskLevel.NONE

    detected = recommended_action != "allow"

    # Build matched text (first match text for display)
    matched_text = ""
    if matched:
        # Use the match with the highest risk weight for display
        best_match = max(matched, key=lambda m: m[0]["risk_weight"])
        matched_text = best_match[1].group(0)

    return {
        "detected": detected,
        "risk_level": risk_level,
        "matched_patterns": [p["id"] for p, _ in matched],
        "matched_text": matched_text,
        "recommended_action": recommended_action,
        "confidence": min(score, 1.0),
    }


def compute_risk_score(
    matched_patterns: list[tuple[CascadePattern, re.Match[str]]],
) -> tuple[float, CascadeRiskLevel]:
    """Compute composite risk score from matched patterns.

    Uses weighted scoring: each matched pattern contributes its
    risk_weight. Multiple matches in different categories compound.
    Same-category matches don't double-count (max weight per category).

    Args:
        matched_patterns: List of (pattern, match) tuples from scanning.

    Returns:
        Tuple of (score: 0.0-1.0, risk_level: CascadeRiskLevel).
    """
    if not matched_patterns:
        return 0.0, CascadeRiskLevel.NONE

    # Group by category, take max weight per category
    category_max: dict[str, float] = {}
    for pattern, _ in matched_patterns:
        cat = pattern["category"]
        weight = pattern["risk_weight"]
        if cat not in category_max or weight > category_max[cat]:
            category_max[cat] = weight

    # Sum max weights across categories
    raw_score = sum(category_max.values())

    # Cap at 1.0
    score = min(raw_score, 1.0)

    # Map to risk level
    if score < 0.3:
        risk_level = CascadeRiskLevel.NONE
    elif score < 0.5:
        risk_level = CascadeRiskLevel.LOW
    elif score < 0.7:
        risk_level = CascadeRiskLevel.MEDIUM
    elif score < 0.9:
        risk_level = CascadeRiskLevel.HIGH
    else:
        risk_level = CascadeRiskLevel.CRITICAL

    return score, risk_level


def is_permission_prompt(text: str) -> bool:
    """Distinguish genuine permission prompts from cascade offers.

    Permission prompts (e.g., "Allow bash command: git push?") should
    NOT be blocked. This function detects the permission prompt format
    to avoid false positives.

    Args:
        text: Text to check.

    Returns:
        True if this looks like a genuine permission/tool approval prompt.
    """
    if not text:
        return False

    # Check against all permission patterns
    # Strip leading/trailing whitespace for matching
    stripped = text.strip()
    for pattern in _PERMISSION_PATTERNS:
        if pattern.search(stripped):
            return True

    return False


def _make_allow_result() -> CascadeDetectionResult:
    """Create a default 'allow' result (no cascade detected)."""
    return {
        "detected": False,
        "risk_level": CascadeRiskLevel.NONE,
        "matched_patterns": [],
        "matched_text": "",
        "recommended_action": "allow",
        "confidence": 0.0,
    }
```

### 6.4 `assemblyzero/hooks/cascade_action.py` (Add)

**Complete file contents:**

```python
"""Action handlers for cascade detection results.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Dispatches actions (allow, block, alert) based on cascade detection results.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from assemblyzero.hooks.cascade_detector import CascadeDetectionResult, CascadeRiskLevel
from assemblyzero.telemetry.cascade_events import create_cascade_event, log_cascade_event

if TYPE_CHECKING:
    pass


def handle_cascade_detection(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    alert_enabled: bool = True,
) -> bool:
    """Execute the recommended action from a cascade detection.

    Depending on the detection result, it will:
    - allow: return True (auto-approve may proceed)
    - block_and_prompt: log event, return False (force human input)
    - block_and_alert: log event, show alert, return False

    Args:
        result: The CascadeDetectionResult from detect_cascade_risk.
        session_id: Current session identifier for telemetry.
        model_output: Full model output for logging context.
        alert_enabled: Whether to show visual/audible alert on block.

    Returns:
        True if auto-approval should proceed, False if blocked.
    """
    action = result["recommended_action"]

    if action == "allow":
        # Optionally log allowed checks (if log_all_checks is configured)
        return True

    # For block_and_prompt and block_and_alert
    action_taken = "blocked" if action == "block_and_prompt" else "alerted"

    # Log the cascade event
    try:
        event = create_cascade_event(
            result=result,
            session_id=session_id,
            model_output=model_output,
            action_taken=action_taken,
        )
        log_cascade_event(event)
    except Exception:  # noqa: BLE001
        # Telemetry failure must not affect blocking behavior
        pass

    # Print block message to stderr
    message = format_block_message(result)
    if action == "block_and_alert" and alert_enabled:
        # Add alert decoration
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"🚨 ALERT: {message}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
    else:
        print(f"\n{message}\n", file=sys.stderr)

    return False


def format_block_message(
    result: CascadeDetectionResult,
) -> str:
    """Format a human-readable message explaining why auto-approve was blocked.

    Shown to the user when cascade detection fires, explaining what
    was detected and asking them to make the decision manually.

    Args:
        result: The detection result.

    Returns:
        Formatted message string for terminal display.
    """
    risk_level = result["risk_level"]
    if isinstance(risk_level, CascadeRiskLevel):
        risk_name = risk_level.value.upper()
    else:
        risk_name = str(risk_level).upper()

    confidence = result["confidence"]
    pattern_ids = result["matched_patterns"] if result["matched_patterns"] else ["unknown"]
    matched_text = result["matched_text"]

    # Truncate matched text for display
    if len(matched_text) > 100:
        matched_text = matched_text[:100] + "..."

    lines = [
        "⚠️  CASCADE DETECTED — Auto-approve blocked",
        f"Risk Level: {risk_name} (confidence: {confidence:.2f})",
        f"Matched Patterns: {', '.join(pattern_ids)}",
        f'Trigger: "{matched_text}"',
        "",
        "The AI is offering to continue to the next task. Please provide manual input.",
        "Type your response to decide what happens next.",
    ]
    return "\n".join(lines)
```

### 6.5 `assemblyzero/telemetry/cascade_events.py` (Add)

**Complete file contents:**

```python
"""Structured logging for cascade_risk events.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Writes newline-delimited JSON (JSONL) for measurement and tuning
of cascade detection accuracy over time.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, TypedDict

from assemblyzero.hooks.cascade_detector import CascadeDetectionResult, CascadeRiskLevel

logger = logging.getLogger(__name__)

# Default log file location
_DEFAULT_LOG_PATH = Path("tmp/cascade-events.jsonl")


class CascadeEvent(TypedDict):
    """Telemetry event for cascade detection."""

    timestamp: str
    event_type: Literal["cascade_risk"]
    risk_level: str
    action_taken: str
    matched_patterns: list[str]
    model_output_snippet: str
    session_id: str
    auto_approve_blocked: bool


def log_cascade_event(
    event: CascadeEvent,
    log_path: str | Path | None = None,
) -> None:
    """Append a cascade_risk event to the telemetry log.

    Events are written as newline-delimited JSON (JSONL) to enable
    measurement of cascade frequency over time.

    Args:
        event: The CascadeEvent to log.
        log_path: Path to JSONL log file. If None, uses default at
                  tmp/cascade-events.jsonl.
    """
    if log_path is None:
        path = _DEFAULT_LOG_PATH
    else:
        path = Path(log_path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except OSError as exc:
        # Log to stderr but don't raise — telemetry must never block
        print(f"[cascade_events] Failed to write event: {exc}", file=sys.stderr)


def create_cascade_event(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    action_taken: str,
) -> CascadeEvent:
    """Create a CascadeEvent from a detection result.

    Args:
        result: Detection result.
        session_id: Current session ID.
        model_output: Original model output (truncated to 200 chars).
        action_taken: The action that was taken ("allowed", "blocked", "alerted").

    Returns:
        CascadeEvent ready for logging.
    """
    risk_level = result["risk_level"]
    if isinstance(risk_level, CascadeRiskLevel):
        risk_str = risk_level.value
    else:
        risk_str = str(risk_level)

    # Truncate snippet to 200 chars
    snippet = model_output[:200] if model_output else ""

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "cascade_risk",
        "risk_level": risk_str,
        "action_taken": action_taken,
        "matched_patterns": result["matched_patterns"],
        "model_output_snippet": snippet,
        "session_id": session_id,
        "auto_approve_blocked": result["recommended_action"] != "allow",
    }


def get_cascade_stats(
    log_path: str | Path | None = None,
    since_hours: int = 24,
) -> dict[str, int]:
    """Retrieve cascade detection statistics from the event log.

    Args:
        log_path: Path to JSONL log file.
        since_hours: Only count events from the last N hours.
                     Use 0 to count all events regardless of time.

    Returns:
        Dict with keys: total_checks, detections, blocks, allowed.
    """
    if log_path is None:
        path = _DEFAULT_LOG_PATH
    else:
        path = Path(log_path)

    stats = {"total_checks": 0, "detections": 0, "blocks": 0, "allowed": 0}

    if not path.exists():
        return stats

    if since_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    else:
        cutoff = None

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue  # Skip corrupt lines

                # Time filter
                if cutoff is not None:
                    try:
                        ts = datetime.fromisoformat(event.get("timestamp", ""))
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue  # Skip events with bad timestamps

                stats["total_checks"] += 1
                if event.get("auto_approve_blocked", False):
                    stats["detections"] += 1
                    stats["blocks"] += 1
                else:
                    stats["allowed"] += 1
    except OSError as exc:
        logger.warning("Failed to read cascade event log: %s", exc)

    return stats
```

### 6.6 `assemblyzero/hooks/__init__.py` (Modify)

**Change:** Replace the entire file content.

```diff
-"""Hooks for workflow validation and enforcement."""
+"""Hooks for workflow validation and enforcement."""
+
+from assemblyzero.hooks.cascade_action import (
+    format_block_message,
+    handle_cascade_detection,
+)
+from assemblyzero.hooks.cascade_detector import (
+    CascadeDetectionResult,
+    CascadeRiskLevel,
+    compute_risk_score,
+    detect_cascade_risk,
+    is_permission_prompt,
+)
+from assemblyzero.hooks.cascade_patterns import (
+    CascadePattern,
+    load_default_patterns,
+    load_user_patterns,
+    merge_patterns,
+)
+
+__all__ = [
+    "CascadeDetectionResult",
+    "CascadePattern",
+    "CascadeRiskLevel",
+    "compute_risk_score",
+    "detect_cascade_risk",
+    "format_block_message",
+    "handle_cascade_detection",
+    "is_permission_prompt",
+    "load_default_patterns",
+    "load_user_patterns",
+    "merge_patterns",
+]
```

### 6.7 `assemblyzero/telemetry/__init__.py` (Modify)

**Change:** Add cascade event imports and exports after existing imports.

```diff
 """AssemblyZero telemetry — structured event emission.

 Fire-and-forget telemetry that never raises, never blocks tool execution.
 Events go to DynamoDB with local JSONL fallback when offline.

 Usage:
     from assemblyzero.telemetry import emit, track_tool

     # Direct event emission
     emit("workflow.start", repo="AssemblyZero", metadata={"issue": 42})

     # Context manager for tool tracking
     with track_tool("run_audit", repo="AssemblyZero"):
         do_work()  # emits tool.start, tool.complete (or tool.error)

 Kill switch: set ASSEMBLYZERO_TELEMETRY=0 to disable all emission.
 """

 from assemblyzero.telemetry.emitter import emit, flush, track_tool
+from assemblyzero.telemetry.cascade_events import (
+    CascadeEvent,
+    create_cascade_event,
+    get_cascade_stats,
+    log_cascade_event,
+)

-__all__ = ["emit", "flush", "track_tool"]
+__all__ = [
+    "CascadeEvent",
+    "create_cascade_event",
+    "emit",
+    "flush",
+    "get_cascade_stats",
+    "log_cascade_event",
+    "track_tool",
+]
```

### 6.8 `data/unleashed/cascade_block_patterns.json` (Add)

**Complete file contents:**

```json
{
    "version": "1.0",
    "enabled": true,
    "patterns": [],
    "risk_threshold": 0.6,
    "alert_on_block": true,
    "log_all_checks": false,
    "_comment": "Add custom cascade detection patterns here. User patterns with the same ID as a default pattern will override the default. See docs/lld/active/358-cascade-prevention.md for pattern format."
}
```

### 6.9 `.claude/hooks/post_output_cascade_check.py` (Add)

**Complete file contents:**

```python
#!/usr/bin/env python3
"""Claude Code PostToolUse hook — cascade detection.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Reads model output from stdin (Claude Code hook contract), runs cascade
detection, and exits with appropriate code:
- exit(0): Allow (no cascade detected, or below threshold)
- exit(2): Block (cascade detected, requires human input)

This hook is invoked by Claude Code after every tool use that produces
output. It only blocks when cascade risk is MEDIUM or above.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    """Claude Code PostToolUse hook entry point."""
    try:
        # Read hook input from stdin (Claude Code hook contract)
        raw_input = sys.stdin.read()

        # Parse the hook input — Claude hooks pass JSON with tool_output field
        model_output = ""
        try:
            hook_data = json.loads(raw_input)
            # Claude Code hook format: {"tool_name": "...", "tool_input": {...}, "tool_output": "..."}
            model_output = hook_data.get("tool_output", "")
            if not isinstance(model_output, str):
                model_output = str(model_output) if model_output else ""
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat the raw input as the model output
            model_output = raw_input

        if not model_output.strip():
            sys.exit(0)

        # Import here to handle import errors gracefully
        from assemblyzero.hooks.cascade_detector import detect_cascade_risk
        from assemblyzero.hooks.cascade_action import handle_cascade_detection

        # Run detection
        result = detect_cascade_risk(model_output)

        # Get session ID from environment or generate a placeholder
        session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown-session")

        # Handle the detection result
        should_allow = handle_cascade_detection(
            result=result,
            session_id=session_id,
            model_output=model_output,
        )

        if should_allow:
            sys.exit(0)  # Allow auto-approve
        else:
            sys.exit(2)  # Block auto-approve

    except SystemExit:
        raise  # Let sys.exit() propagate
    except Exception as exc:  # noqa: BLE001
        # Fail open for hook crashes — don't brick Claude Code
        print(f"[cascade_check] Hook error (failing open): {exc}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
```

### 6.10 `CLAUDE.md` (Modify)

**Change:** Add cascade prevention section after the `## Merging PRs` section (after the closing code fence of the bash block and the "Skipping post-merge cleanup..." line).

```diff
 Skipping post-merge cleanup leaves orphaned worktrees and stale branches.
+
+## Cascade Prevention (Task Completion Behavior)
+
+After completing a task, ask an **open-ended question** such as "What would you like to work on next?"
+
+**NEVER** offer numbered yes/no options for deciding next steps. For example, do NOT output:
+- "Should I continue with the next issue? 1. Yes 2. No"
+- "1. Proceed to issue #44  2. Stop here"
+
+The human orchestrator decides what to do next — not the AI. Present your completed work,
+then ask what the human wants. Do not suggest, enumerate, or auto-propose next tasks.
```

### 6.11 `tests/unit/test_cascade_detector.py` (Add)

**Complete file contents:**

```python
"""Unit tests for cascade detection engine.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T010, T030, T040, T050, T060, T080, T110, T120, T200, T210
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from assemblyzero.hooks.cascade_detector import (
    MAX_INPUT_LENGTH,
    CascadeDetectionResult,
    CascadeRiskLevel,
    compute_risk_score,
    detect_cascade_risk,
    is_permission_prompt,
)
from assemblyzero.hooks.cascade_patterns import (
    CascadePattern,
    load_default_patterns,
    load_user_patterns,
    merge_patterns,
)


# ── Fixture loading ──

FIXTURES_PATH = Path("tests/fixtures/cascade_samples.json")


@pytest.fixture
def fixtures() -> dict:
    """Load test fixtures from cascade_samples.json."""
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def cascade_samples(fixtures: dict) -> list[dict]:
    return fixtures["cascade_samples"]


@pytest.fixture
def permission_samples(fixtures: dict) -> list[dict]:
    return fixtures["permission_prompt_samples"]


@pytest.fixture
def non_cascade_samples(fixtures: dict) -> list[dict]:
    return fixtures["non_cascade_samples"]


@pytest.fixture
def edge_case_samples(fixtures: dict) -> list[dict]:
    return fixtures["edge_case_samples"]


# ── T010: Continuation offer detection ──


class TestContinuationOfferDetection:
    """T010: Detect 'Should I continue with the next issue?' (REQ-1)."""

    def test_should_i_continue(self) -> None:
        result = detect_cascade_risk(
            "Great, issue #42 is fixed! Should I continue with issue #43?"
        )
        assert result["detected"] is True
        assert result["risk_level"] in (
            CascadeRiskLevel.MEDIUM,
            CascadeRiskLevel.HIGH,
            CascadeRiskLevel.CRITICAL,
        )
        assert result["recommended_action"] != "allow"
        assert len(result["matched_patterns"]) > 0

    def test_do_you_want_me_to_proceed(self) -> None:
        result = detect_cascade_risk("Do you want me to proceed with the next task?")
        assert result["matched_patterns"]  # At least one pattern matches
        assert "CP-002" in result["matched_patterns"]


# ── T020: Numbered choice with completion ──


class TestNumberedChoiceDetection:
    """T020: Detect '1. Yes 2. No' numbered choice after task completion (REQ-1)."""

    def test_numbered_yes_no_with_completion(self) -> None:
        result = detect_cascade_risk(
            "Done! What's next?\n1. Yes, start issue #44\n2. No, stop here"
        )
        assert result["detected"] is True
        assert result["risk_level"] == CascadeRiskLevel.CRITICAL
        assert result["recommended_action"] == "block_and_alert"


# ── T030: Permission prompt passthrough ──


class TestPermissionPromptPassthrough:
    """T030: Allow legitimate permission prompt (REQ-3)."""

    def test_bash_permission_prompt(self) -> None:
        result = detect_cascade_risk(
            "Allow bash command: git push origin main? (y/n)"
        )
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE
        assert result["recommended_action"] == "allow"

    def test_file_write_permission_prompt(self) -> None:
        result = detect_cascade_risk("Allow file write: /src/main.py? (y/n)")
        assert result["detected"] is False
        assert result["recommended_action"] == "allow"

    def test_is_permission_prompt_bash(self) -> None:
        assert is_permission_prompt("Allow bash command: git push origin main? (y/n)") is True

    def test_is_permission_prompt_file_write(self) -> None:
        assert is_permission_prompt("Allow file write: /src/main.py? (y/n)") is True

    def test_is_permission_prompt_read_tool(self) -> None:
        assert is_permission_prompt("Allow Read tool to read file: src/config.json?") is True

    def test_is_not_permission_prompt(self) -> None:
        assert is_permission_prompt("Should I continue with the next issue?") is False

    def test_is_permission_prompt_empty(self) -> None:
        assert is_permission_prompt("") is False


# ── T040: Task completion pivot ──


class TestTaskCompletionPivot:
    """T040: Detect 'I finished X. Should I do Y?' pivot (REQ-1)."""

    def test_completion_pivot(self) -> None:
        result = detect_cascade_risk(
            "I've completed the refactor. Now let me also update the tests for the new module."
        )
        assert result["detected"] is True
        assert result["risk_level"] in (
            CascadeRiskLevel.MEDIUM,
            CascadeRiskLevel.HIGH,
            CascadeRiskLevel.CRITICAL,
        )


# ── T050: Scope expansion ──


class TestScopeExpansion:
    """T050: Detect 'While I'm at it, I could also...' (REQ-1)."""

    def test_scope_expansion(self) -> None:
        result = detect_cascade_risk(
            "While I'm at it, I could also fix the related CSS issue in the sidebar."
        )
        assert result["detected"] is True
        assert result["risk_level"] in (
            CascadeRiskLevel.MEDIUM,
            CascadeRiskLevel.HIGH,
            CascadeRiskLevel.CRITICAL,
        )


# ── T060: Empty input ──


class TestEmptyInput:
    """T060: Handle empty/None model output gracefully (REQ-1)."""

    def test_empty_string(self) -> None:
        result = detect_cascade_risk("")
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE
        assert result["recommended_action"] == "allow"

    def test_none_input(self) -> None:
        # Type ignore since we're testing robustness
        result = detect_cascade_risk(None)  # type: ignore[arg-type]
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE


# ── T080: ReDoS resistance ──


class TestReDoSResistance:
    """T080: Pathological input completes fast (REQ-6)."""

    def test_redos_resistance(self) -> None:
        # Pathological input: lots of repetitive characters
        adversarial = "a" * 10000 + " Should I " + "b" * 10000
        adversarial = adversarial[:MAX_INPUT_LENGTH]  # Respect cap

        start = time.perf_counter()
        result = detect_cascade_risk(adversarial)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"ReDoS: detection took {elapsed:.3f}s (limit: 0.1s)"

    def test_redos_with_nested_quantifiers(self) -> None:
        """Ensure patterns don't cause catastrophic backtracking."""
        adversarial = "Should I " * 500 + "continue"
        adversarial = adversarial[:MAX_INPUT_LENGTH]

        start = time.perf_counter()
        _ = detect_cascade_risk(adversarial)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"ReDoS: detection took {elapsed:.3f}s (limit: 0.1s)"


# ── T110: Below threshold allow ──


class TestBelowThresholdAllow:
    """T110: Below-threshold score results in allow (REQ-1)."""

    def test_single_weak_match_below_threshold(self) -> None:
        # "Should I format this differently?" — matches CP-001 "should I" but
        # as a legitimate question. However, our regex checks "should I (continue|proceed|start|begin|move on)"
        # so this should NOT match at all.
        result = detect_cascade_risk("Should I format this differently?")
        assert result["recommended_action"] == "allow"

    def test_low_risk_single_category(self) -> None:
        # A single continuation_offer match with weight 0.5
        # Score = 0.5, which is below default threshold 0.6
        result = detect_cascade_risk("Ready to move on?")
        assert result["risk_level"] in (CascadeRiskLevel.NONE, CascadeRiskLevel.LOW)
        assert result["recommended_action"] == "allow"


# ── T120: Multi-category compounding ──


class TestMultiCategoryCompounding:
    """T120: Multi-category match produces higher score (REQ-1)."""

    def test_multi_category_higher_than_single(self) -> None:
        # Single category match
        single_result = detect_cascade_risk("Should I continue?")
        single_score = single_result["confidence"]

        # Multi-category match: continuation + task completion pivot + numbered
        multi_text = (
            "I've fixed issue #42. Should I start on issue #43?\n"
            "1. Yes, proceed\n"
            "2. No, stop here"
        )
        multi_result = detect_cascade_risk(multi_text)
        multi_score = multi_result["confidence"]

        assert multi_score > single_score, (
            f"Multi-category score ({multi_score}) should exceed "
            f"single-category score ({single_score})"
        )


# ── T200/T210: Performance latency ──


class TestDetectionLatency:
    """T200/T210: Detection completes under 5ms (REQ-6)."""

    def test_typical_input_latency(self) -> None:
        """T200: 2000-char model output."""
        text = "Here is a summary of the changes I made. " * 50  # ~2050 chars
        text = text[:2000]

        total = 0.0
        runs = 100
        for _ in range(runs):
            start = time.perf_counter()
            detect_cascade_risk(text)
            total += time.perf_counter() - start

        avg = total / runs
        assert avg < 0.005, f"Average detection time {avg*1000:.2f}ms exceeds 5ms limit"

    def test_max_input_latency(self) -> None:
        """T210: 10000-char model output (max cap)."""
        text = "Model output content with various words. " * 250  # ~10000 chars
        text = text[:10000]

        total = 0.0
        runs = 100
        for _ in range(runs):
            start = time.perf_counter()
            detect_cascade_risk(text)
            total += time.perf_counter() - start

        avg = total / runs
        assert avg < 0.005, f"Average detection time {avg*1000:.2f}ms exceeds 5ms limit"


# ── T220: Gemini-style cascade ──


class TestGeminiStyleCascade:
    """T220: Detects Gemini-style cascade output (REQ-1)."""

    def test_gemini_cascade(self) -> None:
        result = detect_cascade_risk(
            "I solved issue 1. Should I do issue 2?\n1. Yes\n2. No"
        )
        assert result["detected"] is True
        assert result["risk_level"] == CascadeRiskLevel.CRITICAL


# ── T230: Code output passthrough ──


class TestCodeOutputPassthrough:
    """T230: Code containing pattern keywords is NOT flagged (REQ-3)."""

    def test_code_not_flagged(self) -> None:
        result = detect_cascade_risk("def should_i_continue(): return True")
        assert result["detected"] is False


# ── T240: Legitimate question passthrough ──


class TestLegitimateQuestionPassthrough:
    """T240: Technical questions not flagged (REQ-3)."""

    def test_technical_question_not_flagged(self) -> None:
        result = detect_cascade_risk(
            "Should I use async or sync for this function?"
        )
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE


# ── T250: File write permission passthrough ──


class TestFileWritePermission:
    """T250: File write permission prompt not flagged (REQ-3)."""

    def test_file_write_not_flagged(self) -> None:
        result = detect_cascade_risk("Allow file write: /src/main.py? (y/n)")
        assert result["detected"] is False
        assert is_permission_prompt("Allow file write: /src/main.py? (y/n)") is True


# ── Compute risk score direct tests ──


class TestComputeRiskScore:
    """Direct tests for compute_risk_score function."""

    def test_empty_matches(self) -> None:
        score, level = compute_risk_score([])
        assert score == 0.0
        assert level == CascadeRiskLevel.NONE

    def test_single_category_max(self) -> None:
        """Same category, different weights → takes max."""
        match = re.search(r"test", "test")
        assert match is not None
        patterns_matches = [
            (
                {"id": "CP-001", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.7, "examples": []},
                match,
            ),
            (
                {"id": "CP-002", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.5, "examples": []},
                match,
            ),
        ]
        score, _level = compute_risk_score(patterns_matches)  # type: ignore[arg-type]
        assert score == pytest.approx(0.7, abs=0.01)

    def test_multi_category_sum(self) -> None:
        """Different categories sum their max weights."""
        match = re.search(r"test", "test")
        assert match is not None
        patterns_matches = [
            (
                {"id": "CP-001", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.7, "examples": []},
                match,
            ),
            (
                {"id": "CP-020", "category": "task_completion_pivot", "regex": "test", "description": "", "risk_weight": 0.8, "examples": []},
                match,
            ),
        ]
        score, _level = compute_risk_score(patterns_matches)  # type: ignore[arg-type]
        assert score == pytest.approx(1.0, abs=0.01)  # 0.7 + 0.8 = 1.5 → capped at 1.0

    def test_score_capped_at_one(self) -> None:
        match = re.search(r"test", "test")
        assert match is not None
        patterns_matches = [
            ({"id": "CP-001", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.7, "examples": []}, match),
            ({"id": "CP-020", "category": "task_completion_pivot", "regex": "test", "description": "", "risk_weight": 0.8, "examples": []}, match),
            ({"id": "CP-010", "category": "numbered_choice", "regex": "test", "description": "", "risk_weight": 0.5, "examples": []}, match),
        ]
        score, level = compute_risk_score(patterns_matches)  # type: ignore[arg-type]
        assert score == 1.0
        assert level == CascadeRiskLevel.CRITICAL


# ── Pattern loading tests ──


class TestPatternLoading:
    """T070, T100, T180, T190: Pattern loading and merging."""

    def test_default_patterns_count(self) -> None:
        """Default patterns should have at least 15 entries."""
        patterns = load_default_patterns()
        assert len(patterns) >= 15

    def test_default_patterns_have_required_fields(self) -> None:
        patterns = load_default_patterns()
        for p in patterns:
            assert "id" in p
            assert "category" in p
            assert "regex" in p
            assert "description" in p
            assert "risk_weight" in p

    def test_default_patterns_compile(self) -> None:
        """All default patterns must compile without error."""
        patterns = load_default_patterns()
        for p in patterns:
            try:
                re.compile(p["regex"])
            except re.error as exc:
                pytest.fail(f"Pattern {p['id']} has invalid regex: {exc}")

    def test_corrupt_config_fallback(self, tmp_path: Path) -> None:
        """T070: Corrupt config falls back gracefully (REQ-8)."""
        corrupt_file = tmp_path / "cascade_block_patterns.json"
        corrupt_file.write_text("{invalid json!!!", encoding="utf-8")

        user_patterns = load_user_patterns(config_path=corrupt_file)
        assert user_patterns == []

        # Verify defaults still work
        defaults = load_default_patterns()
        assert len(defaults) >= 15

    def test_merge_override_by_id(self) -> None:
        """T100/T190: User pattern overrides default by ID (REQ-5)."""
        defaults: list[CascadePattern] = [
            {"id": "CP-001", "category": "continuation_offer", "regex": r"regex_a", "description": "default", "risk_weight": 0.7, "examples": []},
            {"id": "CP-010", "category": "numbered_choice", "regex": r"regex_b", "description": "default", "risk_weight": 0.5, "examples": []},
        ]
        overrides: list[CascadePattern] = [
            {"id": "CP-001", "category": "continuation_offer", "regex": r"regex_override", "description": "user override", "risk_weight": 0.8, "examples": []},
            {"id": "CP-100", "category": "scope_expansion", "regex": r"regex_new", "description": "new user", "risk_weight": 0.6, "examples": []},
        ]
        merged = merge_patterns(defaults, overrides)

        merged_map = {p["id"]: p for p in merged}
        assert merged_map["CP-001"]["regex"] == r"regex_override"
        assert merged_map["CP-001"]["risk_weight"] == 0.8
        assert merged_map["CP-010"]["regex"] == r"regex_b"
        assert "CP-100" in merged_map
        assert len(merged) == 3

    def test_user_patterns_from_json(self, tmp_path: Path) -> None:
        """T180: User patterns loaded from JSON config (REQ-5)."""
        config = {
            "version": "1.0",
            "enabled": True,
            "patterns": [
                {
                    "id": "CP-100",
                    "category": "continuation_offer",
                    "regex": r"(?i)want me to tackle the next",
                    "description": "Custom pattern",
                    "risk_weight": 0.7,
                    "examples": ["Want me to tackle the next issue?"],
                },
                {
                    "id": "CP-101",
                    "category": "scope_expansion",
                    "regex": r"(?i)I could additionally",
                    "description": "Custom expansion",
                    "risk_weight": 0.5,
                    "examples": [],
                },
            ],
            "risk_threshold": 0.6,
            "alert_on_block": True,
            "log_all_checks": False,
        }
        config_path = tmp_path / "cascade_block_patterns.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        user = load_user_patterns(config_path=config_path)
        assert len(user) == 2
        user_ids = {p["id"] for p in user}
        assert "CP-100" in user_ids
        assert "CP-101" in user_ids

    def test_disabled_config_returns_empty(self, tmp_path: Path) -> None:
        config = {"version": "1.0", "enabled": False, "patterns": [{"id": "CP-100", "category": "continuation_offer", "regex": "test", "description": "test", "risk_weight": 0.5}]}
        config_path = tmp_path / "cascade_block_patterns.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        user = load_user_patterns(config_path=config_path)
        assert user == []

    def test_missing_config_returns_empty(self, tmp_path: Path) -> None:
        user = load_user_patterns(config_path=tmp_path / "nonexistent.json")
        assert user == []


# ── Fixture-driven comprehensive tests ──


class TestFixtureSamples:
    """Run detection against all fixture samples."""

    def test_all_cascade_samples_detected(self, cascade_samples: list[dict]) -> None:
        for sample in cascade_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] is True, (
                f"Sample {sample['id']} ({sample['category']}) should be detected as cascade "
                f"but got detected={result['detected']}, risk={result['risk_level']}"
            )

    def test_all_permission_prompts_allowed(self, permission_samples: list[dict]) -> None:
        for sample in permission_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] is False, (
                f"Permission prompt {sample['id']} ({sample['category']}) should NOT be detected "
                f"but got detected={result['detected']}, patterns={result['matched_patterns']}"
            )

    def test_all_non_cascade_samples_allowed(self, non_cascade_samples: list[dict]) -> None:
        for sample in non_cascade_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] is False, (
                f"Non-cascade sample {sample['id']} ({sample['category']}) should NOT be detected "
                f"but got detected={result['detected']}, patterns={result['matched_patterns']}"
            )

    def test_edge_cases_detected(self, edge_case_samples: list[dict]) -> None:
        for sample in edge_case_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] == sample["expected_detected"], (
                f"Edge case {sample['id']} ({sample['category']}) expected "
                f"detected={sample['expected_detected']} but got {result['detected']}"
            )
```

### 6.12 `tests/unit/test_cascade_action.py` (Add)

**Complete file contents:**

```python
"""Unit tests for cascade action handlers.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T130, T150, T160
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.hooks.cascade_action import (
    format_block_message,
    handle_cascade_detection,
)
from assemblyzero.hooks.cascade_detector import (
    CascadeDetectionResult,
    CascadeRiskLevel,
)


# ── T130: Block message formatting ──


class TestFormatBlockMessage:
    """T130: format_block_message produces readable output (REQ-2)."""

    def test_contains_required_elements(self) -> None:
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.HIGH,
            "matched_patterns": ["CP-001", "CP-020"],
            "matched_text": "Should I continue with issue #43?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.85,
        }
        message = format_block_message(result)

        assert "CASCADE" in message.upper() or "cascade" in message.lower()
        assert "HIGH" in message
        assert "CP-001" in message
        assert "CP-020" in message
        assert "manual input" in message.lower() or "decide" in message.lower()
        assert "Should I continue" in message

    def test_truncates_long_matched_text(self) -> None:
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": ["CP-031"],
            "matched_text": "x" * 200,
            "recommended_action": "block_and_prompt",
            "confidence": 0.6,
        }
        message = format_block_message(result)
        assert "..." in message

    def test_handles_empty_patterns(self) -> None:
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": [],
            "matched_text": "",
            "recommended_action": "block_and_prompt",
            "confidence": 0.6,
        }
        message = format_block_message(result)
        assert "unknown" in message


# ── T150: Hook exit codes (tested via handle_cascade_detection return) ──


class TestHandleCascadeDetection:
    """T150/T160: handle_cascade_detection returns correct values (REQ-2)."""

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event")
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_allow_returns_true(self, mock_create: object, mock_log: object) -> None:
        result: CascadeDetectionResult = {
            "detected": False,
            "risk_level": CascadeRiskLevel.NONE,
            "matched_patterns": [],
            "matched_text": "",
            "recommended_action": "allow",
            "confidence": 0.0,
        }
        assert handle_cascade_detection(result, "sess-123", "clean output") is True

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event")
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_block_and_prompt_returns_false(self, mock_create: object, mock_log: object) -> None:
        """T160: Auto-approve blocked on MEDIUM risk (REQ-2)."""
        mock_create.return_value = {  # type: ignore[union-attr]
            "timestamp": "2026-02-25T00:00:00+00:00",
            "event_type": "cascade_risk",
            "risk_level": "medium",
            "action_taken": "blocked",
            "matched_patterns": ["CP-031"],
            "model_output_snippet": "test",
            "session_id": "sess-123",
            "auto_approve_blocked": True,
        }
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": ["CP-031"],
            "matched_text": "should I fix those too?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.65,
        }
        assert handle_cascade_detection(result, "sess-123", "model output") is False

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event")
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_block_and_alert_returns_false(self, mock_create: object, mock_log: object) -> None:
        mock_create.return_value = {  # type: ignore[union-attr]
            "timestamp": "2026-02-25T00:00:00+00:00",
            "event_type": "cascade_risk",
            "risk_level": "critical",
            "action_taken": "alerted",
            "matched_patterns": ["CP-001", "CP-020", "CP-010"],
            "model_output_snippet": "test",
            "session_id": "sess-123",
            "auto_approve_blocked": True,
        }
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.CRITICAL,
            "matched_patterns": ["CP-001", "CP-020", "CP-010"],
            "matched_text": "Should I continue?",
            "recommended_action": "block_and_alert",
            "confidence": 1.0,
        }
        assert handle_cascade_detection(result, "sess-123", "model output") is False

    @patch("assemblyzero.hooks.cascade_action.log_cascade_event", side_effect=Exception("disk full"))
    @patch("assemblyzero.hooks.cascade_action.create_cascade_event")
    def test_telemetry_failure_still_blocks(self, mock_create: object, mock_log: object) -> None:
        """Telemetry failure must not prevent blocking."""
        mock_create.return_value = {  # type: ignore[union-attr]
            "timestamp": "2026-02-25T00:00:00+00:00",
            "event_type": "cascade_risk",
            "risk_level": "high",
            "action_taken": "blocked",
            "matched_patterns": ["CP-001"],
            "model_output_snippet": "test",
            "session_id": "sess-123",
            "auto_approve_blocked": True,
        }
        result: CascadeDetectionResult = {
            "detected": True,
            "risk_level": CascadeRiskLevel.HIGH,
            "matched_patterns": ["CP-001"],
            "matched_text": "Should I continue?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.75,
        }
        # Should still return False even though logging failed
        assert handle_cascade_detection(result, "sess-123", "model output") is False
```

### 6.13 `tests/unit/test_cascade_events.py` (Add)

**Complete file contents:**

```python
"""Unit tests for cascade telemetry events.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T090, T140, T170
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from assemblyzero.hooks.cascade_detector import CascadeRiskLevel
from assemblyzero.telemetry.cascade_events import (
    CascadeEvent,
    create_cascade_event,
    get_cascade_stats,
    log_cascade_event,
)


# ── T090: Event logging structure ──


class TestLogCascadeEvent:
    """T090: Valid JSONL with all CascadeEvent fields (REQ-4)."""

    def test_writes_valid_jsonl(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        event: CascadeEvent = {
            "timestamp": "2026-02-25T14:32:07.123456+00:00",
            "event_type": "cascade_risk",
            "risk_level": "high",
            "action_taken": "blocked",
            "matched_patterns": ["CP-001", "CP-020"],
            "model_output_snippet": "I've fixed issue #42. Should I continue?",
            "session_id": "sess_abc123",
            "auto_approve_blocked": True,
        }
        log_cascade_event(event, log_path=log_file)

        content = log_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        assert parsed["event_type"] == "cascade_risk"
        assert parsed["risk_level"] == "high"
        assert parsed["action_taken"] == "blocked"
        assert parsed["matched_patterns"] == ["CP-001", "CP-020"]
        assert parsed["session_id"] == "sess_abc123"
        assert parsed["auto_approve_blocked"] is True
        assert len(parsed["model_output_snippet"]) <= 200

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        for i in range(3):
            event: CascadeEvent = {
                "timestamp": f"2026-02-25T14:32:0{i}.000000+00:00",
                "event_type": "cascade_risk",
                "risk_level": "medium",
                "action_taken": "blocked",
                "matched_patterns": [f"CP-{i:03d}"],
                "model_output_snippet": f"Sample {i}",
                "session_id": "sess_test",
                "auto_approve_blocked": True,
            }
            log_cascade_event(event, log_path=log_file)

        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        log_file = tmp_path / "subdir" / "deep" / "cascade-events.jsonl"
        event: CascadeEvent = {
            "timestamp": "2026-02-25T14:32:07.000000+00:00",
            "event_type": "cascade_risk",
            "risk_level": "low",
            "action_taken": "allowed",
            "matched_patterns": [],
            "model_output_snippet": "",
            "session_id": "sess_test",
            "auto_approve_blocked": False,
        }
        log_cascade_event(event, log_path=log_file)
        assert log_file.exists()


# ── T170: Cascade event field completeness ──


class TestCreateCascadeEvent:
    """T170: Create event with all required fields (REQ-4)."""

    def test_all_fields_present(self) -> None:
        result = {
            "detected": True,
            "risk_level": CascadeRiskLevel.HIGH,
            "matched_patterns": ["CP-001", "CP-020"],
            "matched_text": "Should I continue?",
            "recommended_action": "block_and_prompt",
            "confidence": 0.85,
        }
        event = create_cascade_event(
            result=result,  # type: ignore[arg-type]
            session_id="sess_abc123",
            model_output="I've fixed issue #42. Should I continue with issue #43?",
            action_taken="blocked",
        )

        # Verify all 8 required fields
        assert "timestamp" in event
        # Verify timestamp is valid ISO 8601
        datetime.fromisoformat(event["timestamp"])

        assert event["event_type"] == "cascade_risk"
        assert event["risk_level"] == "high"
        assert event["action_taken"] == "blocked"
        assert event["matched_patterns"] == ["CP-001", "CP-020"]
        assert isinstance(event["model_output_snippet"], str)
        assert len(event["model_output_snippet"]) <= 200
        assert event["session_id"] == "sess_abc123"
        assert event["auto_approve_blocked"] is True

    def test_truncates_long_output(self) -> None:
        result = {
            "detected": True,
            "risk_level": CascadeRiskLevel.MEDIUM,
            "matched_patterns": ["CP-030"],
            "matched_text": "test",
            "recommended_action": "block_and_prompt",
            "confidence": 0.6,
        }
        long_output = "x" * 500
        event = create_cascade_event(
            result=result,  # type: ignore[arg-type]
            session_id="sess_test",
            model_output=long_output,
            action_taken="blocked",
        )
        assert len(event["model_output_snippet"]) == 200

    def test_risk_level_enum_to_string(self) -> None:
        result = {
            "detected": False,
            "risk_level": CascadeRiskLevel.NONE,
            "matched_patterns": [],
            "matched_text": "",
            "recommended_action": "allow",
            "confidence": 0.0,
        }
        event = create_cascade_event(
            result=result,  # type: ignore[arg-type]
            session_id="sess_test",
            model_output="clean output",
            action_taken="allowed",
        )
        assert event["risk_level"] == "none"
        assert isinstance(event["risk_level"], str)


# ── T140: Stats calculation ──


class TestGetCascadeStats:
    """T140: get_cascade_stats returns correct counts (REQ-4)."""

    def test_correct_counts(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        now = datetime.now(timezone.utc)

        # Write 5 events: 3 blocked, 2 allowed
        events = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=2)).isoformat(), "event_type": "cascade_risk", "risk_level": "medium", "action_taken": "blocked", "matched_patterns": ["CP-030"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=3)).isoformat(), "event_type": "cascade_risk", "risk_level": "critical", "action_taken": "alerted", "matched_patterns": ["CP-001", "CP-010"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=4)).isoformat(), "event_type": "cascade_risk", "risk_level": "none", "action_taken": "allowed", "matched_patterns": [], "model_output_snippet": "clean", "session_id": "s1", "auto_approve_blocked": False},
            {"timestamp": (now - timedelta(hours=5)).isoformat(), "event_type": "cascade_risk", "risk_level": "low", "action_taken": "allowed", "matched_patterns": [], "model_output_snippet": "clean", "session_id": "s1", "auto_approve_blocked": False},
        ]
        with log_file.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        stats = get_cascade_stats(log_path=log_file, since_hours=24)
        assert stats["total_checks"] == 5
        assert stats["detections"] == 3
        assert stats["blocks"] == 3
        assert stats["allowed"] == 2

    def test_time_filter(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        now = datetime.now(timezone.utc)

        events = [
            {"timestamp": (now - timedelta(hours=1)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
            {"timestamp": (now - timedelta(hours=48)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True},
        ]
        with log_file.open("w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

        stats = get_cascade_stats(log_path=log_file, since_hours=24)
        assert stats["total_checks"] == 1  # Only the recent one

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        stats = get_cascade_stats(log_path=tmp_path / "nonexistent.jsonl")
        assert stats == {"total_checks": 0, "detections": 0, "blocks": 0, "allowed": 0}

    def test_corrupt_lines_skipped(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cascade-events.jsonl"
        now = datetime.now(timezone.utc)

        with log_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": (now - timedelta(hours=1)).isoformat(), "event_type": "cascade_risk", "risk_level": "high", "action_taken": "blocked", "matched_patterns": ["CP-001"], "model_output_snippet": "test", "session_id": "s1", "auto_approve_blocked": True}) + "\n")
            f.write("THIS IS NOT JSON\n")
            f.write(json.dumps({"timestamp": (now - timedelta(hours=2)).isoformat(), "event_type": "cascade_risk", "risk_level": "none", "action_taken": "allowed", "matched_patterns": [], "model_output_snippet": "clean", "session_id": "s1", "auto_approve_blocked": False}) + "\n")

        stats = get_cascade_stats(log_path=log_file, since_hours=24)
        assert stats["total_checks"] == 2  # Corrupt line skipped
```

### 6.14 `tests/integration/test_cascade_hook_integration.py` (Add)

**Complete file contents:**

```python
"""Integration tests for the full cascade hook pipeline.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T150 (hook exit codes), T260, T270, T280 (CLAUDE.md validation)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Validation utility ──


def validate_claude_md_cascade_rule(
    claude_md_path: str | Path,
) -> dict[str, bool]:
    """Validate that CLAUDE.md contains the required cascade prevention rule.

    Checks that the CLAUDE.md file includes an explicit instruction
    directing models to ask open-ended questions after task completion
    instead of offering numbered yes/no options.

    Args:
        claude_md_path: Path to the CLAUDE.md file.

    Returns:
        Dict with validation results.
    """
    result = {
        "rule_present": False,
        "contains_open_ended": False,
        "forbids_numbered_options": False,
        "section_correct": False,
    }

    path = Path(claude_md_path)
    if not path.exists():
        return result

    content = path.read_text(encoding="utf-8")
    content_lower = content.lower()

    # Check rule is present — look for cascade prevention section
    cascade_section_patterns = [
        r"##\s+cascade\s+prevention",
        r"##\s+.*task\s+completion\s+behavior",
        r"cascade\s+prevention",
    ]
    for pattern in cascade_section_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            result["rule_present"] = True
            break

    if not result["rule_present"]:
        return result

    # Check for open-ended phrasing
    open_ended_patterns = [
        r"what would you like",
        r"what would you like to work on",
        r"open-ended\s+question",
        r"open.ended",
    ]
    for pattern in open_ended_patterns:
        if re.search(pattern, content_lower):
            result["contains_open_ended"] = True
            break

    # Check for prohibition of numbered options
    forbid_patterns = [
        r"never\b.*numbered",
        r"never\b.*yes/no",
        r"never\b.*offer.*numbered",
        r"do\s+not\b.*numbered",
        r"do\s+not\b.*yes/no",
    ]
    for pattern in forbid_patterns:
        if re.search(pattern, content_lower):
            result["forbids_numbered_options"] = True
            break

    # Check section placement — should be a top-level ## section
    # Find where the cascade rule appears
    cascade_match = re.search(r"(##\s+cascade\s+prevention|##\s+.*task\s+completion)", content, re.IGNORECASE)
    if cascade_match:
        # Verify it's a top-level section (## not ###)
        line = cascade_match.group(0)
        if line.startswith("## ") and not line.startswith("### "):
            result["section_correct"] = True

    return result


# ── T260: CLAUDE.md contains cascade prevention rule ──


class TestClaudeMdCascadeRule:
    """T260/T270/T280: CLAUDE.md cascade prevention rule (REQ-7)."""

    def test_rule_present(self) -> None:
        """T260: CLAUDE.md contains cascade prevention rule."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["rule_present"] is True, (
            "CLAUDE.md must contain a cascade prevention rule. "
            "Expected a section header containing 'Cascade Prevention' or 'Task Completion Behavior'."
        )

    def test_open_ended_phrasing(self) -> None:
        """T270: CLAUDE.md rule uses open-ended phrasing."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["contains_open_ended"] is True, (
            "CLAUDE.md cascade rule must contain open-ended phrasing like "
            "'What would you like to work on next?' or reference 'open-ended question'."
        )

    def test_forbids_numbered_options(self) -> None:
        """T270: CLAUDE.md rule forbids numbered yes/no options."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["forbids_numbered_options"] is True, (
            "CLAUDE.md cascade rule must explicitly forbid numbered yes/no options "
            "for deciding next steps."
        )

    def test_section_correct(self) -> None:
        """T280: CLAUDE.md rule is in correct section."""
        result = validate_claude_md_cascade_rule("CLAUDE.md")
        assert result["section_correct"] is True, (
            "CLAUDE.md cascade rule must be in a top-level ## section "
            "(not nested under ###)."
        )


# ── T150: Hook exit codes ──


class TestHookExitCodes:
    """T150: Hook main() exits with correct code based on detection."""

    def test_hook_allows_clean_output(self) -> None:
        """Clean model output → exit(0)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "echo hello"},
            "tool_output": "hello\n",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_hook_blocks_cascade_output(self) -> None:
        """Cascade model output → exit(2)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "fix issue"},
            "tool_output": "I've fixed issue #42. Should I continue with issue #43?\n1. Yes, proceed\n2. No, stop here",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 2

    def test_hook_allows_empty_output(self) -> None:
        """Empty model output → exit(0)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "true"},
            "tool_output": "",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_hook_allows_permission_prompt(self) -> None:
        """Permission prompt → exit(0)."""
        hook_input = json.dumps({
            "tool_name": "bash",
            "tool_input": {"command": "git push"},
            "tool_output": "Allow bash command: git push origin main? (y/n)",
        })
        result = subprocess.run(
            [sys.executable, ".claude/hooks/post_output_cascade_check.py"],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


# ── Full pipeline integration test ──


class TestFullPipeline:
    """Integration test: detection → action → telemetry."""

    def test_end_to_end_block(self, tmp_path: Path) -> None:
        """Full pipeline: cascade input → detection → block → log event."""
        from assemblyzero.hooks.cascade_detector import detect_cascade_risk
        from assemblyzero.hooks.cascade_action import handle_cascade_detection
        from assemblyzero.telemetry.cascade_events import get_cascade_stats, log_cascade_event, create_cascade_event

        log_file = tmp_path / "cascade-events.jsonl"
        model_output = "I've fixed issue #42. Should I continue with issue #43?\n1. Yes, proceed\n2. No, stop here"

        # Step 1: Detect
        result = detect_cascade_risk(model_output)
        assert result["detected"] is True
        assert result["risk_level"] in (CascadeRiskLevel.HIGH, CascadeRiskLevel.CRITICAL)

        # Step 2: Create and log event
        event = create_cascade_event(
            result=result,
            session_id="integration-test-sess",
            model_output=model_output,
            action_taken="blocked",
        )
        log_cascade_event(event, log_path=log_file)

        # Step 3: Verify telemetry
        stats = get_cascade_stats(log_path=log_file, since_hours=1)
        assert stats["total_checks"] == 1
        assert stats["blocks"] == 1

        # Step 4: Verify logged event structure
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        parsed = json.loads(lines[0])
        assert parsed["event_type"] == "cascade_risk"
        assert parsed["auto_approve_blocked"] is True
        assert parsed["session_id"] == "integration-test-sess"

    def test_end_to_end_allow(self, tmp_path: Path) -> None:
        """Full pipeline: clean input → detection → allow."""
        from assemblyzero.hooks.cascade_detector import detect_cascade_risk
        from assemblyzero.hooks.cascade_action import handle_cascade_detection

        model_output = "I've updated the file. Here are the changes:\n- Added error handling\n- Updated tests"

        result = detect_cascade_risk(model_output)
        assert result["detected"] is False
        assert result["recommended_action"] == "allow"

        should_allow = handle_cascade_detection(
            result=result,
            session_id="integration-test-sess",
            model_output=model_output,
        )
        assert should_allow is True
```

## 7. Pattern References

### 7.1 Existing Test Structure

**File:** `tests/test_integration_workflow.py` (lines 1-80)

```python
# This test file demonstrates the project's test pattern:
# - pytest-based
# - fixtures loaded via pytest fixtures
# - class-based test grouping
# - descriptive test method names with test_ prefix
```

**Relevance:** Follow the same test organization pattern — pytest, class-based grouping, descriptive names. The cascade tests use the same structure.

### 7.2 Existing Telemetry Module Pattern

**File:** `assemblyzero/telemetry/__init__.py` (lines 1-19)

```python
"""AssemblyZero telemetry — structured event emission.

Fire-and-forget telemetry that never raises, never blocks tool execution.
"""

from assemblyzero.telemetry.emitter import emit, flush, track_tool

__all__ = ["emit", "flush", "track_tool"]
```

**Relevance:** The cascade_events module follows the same "fire-and-forget, never raises" pattern. The `__init__.py` export style is the model for adding cascade exports.

### 7.3 Existing Hooks Module

**File:** `assemblyzero/hooks/__init__.py` (line 1)

```python
"""Hooks for workflow validation and enforcement."""
```

**Relevance:** Currently minimal. The cascade detector is the first significant addition to this module. Follow the same docstring convention.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from __future__ import annotations` | stdlib | All new Python files |
| `import re` | stdlib | `cascade_detector.py`, `cascade_patterns.py` |
| `import json` | stdlib | `cascade_patterns.py`, `cascade_events.py`, `post_output_cascade_check.py` |
| `import logging` | stdlib | `cascade_patterns.py`, `cascade_events.py` |
| `import sys` | stdlib | `cascade_action.py`, `cascade_events.py`, `post_output_cascade_check.py` |
| `import os` | stdlib | `post_output_cascade_check.py` |
| `import time` | stdlib | `test_cascade_detector.py` (performance tests) |
| `import subprocess` | stdlib | `test_cascade_hook_integration.py` |
| `from enum import Enum` | stdlib | `cascade_detector.py` |
| `from pathlib import Path` | stdlib | `cascade_patterns.py`, `cascade_events.py` |
| `from datetime import datetime, timedelta, timezone` | stdlib | `cascade_events.py` |
| `from typing import Literal, TypedDict` | stdlib | All new modules |
| `import pytest` | dev dependency (existing) | All test files |
| `from unittest.mock import patch` | stdlib | `test_cascade_action.py` |
| `from assemblyzero.hooks.cascade_patterns import ...` | internal | `cascade_detector.py` |
| `from assemblyzero.hooks.cascade_detector import ...` | internal | `cascade_action.py`, `cascade_events.py` |
| `from assemblyzero.telemetry.cascade_events import ...` | internal | `cascade_action.py` |

**New Dependencies:** None. All stdlib + existing dev dependencies (pytest).

## 9. Test Mapping

| Test ID | Tests Function(s) | Input | Expected Output |
|---------|-------------------|-------|-----------------|
| T010 | `detect_cascade_risk()` | `"Great, issue #42 is fixed! Should I continue with issue #43?"` | `detected=True, risk_level>=MEDIUM` |
| T020 | `detect_cascade_risk()` | `"Done! What's next?\n1. Yes, start issue #44\n2. No, stop here"` | `risk_level=CRITICAL, action=block_and_alert` |
| T030 | `detect_cascade_risk()`, `is_permission_prompt()` | `"Allow bash command: git push origin main? (y/n)"` | `detected=False, action=allow` |
| T040 | `detect_cascade_risk()` | `"I've completed the refactor. Now let me also update the tests..."` | `detected=True, risk_level>=MEDIUM` |
| T050 | `detect_cascade_risk()` | `"While I'm at it, I could also fix the related CSS issue..."` | `detected=True, risk_level>=MEDIUM` |
| T060 | `detect_cascade_risk()` | `""` and `None` | `detected=False, risk_level=NONE` |
| T070 | `load_user_patterns()`, `load_default_patterns()` | Corrupt JSON file | Empty user patterns, 15+ defaults, no crash |
| T080 | `detect_cascade_risk()` | `"a"*10000 + " Should I " + "b"*10000` | Completes in <100ms |
| T090 | `log_cascade_event()` | Valid CascadeEvent | JSONL file with all fields |
| T100 | `merge_patterns()` | Default CP-001 + user CP-001 | User regex used |
| T110 | `detect_cascade_risk()` | `"Should I format this differently?"` | `action=allow` |
| T120 | `detect_cascade_risk()` | Single-category vs multi-category text | Multi score > single score |
| T130 | `format_block_message()` | HIGH risk result | Contains "cascade", risk level, pattern IDs |
| T140 | `get_cascade_stats()` | Log with 5 events (3 blocked, 2 allowed) | `{total_checks: 5, detections: 3, blocks: 3, allowed: 2}` |
| T150 | `main()` via subprocess | JSON hook input with cascade/clean text | exit(2) for cascade, exit(0) for clean |
| T160 | `handle_cascade_detection()` | MEDIUM risk result | Returns `False` |
| T170 | `create_cascade_event()` | HIGH risk result | All 8 CascadeEvent fields present |
| T180 | `load_user_patterns()` | Valid JSON with 2 patterns | Returns 2 patterns |
| T190 | `merge_patterns()` | Default CP-001 regex A + user CP-001 regex B | Merged CP-001 has regex B |
| T200 | `detect_cascade_risk()` | 2000-char text, 100 runs | Average <5ms |
| T210 | `detect_cascade_risk()` | 10000-char text, 100 runs | Average <5ms |
| T260 | `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `rule_present=True` |
| T270 | `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `contains_open_ended=True, forbids_numbered_options=True` |
| T280 | `validate_claude_md_cascade_rule()` | `CLAUDE.md` | `section_correct=True` |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All cascade detection functions follow fire-and-forget telemetry conventions:
- Detection functions never raise exceptions to callers — internal errors result in `allow` (fail open for hook infrastructure errors only)
- Telemetry logging failures are caught internally and printed to stderr
- Pattern loading failures fall back to hardcoded defaults (REQ-8)
- The hook entry point wraps everything in try/except and fails open with `exit(0)` on unexpected errors

### 10.2 Logging Convention

- Use `logging.getLogger(__name__)` in library modules (`cascade_patterns.py`, `cascade_events.py`)
- Use `print(..., file=sys.stderr)` in the hook entry point (`.claude/hooks/`) since it runs as a subprocess
- Block messages use `print(..., file=sys.stderr)` for terminal display

### 10.3 Constants

| Constant | Value | Rationale | File |
|----------|-------|-----------|------|
| `MAX_INPUT_LENGTH` | `10_000` | Prevent performance issues on huge model outputs | `cascade_detector.py` |
| `_DEFAULT_CONFIG_PATH` | `Path("data/unleashed/cascade_block_patterns.json")` | Standard location for user patterns | `cascade_patterns.py` |
| `_DEFAULT_LOG_PATH` | `Path("tmp/cascade-events.jsonl")` | Standard location for telemetry logs | `cascade_events.py` |
| Default `risk_threshold` | `0.6` | Calibrated to require multi-category evidence before blocking | `cascade_detector.py` |
| Snippet truncation | `200` chars | Balance between context and log size | `cascade_events.py` |
| Risk level thresholds | `0.3 / 0.5 / 0.7 / 0.9` | NONE/LOW/MEDIUM/HIGH/CRITICAL boundaries | `cascade_detector.py` |

### 10.4 Pattern Compilation Strategy

Patterns are compiled on each call to `detect_cascade_risk()` rather than being pre-compiled at module level. This is because:
1. User patterns can change between calls (config file updated)
2. Compilation of ~15 simple patterns takes <0.1ms — well within the 5ms budget
3. Pre-compilation would require a cache invalidation strategy

If performance profiling shows pattern compilation as a bottleneck (unlikely), a `functools.lru_cache` can be added to `load_default_patterns()`.

### 10.5 TDD Note

All test files (Section 6.11–6.14) should be created **before** the implementation files (Section 6.2–6.5). The tests should initially fail (RED), then pass after implementation (GREEN). The implementation order in Section 2 is the logical dependency order, but the physical creation order should be: fixtures → tests → implementation → exports → config → hook → CLAUDE.md.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3: `__init__.py` ×2, `CLAUDE.md`)
- [x] Every data structure has a concrete JSON/YAML example (Section 4: 6 structures with examples)
- [x] Every function has input/output examples with realistic values (Section 5: 13 functions)
- [x] Change instructions are diff-level specific (Section 6: 14 files with diffs/complete contents)
- [x] Pattern references include file:line and are verified to exist (Section 7: 3 patterns)
- [x] All imports are listed and verified (Section 8: 17 imports)
- [x] Test mapping covers all LLD test scenarios (Section 9: 28 test IDs mapped)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #358 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 1 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #358 |
| Verdict | APPROVED |
| Date | 2026-02-25 |
| Iterations | 0 |
| Finalized | 2026-02-25T08:46:28Z |

### Review Feedback Summary

Approved with suggestions:
- **Configuration Path:** Ensure the directory `data/unleashed/` exists or is created by the build system if it doesn't already exist in the repo (the spec assumes existing directory, which is likely correct for an established repo).
- **Execution Bit:** When implementing `.claude/hooks/post_output_cascade_check.py`, ensure the file is made executable (`chmod +x`) if the Claude Code runner requires it (though `python3 script.py` invocation in tests handles it, direct h...


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
    mock_repo/
      src/
    scout/
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

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_358.py
"""Test file for Issue #358.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.hooks.cascade_patterns import *  # noqa: F401, F403


# Unit Tests
# -----------

def test_t010():
    """
    `detect_cascade_risk()` | `"Great, issue #42 is fixed! Should I
    continue with issue #43?"` | `detected=True, risk_level>=MEDIUM`
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
    `detect_cascade_risk()` | `"Done! What's next?\n1. Yes, start issue
    #44\n2. No, stop here"` | `risk_level=CRITICAL,
    action=block_and_alert`
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
    `detect_cascade_risk()`, `is_permission_prompt()` | `"Allow bash
    command: git push origin main? (y/n)"` | `detected=False,
    action=allow`
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
    `detect_cascade_risk()` | `"I've completed the refactor. Now let me
    also update the tests..."` | `detected=True, risk_level>=MEDIUM`
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
    `detect_cascade_risk()` | `"While I'm at it, I could also fix the
    related CSS issue..."` | `detected=True, risk_level>=MEDIUM`
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
    `detect_cascade_risk()` | `""` and `None` | `detected=False,
    risk_level=NONE`
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
    `load_user_patterns()`, `load_default_patterns()` | Corrupt JSON file
    | Empty user patterns, 15+ defaults, no crash
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
    `detect_cascade_risk()` | `"a"*10000 + " Should I " + "b"*10000` |
    Completes in <100ms
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
    `log_cascade_event()` | Valid CascadeEvent | JSONL file with all
    fields
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
    `merge_patterns()` | Default CP-001 + user CP-001 | User regex used
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
    `detect_cascade_risk()` | `"Should I format this differently?"` |
    `action=allow`
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
    `detect_cascade_risk()` | Single-category vs multi-category text |
    Multi score > single score
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
    `format_block_message()` | HIGH risk result | Contains "cascade",
    risk level, pattern IDs
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
    `get_cascade_stats()` | Log with 5 events (3 blocked, 2 allowed) |
    `{total_checks: 5, detections: 3, blocks: 3, allowed: 2}`
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
    `main()` via subprocess | JSON hook input with cascade/clean text |
    exit(2) for cascade, exit(0) for clean
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
    `handle_cascade_detection()` | MEDIUM risk result | Returns `False`
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
    `create_cascade_event()` | HIGH risk result | All 8 CascadeEvent
    fields present
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
    `load_user_patterns()` | Valid JSON with 2 patterns | Returns 2
    patterns
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
    `merge_patterns()` | Default CP-001 regex A + user CP-001 regex B |
    Merged CP-001 has regex B
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
    `detect_cascade_risk()` | 2000-char text, 100 runs | Average <5ms
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
    `detect_cascade_risk()` | 10000-char text, 100 runs | Average <5ms
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t210 works correctly
    assert False, 'TDD RED: test_t210 not implemented'


def test_t260():
    """
    `validate_claude_md_cascade_rule()` | `CLAUDE.md` |
    `rule_present=True`
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
    `validate_claude_md_cascade_rule()` | `CLAUDE.md` |
    `contains_open_ended=True, forbids_numbered_options=True`
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
    `validate_claude_md_cascade_rule()` | `CLAUDE.md` |
    `section_correct=True`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t280 works correctly
    assert False, 'TDD RED: test_t280 not implemented'




```

## Previously Implemented Files

These files have already been implemented. Use them for imports and references:

### tests/fixtures/cascade_samples.json (signatures)

```python

```

### assemblyzero/hooks/cascade_patterns.py (signatures)

```python
"""Cascade detection pattern definitions.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Contains regex patterns for detecting cascade-risk scenarios in model output.
Patterns are organized by category and scored by risk weight.
"""

from __future__ import annotations

import json

import logging

import re

from pathlib import Path

from typing import Any, Literal, TypedDict

class CascadePattern(TypedDict):

    """A single pattern definition for cascade detection."""

def load_default_patterns() -> list[CascadePattern]:
    """Load the built-in cascade detection patterns.

Returns the hardcoded baseline pattern set derived from 3 months"""
    ...

def load_user_patterns(
    config_path: str | Path | None = None,
) -> list[CascadePattern]:
    """Load user-defined patterns from cascade_block_patterns.json.

Merges with defaults. User patterns can override built-in patterns"""
    ...

def merge_patterns(
    defaults: list[CascadePattern],
    overrides: list[CascadePattern],
) -> list[CascadePattern]:
    """Merge two pattern lists, with overrides taking precedence by ID.

Args:"""
    ...

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("data/unleashed/cascade_block_patterns.json")
```

### assemblyzero/hooks/cascade_detector.py (signatures)

```python
"""Core cascade detection engine.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Analyzes model output text for cascade-risk patterns using multi-category
weighted regex scoring.
"""

from __future__ import annotations

import re

from enum import Enum

from typing import Any, Literal, TypedDict

from assemblyzero.hooks.cascade_patterns import (
    CascadePattern,
    load_default_patterns,
    load_user_patterns,
    merge_patterns,
)

class CascadeRiskLevel(Enum):

    """Severity of detected cascade risk."""

class CascadeDetectionResult(TypedDict):

    """Result from analyzing a model output block."""

def detect_cascade_risk(
    model_output: str,
    patterns: list[CascadePattern] | None = None,
    risk_threshold: float = 0.6,
) -> CascadeDetectionResult:
    """Analyze model output text for cascade-risk patterns.

Scans the output against all registered patterns, calculates a"""
    ...

def compute_risk_score(
    matched_patterns: list[tuple[CascadePattern, re.Match[str]]],
) -> tuple[float, CascadeRiskLevel]:
    """Compute composite risk score from matched patterns.

Uses weighted scoring: each matched pattern contributes its"""
    ...

def is_permission_prompt(text: str) -> bool:
    """Distinguish genuine permission prompts from cascade offers.

Permission prompts (e.g., "Allow bash command: git push?") should"""
    ...

def _make_allow_result() -> CascadeDetectionResult:
    """Create a default 'allow' result (no cascade detected)."""
    ...

MAX_INPUT_LENGTH = 10_000
```

### assemblyzero/hooks/cascade_action.py (full)

```python
"""Action handlers for cascade detection results.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Dispatches actions (allow, block, alert) based on cascade detection results.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from assemblyzero.hooks.cascade_detector import CascadeDetectionResult, CascadeRiskLevel
from assemblyzero.telemetry.cascade_events import create_cascade_event, log_cascade_event

if TYPE_CHECKING:
    pass


def handle_cascade_detection(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    alert_enabled: bool = True,
) -> bool:
    """Execute the recommended action from a cascade detection.

    Depending on the detection result, it will:
    - allow: return True (auto-approve may proceed)
    - block_and_prompt: log event, return False (force human input)
    - block_and_alert: log event, show alert, return False

    Args:
        result: The CascadeDetectionResult from detect_cascade_risk.
        session_id: Current session identifier for telemetry.
        model_output: Full model output for logging context.
        alert_enabled: Whether to show visual/audible alert on block.

    Returns:
        True if auto-approval should proceed, False if blocked.
    """
    action = result["recommended_action"]

    if action == "allow":
        # Optionally log allowed checks (if log_all_checks is configured)
        return True

    # For block_and_prompt and block_and_alert
    action_taken = "blocked" if action == "block_and_prompt" else "alerted"

    # Log the cascade event
    try:
        event = create_cascade_event(
            result=result,
            session_id=session_id,
            model_output=model_output,
            action_taken=action_taken,
        )
        log_cascade_event(event)
    except Exception:  # noqa: BLE001
        # Telemetry failure must not affect blocking behavior
        pass

    # Print block message to stderr
    message = format_block_message(result)
    if action == "block_and_alert" and alert_enabled:
        # Add alert decoration
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"\U0001f6a8 ALERT: {message}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
    else:
        print(f"\n{message}\n", file=sys.stderr)

    return False


def format_block_message(
    result: CascadeDetectionResult,
) -> str:
    """Format a human-readable message explaining why auto-approve was blocked.

    Shown to the user when cascade detection fires, explaining what
    was detected and asking them to make the decision manually.

    Args:
        result: The detection result.

    Returns:
        Formatted message string for terminal display.
    """
    risk_level = result["risk_level"]
    if isinstance(risk_level, CascadeRiskLevel):
        risk_name = risk_level.value.upper()
    else:
        risk_name = str(risk_level).upper()

    confidence = result["confidence"]
    pattern_ids = result["matched_patterns"] if result["matched_patterns"] else ["unknown"]
    matched_text = result["matched_text"]

    # Truncate matched text for display
    if len(matched_text) > 100:
        matched_text = matched_text[:100] + "..."

    lines = [
        "\u26a0\ufe0f  CASCADE DETECTED \u2014 Auto-approve blocked",
        f"Risk Level: {risk_name} (confidence: {confidence:.2f})",
        f"Matched Patterns: {', '.join(pattern_ids)}",
        f'Trigger: "{matched_text}"',
        "",
        "The AI is offering to continue to the next task. Please provide manual input.",
        "Type your response to decide what happens next.",
    ]
    return "\n".join(lines)
```

## Previous Attempt Failed

The previous implementation had this error:

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\mcwiz\AppData\Local\pypoetry\Cache\virtualenvs\unleashed-Zukdy2xA-py3.14\Scripts\python.exe
cachedir: .pytest_cache
benchmark: 5.2.3 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
rootdir: C:\Users\mcwiz\Projects\AssemblyZero
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.6.9, benchmark-5.2.3, cov-7.0.0
collecting ... collected 24 items

tests/test_issue_358.py::test_t010 FAILED                                [  4%]
tests/test_issue_358.py::test_t020 FAILED                                [  8%]
tests/test_issue_358.py::test_t030 FAILED                                [ 12%]
tests/test_issue_358.py::test_t040 FAILED                                [ 16%]
tests/test_issue_358.py::test_t050 FAILED                                [ 20%]
tests/test_issue_358.py::test_t060 FAILED                                [ 25%]
tests/test_issue_358.py::test_t070 FAILED                                [ 29%]
tests/test_issue_358.py::test_t080 FAILED                                [ 33%]
tests/test_issue_358.py::test_t090 FAILED                                [ 37%]
tests/test_issue_358.py::test_t100 FAILED                                [ 41%]
tests/test_issue_358.py::test_t110 FAILED                                [ 45%]
tests/test_issue_358.py::test_t120 FAILED                                [ 50%]
tests/test_issue_358.py::test_t130 FAILED                                [ 54%]
tests/test_issue_358.py::test_t140 FAILED                                [ 58%]
tests/test_issue_358.py::test_t150 FAILED                                [ 62%]
tests/test_issue_358.py::test_t160 FAILED                                [ 66%]
tests/test_issue_358.py::test_t170 FAILED                                [ 70%]
tests/test_issue_358.py::test_t180 FAILED                                [ 75%]
tests/test_issue_358.py::test_t190 FAILED                                [ 79%]
tests/test_issue_358.py::test_t200 FAILED                                [ 83%]
tests/test_issue_358.py::test_t210 FAILED                                [ 87%]
tests/test_issue_358.py::test_t260 FAILED                                [ 91%]
tests/test_issue_358.py::test_t270 FAILED                                [ 95%]
tests/test_issue_358.py::test_t280 FAILED                                [100%]
ERROR: Coverage failure: total of 26 is less than fail-under=95


================================== FAILURES ===================================
__________________________________ test_t010 __________________________________
tests\test_issue_358.py:30: in test_t010
    assert False, 'TDD RED: test_t010 not implemented'
E   AssertionError: TDD RED: test_t010 not implemented
E   assert False
__________________________________ test_t020 __________________________________
tests\test_issue_358.py:47: in test_t020
    assert False, 'TDD RED: test_t020 not implemented'
E   AssertionError: TDD RED: test_t020 not implemented
E   assert False
__________________________________ test_t030 __________________________________
tests\test_issue_358.py:64: in test_t030
    assert False, 'TDD RED: test_t030 not implemented'
E   AssertionError: TDD RED: test_t030 not implemented
E   assert False
__________________________________ test_t040 __________________________________
tests\test_issue_358.py:80: in test_t040
    assert False, 'TDD RED: test_t040 not implemented'
E   AssertionError: TDD RED: test_t040 not implemented
E   assert False
__________________________________ test_t050 __________________________________
tests\test_issue_358.py:96: in test_t050
    assert False, 'TDD RED: test_t050 not implemented'
E   AssertionError: TDD RED: test_t050 not implemented
E   assert False
__________________________________ test_t060 __________________________________
tests\test_issue_358.py:112: in test_t060
    assert False, 'TDD RED: test_t060 not implemented'
E   AssertionError: TDD RED: test_t060 not implemented
E   assert False
__________________________________ test_t070 __________________________________
tests\test_issue_358.py:128: in test_t070
    assert False, 'TDD RED: test_t070 not implemented'
E   AssertionError: TDD RED: test_t070 not implemented
E   assert False
__________________________________ test_t080 __________________________________
tests\test_issue_358.py:144: in test_t080
    assert False, 'TDD RED: test_t080 not implemented'
E   AssertionError: TDD RED: test_t080 not implemented
E   assert False
__________________________________ test_t090 __________________________________
tests\test_issue_358.py:160: in test_t090
    assert False, 'TDD RED: test_t090 not implemented'
E   AssertionError: TDD RED: test_t090 not implemented
E   assert False
__________________________________ test_t100 __________________________________
tests\test_issue_358.py:175: in test_t100
    assert False, 'TDD RED: test_t100 not implemented'
E   AssertionError: TDD RED: test_t100 not implemented
E   assert False
__________________________________ test_t110 __________________________________
tests\test_issue_358.py:191: in test_t110
    assert False, 'TDD RED: test_t110 not implemented'
E   AssertionError: TDD RED: test_t110 not implemented
E   assert False
__________________________________ test_t120 __________________________________
tests\test_issue_358.py:207: in test_t120
    assert False, 'TDD RED: test_t120 not implemented'
E   AssertionError: TDD RED: test_t120 not implemented
E   assert False
__________________________________ test_t130 __________________________________
tests\test_issue_358.py:223: in test_t130
    assert False, 'TDD RED: test_t130 not implemented'
E   AssertionError: TDD RED: test_t130 not implemented
E   assert False
__________________________________ test_t140 __________________________________
tests\test_issue_358.py:239: in test_t140
    assert False, 'TDD RED: test_t140 not implemented'
E   AssertionError: TDD RED: test_t140 not implemented
E   assert False
__________________________________ test_t150 __________________________________
tests\test_issue_358.py:255: in test_t150
    assert False, 'TDD RED: test_t150 not implemented'
E   AssertionError: TDD RED: test_t150 not implemented
E   assert False
__________________________________ test_t160 __________________________________
tests\test_issue_358.py:270: in test_t160
    assert False, 'TDD RED: test_t160 not implemented'
E   AssertionError: TDD RED: test_t160 not implemented
E   assert False
__________________________________ test_t170 __________________________________
tests\test_issue_358.py:286: in test_t170
    assert False, 'TDD RED: test_t170 not implemented'
E   AssertionError: TDD RED: test_t170 not implemented
E   assert False
__________________________________ test_t180 __________________________________
tests\test_issue_358.py:302: in test_t180
    assert False, 'TDD RED: test_t180 not implemented'
E   AssertionError: TDD RED: test_t180 not implemented
E   assert False
__________________________________ test_t190 __________________________________
tests\test_issue_358.py:318: in test_t190
    assert False, 'TDD RED: test_t190 not implemented'
E   AssertionError: TDD RED: test_t190 not implemented
E   assert False
__________________________________ test_t200 __________________________________
tests\test_issue_358.py:333: in test_t200
    assert False, 'TDD RED: test_t200 not implemented'
E   AssertionError: TDD RED: test_t200 not implemented
E   assert False
__________________________________ test_t210 __________________________________
tests\test_issue_358.py:348: in test_t210
    assert False, 'TDD RED: test_t210 not implemented'
E   AssertionError: TDD RED: test_t210 not implemented
E   assert False
__________________________________ test_t260 __________________________________
tests\test_issue_358.py:364: in test_t260
    assert False, 'TDD RED: test_t260 not implemented'
E   AssertionError: TDD RED: test_t260 not implemented
E   assert False
__________________________________ test_t270 __________________________________
tests\test_issue_358.py:380: in test_t270
    assert False, 'TDD RED: test_t270 not implemented'
E   AssertionError: TDD RED: test_t270 not implemented
E   assert False
__________________________________ test_t280 __________________________________
tests\test_issue_358.py:396: in test_t280
    assert False, 'TDD RED: test_t280 not implemented'
E   AssertionError: TDD RED: test_t280 not implemented
E   assert False
=============================== tests coverage ================================
_______________ coverage: platform win32, python 3.14.0-final-0 _______________

Name                                     Stmts   Miss  Cover   Missing
----------------------------------------------------------------------
assemblyzero\hooks\cascade_patterns.py      70     52    26%   49, 193-244, 260-276
----------------------------------------------------------------------
TOTAL                                       70     52    26%
FAIL Required test coverage of 95% not reached. Total coverage: 25.71%
=========================== short test summary info ===========================
FAILED tests/test_issue_358.py::test_t010 - AssertionError: TDD RED: test_t01...
FAILED tests/test_issue_358.py::test_t020 - AssertionError: TDD RED: test_t02...
FAILED tests/test_issue_358.py::test_t030 - AssertionError: TDD RED: test_t03...
FAILED tests/test_issue_358.py::test_t040 - AssertionError: TDD RED: test_t04...
FAILED tests/test_issue_358.py::test_t050 - AssertionError: TDD RED: test_t05...
FAILED tests/test_issue_358.py::test_t060 - AssertionError: TDD RED: test_t06...
FAILED tests/test_issue_358.py::test_t070 - AssertionError: TDD RED: test_t07...
FAILED tests/test_issue_358.py::test_t080 - AssertionError: TDD RED: test_t08...
FAILED tests/test_issue_358.py::test_t090 - AssertionError: TDD RED: test_t09...
FAILED tests/test_issue_358.py::test_t100 - AssertionError: TDD RED: test_t10...
FAILED tests/test_issue_358.py::test_t110 - AssertionError: TDD RED: test_t11...
FAILED tests/test_issue_358.py::test_t120 - AssertionError: TDD RED: test_t12...
FAILED tests/test_issue_358.py::test_t130 - AssertionError: TDD RED: test_t13...
FAILED tests/test_issue_358.py::test_t140 - AssertionError: TDD RED: test_t14...
FAILED tests/test_issue_358.py::test_t150 - AssertionError: TDD RED: test_t15...
FAILED tests/test_issue_358.py::test_t160 - AssertionError: TDD RED: test_t16...
FAILED tests/test_issue_358.py::test_t170 - AssertionError: TDD RED: test_t17...
FAILED tests/test_issue_358.py::test_t180 - AssertionError: TDD RED: test_t18...
FAILED tests/test_issue_358.py::test_t190 - AssertionError: TDD RED: test_t19...
FAILED tests/test_issue_358.py::test_t200 - AssertionError: TDD RED: test_t20...
FAILED tests/test_issue_358.py::test_t210 - AssertionError: TDD RED: test_t21...
FAILED tests/test_issue_358.py::test_t260 - AssertionError: TDD RED: test_t26...
FAILED tests/test_issue_358.py::test_t270 - AssertionError: TDD RED: test_t27...
FAILED tests/test_issue_358.py::test_t280 - AssertionError: TDD RED: test_t28...
============================= 24 failed in 0.16s ==============================


```

Fix the issue in your implementation.

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
