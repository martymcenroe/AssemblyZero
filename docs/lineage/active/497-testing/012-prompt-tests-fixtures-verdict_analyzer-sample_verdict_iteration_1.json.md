# Implementation Request: tests/fixtures/verdict_analyzer/sample_verdict_iteration_1.json

## Task

Write the complete contents of `tests/fixtures/verdict_analyzer/sample_verdict_iteration_1.json`.

Change type: Add
Description: Test fixture: blocked verdict with 3 issues

## LLD Specification

# Implementation Spec: Bounded Verdict History in LLD Revision Loop

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #497 |
| LLD | `docs/lld/active/497-bounded-verdict-history.md` |
| Generated | 2026-02-28 |
| Status | DRAFT |

## 1. Overview

Replace unbounded cumulative verdict history in the LLD revision prompt with a bounded rolling-window strategy. The latest verdict is kept verbatim while prior verdicts are compressed into structured one-line summaries with persistence tracking, all capped at a configurable token budget (~4,000 tokens).

**Objective:** Keep prompt size within ~20% of iteration 2 regardless of iteration count.

**Success Criteria:** Feedback section tokens bounded at `token_budget` (default 4,000); iteration 5 tokens within 20% of iteration 2 tokens; both JSON and text verdict formats supported.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/verdict_analyzer/sample_verdict_iteration_1.json` | Add | Test fixture: blocked verdict with 3 issues |
| 2 | `tests/fixtures/verdict_analyzer/sample_verdict_iteration_2.json` | Add | Test fixture: blocked verdict with 2 issues (1 persisting) |
| 3 | `tests/fixtures/verdict_analyzer/sample_verdict_iteration_3.json` | Add | Test fixture: approved verdict |
| 4 | `assemblyzero/workflows/requirements/verdict_summarizer.py` | Add | Verdict summarization logic |
| 5 | `assemblyzero/workflows/requirements/feedback_window.py` | Add | Feedback window assembly with token budget |
| 6 | `assemblyzero/workflows/requirements/nodes/generate_draft.py` | Modify | Replace cumulative feedback with bounded feedback |
| 7 | `tests/unit/test_verdict_summarizer.py` | Add | Unit tests for verdict summarizer |
| 8 | `tests/unit/test_feedback_window.py` | Add | Unit tests for feedback window |
| 9 | `tests/unit/test_generate_draft_feedback.py` | Add | Integration-style tests for generate_draft feedback usage |

**Implementation Order Rationale:** Fixtures first (no dependencies), then core modules bottom-up (summarizer has no internal deps, feedback_window depends on summarizer), then modify the consumer (generate_draft), then tests last since they validate the whole chain.

## 3. Current State (for Modify/Delete files)

### 3.1 `assemblyzero/workflows/requirements/nodes/generate_draft.py`

**Relevant excerpt — module header and imports** (lines 1-30):

```python
"""N1: Generate draft node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Remove pre-review validation gate - Gemini answers open questions

Uses the configured drafter LLM to generate a draft based on:
- Issue workflow: brief content + template
- LLD workflow: issue content + context + template

Supports revision mode with cumulative verdict history.
"""

import re

from pathlib import Path

from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider

from assemblyzero.utils.cost_tracker import accumulate_node_cost, accumulate_node_tokens

from assemblyzero.core.section_utils import (
    build_targeted_prompt,
    extract_sections,
    identify_changed_sections,
)

from assemblyzero.workflows.requirements.audit import (
    get_repo_structure,
    load_template,
    next_file_number,
    save_audit_file,
)

from assemblyzero.workflows.requirements.state import RequirementsWorkflowState
```

**Relevant excerpt — `_build_prompt` function, cumulative verdict history insertion** (lines ~250-270, approximate — the critical section where `verdict_history` is joined into the prompt):

```python
    # Inside _build_prompt(), the revision/feedback section:
    verdict_history = state.get("verdict_history", [])
    if verdict_history:
        feedback_section = "## ALL Gemini Review Feedback (CUMULATIVE)\n" + "\n\n".join(verdict_history)
        prompt_parts.append(feedback_section)
```

**What changes:**
1. Add imports for `build_feedback_block` and `render_feedback_markdown` from the new `feedback_window` module.
2. Replace the cumulative verdict join (the 2-line `feedback_section` assignment above) with calls to `build_feedback_block()` and `render_feedback_markdown()`.

## 4. Data Structures

### 4.1 `VerdictSummary`

**Definition:**

```python
@dataclass
class VerdictSummary:
    """Compressed representation of a single prior verdict."""
    iteration: int
    verdict: str
    issue_count: int
    persisting_issues: list[str]
    new_issues: list[str]
```

**Concrete Example (iteration 2 with persistence):**

```json
{
    "iteration": 2,
    "verdict": "BLOCKED",
    "issue_count": 2,
    "persisting_issues": ["No rollback plan for database migration"],
    "new_issues": ["Test coverage section missing edge cases"]
}
```

**Concrete Example (iteration 1, no prior):**

```json
{
    "iteration": 1,
    "verdict": "BLOCKED",
    "issue_count": 3,
    "persisting_issues": [],
    "new_issues": [
        "Missing error handling for API timeout",
        "No rollback plan for database migration",
        "Security section omits OWASP references"
    ]
}
```

**Concrete Example (approved verdict):**

```json
{
    "iteration": 3,
    "verdict": "APPROVED",
    "issue_count": 0,
    "persisting_issues": [],
    "new_issues": []
}
```

### 4.2 `FeedbackWindow`

**Definition:**

```python
@dataclass
class FeedbackWindow:
    """Assembled feedback block ready for prompt insertion."""
    latest_verdict_full: str
    prior_summaries: list[VerdictSummary]
    total_tokens: int
    was_truncated: bool
```

**Concrete Example (3 verdicts in history):**

```json
{
    "latest_verdict_full": "{\"verdict\": \"APPROVED\", \"blocking_issues\": []}",
    "prior_summaries": [
        {
            "iteration": 1,
            "verdict": "BLOCKED",
            "issue_count": 3,
            "persisting_issues": [],
            "new_issues": [
                "Missing error handling for API timeout",
                "No rollback plan for database migration",
                "Security section omits OWASP references"
            ]
        },
        {
            "iteration": 2,
            "verdict": "BLOCKED",
            "issue_count": 2,
            "persisting_issues": ["No rollback plan for database migration"],
            "new_issues": ["Test coverage section missing edge cases"]
        }
    ],
    "total_tokens": 156,
    "was_truncated": false
}
```

**Concrete Example (empty history):**

```json
{
    "latest_verdict_full": "",
    "prior_summaries": [],
    "total_tokens": 0,
    "was_truncated": false
}
```

### 4.3 JSON Verdict Format (from #494)

**Concrete Example:**

```json
{
    "verdict": "BLOCKED",
    "blocking_issues": [
        {"id": 1, "description": "Missing error handling for API timeout"},
        {"id": 2, "description": "No rollback plan for database migration"},
        {"id": 3, "description": "Security section omits OWASP references"}
    ]
}
```

### 4.4 Text Verdict Format (current)

**Concrete Example:**

```text
## Verdict: BLOCKED

### Blocking Issues
- **[BLOCKING]** Missing error handling for API timeout
- **[BLOCKING]** No rollback plan for database migration
- **[BLOCKING]** Security section omits OWASP references
```

## 5. Function Specifications

### 5.1 `extract_blocking_issues()`

**File:** `assemblyzero/workflows/requirements/verdict_summarizer.py`

**Signature:**

```python
def extract_blocking_issues(verdict_text: str) -> list[str]:
    """Extract blocking issue descriptions from a verdict string.
    
    Auto-detects format: JSON (#494) or text (current).
    Falls back to text parsing with logger.warning() if JSON detection fails.
    """
    ...
```

**Input Example (JSON format):**

```python
verdict_text = '{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "Missing error handling for API timeout"}, {"id": 2, "description": "No rollback plan for database migration"}]}'
```

**Output Example (JSON format):**

```python
["Missing error handling for API timeout", "No rollback plan for database migration"]
```

**Input Example (text format):**

```python
verdict_text = """## Verdict: BLOCKED

### Blocking Issues
- **[BLOCKING]** Missing error handling for API timeout
- **[BLOCKING]** No rollback plan for database migration"""
```

**Output Example (text format):**

```python
["Missing error handling for API timeout", "No rollback plan for database migration"]
```

**Edge Cases:**
- Empty string → returns `[]`
- `None`-like empty → returns `[]`
- Malformed JSON (starts with `{` but invalid) → falls back to text parsing, emits `logger.warning()`
- `APPROVED` verdict with no blocking issues → returns `[]`
- Text verdict with `**BLOCKING**` variant (no brackets) → also matched by regex

### 5.2 `identify_persisting_issues()`

**File:** `assemblyzero/workflows/requirements/verdict_summarizer.py`

**Signature:**

```python
def identify_persisting_issues(
    current_issues: list[str],
    prior_issues: list[str],
    similarity_threshold: float = 0.8,
) -> tuple[list[str], list[str]]:
    """Classify current issues as persisting or new relative to prior iteration."""
    ...
```

**Input Example:**

```python
current_issues = [
    "No rollback plan for database migration",
    "Test coverage section missing edge cases",
]
prior_issues = [
    "Missing error handling for API timeout",
    "No rollback plan for database migration",
    "Security section omits OWASP references",
]
similarity_threshold = 0.8
```

**Output Example:**

```python
(
    ["No rollback plan for database migration"],   # persisting
    ["Test coverage section missing edge cases"],   # new
)
```

**Input Example (minor rephrasing):**

```python
current_issues = ["Missing rollback plan for database migration"]
prior_issues = ["No rollback plan for database migration"]
similarity_threshold = 0.8
```

**Output Example (rephrasing detected):**

```python
(
    ["Missing rollback plan for database migration"],  # persisting (similarity > 0.8)
    [],                                                 # new
)
```

**Edge Cases:**
- Empty `current_issues` → returns `([], [])`
- Empty `prior_issues` → all current issues are new: `([], current_issues)`
- Both empty → returns `([], [])`
- Exact match → persisting
- Similarity below threshold → new

### 5.3 `summarize_verdict()`

**File:** `assemblyzero/workflows/requirements/verdict_summarizer.py`

**Signature:**

```python
def summarize_verdict(
    verdict_text: str,
    iteration: int,
    prior_issues: Optional[list[str]] = None,
) -> VerdictSummary:
    """Produce a structured summary of a single verdict."""
    ...
```

**Input Example:**

```python
verdict_text = '{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "No rollback plan for database migration"}, {"id": 2, "description": "Test coverage section missing edge cases"}]}'
iteration = 2
prior_issues = [
    "Missing error handling for API timeout",
    "No rollback plan for database migration",
    "Security section omits OWASP references",
]
```

**Output Example:**

```python
VerdictSummary(
    iteration=2,
    verdict="BLOCKED",
    issue_count=2,
    persisting_issues=["No rollback plan for database migration"],
    new_issues=["Test coverage section missing edge cases"],
)
```

**Edge Cases:**
- `prior_issues=None` (iteration 1) → all issues classified as new, no persisting
- Approved verdict → `VerdictSummary(iteration=N, verdict="APPROVED", issue_count=0, persisting_issues=[], new_issues=[])`
- Verdict format unrecognizable → `verdict="UNKNOWN"`, `issue_count=0`

### 5.4 `format_summary_line()`

**File:** `assemblyzero/workflows/requirements/verdict_summarizer.py`

**Signature:**

```python
def format_summary_line(summary: VerdictSummary) -> str:
    """Render a VerdictSummary as a single human-readable markdown line."""
    ...
```

**Input Example:**

```python
summary = VerdictSummary(
    iteration=2,
    verdict="BLOCKED",
    issue_count=2,
    persisting_issues=["No rollback plan for database migration"],
    new_issues=["Test coverage section missing edge cases"],
)
```

**Output Example:**

```python
'- Iteration 2: BLOCKED — 2 issues (1 persists: "No rollback plan for database migration"; 1 new)'
```

**Input Example (iteration 1, all new):**

```python
summary = VerdictSummary(
    iteration=1,
    verdict="BLOCKED",
    issue_count=3,
    persisting_issues=[],
    new_issues=["Missing error handling", "No rollback plan", "Security omits OWASP"],
)
```

**Output Example:**

```python
'- Iteration 1: BLOCKED — 3 issues (0 persists; 3 new)'
```

**Input Example (approved):**

```python
summary = VerdictSummary(iteration=3, verdict="APPROVED", issue_count=0, persisting_issues=[], new_issues=[])
```

**Output Example:**

```python
'- Iteration 3: APPROVED — 0 issues (0 persists; 0 new)'
```

**Edge Cases:**
- Multiple persisting issues → all listed with commas: `(2 persists: "issue1", "issue2"; 0 new)`

### 5.5 `count_tokens()`

**File:** `assemblyzero/workflows/requirements/feedback_window.py`

**Signature:**

```python
def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken."""
    ...
```

**Input Example:**

```python
text = "- Iteration 1: BLOCKED — 3 issues (0 persists; 3 new)"
model = "cl100k_base"
```

**Output Example:**

```python
18  # approximate — actual value depends on tiktoken encoding
```

**Edge Cases:**
- Empty string → returns `0`
- Very long text → returns accurate count (no truncation)

### 5.6 `build_feedback_block()`

**File:** `assemblyzero/workflows/requirements/feedback_window.py`

**Signature:**

```python
def build_feedback_block(
    verdict_history: list[str],
    token_budget: int = 4000,
) -> FeedbackWindow:
    """Assemble a bounded feedback block from verdict history."""
    ...
```

**Input Example (3 verdicts):**

```python
verdict_history = [
    '{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "Missing error handling for API timeout"}, {"id": 2, "description": "No rollback plan for database migration"}, {"id": 3, "description": "Security section omits OWASP references"}]}',
    '{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "No rollback plan for database migration"}, {"id": 2, "description": "Test coverage section missing edge cases"}]}',
    '{"verdict": "APPROVED", "blocking_issues": []}',
]
token_budget = 4000
```

**Output Example:**

```python
FeedbackWindow(
    latest_verdict_full='{"verdict": "APPROVED", "blocking_issues": []}',
    prior_summaries=[
        VerdictSummary(iteration=1, verdict="BLOCKED", issue_count=3, persisting_issues=[], new_issues=["Missing error handling for API timeout", "No rollback plan for database migration", "Security section omits OWASP references"]),
        VerdictSummary(iteration=2, verdict="BLOCKED", issue_count=2, persisting_issues=["No rollback plan for database migration"], new_issues=["Test coverage section missing edge cases"]),
    ],
    total_tokens=156,  # approximate
    was_truncated=False,
)
```

**Edge Cases:**
- Empty list → `FeedbackWindow(latest_verdict_full="", prior_summaries=[], total_tokens=0, was_truncated=False)`
- Single verdict → `latest_verdict_full` set, no prior summaries
- Latest verdict exceeds budget → still included, `was_truncated=True`, warning logged
- Budget requires truncation → oldest summaries dropped first

### 5.7 `render_feedback_markdown()`

**File:** `assemblyzero/workflows/requirements/feedback_window.py`

**Signature:**

```python
def render_feedback_markdown(window: FeedbackWindow) -> str:
    """Render a FeedbackWindow as a markdown string for prompt insertion."""
    ...
```

**Input Example (with prior summaries):**

```python
window = FeedbackWindow(
    latest_verdict_full='{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "Test coverage section missing edge cases"}]}',
    prior_summaries=[
        VerdictSummary(iteration=1, verdict="BLOCKED", issue_count=3, persisting_issues=[], new_issues=["Missing error handling", "No rollback plan", "Security omits OWASP"]),
    ],
    total_tokens=200,
    was_truncated=False,
)
```

**Output Example:**

```python
"""## Review Feedback (Iteration 2)
{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "Test coverage section missing edge cases"}]}

## Prior Review Summary
- Iteration 1: BLOCKED — 3 issues (0 persists; 3 new)"""
```

**Input Example (single verdict, no priors):**

```python
window = FeedbackWindow(
    latest_verdict_full='{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "Missing error handling"}]}',
    prior_summaries=[],
    total_tokens=100,
    was_truncated=False,
)
```

**Output Example:**

```python
"""## Review Feedback (Iteration 1)
{"verdict": "BLOCKED", "blocking_issues": [{"id": 1, "description": "Missing error handling"}]}"""
```

**Edge Cases:**
- Empty `latest_verdict_full` (from empty history) → returns `""`
- No prior summaries → "Prior Review Summary" section omitted entirely

### 5.8 `test_budget_enforced_with_5_verdicts()`

**File:** `tests/unit/test_feedback_window.py`

**Signature:**

```python
def test_budget_enforced_with_5_verdicts(self):
    """Test ID 010: 5 verdicts, default budget, total_tokens <= 4000."""
    ...
```

**Input Example:**

```python
# 5 large verdicts, each with 50 issues of ~40 chars each
verdicts = [
    json.dumps({
        "verdict": "BLOCKED",
        "blocking_issues": [
            {"id": i + 1, "description": f"Issue number {i + 1}: " + "x" * 40}
            for i in range(50)
        ]
    })
    for _ in range(5)
]
token_budget = 4000
```

**Output Example:**

```python
window = build_feedback_block(verdicts, token_budget=4000)
assert window.total_tokens <= 4000  # True
assert window.latest_verdict_full == verdicts[-1]  # True — latest always preserved
# was_truncated may be True if summaries were dropped to fit
```

### 5.9 `test_custom_budget()`

**File:** `tests/unit/test_feedback_window.py`

**Signature:**

```python
def test_custom_budget(self):
    """Test ID 015: Custom budget of 2000 respected."""
    ...
```

**Input Example:**

```python
verdicts = [
    json.dumps({
        "verdict": "BLOCKED",
        "blocking_issues": [
            {"id": i + 1, "description": f"Issue number {i + 1}: " + "x" * 40}
            for i in range(50)
        ]
    })
    for _ in range(5)
]
token_budget = 2000
```

**Output Example:**

```python
window = build_feedback_block(verdicts, token_budget=2000)
assert window.total_tokens <= 2000  # True
```

### 5.10 `test_empty_prior_all_new()`

**File:** `tests/unit/test_verdict_summarizer.py`

**Signature:**

```python
def test_empty_prior_all_new(self):
    """Empty prior issues means all current are new."""
    ...
```

**Input Example:**

```python
current_issues = ["issue1", "issue2"]
prior_issues = []
```

**Output Example:**

```python
persisting, new = identify_persisting_issues(current_issues, prior_issues)
assert persisting == []  # True — no prior to compare against
assert new == ["issue1", "issue2"]  # True — all classified as new
```

### 5.11 `test_latest_exceeds_budget_still_included()`

**File:** `tests/unit/test_feedback_window.py`

**Signature:**

```python
def test_latest_exceeds_budget_still_included(self, caplog):
    """Latest verdict exceeds budget but is still included."""
    ...
```

**Input Example:**

```python
large_verdict = json.dumps({
    "verdict": "BLOCKED",
    "blocking_issues": [
        {"id": i + 1, "description": f"Issue number {i + 1}: " + "x" * 40}
        for i in range(50)
    ]
})
token_budget = 100  # Very small — large_verdict is ~1500 tokens
```

**Output Example:**

```python
window = build_feedback_block([large_verdict], token_budget=100)
assert window.latest_verdict_full == large_verdict  # True — latest always included
assert window.was_truncated is True  # True — budget exceeded
assert window.prior_summaries == []  # True — no room for summaries
# caplog contains: "Latest verdict alone exceeds token budget (XXXX >= 100)"
```

### 5.12 `test_mixed_persisting_and_new()`

**File:** `tests/unit/test_verdict_summarizer.py`

**Signature:**

```python
def test_mixed_persisting_and_new(self):
    """Mixed: one persists, one new."""
    ...
```

**Input Example:**

```python
current_issues = [
    "No rollback plan for database migration",
    "Test coverage section missing edge cases",
]
prior_issues = [
    "Missing error handling for API timeout",
    "No rollback plan for database migration",
    "Security section omits OWASP references",
]
```

**Output Example:**

```python
persisting, new = identify_persisting_issues(current_issues, prior_issues)
assert persisting == ["No rollback plan for database migration"]  # True — exact match with prior
assert new == ["Test coverage section missing edge cases"]  # True — not in prior
```

### 5.13 `test_truncation_logs_and_increments()`

**File:** `tests/unit/test_feedback_window.py`

**Signature:**

```python
def test_truncation_logs_and_increments(self, caplog):
    """Test ID 100: Truncation logs warning and increments counter."""
    ...
```

**Input Example:**

```python
verdicts = [
    json.dumps({
        "verdict": "BLOCKED",
        "blocking_issues": [
            {"id": i + 1, "description": f"Issue number {i + 1}: " + "x" * 40}
            for i in range(50)
        ]
    })
    for _ in range(5)
]
token_budget = 2000  # Tight enough to trigger truncation of summary lines
```

**Output Example:**

```python
# Before: fw_module.feedback_window_truncation_count == 0
window = build_feedback_block(verdicts, token_budget=2000)
if window.was_truncated:
    assert fw_module.feedback_window_truncation_count >= 1  # True — counter incremented
    # caplog contains a record with "truncat" in the message
```

## 6. Change Instructions

### 6.1 `tests/fixtures/verdict_analyzer/sample_verdict_iteration_1.json` (Add)

**Complete file contents:**

```json
{
    "verdict": "BLOCKED",
    "blocking_issues": [
        {"id": 1, "description": "Missing error handling for API timeout"},
        {"id": 2, "description": "No rollback plan for database migration"},
        {"id": 3, "description": "Security section omits OWASP references"}
    ]
}
```

### 6.2 `tests/fixtures/verdict_analyzer/sample_verdict_iteration_2.json` (Add)

**Complete file contents:**

```json
{
    "verdict": "BLOCKED",
    "blocking_issues": [
        {"id": 1, "description": "No rollback plan for database migration"},
        {"id": 2, "description": "Test coverage section missing edge cases"}
    ]
}
```

### 6.3 `tests/fixtures/verdict_analyzer/sample_verdict_iteration_3.json` (Add)

**Complete file contents:**

```json
{
    "verdict": "APPROVED",
    "blocking_issues": []
}
```

### 6.4 `assemblyzero/workflows/requirements/verdict_summarizer.py` (Add)

**Complete file contents:**

```python
"""Verdict summarization for bounded feedback windows.

Issue #497: Bounded Verdict History in LLD Revision Loop

Summarizes prior verdicts into structured one-line summaries with
persistence tracking. Supports both JSON (#494) and text verdict formats.
"""

import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VerdictSummary:
    """Compressed representation of a single prior verdict."""

    iteration: int
    verdict: str
    issue_count: int
    persisting_issues: list[str]
    new_issues: list[str]


def extract_blocking_issues(verdict_text: str) -> list[str]:
    """Extract blocking issue descriptions from a verdict string.

    Auto-detects format:
    - JSON format (#494): parses ``blocking_issues`` array from JSON
    - Text format (current): regex extracts lines matching ``[BLOCKING]``
      or ``**BLOCKING**`` patterns

    Falls back to text parsing with logger.warning() if JSON detection fails.

    Args:
        verdict_text: Raw verdict string (text or JSON format).

    Returns:
        List of blocking issue description strings. Empty list if no issues
        found or if verdict_text is empty/None.
    """
    if not verdict_text or not verdict_text.strip():
        return []

    stripped = verdict_text.strip()

    # Attempt JSON parsing first
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "blocking_issues" in data:
                issues = data["blocking_issues"]
                if isinstance(issues, list):
                    return [
                        item["description"]
                        for item in issues
                        if isinstance(item, dict) and "description" in item
                    ]
            return []
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning(
                "Verdict text starts with '{' but failed JSON parsing; "
                "falling back to text extraction"
            )

    # Text format extraction
    # Match patterns like:
    #   - **[BLOCKING]** Description here
    #   - **BLOCKING** Description here
    #   - [BLOCKING] Description here
    pattern = r"-\s*\*{0,2}\[?BLOCKING\]?\*{0,2}\s+(.+)"
    matches = re.findall(pattern, stripped)
    return [m.strip() for m in matches]


def _extract_verdict_status(verdict_text: str) -> str:
    """Extract the verdict status string from a verdict.

    Args:
        verdict_text: Raw verdict text.

    Returns:
        One of "BLOCKED", "APPROVED", or "UNKNOWN".
    """
    if not verdict_text or not verdict_text.strip():
        return "UNKNOWN"

    stripped = verdict_text.strip()

    # Try JSON first
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "verdict" in data:
                verdict_val = str(data["verdict"]).upper()
                if verdict_val in ("BLOCKED", "APPROVED"):
                    return verdict_val
                return "UNKNOWN"
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Fall through to text parsing

    # Text format: look for "Verdict: BLOCKED" or "Verdict: APPROVED"
    upper = stripped.upper()
    if "APPROVED" in upper:
        return "APPROVED"
    if "BLOCKED" in upper:
        return "BLOCKED"
    return "UNKNOWN"


def identify_persisting_issues(
    current_issues: list[str],
    prior_issues: list[str],
    similarity_threshold: float = 0.8,
) -> tuple[list[str], list[str]]:
    """Classify current issues as persisting or new relative to prior iteration.

    Uses normalized string comparison (lowered, stripped, punctuation-removed)
    to detect when the same issue reappears across iterations.

    Args:
        current_issues: Issues from the current verdict.
        prior_issues: Issues from the immediately preceding verdict.
        similarity_threshold: Minimum ratio for SequenceMatcher to consider
            two issue strings as "the same issue". Default 0.8.

    Returns:
        Tuple of (persisting_issues, new_issues).
    """
    if not current_issues:
        return [], []
    if not prior_issues:
        return [], list(current_issues)

    def _normalize(text: str) -> str:
        """Lowercase, strip, remove punctuation for comparison."""
        cleaned = re.sub(r"[^\w\s]", "", text.lower().strip())
        return cleaned

    persisting: list[str] = []
    new: list[str] = []

    normalized_prior = [_normalize(p) for p in prior_issues]

    for issue in current_issues:
        norm_current = _normalize(issue)
        is_persisting = False
        for norm_prior in normalized_prior:
            ratio = SequenceMatcher(None, norm_current, norm_prior).ratio()
            if ratio >= similarity_threshold:
                is_persisting = True
                break
        if is_persisting:
            persisting.append(issue)
        else:
            new.append(issue)

    return persisting, new


def summarize_verdict(
    verdict_text: str,
    iteration: int,
    prior_issues: Optional[list[str]] = None,
) -> VerdictSummary:
    """Produce a structured summary of a single verdict.

    Args:
        verdict_text: Raw verdict string.
        iteration: 1-based iteration number.
        prior_issues: Blocking issues from the previous iteration
            (for persistence detection). None for iteration 1 (no prior).

    Returns:
        VerdictSummary dataclass.
    """
    verdict_status = _extract_verdict_status(verdict_text)
    current_issues = extract_blocking_issues(verdict_text)
    issue_count = len(current_issues)

    if prior_issues is not None:
        persisting, new = identify_persisting_issues(current_issues, prior_issues)
    else:
        persisting = []
        new = list(current_issues)

    return VerdictSummary(
        iteration=iteration,
        verdict=verdict_status,
        issue_count=issue_count,
        persisting_issues=persisting,
        new_issues=new,
    )


def format_summary_line(summary: VerdictSummary) -> str:
    """Render a VerdictSummary as a single human-readable markdown line.

    Format:
        - Iteration {N}: {VERDICT} — {count} issues ({M} persists: "desc1", "desc2"; {K} new)

    Args:
        summary: VerdictSummary to format.

    Returns:
        Single markdown line string.
    """
    persist_count = len(summary.persisting_issues)
    new_count = len(summary.new_issues)

    if persist_count > 0:
        persist_descs = ", ".join(f'"{desc}"' for desc in summary.persisting_issues)
        persist_part = f"{persist_count} persists: {persist_descs}"
    else:
        persist_part = "0 persists"

    return (
        f"- Iteration {summary.iteration}: {summary.verdict} — "
        f"{summary.issue_count} issues ({persist_part}; {new_count} new)"
    )
```

### 6.5 `assemblyzero/workflows/requirements/feedback_window.py` (Add)

**Complete file contents:**

```python
"""Feedback window assembly for bounded verdict history.

Issue #497: Bounded Verdict History in LLD Revision Loop

Assembles a bounded feedback block from verdict history, keeping the latest
verdict verbatim and summarizing all prior verdicts. Enforces a token budget
using tiktoken.
"""

import logging
from dataclasses import dataclass

import tiktoken

from assemblyzero.workflows.requirements.verdict_summarizer import (
    VerdictSummary,
    extract_blocking_issues,
    format_summary_line,
    summarize_verdict,
)

logger = logging.getLogger(__name__)

# Module-level counter for observability
feedback_window_truncation_count: int = 0


@dataclass
class FeedbackWindow:
    """Assembled feedback block ready for prompt insertion."""

    latest_verdict_full: str
    prior_summaries: list[VerdictSummary]
    total_tokens: int
    was_truncated: bool


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: String to count tokens for.
        model: Tiktoken encoding name. Default "cl100k_base".

    Returns:
        Integer token count.
    """
    if not text:
        return 0
    encoding = tiktoken.get_encoding(model)
    return len(encoding.encode(text))


def build_feedback_block(
    verdict_history: list[str],
    token_budget: int = 4000,
) -> FeedbackWindow:
    """Assemble a bounded feedback block from verdict history.

    Algorithm:
    1. If verdict_history is empty, return empty FeedbackWindow.
    2. Reserve the latest verdict verbatim.
    3. Summarize all prior verdicts (with persistence detection).
    4. Assemble: latest verdict + prior summary lines.
    5. If total tokens exceed budget, progressively drop oldest summary lines.
    6. Log warning and increment counter if truncation occurred.

    Args:
        verdict_history: List of verdict strings, ordered oldest-first.
            Index 0 = iteration 1's verdict.
        token_budget: Maximum tokens for the entire feedback block. Default 4000.

    Returns:
        FeedbackWindow dataclass with assembled content and metadata.
    """
    global feedback_window_truncation_count

    if not verdict_history:
        return FeedbackWindow(
            latest_verdict_full="",
            prior_summaries=[],
            total_tokens=0,
            was_truncated=False,
        )

    latest_verdict = verdict_history[-1]
    latest_tokens = count_tokens(latest_verdict)

    # If latest verdict alone exceeds budget, still include it (priority)
    if latest_tokens >= token_budget:
        logger.warning(
            "Latest verdict alone exceeds token budget (%d >= %d)",
            latest_tokens,
            token_budget,
        )
        feedback_window_truncation_count += 1
        return FeedbackWindow(
            latest_verdict_full=latest_verdict,
            prior_summaries=[],
            total_tokens=latest_tokens,
            was_truncated=True,
        )

    remaining_budget = token_budget - latest_tokens

    # Summarize prior verdicts
    prior_verdicts = verdict_history[:-1]
    summaries: list[VerdictSummary] = []
    prev_issues: list[str] | None = None

    for i, verdict in enumerate(prior_verdicts):
        iteration = i + 1
        summary = summarize_verdict(verdict, iteration, prior_issues=prev_issues)
        summaries.append(summary)
        prev_issues = extract_blocking_issues(verdict)

    # Build summary lines and check budget
    summary_lines = [format_summary_line(s) for s in summaries]
    summary_block = "\n".join(summary_lines)
    summary_tokens = count_tokens(summary_block)

    truncated = False
    while summary_tokens > remaining_budget and summary_lines:
        # Drop oldest summary first
        summary_lines.pop(0)
        summaries.pop(0)
        summary_block = "\n".join(summary_lines)
        summary_tokens = count_tokens(summary_block)
        truncated = True

    if truncated:
        logger.warning(
            "Feedback window truncated: dropped oldest summaries to fit budget"
        )
        feedback_window_truncation_count += 1

    total_tokens = latest_tokens + summary_tokens

    return FeedbackWindow(
        latest_verdict_full=latest_verdict,
        prior_summaries=summaries,
        total_tokens=total_tokens,
        was_truncated=truncated,
    )


def render_feedback_markdown(window: FeedbackWindow) -> str:
    """Render a FeedbackWindow as a markdown string for prompt insertion.

    Output format:
        ## Review Feedback (Iteration {N})
        {latest_verdict_full}

        ## Prior Review Summary
        - Iteration 1: BLOCKED — 3 issues (0 persists; 3 new)
        - Iteration 2: BLOCKED — 2 issues (1 persists: "..."; 1 new)

    If no prior summaries exist, the "Prior Review Summary" section is omitted.
    If verdict_history was empty, returns empty string.

    Args:
        window: FeedbackWindow to render.

    Returns:
        Markdown string ready for prompt insertion.
    """
    if not window.latest_verdict_full:
        return ""

    # Determine current iteration number:
    # latest is the Nth verdict where N = len(prior_summaries) + 1
    current_iteration = len(window.prior_summaries) + 1

    parts: list[str] = []
    parts.append(f"## Review Feedback (Iteration {current_iteration})")
    parts.append(window.latest_verdict_full)

    if window.prior_summaries:
        parts.append("")  # blank line separator
        parts.append("## Prior Review Summary")
        for summary in window.prior_summaries:
            parts.append(format_summary_line(summary))

    return "\n".join(parts)
```

### 6.6 `assemblyzero/workflows/requirements/nodes/generate_draft.py` (Modify)

**Change 1:** Add imports after the existing `from assemblyzero.workflows.requirements.state import RequirementsWorkflowState` line.

```diff
 from assemblyzero.workflows.requirements.state import RequirementsWorkflowState
+from assemblyzero.workflows.requirements.feedback_window import (
+    build_feedback_block,
+    render_feedback_markdown,
+)
```

**Change 2:** Replace the cumulative verdict history block in `_build_prompt()`. Search for the string `"## ALL Gemini Review Feedback (CUMULATIVE)"` or the `"\n\n".join(verdict_history)` expression. Find this block:

```python
    verdict_history = state.get("verdict_history", [])
    if verdict_history:
        feedback_section = "## ALL Gemini Review Feedback (CUMULATIVE)\n" + "\n\n".join(verdict_history)
        prompt_parts.append(feedback_section)
```

Replace with:

```python
    verdict_history = state.get("verdict_history", [])
    if verdict_history:
        window = build_feedback_block(verdict_history)
        feedback_section = render_feedback_markdown(window)
        if feedback_section:
            prompt_parts.append(feedback_section)
```

**Note:** The exact line numbers (~256-259) should be confirmed by inspecting the actual file. The pattern to search for is `"## ALL Gemini Review Feedback (CUMULATIVE)"` or the `"\n\n".join(verdict_history)` expression. Replace the 2-line assignment and append with the 4-line block above.

### 6.7 `tests/unit/test_verdict_summarizer.py` (Add)

**Complete file contents:**

```python
"""Unit tests for verdict_summarizer module.

Issue #497: Bounded Verdict History in LLD Revision Loop
"""

import json
import logging
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.verdict_summarizer import (
    VerdictSummary,
    extract_blocking_issues,
    format_summary_line,
    identify_persisting_issues,
    summarize_verdict,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "verdict_analyzer"


@pytest.fixture
def json_verdict_iter1() -> str:
    """Load iteration 1 JSON verdict fixture."""
    return (FIXTURES_DIR / "sample_verdict_iteration_1.json").read_text()


@pytest.fixture
def json_verdict_iter2() -> str:
    """Load iteration 2 JSON verdict fixture."""
    return (FIXTURES_DIR / "sample_verdict_iteration_2.json").read_text()


@pytest.fixture
def json_verdict_iter3() -> str:
    """Load iteration 3 JSON verdict fixture."""
    return (FIXTURES_DIR / "sample_verdict_iteration_3.json").read_text()


@pytest.fixture
def text_verdict_blocked() -> str:
    """Text-format blocked verdict."""
    return (
        "## Verdict: BLOCKED\n\n"
        "### Blocking Issues\n"
        "- **[BLOCKING]** Missing error handling for API timeout\n"
        "- **[BLOCKING]** No rollback plan for database migration\n"
        "- **[BLOCKING]** Security section omits OWASP references"
    )


# ── Test ID 080: JSON-format verdict correctly parsed (REQ-7) ──


class TestExtractBlockingIssuesJSON:
    def test_json_format_extracts_issues(self, json_verdict_iter1: str):
        """Test ID 080: JSON-format verdict correctly parsed."""
        issues = extract_blocking_issues(json_verdict_iter1)
        assert len(issues) == 3
        assert "Missing error handling for API timeout" in issues
        assert "No rollback plan for database migration" in issues
        assert "Security section omits OWASP references" in issues

    def test_json_approved_returns_empty(self, json_verdict_iter3: str):
        """Approved JSON verdict returns empty list."""
        issues = extract_blocking_issues(json_verdict_iter3)
        assert issues == []

    def test_json_iter2_extracts_two_issues(self, json_verdict_iter2: str):
        """JSON verdict iteration 2 returns 2 issues."""
        issues = extract_blocking_issues(json_verdict_iter2)
        assert len(issues) == 2
        assert "No rollback plan for database migration" in issues
        assert "Test coverage section missing edge cases" in issues


# ── Test ID 085: Text-format verdict correctly parsed (REQ-7) ──


class TestExtractBlockingIssuesText:
    def test_text_format_extracts_issues(self, text_verdict_blocked: str):
        """Test ID 085: Text-format verdict correctly parsed."""
        issues = extract_blocking_issues(text_verdict_blocked)
        assert len(issues) == 3
        assert "Missing error handling for API timeout" in issues
        assert "No rollback plan for database migration" in issues
        assert "Security section omits OWASP references" in issues

    def test_text_alternative_blocking_format(self):
        """Text verdict with **BLOCKING** (no brackets) variant."""
        text = "- **BLOCKING** Some issue description"
        issues = extract_blocking_issues(text)
        assert len(issues) == 1
        assert "Some issue description" in issues

    def test_empty_string_returns_empty(self):
        """Empty verdict text returns empty list."""
        assert extract_blocking_issues("") == []
        assert extract_blocking_issues("   ") == []


# ── Test ID 095: Malformed JSON falls back to text parsing with warning (REQ-7) ──


class TestExtractBlockingIssuesFallback:
    def test_malformed_json_falls_back_with_warning(self, caplog):
        """Test ID 095: Malformed JSON falls back to text parsing."""
        malformed = '{invalid json\n- **[BLOCKING]** Fallback issue found'
        with caplog.at_level(logging.WARNING):
            issues = extract_blocking_issues(malformed)
        assert "Fallback issue found" in issues
        assert any("falling back to text extraction" in r.message for r in caplog.records)


# ── Test ID 040: Persisting issue flagged across consecutive iterations (REQ-4) ──


class TestIdentifyPersistingIssues:
    def test_exact_match_is_persisting(self):
        """Test ID 040: Exact match detected as persisting."""
        current = ["No rollback plan for database migration"]
        prior = [
            "Missing error handling for API timeout",
            "No rollback plan for database migration",
        ]
        persisting, new = identify_persisting_issues(current, prior)
        assert persisting == ["No rollback plan for database migration"]
        assert new == []

    # ── Test ID 045: Persisting issue detected with minor rephrasing (REQ-4) ──

    def test_rephrased_issue_detected_as_persisting(self):
        """Test ID 045: Minor rephrasing still detected as persisting."""
        current = ["Missing rollback plan for database migration"]
        prior = ["No rollback plan for database migration"]
        persisting, new = identify_persisting_issues(current, prior)
        assert len(persisting) == 1
        assert "Missing rollback plan for database migration" in persisting
        assert new == []

    # ── Test ID 050: Non-persisting issues classified as new (REQ-4) ──

    def test_different_issue_is_new(self):
        """Test ID 050: Completely different issue classified as new."""
        current = ["Test coverage section missing edge cases"]
        prior = ["Missing error handling for API timeout"]
        persisting, new = identify_persisting_issues(current, prior)
        assert persisting == []
        assert new == ["Test coverage section missing edge cases"]

    def test_empty_current_returns_empty(self):
        """Empty current issues returns empty tuples."""
        persisting, new = identify_persisting_issues([], ["some issue"])
        assert persisting == []
        assert new == []

    def test_empty_prior_all_new(self):
        """Empty prior issues means all current are new.

        Input: current_issues=["issue1", "issue2"], prior_issues=[]
        Output: persisting=[], new=["issue1", "issue2"]
        """
        current = ["issue1", "issue2"]
        persisting, new = identify_persisting_issues(current, [])
        assert persisting == []
        assert new == ["issue1", "issue2"]

    def test_mixed_persisting_and_new(self):
        """Mixed: one persists, one new.

        Input: current=["No rollback plan for database migration",
                        "Test coverage section missing edge cases"],
               prior=["Missing error handling for API timeout",
                      "No rollback plan for database migration",
                      "Security section omits OWASP references"]
        Output: persisting=["No rollback plan for database migration"],
                new=["Test coverage section missing edge cases"]
        """
        current = [
            "No rollback plan for database migration",
            "Test coverage section missing edge cases",
        ]
        prior = [
            "Missing error handling for API timeout",
            "No rollback plan for database migration",
            "Security section omits OWASP references",
        ]
        persisting, new = identify_persisting_issues(current, prior)
        assert persisting == ["No rollback plan for database migration"]
        assert new == ["Test coverage section missing edge cases"]


# ── Tests for summarize_verdict ──


class TestSummarizeVerdict:
    def test_iteration_1_all_new(self, json_verdict_iter1: str):
        """Iteration 1 with no prior: all issues are new."""
        summary = summarize_verdict(json_verdict_iter1, iteration=1, prior_issues=None)
        assert summary.iteration == 1
        assert summary.verdict == "BLOCKED"
        assert summary.issue_count == 3
        assert summary.persisting_issues == []
        assert len(summary.new_issues) == 3

    def test_iteration_2_with_persistence(self, json_verdict_iter2: str):
        """Iteration 2 with prior issues: detects persistence."""
        prior = [
            "Missing error handling for API timeout",
            "No rollback plan for database migration",
            "Security section omits OWASP references",
        ]
        summary = summarize_verdict(json_verdict_iter2, iteration=2, prior_issues=prior)
        assert summary.iteration == 2
        assert summary.verdict == "BLOCKED"
        assert summary.issue_count == 2
        assert "No rollback plan for database migration" in summary.persisting_issues
        assert "Test coverage section missing edge cases" in summary.new_issues

    def test_approved_verdict(self, json_verdict_iter3: str):
        """Approved verdict has zero issues."""
        summary = summarize_verdict(json_verdict_iter3, iteration=3, prior_issues=[])
        assert summary.iteration == 3
        assert summary.verdict == "APPROVED"
        assert summary.issue_count == 0
        assert summary.persisting_issues == []
        assert summary.new_issues == []


# ── Test ID 035: Summary line format includes all required fields (REQ-3) ──


class TestFormatSummaryLine:
    def test_blocked_with_persisting(self):
        """Test ID 035: Summary line with persisting issues."""
        summary = VerdictSummary(
            iteration=2,
            verdict="BLOCKED",
            issue_count=2,
            persisting_issues=["No rollback plan for database migration"],
            new_issues=["Test coverage section missing edge cases"],
        )
        line = format_summary_line(summary)
        assert "Iteration 2" in line
        assert "BLOCKED" in line
        assert "2 issues" in line
        assert '1 persists: "No rollback plan for database migration"' in line
        assert "1 new" in line

    def test_blocked_all_new(self):
        """Summary line iteration 1, all new."""
        summary = VerdictSummary(
            iteration=1,
            verdict="BLOCKED",
            issue_count=3,
            persisting_issues=[],
            new_issues=["a", "b", "c"],
        )
        line = format_summary_line(summary)
        assert "Iteration 1" in line
        assert "BLOCKED" in line
        assert "3 issues" in line
        assert "0 persists" in line
        assert "3 new" in line

    def test_approved(self):
        """Approved verdict summary line."""
        summary = VerdictSummary(
            iteration=3,
            verdict="APPROVED",
            issue_count=0,
            persisting_issues=[],
            new_issues=[],
        )
        line = format_summary_line(summary)
        assert "Iteration 3" in line
        assert "APPROVED" in line
        assert "0 issues" in line

    def test_multiple_persisting(self):
        """Multiple persisting issues listed."""
        summary = VerdictSummary(
            iteration=3,
            verdict="BLOCKED",
            issue_count=3,
            persisting_issues=["issue1", "issue2"],
            new_issues=["issue3"],
        )
        line = format_summary_line(summary)
        assert '2 persists: "issue1", "issue2"' in line
        assert "1 new" in line
```

### 6.8 `tests/unit/test_feedback_window.py` (Add)

**Complete file contents:**

```python
"""Unit tests for feedback_window module.

Issue #497: Bounded Verdict History in LLD Revision Loop
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements import feedback_window as fw_module
from assemblyzero.workflows.requirements.feedback_window import (
    FeedbackWindow,
    build_feedback_block,
    count_tokens,
    render_feedback_markdown,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "verdict_analyzer"


@pytest.fixture
def json_verdict_iter1() -> str:
    return (FIXTURES_DIR / "sample_verdict_iteration_1.json").read_text()


@pytest.fixture
def json_verdict_iter2() -> str:
    return (FIXTURES_DIR / "sample_verdict_iteration_2.json").read_text()


@pytest.fixture
def json_verdict_iter3() -> str:
    return (FIXTURES_DIR / "sample_verdict_iteration_3.json").read_text()


@pytest.fixture(autouse=True)
def reset_truncation_counter():
    """Reset module-level truncation counter before each test."""
    fw_module.feedback_window_truncation_count = 0
    yield


def _make_large_verdict(token_target: int = 1500) -> str:
    """Create a large verdict text for budget testing.

    Generates a BLOCKED verdict with 50 issues, each containing a
    ~40 character padding string to inflate token count.

    Args:
        token_target: Approximate target token count (not exact).

    Returns:
        JSON verdict string of approximately token_target tokens.
    """
    issues = []
    for i in range(50):
        issues.append(
            {
                "id": i + 1,
                "description": f"Issue number {i + 1}: " + "x" * 40,
            }
        )
    return json.dumps({"verdict": "BLOCKED", "blocking_issues": issues})


# ── count_tokens tests ──


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_nonempty_string(self):
        tokens = count_tokens("Hello, world!")
        assert tokens > 0
        assert isinstance(tokens, int)


# ── Test ID 070: Empty verdict history returns empty feedback (REQ-6) ──


class TestBuildFeedbackBlockEmpty:
    def test_empty_history(self):
        """Test ID 070: Empty verdict history returns empty FeedbackWindow.

        Input: verdict_history=[]
        Output: FeedbackWindow(latest_verdict_full="", prior_summaries=[],
                               total_tokens=0, was_truncated=False)
        """
        window = build_feedback_block([])
        assert window.latest_verdict_full == ""
        assert window.prior_summaries == []
        assert window.total_tokens == 0
        assert window.was_truncated is False


# ── Test ID 020: Latest verdict included verbatim with single verdict (REQ-2) ──


class TestBuildFeedbackBlockSingle:
    def test_single_verdict(self, json_verdict_iter1: str):
        """Test ID 020: Single verdict is latest, no priors."""
        window = build_feedback_block([json_verdict_iter1])
        assert window.latest_verdict_full == json_verdict_iter1
        assert window.prior_summaries == []
        assert window.total_tokens > 0
        assert window.was_truncated is False


# ── Test ID 025: Latest verdict included verbatim with multiple verdicts (REQ-2) ──
# ── Test ID 030: Prior verdicts are summarized (REQ-3) ──


class TestBuildFeedbackBlockMultiple:
    def test_three_verdicts(
        self,
        json_verdict_iter1: str,
        json_verdict_iter2: str,
        json_verdict_iter3: str,
    ):
        """Test ID 025 + 030: Latest verbatim, priors summarized."""
        history = [json_verdict_iter1, json_verdict_iter2, json_verdict_iter3]
        window = build_feedback_block(history)

        # Latest verdict is the 3rd (approved)
        assert window.latest_verdict_full == json_verdict_iter3

        # Prior summaries: 2 entries (iter 1 and iter 2)
        assert len(window.prior_summaries) == 2
        assert window.prior_summaries[0].iteration == 1
        assert window.prior_summaries[0].verdict == "BLOCKED"
        assert window.prior_summaries[0].issue_count == 3
        assert window.prior_summaries[1].iteration == 2
        assert window.prior_summaries[1].verdict == "BLOCKED"
        assert window.prior_summaries[1].issue_count == 2

        # Persistence detection: iter 2 should have "No rollback plan" persisting
        assert any(
            "rollback" in issue.lower()
            for issue in window.prior_summaries[1].persisting_issues
        )

        assert window.total_tokens > 0
        assert window.was_truncated is False


# ── Test ID 010: Token budget caps feedback block (REQ-1) ──
# ── Test ID 015: Custom token budget (REQ-1) ──


class TestBuildFeedbackBlockBudget:
    def test_budget_enforced_with_5_verdicts(self):
        """Test ID 010: 5 verdicts, default budget, total_tokens <= 4000.

        Input: 5 large verdicts (each ~1500 tokens with 50 issues),
               token_budget=4000
        Output: window.total_tokens <= 4000,
                window.latest_verdict_full == verdicts[-1]
        """
        verdicts = [_make_large_verdict() for _ in range(5)]
        window = build_feedback_block(verdicts, token_budget=4000)
        assert window.total_tokens <= 4000
        assert window.latest_verdict_full == verdicts[-1]

    def test_custom_budget(self):
        """Test ID 015: Custom budget of 2000 respected.

        Input: 5 large verdicts (each ~1500 tokens), token_budget=2000
        Output: window.total_tokens <= 2000
        """
        verdicts = [_make_large_verdict() for _ in range(5)]
        window = build_feedback_block(verdicts, token_budget=2000)
        assert window.total_tokens <= 2000

    def test_latest_exceeds_budget_still_included(self, caplog):
        """Latest verdict exceeds budget but is still included.

        Input: 1 large verdict (~1500 tokens), token_budget=100
        Output: window.latest_verdict_full == large_verdict,
                window.was_truncated == True,
                warning logged about budget exceeded
        """
        large = _make_large_verdict(token_target=5000)
        with caplog.at_level(logging.WARNING):
            window = build_feedback_block([large], token_budget=100)
        assert window.latest_verdict_full == large
        assert window.was_truncated is True
        assert any("exceeds token budget" in r.message for r in caplog.records)


# ── Test ID 100: Budget truncation logs warning and increments counter (REQ-1) ──


class TestTruncationObservability:
    def test_truncation_logs_and_increments(self, caplog):
        """Test ID 100: Truncation logs warning and increments counter.

        Input: 5 large verdicts (~1500 tokens each), token_budget=2000
        Output: if was_truncated, then feedback_window_truncation_count >= 1
                and caplog contains warning with "truncat"
        """
        verdicts = [_make_large_verdict() for _ in range(5)]
        with caplog.at_level(logging.WARNING):
            window = build_feedback_block(verdicts, token_budget=2000)

        if window.was_truncated:
            assert fw_module.feedback_window_truncation_count >= 1
            assert any("truncat" in r.message.lower() for r in caplog.records)


# ── Test ID 060: Iteration 5 tokens within 20% of iteration 2 (REQ-5) ──


class TestTokenStability:
    def test_iter5_within_20pct_of_iter2(self):
        """Test ID 060: Token cost stability across iterations."""
        base_verdict = json.dumps(
            {
                "verdict": "BLOCKED",
                "blocking_issues": [
                    {"id": i, "description": f"Blocking issue {i}: " + "detail " * 20}
                    for i in range(1, 4)
                ],
            }
        )

        # 2-verdict history
        history_2 = [base_verdict, base_verdict]
        window_2 = build_feedback_block(history_2, token_budget=4000)

        # 5-verdict history
        history_5 = [base_verdict] * 5
        window_5 = build_feedback_block(history_5, token_budget=4000)

        tokens_2 = window_2.total_tokens
        tokens_5 = window_5.total_tokens

        assert tokens_2 > 0, "Iteration 2 should have non-zero tokens"
        assert tokens_5 > 0, "Iteration 5 should have non-zero tokens"

        pct_diff = abs(tokens_5 - tokens_2) / tokens_2
        assert pct_diff < 0.20, (
            f"Iteration 5 tokens ({tokens_5}) differ from iteration 2 ({tokens_2}) "
            f"by {pct_diff:.1%}, exceeding 20% threshold"
        )


# ── Test ID 075: Empty history renders to empty string (REQ-6) ──
# ── Test ID 120: Single verdict produces no Prior Review Summary (REQ-2) ──


class TestRenderFeedbackMarkdown:
    def test_empty_window_renders_empty(self):
        """Test ID 075: Empty window renders to empty string."""
        window = FeedbackWindow(
            latest_verdict_full="",
            prior_summaries=[],
            total_tokens=0,
            was_truncated=False,
        )
        assert render_feedback_markdown(window) == ""

    def test_single_verdict_no_prior_summary_header(
        self, json_verdict_iter1: str
    ):
        """Test ID 120: Single verdict — no 'Prior Review Summary' header."""
        window = build_feedback_block([json_verdict_iter1])
        rendered = render_feedback_markdown(window)
        assert "## Review Feedback" in rendered
        assert "Prior Review Summary" not in rendered
        assert json_verdict_iter1 in rendered

    def test_multiple_verdicts_includes_prior_summary(
        self,
        json_verdict_iter1: str,
        json_verdict_iter2: str,
        json_verdict_iter3: str,
    ):
        """Multiple verdicts include Prior Review Summary section."""
        history = [json_verdict_iter1, json_verdict_iter2, json_verdict_iter3]
        window = build_feedback_block(history)
        rendered = render_feedback_markdown(window)
        assert "## Review Feedback (Iteration 3)" in rendered
        assert "## Prior Review Summary" in rendered
        assert "Iteration 1:" in rendered
        assert "Iteration 2:" in rendered


# ── Test ID 090: Mixed format history (REQ-7) ──


class TestMixedFormat:
    def test_mixed_json_and_text(self, json_verdict_iter1: str):
        """Test ID 090: Mixed format history processed correctly."""
        text_verdict = (
            "## Verdict: BLOCKED\n\n"
            "### Blocking Issues\n"
            "- **[BLOCKING]** Some text-format issue"
        )
        history = [text_verdict, json_verdict_iter1]
        window = build_feedback_block(history)
        assert window.latest_verdict_full == json_verdict_iter1
        assert len(window.prior_summaries) == 1
        assert window.prior_summaries[0].verdict == "BLOCKED"
```

### 6.9 `tests/unit/test_generate_draft_feedback.py` (Add)

**Complete file contents:**

```python
"""Integration-style unit tests for generate_draft bounded feedback usage.

Issue #497: Bounded Verdict History in LLD Revision Loop
"""

from unittest.mock import MagicMock, patch

import pytest


# ── Test ID 110: generate_draft uses bounded feedback (REQ-1) ──


class TestGenerateDraftBoundedFeedback:
    @patch(
        "assemblyzero.workflows.requirements.nodes.generate_draft.build_feedback_block"
    )
    @patch(
        "assemblyzero.workflows.requirements.nodes.generate_draft.render_feedback_markdown"
    )
    def test_build_feedback_block_called_with_verdict_history(
        self,
        mock_render: MagicMock,
        mock_build: MagicMock,
    ):
        """Test ID 110: generate_draft calls build_feedback_block with verdict_history."""
        from assemblyzero.workflows.requirements.feedback_window import FeedbackWindow
        from assemblyzero.workflows.requirements.verdict_summarizer import (
            VerdictSummary,
        )

        # Set up mock return values
        mock_window = FeedbackWindow(
            latest_verdict_full="latest verdict text",
            prior_summaries=[],
            total_tokens=50,
            was_truncated=False,
        )
        mock_build.return_value = mock_window
        mock_render.return_value = "## Review Feedback (Iteration 1)\nlatest verdict text"

        # We test by importing _build_prompt and checking it calls our functions.
        # Since _build_prompt is internal, we verify the import path is correct
        # and the module-level imports resolve.
        from assemblyzero.workflows.requirements.nodes.generate_draft import (
            build_feedback_block,
            render_feedback_markdown,
        )

        # Verify the imports are our mocked versions
        assert build_feedback_block is mock_build
        assert render_feedback_markdown is mock_render

    def test_imports_resolve(self):
        """Verify that generate_draft can import the new modules."""
        # This test validates the import chain works
        from assemblyzero.workflows.requirements.feedback_window import (
            build_feedback_block,
            render_feedback_markdown,
        )

        assert callable(build_feedback_block)
        assert callable(render_feedback_markdown)
```

## 7. Pattern References

### 7.1 Node Implementation Pattern

**File:** `assemblyzero/workflows/requirements/nodes/generate_draft.py` (lines 1-30)

```python
"""N1: Generate draft node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Remove pre-review validation gate - Gemini answers open questions
...
"""

import re
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider
from assemblyzero.utils.cost_tracker import accumulate_node_cost, accumulate_node_tokens
```

**Relevance:** Module docstring convention (issue references), import grouping style (stdlib first, then internal). All new modules should follow this pattern.

### 7.2 State Access Pattern

**File:** `assemblyzero/workflows/requirements/nodes/generate_draft.py` (lines ~250-259)

```python
    verdict_history = state.get("verdict_history", [])
    if verdict_history:
        feedback_section = "## ALL Gemini Review Feedback (CUMULATIVE)\n" + "\n\n".join(verdict_history)
        prompt_parts.append(feedback_section)
```

**Relevance:** This is the exact code being replaced. Shows how `verdict_history` is accessed from state (via `.get()` with default) and how the feedback section is appended to `prompt_parts`. The replacement must follow the same flow: access state → build section → append to `prompt_parts`.

### 7.3 Test Fixture Loading Pattern

**File:** `tests/e2e/test_issue_workflow_mock.py` (lines 1-30)

```python
"""E2E tests for issue workflow with mocked LLM."""
import pytest
from pathlib import Path

# Fixture loading pattern
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
```

**Relevance:** Shows the canonical pattern for constructing fixture paths relative to test file location. All new test files use this same `Path(__file__).resolve().parent.parent / "fixtures"` pattern.

### 7.4 Workflow Module Organization Pattern

**File:** `assemblyzero/workflows/requirements/audit.py` (exists alongside `state.py` in the requirements workflow package)

**Relevance:** The new `verdict_summarizer.py` and `feedback_window.py` are placed at the same level as `audit.py` and `state.py` within the `assemblyzero/workflows/requirements/` package. This follows the existing convention of utility modules alongside the workflow's `nodes/` directory.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `from dataclasses import dataclass` | stdlib | `verdict_summarizer.py`, `feedback_window.py` |
| `import json` | stdlib | `verdict_summarizer.py` |
| `import logging` | stdlib | `verdict_summarizer.py`, `feedback_window.py` |
| `import re` | stdlib | `verdict_summarizer.py` |
| `from difflib import SequenceMatcher` | stdlib | `verdict_summarizer.py` |
| `from typing import Optional` | stdlib | `verdict_summarizer.py` |
| `import tiktoken` | `tiktoken>=0.9.0,<1.0.0` (in pyproject.toml) | `feedback_window.py` |
| `from assemblyzero.workflows.requirements.verdict_summarizer import VerdictSummary, extract_blocking_issues, format_summary_line, summarize_verdict` | internal (new) | `feedback_window.py` |
| `from assemblyzero.workflows.requirements.feedback_window import build_feedback_block, render_feedback_markdown` | internal (new) | `generate_draft.py` |

**New Dependencies:** None — `tiktoken` is already in `pyproject.toml`.

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| 010 | `build_feedback_block()` | 5 large verdicts (~1500 tokens each), budget=4000 | `total_tokens <= 4000` |
| 015 | `build_feedback_block()` | 5 large verdicts, budget=2000 | `total_tokens <= 2000` |
| 020 | `build_feedback_block()` | `[v1]` (single JSON verdict fixture) | `latest_verdict_full == v1`, `prior_summaries == []` |
| 025 | `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | `latest_verdict_full == v3` |
| 030 | `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) | 2 VerdictSummary in `prior_summaries` |
| 035 | `format_summary_line()` | `VerdictSummary(iter=2, BLOCKED, 2 issues, 1 persist)` | Contains `"Iteration 2"`, `"BLOCKED"`, `"2 issues"`, persist desc |
| 040 | `identify_persisting_issues()` | `current=["No rollback plan..."]`, `prior=["Missing error...", "No rollback plan..."]` | `(["No rollback plan..."], [])` |
| 045 | `identify_persisting_issues()` | `current=["Missing rollback plan..."]`, `prior=["No rollback plan..."]` | Persisting detected (similarity > 0.8) |
| 050 | `identify_persisting_issues()` | `current=["Test coverage..."]`, `prior=["Missing error..."]` | `([], ["Test coverage..."])` |
| 060 | `build_feedback_block()` | 2-verdict vs 5-verdict history with identical base verdict | `abs(t5 - t2) / t2 < 0.20` |
| 070 | `build_feedback_block()` | `[]` | `FeedbackWindow(latest="", prior=[], tokens=0, truncated=False)` |
| 075 | `render_feedback_markdown()` | Empty `FeedbackWindow` | `""` |
| 080 | `extract_blocking_issues()` | JSON verdict fixture string (3 issues) | `["Missing error handling...", "No rollback plan...", "Security section..."]` |
| 085 | `extract_blocking_issues()` | Text verdict with `**[BLOCKING]**` lines | `["Missing error handling...", "No rollback plan...", "Security section..."]` |
| 090 | `build_feedback_block()` | `[text_verdict, json_verdict]` | Valid `FeedbackWindow`, `prior_summaries[0].verdict == "BLOCKED"` |
| 095 | `extract_blocking_issues()` | `'{invalid json\n- **[BLOCKING]** Fallback issue found'` | `["Fallback issue found"]`, `logger.warning` captured |
| 100 | `build_feedback_block()` | 5 large verdicts, tight budget (2000) | `was_truncated=True`, counter incremented, warning logged |
| 110 | `generate_draft` import chain | Module-level mock patching | `build_feedback_block` and `render_feedback_markdown` importable and patchable |
| 120 | `render_feedback_markdown()` | Single-verdict `FeedbackWindow` | Contains `"## Review Feedback"`, not `"Prior Review Summary"` |

## 10. Implementation Notes

### 10.1 Error Handling Convention

All functions in `verdict_summarizer.py` and `feedback_window.py` use defensive programming:
- Empty/None inputs return sensible defaults (empty lists, zero counts)
- JSON parsing failures fall back gracefully with `logger.warning()` — never raise
- The `build_feedback_block` function always returns a valid `FeedbackWindow` — budget overruns result in `was_truncated=True` but never an exception

### 10.2 Logging Convention

Use Python standard `logging` module. Each module creates its own logger:
```python
logger = logging.getLogger(__name__)
```

Warning events:
- `logger.warning("Latest verdict alone exceeds token budget (%d >= %d)", ...)` — when single verdict > budget
- `logger.warning("Feedback window truncated: dropped oldest summaries to fit budget")` — when summaries are dropped
- `logger.warning("Verdict text starts with '{' but failed JSON parsing; falling back to text extraction")` — JSON parse failure

**Never use `print()`** — this is explicitly called out in the LLD.

### 10.3 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| Default `token_budget` | `4000` | Fits 1 full verdict (~2,000 tokens) + summaries for 3-4 prior iterations. Achieves ~20% stability target. |
| Default `similarity_threshold` | `0.8` | Conservative SequenceMatcher ratio. Catches rephrased issues without false positives on unrelated issues. |
| Default `model` (tiktoken) | `"cl100k_base"` | GPT-4/Claude-compatible encoding. Already used elsewhere in project. |

### 10.4 Module-Level Counter

The `feedback_window_truncation_count` is a simple module-level `int` variable in `feedback_window.py`. It is incremented each time truncation occurs. Tests must reset it via `fw_module.feedback_window_truncation_count = 0` before each test (handled by the `autouse` fixture in `test_feedback_window.py`).

### 10.5 Key Implementation Detail: Verdict Status Extraction

The `_extract_verdict_status()` helper function (private, in `verdict_summarizer.py`) handles extracting the verdict status ("BLOCKED"/"APPROVED"/"UNKNOWN") from both JSON and text formats. This is separate from `extract_blocking_issues()` because the verdict status is needed for the `VerdictSummary.verdict` field even when there are no blocking issues (e.g., APPROVED verdicts).

### 10.6 `__init__.py` Consideration

The `assemblyzero/workflows/requirements/` package likely already has an `__init__.py` file (since it contains `audit.py`, `state.py`, and the `nodes/` subpackage). No modification to `__init__.py` is needed — the new modules are imported directly by their full path.

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3)
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5)
- [x] Change instructions are diff-level specific (Section 6)
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9)

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #497 |
| Verdict | DRAFT |
| Date | 2026-02-28 |
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #497 |
| Verdict | APPROVED |
| Date | 2026-02-28 |
| Iterations | 1 |
| Finalized | 2026-02-28T23:08:05Z |

### Review Feedback Summary

The Implementation Spec is exceptional in its detail and executability. It provides full, parseable source code for the new modules (`verdict_summarizer.py` and `feedback_window.py`) and specific, anchored replacement instructions for `generate_draft.py`. The test plan is comprehensive, with concrete fixtures and input/output examples for all key functions. The use of `dataclasses` and specific error handling strategies (logging vs raising) is clearly defined.

## Suggestions
- In `verdict_summa...


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
    issue_workflow/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_gate/
    test_metrics/
    test_rag/
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
  telemetry/
  utils/
  workflow/
  workflows/
    implementation_spec/
      nodes/
    issue/
      nodes/
    lld/
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
  unleashed/
  handoff-log.md
```

Use these real paths — do NOT invent paths that don't exist.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_497.py
"""Test file for Issue #497.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from assemblyzero.workflows.requirements.verdict_summarizer import *  # noqa: F401, F403


# Fixtures for mocking
@pytest.fixture
def mock_external_service():
    """Mock external service for isolation."""
    # TODO: Implement mock
    yield None


# Unit Tests
# -----------

def test_010():
    """
    `build_feedback_block()` | 5 large verdicts (~1500 tokens each),
    budget=4000 | `total_tokens <= 4000`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_010 works correctly
    assert False, 'TDD RED: test_010 not implemented'


def test_015():
    """
    `build_feedback_block()` | 5 large verdicts, budget=2000 |
    `total_tokens <= 2000`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_015 works correctly
    assert False, 'TDD RED: test_015 not implemented'


def test_020():
    """
    `build_feedback_block()` | `[v1]` (single JSON verdict fixture) |
    `latest_verdict_full == v1`, `prior_summaries == []`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_020 works correctly
    assert False, 'TDD RED: test_020 not implemented'


def test_025():
    """
    `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) |
    `latest_verdict_full == v3`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_025 works correctly
    assert False, 'TDD RED: test_025 not implemented'


def test_030():
    """
    `build_feedback_block()` | `[v1, v2, v3]` (3 JSON verdict fixtures) |
    2 VerdictSummary in `prior_summaries`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_030 works correctly
    assert False, 'TDD RED: test_030 not implemented'


def test_035():
    """
    `format_summary_line()` | `VerdictSummary(iter=2, BLOCKED, 2 issues,
    1 persist)` | Contains `"Iteration 2"`, `"BLOCKED"`, `"2 issues"`,
    persist desc
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_035 works correctly
    assert False, 'TDD RED: test_035 not implemented'


def test_040():
    """
    `identify_persisting_issues()` | `current=["No rollback plan..."]`,
    `prior=["Missing error...", "No rollback plan..."]` | `(["No rollback
    plan..."], [])`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_040 works correctly
    assert False, 'TDD RED: test_040 not implemented'


def test_045():
    """
    `identify_persisting_issues()` | `current=["Missing rollback
    plan..."]`, `prior=["No rollback plan..."]` | Persisting detected
    (similarity > 0.8)
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_045 works correctly
    assert False, 'TDD RED: test_045 not implemented'


def test_050():
    """
    `identify_persisting_issues()` | `current=["Test coverage..."]`,
    `prior=["Missing error..."]` | `([], ["Test coverage..."])`
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
    `build_feedback_block()` | `abs(t5 - t2) / t2 < 0.20`
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
    `build_feedback_block()` | `[]` | `FeedbackWindow(latest="",
    prior=[], tokens=0, truncated=False)`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_070 works correctly
    assert False, 'TDD RED: test_070 not implemented'


def test_075():
    """
    `render_feedback_markdown()` | Empty `FeedbackWindow` | `""`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_075 works correctly
    assert False, 'TDD RED: test_075 not implemented'


def test_080():
    """
    `extract_blocking_issues()` | JSON verdict fixture string (3 issues)
    | `["Missing error handling...", "No rollback plan...", "Security
    section..."]`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_080 works correctly
    assert False, 'TDD RED: test_080 not implemented'


def test_085():
    """
    `extract_blocking_issues()` | Text verdict with `**[BLOCKING]**`
    lines | `["Missing error handling...", "No rollback plan...",
    "Security section..."]`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_085 works correctly
    assert False, 'TDD RED: test_085 not implemented'


def test_090():
    """
    `build_feedback_block()` | `[text_verdict, json_verdict]` | Valid
    `FeedbackWindow`, `prior_summaries[0].verdict == "BLOCKED"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_090 works correctly
    assert False, 'TDD RED: test_090 not implemented'


def test_095():
    """
    `extract_blocking_issues()` | `'{invalid json\n- **[BLOCKING]**
    Fallback issue found'` | `["Fallback issue found"]`, `logger.warning`
    captured
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_095 works correctly
    assert False, 'TDD RED: test_095 not implemented'


def test_100():
    """
    `build_feedback_block()` | 5 large verdicts, tight budget (2000) |
    `was_truncated=True`, counter incremented, warning logged
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_100 works correctly
    assert False, 'TDD RED: test_100 not implemented'


def test_110(mock_external_service):
    """
    `generate_draft` import chain | Module-level mock patching |
    `build_feedback_block` and `render_feedback_markdown` importable and
    patchable
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_110 works correctly
    assert False, 'TDD RED: test_110 not implemented'


def test_120():
    """
    `render_feedback_markdown()` | Single-verdict `FeedbackWindow` |
    Contains `"## Review Feedback"`, not `"Prior Review Summary"`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_120 works correctly
    assert False, 'TDD RED: test_120 not implemented'




```

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the JSON data.

```json
# Your JSON data here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the JSON data in a single fenced code block
