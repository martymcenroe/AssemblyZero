# Implementation Request: tests/fixtures/lld_tracking/sample_lld_with_review.md

## Task

Write the complete contents of `tests/fixtures/lld_tracking/sample_lld_with_review.md`.

Change type: Add
Description: LLD content containing a Gemini review section

## LLD Specification

# Implementation Spec: Test: Add Unit Tests for LLD Audit Tracking Functions

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #435 |
| LLD | `docs/lld/active/435-test-lld-audit-tracking.md` |
| Generated | 2026-02-25 |
| Status | DRAFT |

## 1. Overview

*Add 22 unit tests covering four untested LLD audit tracking functions (`detect_gemini_review`, `embed_review_evidence`, `load_lld_tracking`, `update_lld_status`) plus a project conventions check. Tests use pytest with `tmp_path` for file I/O isolation and static fixture files for complex LLD content.*

**Objective:** Achieve ≥95% branch coverage of the four target functions with comprehensive happy-path, edge-case, and error-case tests.

**Success Criteria:** All 22 test scenarios pass; ≥95% branch coverage; tests run in CI without external dependencies.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `tests/fixtures/lld_tracking/sample_lld_with_review.md` | Add | LLD content containing a Gemini review section |
| 2 | `tests/fixtures/lld_tracking/sample_lld_no_review.md` | Add | LLD content with no review section |
| 3 | `tests/fixtures/lld_tracking/sample_tracking.json` | Add | Valid LLD tracking JSON with multiple entries |
| 4 | `tests/fixtures/lld_tracking/sample_tracking_corrupt.json` | Add | Corrupt/invalid JSON for error testing |
| 5 | `tests/unit/test_lld_tracking.py` | Add | Unit tests for all four LLD audit tracking functions |

**Implementation Order Rationale:** Fixtures must exist before the test file can load them. The directory is created first, then fixture files, then the test module that depends on them.

## 3. Current State (for Modify/Delete files)

*No files are being modified or deleted. All files are new additions.*

### 3.1 Source Module Discovery

**Pre-implementation step (MANDATORY):** Before writing tests, locate the exact module containing the four target functions:

```bash
# Find the source module
grep -rn "def detect_gemini_review" assemblyzero/
grep -rn "def embed_review_evidence" assemblyzero/
grep -rn "def load_lld_tracking" assemblyzero/
grep -rn "def update_lld_status" assemblyzero/
```

The import path discovered here replaces the placeholder `assemblyzero.MODULE_NAME` used throughout this spec. If functions are spread across multiple modules, adjust imports accordingly.

**Fallback search paths** (if `assemblyzero/` yields nothing):

```bash
grep -rn "def detect_gemini_review" tools/
grep -rn "def detect_gemini_review" src/
grep -rn "def detect_gemini_review" .
```

### 3.2 Existing Test Patterns

**File:** `tests/test_audit.py` (lines 1–30, representative of project test style)

**What to extract from this pattern:**
- Import conventions (absolute imports from `assemblyzero.*`)
- Assertion style (bare `assert` vs `pytest.raises`)
- Fixture usage patterns (`tmp_path`, `@pytest.fixture`)
- Docstring conventions

**File:** `tests/unit/test_gate/` (directory)

**What to extract:** Confirms the project uses `tests/unit/` for unit-level tests and that subdirectories/files within `tests/unit/` are valid locations.

### 3.3 Existing Fixtures Directory

**File:** `tests/fixtures/` (directory listing)

Existing subdirectories confirm the pattern for adding `tests/fixtures/lld_tracking/`:
- `tests/fixtures/metrics/`
- `tests/fixtures/mock_lineage/`
- `tests/fixtures/mock_repo/`
- `tests/fixtures/scout/`
- `tests/fixtures/scraper/`
- `tests/fixtures/verdict_analyzer/`

New directory `tests/fixtures/lld_tracking/` follows this established naming convention.

## 4. Data Structures

### 4.1 LLDTrackingEntry

**Definition:**

```python
class LLDTrackingEntry(TypedDict):
    issue_id: int
    lld_path: str
    status: str                    # "draft" | "reviewed" | "approved" | "rejected"
    gemini_reviewed: bool
    review_verdict: Optional[str]  # "APPROVED" | "REJECTED" | None
    review_timestamp: Optional[str]
    evidence_embedded: bool
```

**Concrete Example:**

```json
{
    "issue_id": 100,
    "lld_path": "docs/lld/active/100-feature-example.md",
    "status": "approved",
    "gemini_reviewed": true,
    "review_verdict": "APPROVED",
    "review_timestamp": "2026-02-20T14:30:00Z",
    "evidence_embedded": true
}
```

### 4.2 ReviewEvidence

**Definition:**

```python
class ReviewEvidence(TypedDict):
    reviewer: str
    verdict: str
    comments: list[str]
    timestamp: str
    model: Optional[str]
```

**Concrete Example:**

```json
{
    "reviewer": "Gemini",
    "verdict": "APPROVED",
    "comments": ["Design is sound", "No security concerns identified"],
    "timestamp": "2026-02-25T10:00:00Z",
    "model": "gemini-2.5-pro"
}
```

### 4.3 TrackingFile (top-level JSON structure)

**Concrete Example:**

```json
{
    "100": {
        "issue_id": 100,
        "lld_path": "docs/lld/active/100-feature-example.md",
        "status": "approved",
        "gemini_reviewed": true,
        "review_verdict": "APPROVED",
        "review_timestamp": "2026-02-20T14:30:00Z",
        "evidence_embedded": true
    },
    "200": {
        "issue_id": 200,
        "lld_path": "docs/lld/active/200-bugfix-example.md",
        "status": "draft",
        "gemini_reviewed": false,
        "review_verdict": null,
        "review_timestamp": null,
        "evidence_embedded": false
    },
    "300": {
        "issue_id": 300,
        "lld_path": "docs/lld/active/300-docs-example.md",
        "status": "reviewed",
        "gemini_reviewed": true,
        "review_verdict": "REJECTED",
        "review_timestamp": "2026-02-24T09:15:00Z",
        "evidence_embedded": false
    }
}
```

## 5. Function Specifications

*These are the functions UNDER TEST — not functions being implemented. Each spec details the behavior being tested.*

### 5.1 `detect_gemini_review()`

**File:** `assemblyzero/MODULE_NAME.py` (discover via grep — see Section 3.1)

**Signature:**

```python
def detect_gemini_review(lld_content: str) -> bool:
    """Detect whether an LLD contains a Gemini review section."""
    ...
```

**Input Example:**

```python
lld_content = """# 100 - Feature Example

## 1. Context & Goal
Some context here.

## Appendix: Review Log

### Gemini Review

| Field | Value |
|-------|-------|
| Verdict | APPROVED |
| Date | 2026-02-20 |
"""
```

**Output Example:**

```python
True
```

**Edge Cases:**
- Empty string `""` → returns `False`
- LLD with no review section → returns `False`
- LLD with partial/malformed review markers → returns `False`
- LLD with multiple Gemini review sections → returns `True`

### 5.2 `embed_review_evidence()`

**File:** `assemblyzero/MODULE_NAME.py`

**Signature:**

```python
def embed_review_evidence(lld_content: str, evidence: dict) -> str:
    """Embed review evidence into LLD content, returning updated content."""
    ...
```

**Input Example:**

```python
lld_content = "# 100 - Feature Example\n\n## 1. Context & Goal\nSome context.\n"
evidence = {
    "reviewer": "Gemini",
    "verdict": "APPROVED",
    "comments": ["Design is sound"],
    "timestamp": "2026-02-25T10:00:00Z",
    "model": "gemini-2.5-pro"
}
```

**Output Example:**

```python
"""# 100 - Feature Example

## 1. Context & Goal
Some context.

## Review Evidence

| Field | Value |
|-------|-------|
| Reviewer | Gemini |
| Verdict | APPROVED |
| Model | gemini-2.5-pro |
| Timestamp | 2026-02-25T10:00:00Z |

### Comments
- Design is sound
"""
```

**Edge Cases:**
- Empty evidence `{}` → raises `ValueError` or returns content unchanged
- Empty LLD content `""` → raises `ValueError` or returns minimal content with evidence
- LLD with existing evidence → updates (not duplicates) the section
- Evidence with all optional fields → all fields appear in output

### 5.3 `load_lld_tracking()`

**File:** `assemblyzero/MODULE_NAME.py`

**Signature:**

```python
def load_lld_tracking(tracking_path: Path) -> dict:
    """Load LLD tracking data from a JSON file."""
    ...
```

**Input Example:**

```python
tracking_path = Path("/tmp/pytest-xxx/test_load/lld_tracking.json")
# File contains valid JSON as in Section 4.3
```

**Output Example:**

```python
{
    "100": {"issue_id": 100, "lld_path": "docs/lld/active/100-feature-example.md", "status": "approved", "gemini_reviewed": True, "review_verdict": "APPROVED", "review_timestamp": "2026-02-20T14:30:00Z", "evidence_embedded": True},
    "200": {"issue_id": 200, "lld_path": "docs/lld/active/200-bugfix-example.md", "status": "draft", "gemini_reviewed": False, "review_verdict": None, "review_timestamp": None, "evidence_embedded": False},
    "300": {"issue_id": 300, "lld_path": "docs/lld/active/300-docs-example.md", "status": "reviewed", "gemini_reviewed": True, "review_verdict": "REJECTED", "review_timestamp": "2026-02-24T09:15:00Z", "evidence_embedded": False},
}
```

**Edge Cases:**
- File not found → raises `FileNotFoundError` or returns `{}`
- Corrupt JSON → raises `json.JSONDecodeError` or returns `{}`
- Empty file → returns `{}`
- Valid file with multiple entries → all entries returned

### 5.4 `update_lld_status()`

**File:** `assemblyzero/MODULE_NAME.py`

**Signature:**

```python
def update_lld_status(tracking_path: Path, issue_id: int, status: str, **kwargs) -> None:
    """Update the status of an LLD entry in the tracking file."""
    ...
```

**Input Example:**

```python
tracking_path = Path("/tmp/pytest-xxx/test_update/lld_tracking.json")
issue_id = 100
status = "approved"
# kwargs: gemini_reviewed=True, review_verdict="APPROVED"
```

**Output Example:**

```python
None  # Side effect: file at tracking_path updated
# After call, loading the file shows issue 100 with status="approved"
```

**Edge Cases:**
- Update existing entry → status changes, other fields preserved
- New entry (issue_id not in file) → entry added
- File doesn't exist → file created with single entry
- Extra kwargs → merged into entry
- Invalid status value → raises `ValueError`

### 5.5 `test_add_new_entry()` (Test Function)

**File:** `tests/unit/test_lld_tracking.py`

**Signature:**

```python
def test_add_new_entry(self, tmp_path: Path, sample_tracking_data: dict[str, Any]) -> None:
    """T180: Adding a status for an untracked issue creates a new entry."""
    ...
```

**Input Example:**

```python
# tmp_path = Path("/tmp/pytest-abc123/test_add_new_entry0/")
# sample_tracking_data = {
#     "100": {"issue_id": 100, "lld_path": "docs/lld/active/100-feature-example.md", "status": "approved", ...},
#     "200": {"issue_id": 200, "lld_path": "docs/lld/active/200-bugfix-example.md", "status": "draft", ...},
#     "300": {"issue_id": 300, "lld_path": "docs/lld/active/300-docs-example.md", "status": "reviewed", ...},
# }
# Writes sample_tracking_data to tmp_path / "tracking.json"
# Then calls: update_lld_status(tracking_file, issue_id=999, status="draft")
```

**Output Example:**

```python
# After execution:
# - tracking_file exists and is valid JSON
# - JSON contains key "999" (or 999) with entry {"status": "draft", ...}
# - JSON still contains keys "100", "200", "300" (original entries preserved)
# Test assertions:
#   assert entry is not None           # passes
#   assert entry["status"] == "draft"  # passes
#   assert ("100" in updated) or (100 in updated)  # passes
```

**Edge Cases:**
- If `update_lld_status` uses string keys, entry found via `updated.get("999")`
- If `update_lld_status` uses int keys, entry found via `updated.get(999)`
- The test handles both via `updated.get("999") or updated.get(999)`

## 6. Change Instructions

### 6.1 `tests/fixtures/lld_tracking/` (Add Directory)

**Action:** Create directory.

```bash
mkdir -p tests/fixtures/lld_tracking/
```

### 6.2 `tests/fixtures/lld_tracking/sample_lld_with_review.md` (Add)

**Complete file contents:**

```markdown
# 100 - Feature: Example Feature

<!-- Template Metadata
Last Updated: 2026-02-20
Updated By: Issue #100 LLD revision
-->

## 1. Context & Goal
* **Issue:** #100
* **Objective:** Example feature for testing

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `example.py` | Add | Example file |

## 3. Requirements

1. Example requirement

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type |
|----|----------|------|
| 010 | Example test | Auto |

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-20 | APPROVED | None |

### Gemini Review

| Field | Value |
|-------|-------|
| Reviewer | Gemini |
| Verdict | APPROVED |
| Model | gemini-2.5-pro |
| Timestamp | 2026-02-20T14:30:00Z |

#### Comments
- Design is sound and well-structured
- No security concerns identified
- Implementation approach is appropriate
```

### 6.3 `tests/fixtures/lld_tracking/sample_lld_no_review.md` (Add)

**Complete file contents:**

```markdown
# 200 - Feature: Another Example

<!-- Template Metadata
Last Updated: 2026-02-18
Updated By: Issue #200 LLD draft
-->

## 1. Context & Goal
* **Issue:** #200
* **Objective:** Another example feature for testing

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `another.py` | Add | Another example file |

## 3. Requirements

1. Another example requirement

## 10. Verification & Testing

### 10.1 Test Scenarios

| ID | Scenario | Type |
|----|----------|------|
| 010 | Another test | Auto |

## Appendix: Review Log

*No reviews yet.*
```

### 6.4 `tests/fixtures/lld_tracking/sample_tracking.json` (Add)

**Complete file contents:**

```json
{
    "100": {
        "issue_id": 100,
        "lld_path": "docs/lld/active/100-feature-example.md",
        "status": "approved",
        "gemini_reviewed": true,
        "review_verdict": "APPROVED",
        "review_timestamp": "2026-02-20T14:30:00Z",
        "evidence_embedded": true
    },
    "200": {
        "issue_id": 200,
        "lld_path": "docs/lld/active/200-bugfix-example.md",
        "status": "draft",
        "gemini_reviewed": false,
        "review_verdict": null,
        "review_timestamp": null,
        "evidence_embedded": false
    },
    "300": {
        "issue_id": 300,
        "lld_path": "docs/lld/active/300-docs-example.md",
        "status": "reviewed",
        "gemini_reviewed": true,
        "review_verdict": "REJECTED",
        "review_timestamp": "2026-02-24T09:15:00Z",
        "evidence_embedded": false
    }
}
```

### 6.5 `tests/fixtures/lld_tracking/sample_tracking_corrupt.json` (Add)

**Complete file contents:**

```
{"100": {"issue_id": 100, "status": "approved", "lld_path": "docs/lld/active/100.md"
```

*(Intentionally truncated — missing closing braces. This is valid corrupt JSON for testing `json.JSONDecodeError` handling.)*

### 6.6 `tests/unit/test_lld_tracking.py` (Add)

**Complete file contents:**

```python
"""Unit tests for LLD audit tracking functions.

Issue #435: Add comprehensive unit tests for detect_gemini_review,
embed_review_evidence, load_lld_tracking, and update_lld_status.

Source: docs/reports/done/95-test-report.md (test gap recommendation)
"""

import json
from pathlib import Path
from typing import Any

import pytest

# -----------------------------------------------------------------
# IMPORTANT: Discover the real module path before implementation.
# Run:
#   grep -rn "def detect_gemini_review" assemblyzero/
#   grep -rn "def embed_review_evidence" assemblyzero/
#   grep -rn "def load_lld_tracking" assemblyzero/
#   grep -rn "def update_lld_status" assemblyzero/
#
# Replace MODULE_NAME below with the actual module path.
# Example: from assemblyzero.lld_tracking import detect_gemini_review
# -----------------------------------------------------------------
from assemblyzero.MODULE_NAME import (
    detect_gemini_review,
    embed_review_evidence,
    load_lld_tracking,
    update_lld_status,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "lld_tracking"


@pytest.fixture
def lld_with_review() -> str:
    """Load sample LLD content that contains a Gemini review section."""
    return (FIXTURES_DIR / "sample_lld_with_review.md").read_text(encoding="utf-8")


@pytest.fixture
def lld_no_review() -> str:
    """Load sample LLD content with no review section."""
    return (FIXTURES_DIR / "sample_lld_no_review.md").read_text(encoding="utf-8")


@pytest.fixture
def tracking_json_path() -> Path:
    """Return the path to the valid sample tracking JSON fixture."""
    return FIXTURES_DIR / "sample_tracking.json"


@pytest.fixture
def tracking_corrupt_path() -> Path:
    """Return the path to the corrupt sample tracking JSON fixture."""
    return FIXTURES_DIR / "sample_tracking_corrupt.json"


@pytest.fixture
def valid_evidence() -> dict[str, Any]:
    """Return a valid review evidence payload with all fields populated."""
    return {
        "reviewer": "Gemini",
        "verdict": "APPROVED",
        "comments": ["Design is sound", "No security concerns identified"],
        "timestamp": "2026-02-25T10:00:00Z",
        "model": "gemini-2.5-pro",
    }


@pytest.fixture
def sample_tracking_data() -> dict[str, Any]:
    """Return in-memory tracking data matching sample_tracking.json."""
    return {
        "100": {
            "issue_id": 100,
            "lld_path": "docs/lld/active/100-feature-example.md",
            "status": "approved",
            "gemini_reviewed": True,
            "review_verdict": "APPROVED",
            "review_timestamp": "2026-02-20T14:30:00Z",
            "evidence_embedded": True,
        },
        "200": {
            "issue_id": 200,
            "lld_path": "docs/lld/active/200-bugfix-example.md",
            "status": "draft",
            "gemini_reviewed": False,
            "review_verdict": None,
            "review_timestamp": None,
            "evidence_embedded": False,
        },
        "300": {
            "issue_id": 300,
            "lld_path": "docs/lld/active/300-docs-example.md",
            "status": "reviewed",
            "gemini_reviewed": True,
            "review_verdict": "REJECTED",
            "review_timestamp": "2026-02-24T09:15:00Z",
            "evidence_embedded": False,
        },
    }


# ---------------------------------------------------------------------------
# T010-T050: TestDetectGeminiReview
# ---------------------------------------------------------------------------


class TestDetectGeminiReview:
    """Tests for detect_gemini_review() — 5 scenarios."""

    def test_returns_true_when_review_present(self, lld_with_review: str) -> None:
        """T010: LLD containing '### Gemini Review' section returns True."""
        result = detect_gemini_review(lld_with_review)
        assert result is True

    def test_returns_false_when_no_review(self, lld_no_review: str) -> None:
        """T020: LLD with no review markers returns False."""
        result = detect_gemini_review(lld_no_review)
        assert result is False

    def test_returns_false_for_empty_string(self) -> None:
        """T030: Empty string input returns False without raising."""
        result = detect_gemini_review("")
        assert result is False

    def test_returns_false_for_malformed_section(self) -> None:
        """T040: Partial/broken review markers return False (false-negative branch)."""
        malformed = (
            "# 400 - Example\n\n"
            "## Appendix: Review Log\n\n"
            "### Gemini Revi"  # truncated marker
        )
        result = detect_gemini_review(malformed)
        assert result is False

    def test_returns_true_for_multiple_reviews(self, lld_with_review: str) -> None:
        """T050: LLD with 2+ Gemini review sections still returns True."""
        second_review = (
            "\n\n### Gemini Review\n\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Verdict | APPROVED |\n"
            "| Date | 2026-02-25 |\n"
        )
        multi_review_content = lld_with_review + second_review
        result = detect_gemini_review(multi_review_content)
        assert result is True


# ---------------------------------------------------------------------------
# T060-T110: TestEmbedReviewEvidence
# ---------------------------------------------------------------------------


class TestEmbedReviewEvidence:
    """Tests for embed_review_evidence() — 6 scenarios."""

    def test_embeds_evidence_into_clean_lld(
        self, lld_no_review: str, valid_evidence: dict[str, Any]
    ) -> None:
        """T060: Embedding valid evidence into a clean LLD appends an evidence section."""
        result = embed_review_evidence(lld_no_review, valid_evidence)
        assert isinstance(result, str)
        assert len(result) > len(lld_no_review)
        # Evidence content must be present
        assert valid_evidence["verdict"] in result
        assert valid_evidence["reviewer"] in result
        assert valid_evidence["timestamp"] in result

    def test_no_duplication_on_existing_evidence(
        self, lld_no_review: str, valid_evidence: dict[str, Any]
    ) -> None:
        """T070: Embedding twice does not duplicate the evidence section (idempotency)."""
        first_pass = embed_review_evidence(lld_no_review, valid_evidence)
        second_pass = embed_review_evidence(first_pass, valid_evidence)
        # Count occurrences of the verdict — should appear exactly once
        # (or exactly the same number of times as after the first embed)
        verdict_count_first = first_pass.count(valid_evidence["verdict"])
        verdict_count_second = second_pass.count(valid_evidence["verdict"])
        assert verdict_count_second == verdict_count_first

    def test_empty_evidence_raises_or_unchanged(self, lld_no_review: str) -> None:
        """T080: Empty evidence dict raises ValueError or returns content unchanged."""
        try:
            result = embed_review_evidence(lld_no_review, {})
            # If no exception, content must be unchanged
            assert result == lld_no_review
        except (ValueError, KeyError, TypeError):
            # Acceptable — function rejects empty evidence
            pass

    def test_empty_content_raises_or_minimal(self, valid_evidence: dict[str, Any]) -> None:
        """T090: Empty LLD content raises ValueError or returns minimal valid output."""
        try:
            result = embed_review_evidence("", valid_evidence)
            # If no exception, result must contain evidence
            assert valid_evidence["verdict"] in result
        except (ValueError, TypeError):
            # Acceptable — function rejects empty content
            pass

    def test_preserves_existing_content(
        self, lld_no_review: str, valid_evidence: dict[str, Any]
    ) -> None:
        """T100: Original LLD sections remain intact after embedding evidence."""
        # Capture key sections from original
        assert "## 1. Context & Goal" in lld_no_review  # precondition
        assert "## 2. Proposed Changes" in lld_no_review  # precondition

        result = embed_review_evidence(lld_no_review, valid_evidence)
        assert "## 1. Context & Goal" in result
        assert "## 2. Proposed Changes" in result

    def test_all_optional_fields_present(
        self, lld_no_review: str, valid_evidence: dict[str, Any]
    ) -> None:
        """T110: Evidence with all fields (reviewer, verdict, comments, timestamp, model)
        has each field visible in the output."""
        result = embed_review_evidence(lld_no_review, valid_evidence)
        assert valid_evidence["reviewer"] in result
        assert valid_evidence["verdict"] in result
        assert valid_evidence["timestamp"] in result
        # Model is optional but provided — should appear
        assert valid_evidence["model"] in result
        # At least one comment should appear
        assert valid_evidence["comments"][0] in result


# ---------------------------------------------------------------------------
# T120-T160: TestLoadLLDTracking
# ---------------------------------------------------------------------------


class TestLoadLLDTracking:
    """Tests for load_lld_tracking() — 5 scenarios."""

    def test_loads_valid_json(self, tracking_json_path: Path) -> None:
        """T120: Valid tracking JSON returns parsed dict with expected keys."""
        result = load_lld_tracking(tracking_json_path)
        assert isinstance(result, dict)
        assert "100" in result or 100 in result
        # Verify structure of at least one entry
        entry = result.get("100") or result.get(100)
        assert entry is not None
        assert entry["issue_id"] == 100
        assert entry["status"] == "approved"

    def test_file_not_found(self, tmp_path: Path) -> None:
        """T130: Non-existent file raises FileNotFoundError or returns empty dict."""
        nonexistent = tmp_path / "does_not_exist.json"
        try:
            result = load_lld_tracking(nonexistent)
            # If no exception, must return empty dict
            assert result == {}
        except FileNotFoundError:
            # Acceptable behavior
            pass

    def test_corrupt_json(self, tracking_corrupt_path: Path) -> None:
        """T140: Corrupt JSON raises JSONDecodeError or returns empty dict."""
        try:
            result = load_lld_tracking(tracking_corrupt_path)
            # If no exception, must return empty dict
            assert result == {}
        except json.JSONDecodeError:
            # Acceptable behavior
            pass

    def test_empty_file(self, tmp_path: Path) -> None:
        """T150: Empty file returns empty dict (exercises empty-input branch)."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        try:
            result = load_lld_tracking(empty_file)
            assert result == {}
        except (json.JSONDecodeError, ValueError):
            # Also acceptable — depends on implementation
            pass

    def test_multiple_entries(
        self, tracking_json_path: Path, sample_tracking_data: dict[str, Any]
    ) -> None:
        """T160: Tracking file with 3 entries returns all entries correctly."""
        result = load_lld_tracking(tracking_json_path)
        assert isinstance(result, dict)
        # Must have all 3 entries
        # Handle both string and int keys
        keys = {str(k) for k in result.keys()}
        assert "100" in keys
        assert "200" in keys
        assert "300" in keys


# ---------------------------------------------------------------------------
# T170-T210: TestUpdateLLDStatus
# ---------------------------------------------------------------------------


class TestUpdateLLDStatus:
    """Tests for update_lld_status() — 5 scenarios."""

    def _write_tracking(self, path: Path, data: dict[str, Any]) -> None:
        """Helper: write tracking data as JSON to the given path."""
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read_tracking(self, path: Path) -> dict[str, Any]:
        """Helper: read tracking data from JSON at the given path."""
        return json.loads(path.read_text(encoding="utf-8"))

    def test_update_existing_entry(
        self, tmp_path: Path, sample_tracking_data: dict[str, Any]
    ) -> None:
        """T170: Updating an existing entry changes its status, preserving other fields."""
        tracking_file = tmp_path / "tracking.json"
        self._write_tracking(tracking_file, sample_tracking_data)

        update_lld_status(tracking_file, issue_id=100, status="rejected")

        updated = self._read_tracking(tracking_file)
        entry = updated.get("100") or updated.get(100)
        assert entry is not None
        assert entry["status"] == "rejected"
        # Other fields preserved
        assert entry["issue_id"] == 100
        assert entry["lld_path"] == "docs/lld/active/100-feature-example.md"

    def test_add_new_entry(
        self, tmp_path: Path, sample_tracking_data: dict[str, Any]
    ) -> None:
        """T180: Adding a status for an untracked issue creates a new entry.

        Input:
            - tmp_path: pytest-provided temporary directory (e.g., /tmp/pytest-abc123/test_add0/)
            - sample_tracking_data: dict with keys "100", "200", "300" (see fixture)
            - Writes sample_tracking_data to tmp_path / "tracking.json"
            - Calls update_lld_status(tracking_file, issue_id=999, status="draft")

        Expected Output:
            - tracking.json now contains a key "999" (or 999)
            - entry["status"] == "draft"
            - Original entries ("100", "200", "300") still present
        """
        tracking_file = tmp_path / "tracking.json"
        self._write_tracking(tracking_file, sample_tracking_data)

        update_lld_status(tracking_file, issue_id=999, status="draft")

        updated = self._read_tracking(tracking_file)
        entry = updated.get("999") or updated.get(999)
        assert entry is not None
        assert entry["status"] == "draft"
        # Original entries still present
        assert ("100" in updated) or (100 in updated)

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """T190: If the tracking file doesn't exist, it is created with a single entry."""
        tracking_file = tmp_path / "new_tracking.json"
        assert not tracking_file.exists()  # precondition

        update_lld_status(tracking_file, issue_id=500, status="draft")

        assert tracking_file.exists()
        data = self._read_tracking(tracking_file)
        entry = data.get("500") or data.get(500)
        assert entry is not None
        assert entry["status"] == "draft"

    def test_kwargs_merged_into_entry(
        self, tmp_path: Path, sample_tracking_data: dict[str, Any]
    ) -> None:
        """T200: Extra kwargs are merged into the entry (exercises kwargs branch)."""
        tracking_file = tmp_path / "tracking.json"
        self._write_tracking(tracking_file, sample_tracking_data)

        update_lld_status(
            tracking_file,
            issue_id=200,
            status="reviewed",
            gemini_reviewed=True,
            review_verdict="APPROVED",
            review_timestamp="2026-02-25T12:00:00Z",
        )

        updated = self._read_tracking(tracking_file)
        entry = updated.get("200") or updated.get(200)
        assert entry is not None
        assert entry["status"] == "reviewed"
        assert entry["gemini_reviewed"] is True
        assert entry["review_verdict"] == "APPROVED"
        assert entry["review_timestamp"] == "2026-02-25T12:00:00Z"

    def test_invalid_status_raises(
        self, tmp_path: Path, sample_tracking_data: dict[str, Any]
    ) -> None:
        """T210: Invalid status value raises ValueError (or handles gracefully)."""
        tracking_file = tmp_path / "tracking.json"
        self._write_tracking(tracking_file, sample_tracking_data)

        try:
            update_lld_status(tracking_file, issue_id=100, status="invalid_value")
            # If no exception, verify function handled it (e.g., clamped to valid)
            updated = self._read_tracking(tracking_file)
            entry = updated.get("100") or updated.get(100)
            # If it accepted the value, at least verify it was stored
            assert entry is not None
        except (ValueError, KeyError):
            # Acceptable — function validates status values
            pass


# ---------------------------------------------------------------------------
# T220: TestProjectConventions
# ---------------------------------------------------------------------------


class TestProjectConventions:
    """Verify the test file itself follows project conventions."""

    def test_file_location_and_naming(self) -> None:
        """T220: Test file at tests/unit/test_lld_tracking.py, classes named Test*."""
        this_file = Path(__file__).resolve()
        # File must be in tests/unit/
        assert this_file.parent.name == "unit"
        assert this_file.parent.parent.name == "tests"
        # File must be named test_lld_tracking.py
        assert this_file.name == "test_lld_tracking.py"

        # Verify all test classes follow Test* naming
        import inspect
        import sys

        current_module = sys.modules[__name__]
        test_classes = [
            name
            for name, obj in inspect.getmembers(current_module, inspect.isclass)
            if name.startswith("Test")
        ]
        assert len(test_classes) >= 5, (
            f"Expected at least 5 test classes, found {len(test_classes)}: {test_classes}"
        )
```

## 7. Pattern References

### 7.1 Existing Fixture Directory Structure

**File:** `tests/fixtures/` (directory)

**Existing subdirectories:** `metrics/`, `mock_lineage/`, `mock_repo/`, `scout/`, `scraper/`, `verdict_analyzer/`

**Relevance:** The new `tests/fixtures/lld_tracking/` directory follows the same pattern: a subdirectory named after the feature/module being tested, containing static test data files. This confirms the naming convention and location are consistent with the project.

### 7.2 Existing Unit Test Directory

**File:** `tests/unit/test_gate/` (directory)

**Relevance:** Confirms that `tests/unit/` is used for unit-level test files in this project. The new `tests/unit/test_lld_tracking.py` follows this convention. The `test_gate/` subdirectory shows test modules can be organized within `tests/unit/`.

### 7.3 Existing Test File Pattern

**File:** `tests/test_audit.py` (lines 1–30)

**Relevance:** Follow the import style, docstring format, and assertion patterns used in this existing test file. Specifically:
- How the project imports from `assemblyzero.*` modules
- Whether `pytest.fixture` functions use `yield` or `return`
- Whether tests use `assert x == y` or `assert x is True` style

### 7.4 Conftest Pattern

**File:** `tests/conftest.py`

**Relevance:** Check if there are shared fixtures defined here that could be reused (e.g., `tmp_path` wrappers, common data loaders). If any fixtures overlap with what this spec defines, prefer using the shared fixtures.

## 8. Dependencies & Imports

| Import | Source | Used In |
|--------|--------|---------|
| `json` | stdlib | `test_lld_tracking.py` |
| `pathlib.Path` | stdlib | `test_lld_tracking.py` |
| `typing.Any` | stdlib | `test_lld_tracking.py` |
| `pytest` | dev dependency (existing) | `test_lld_tracking.py` |
| `inspect` | stdlib | `test_lld_tracking.py` (T220 only) |
| `sys` | stdlib | `test_lld_tracking.py` (T220 only) |
| `assemblyzero.MODULE_NAME.detect_gemini_review` | internal (discover path) | `test_lld_tracking.py` |
| `assemblyzero.MODULE_NAME.embed_review_evidence` | internal (discover path) | `test_lld_tracking.py` |
| `assemblyzero.MODULE_NAME.load_lld_tracking` | internal (discover path) | `test_lld_tracking.py` |
| `assemblyzero.MODULE_NAME.update_lld_status` | internal (discover path) | `test_lld_tracking.py` |

**New Dependencies:** None. All imports are from stdlib or existing dev dependencies.

**Critical:** The `MODULE_NAME` placeholder must be replaced during implementation after running the grep commands in Section 3.1. If the four functions are spread across multiple modules, split the import into multiple `from` statements.

## 9. Test Mapping

| Test ID | Tests Function | Input | Expected Output |
|---------|---------------|-------|-----------------|
| T010 | `detect_gemini_review()` | Fixture `sample_lld_with_review.md` content (contains `### Gemini Review` heading) | `True` |
| T020 | `detect_gemini_review()` | Fixture `sample_lld_no_review.md` content (ends with `*No reviews yet.*`) | `False` |
| T030 | `detect_gemini_review()` | `""` | `False` |
| T040 | `detect_gemini_review()` | `"# 400 - Example\n\n## Appendix: Review Log\n\n### Gemini Revi"` (truncated marker) | `False` |
| T050 | `detect_gemini_review()` | Fixture with_review content + `"\n\n### Gemini Review\n\n| Field | Value |..."` appended | `True` |
| T060 | `embed_review_evidence()` | No-review fixture + `{"reviewer": "Gemini", "verdict": "APPROVED", "comments": ["Design is sound"], "timestamp": "2026-02-25T10:00:00Z", "model": "gemini-2.5-pro"}` | String containing `"APPROVED"`, `"Gemini"`, `"2026-02-25T10:00:00Z"` |
| T070 | `embed_review_evidence()` | Result of T060 + same evidence dict | Verdict count equals T060 verdict count (no duplication) |
| T080 | `embed_review_evidence()` | No-review fixture + `{}` | `ValueError`/`KeyError`/`TypeError` raised, OR returns original content unchanged |
| T090 | `embed_review_evidence()` | `""` + valid evidence dict | `ValueError`/`TypeError` raised, OR returns string containing verdict |
| T100 | `embed_review_evidence()` | No-review fixture + valid evidence | Output contains `"## 1. Context & Goal"` and `"## 2. Proposed Changes"` |
| T110 | `embed_review_evidence()` | No-review fixture + valid evidence (all fields) | Output contains `"Gemini"`, `"APPROVED"`, `"2026-02-25T10:00:00Z"`, `"gemini-2.5-pro"`, `"Design is sound"` |
| T120 | `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with key `"100"`, entry `{"issue_id": 100, "status": "approved", ...}` |
| T130 | `load_lld_tracking()` | `tmp_path / "does_not_exist.json"` | `FileNotFoundError` raised OR `{}` |
| T140 | `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking_corrupt.json")` | `json.JSONDecodeError` raised OR `{}` |
| T150 | `load_lld_tracking()` | `tmp_path / "empty.json"` (0 bytes) | `{}` OR `json.JSONDecodeError` |
| T160 | `load_lld_tracking()` | `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with keys `{"100", "200", "300"}` |
| T170 | `update_lld_status()` | File with 3 entries, `issue_id=100, status="rejected"` | File re-read: entry 100 has `status="rejected"`, `lld_path` unchanged |
| T180 | `update_lld_status()` | File with 3 entries (100, 200, 300), `issue_id=999, status="draft"` | File re-read: new entry 999 with `status="draft"`, keys 100/200/300 still present |
| T190 | `update_lld_status()` | Non-existent file path, `issue_id=500, status="draft"` | File created, re-read: entry 500 with `status="draft"` |
| T200 | `update_lld_status()` | File with 3 entries, `issue_id=200, status="reviewed", gemini_reviewed=True, review_verdict="APPROVED", review_timestamp="2026-02-25T12:00:00Z"` | Entry 200 has all kwargs merged: `gemini_reviewed=True`, `review_verdict="APPROVED"` |
| T210 | `update_lld_status()` | File with 3 entries, `issue_id=100, status="invalid_value"` | `ValueError` raised OR graceful handling (entry stored) |
| T220 | N/A (meta-test) | `Path(__file__)` introspection + `inspect.getmembers()` | File in `tests/unit/`, name `test_lld_tracking.py`, ≥5 `Test*` classes |

## 10. Implementation Notes

### 10.1 Source Module Discovery (CRITICAL FIRST STEP)

Before writing any code, the implementing agent **must** run:

```bash
grep -rn "def detect_gemini_review" assemblyzero/ tools/ src/
grep -rn "def embed_review_evidence" assemblyzero/ tools/ src/
grep -rn "def load_lld_tracking" assemblyzero/ tools/ src/
grep -rn "def update_lld_status" assemblyzero/ tools/ src/
```

The output determines:
1. The exact import path (replaces `assemblyzero.MODULE_NAME`)
2. Whether all four functions are in one module or spread across multiple
3. The actual function signatures (may differ slightly from LLD pseudocode)

**If signatures differ from this spec**, adapt the test assertions to match the real signatures. Document deviations in the implementation report.

**If functions are not found**, search the entire repository:
```bash
grep -rn "def detect_gemini_review" .
grep -rn "def embed_review_evidence" .
grep -rn "def load_lld_tracking" .
grep -rn "def update_lld_status" .
```

### 10.2 Error Handling Convention

Tests use a **try/except pattern** for behavior that the LLD marks as "raises X or returns Y":

```python
try:
    result = function_under_test(bad_input)
    # If no exception, assert the alternate acceptable behavior
    assert result == expected_fallback
except ExpectedError:
    # This is also acceptable
    pass
```

This pattern allows the tests to pass regardless of whether the function raises or returns a sentinel value. The tests are testing that the function **handles** the edge case — not prescribing a specific error handling mechanism.

### 10.3 Fixture Path Resolution

All fixture paths are resolved relative to the test file:

```python
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "lld_tracking"
```

This resolves to `tests/fixtures/lld_tracking/` regardless of the working directory when pytest is invoked.

### 10.4 Key/Type Flexibility for Tracking Data

The source implementation may use string keys (`"100"`) or integer keys (`100`) in the tracking dict. Tests handle both:

```python
entry = result.get("100") or result.get(100)
```

After discovering the actual implementation, simplify these to use only the correct key type.

### 10.5 Idempotency Testing Strategy (T070, T180)

- **T070** (embed_review_evidence): Embed once, embed again on the result, count verdict occurrences. Same count = idempotent.
- **T180** (update_lld_status new entry): Verify the entry exists after adding. Original entries must also still be present.

### 10.6 Constants

| Constant | Value | Rationale |
|----------|-------|-----------|
| `FIXTURES_DIR` | `Path(__file__).resolve().parent.parent / "fixtures" / "lld_tracking"` | Portable fixture resolution |
| Valid statuses (assumed) | `"draft"`, `"reviewed"`, `"approved"`, `"rejected"` | Based on LLD `LLDTrackingEntry` — confirm from source |
| Test class count | `>= 5` | 4 function classes + 1 conventions class |

---

## Completeness Checklist

- [x] Every "Modify" file has a current state excerpt (Section 3) — N/A, all files are Add
- [x] Every data structure has a concrete JSON/YAML example (Section 4)
- [x] Every function has input/output examples with realistic values (Section 5) — including `test_add_new_entry()` (Section 5.5)
- [x] Change instructions are diff-level specific (Section 6) — complete file contents for all Add files
- [x] Pattern references include file:line and are verified to exist (Section 7)
- [x] All imports are listed and verified (Section 8)
- [x] Test mapping covers all LLD test scenarios (Section 9) — all 22 test IDs mapped

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #435 |
| Verdict | DRAFT |
| Date | 2026-02-25 |
| Iterations | 2 |
| Finalized | — |

---

## Review Log

| Field | Value |
|-------|-------|
| Issue | #435 |
| Verdict | APPROVED |
| Date | 2026-02-26 |
| Iterations | 1 |
| Finalized | 2026-02-26T03:11:23Z |

### Review Feedback Summary

Approved with suggestions:
- The spec is excellent. The explicit instruction to discover the `MODULE_NAME` via `grep` before writing the test file is a perfect pattern for handling pre-existing code dependencies.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:

- `example.py`

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
    lld_tracking/
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

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero\tests\test_issue_435.py
"""Test file for Issue #435.

Generated by AssemblyZero TDD Testing Workflow.
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest


# Unit Tests
# -----------

def test_t010():
    """
    `detect_gemini_review()` | Fixture `sample_lld_with_review.md`
    content (contains `### Gemini Review` heading) | `True`
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
    `detect_gemini_review()` | Fixture `sample_lld_no_review.md` content
    (ends with `*No reviews yet.*`) | `False`
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
    `detect_gemini_review()` | `""` | `False`
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
    `detect_gemini_review()` | `"# 400 - Example\n\n## Appendix: Review
    Log\n\n### Gemini Revi"` (truncated marker) | `False`
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
    `detect_gemini_review()` | Fixture with_review content + `"\n\n###
    Gemini Review\n\n | Field | Value | ..."` appended | `True`
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
    `embed_review_evidence()` | String containing `"APPROVED"`,
    `"Gemini"`, `"2026-02-25T10:00:00Z"`
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
    `embed_review_evidence()` | Result of T060 + same evidence dict |
    Verdict count equals T060 verdict count (no duplication)
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
    `embed_review_evidence()` | `ValueError`/`KeyError`/`TypeError`
    raised, OR returns original content unchanged
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
    `embed_review_evidence()` | `""` + valid evidence dict |
    `ValueError`/`TypeError` raised, OR returns string containing verdict
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
    `embed_review_evidence()` | Output contains `"## 1. Context & Goal"`
    and `"## 2. Proposed Changes"`
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
    `embed_review_evidence()` | Output contains `"Gemini"`, `"APPROVED"`,
    `"2026-02-25T10:00:00Z"`, `"gemini-2.5-pro"`, `"Design is sound"`
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
    `load_lld_tracking()` |
    `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with
    key `"100"`, entry `{"issue_id": 100, "status": "approved", ...}`
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
    `load_lld_tracking()` | `tmp_path / "does_not_exist.json"` |
    `FileNotFoundError` raised OR `{}`
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
    `load_lld_tracking()` |
    `Path("tests/fixtures/lld_tracking/sample_tracking_corrupt.json")` |
    `json.JSONDecodeError` raised OR `{}`
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
    `load_lld_tracking()` | `tmp_path / "empty.json"` (0 bytes) | `{}` OR
    `json.JSONDecodeError`
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
    `load_lld_tracking()` |
    `Path("tests/fixtures/lld_tracking/sample_tracking.json")` | Dict with
    keys `{"100", "200", "300"}`
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
    `update_lld_status()` | File with 3 entries, `issue_id=100,
    status="rejected"` | File re-read: entry 100 has `status="rejected"`,
    `lld_path` unchanged
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
    `update_lld_status()` | File with 3 entries (100, 200, 300),
    `issue_id=999, status="draft"` | File re-read: new entry 999 with
    `status="draft"`, keys 100/200/300 still present
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
    `update_lld_status()` | Non-existent file path, `issue_id=500,
    status="draft"` | File created, re-read: entry 500 with
    `status="draft"`
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
    `update_lld_status()` | File with 3 entries, `issue_id=200,
    status="reviewed", gemini_reviewed=True, review_verdict="APPROVED",
    review_timestamp="2026-02-25T12:00:00Z"` | Entry 200 has all kwargs
    merg
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
    `update_lld_status()` | File with 3 entries, `issue_id=100,
    status="invalid_value"` | `ValueError` raised OR graceful handling
    (entry stored)
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
    N/A (meta-test) | `Path(__file__)` introspection +
    `inspect.getmembers()` | File in `tests/unit/`, name
    `test_lld_tracking.py`, ≥5 `Test*` classes
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t220 works correctly
    assert False, 'TDD RED: test_t220 not implemented'




```



## Previous Attempt Failed (Attempt 2/3)

Your previous response had an error:

```
No code block found in response
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Markdown content.

```markdown
# Your Markdown content here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Markdown content in a single fenced code block
