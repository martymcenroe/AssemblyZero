# Implementation Request

## Context

You are implementing code for Issue #177 using TDD.
This is iteration 8 of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

# 177 - Feature: Implementation workflow gate to verify LLD was genuinely approved

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #177 creation
Update Reason: Revision addressing Gemini Review #1 feedback
-->

## 1. Context & Goal
* **Issue:** #177
* **Objective:** Add a pre-flight verification gate to the implementation workflow that ensures LLDs were genuinely approved by Gemini review, preventing wasted effort on unreviewed designs
* **Status:** Approved (gemini-3-pro-preview, 2026-02-02)
* **Related Issues:** #176 (Bug: LLD workflow stamps APPROVED regardless of verdict)

### Open Questions

*All questions resolved per Gemini Review #1 feedback:*

- [x] ~~Should the gate also verify the approval is recent (within N days)?~~ **Decision: No recency check for MVP.** Keep implementation simple; users can always re-run review if concerned about staleness.
- [x] ~~Should there be a `--force` flag to bypass the gate for exceptional circumstances?~~ **Decision: No force flag.** Users should fix the LLD or get a new approval per the Recovery Strategy. This maintains integrity of the approval process.

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/workflows/run_implement_from_lld.py` | Modify | Add verification gate in N0 (load LLD) |
| `src/utils/lld_verification.py` | Add | New module containing verification logic |
| `tests/test_lld_verification.py` | Add | Unit tests for verification logic |

### 2.2 Dependencies

```toml
# pyproject.toml additions (if any)
# No new dependencies required - uses standard library only
```

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation
class LLDVerificationResult(TypedDict):
    is_valid: bool           # Whether approval is genuine
    reason: str              # Human-readable explanation
    approval_source: str | ...

### Test Scenarios

- **test_010**: Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:** APPROVED...` | is_valid=True, confidence="high" | Returns pass
  - Requirement: 
  - Type: unit

- **test_020**: Review log approval (final) | Auto | LLD with `\ | APPROVED \ | ` as last row | is_valid=True, confidence="medium" | Returns pass
  - Requirement: 
  - Type: unit

- **test_030**: False approval - REVISE then APPROVED status | Auto | Review shows REVISE, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL"
  - Requirement: 
  - Type: unit

- **test_040**: False approval - PENDING then APPROVED status | Auto | Review shows PENDING, status APPROVED | is_valid=False, error_type="forgery" | Returns fail with "FALSE APPROVAL"
  - Requirement: 
  - Type: unit

- **test_050**: No approval evidence | Auto | LLD with no approval markers | is_valid=False, error_type="not_approved" | Returns fail
  - Requirement: 
  - Type: unit

- **test_060**: Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE, REVISE, APPROVED | is_valid=True | Returns pass
  - Requirement: 
  - Type: unit

- **test_070**: Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE | is_valid=False | Returns fail
  - Requirement: 
  - Type: unit

- **test_080**: Empty review log | Auto | Review log section exists but empty | is_valid=False, error_type="not_approved" | Returns fail
  - Requirement: 
  - Type: unit

- **test_090**: Gate integration - pass | Auto | Valid LLD path | No exception raised | Workflow continues
  - Requirement: 
  - Type: integration

- **test_100**: Gate integration - fail | Auto | Invalid LLD path | LLDVerificationError raised | Exception has suggestion
  - Requirement: 
  - Type: integration

- **test_110**: Path traversal attempt | Auto | Path outside project root | Raises exception before read | Security check blocks
  - Requirement: 
  - Type: unit

- **test_120**: Status APPROVED but no Final Status line | Auto | LLD missing Final Status section | is_valid=False, error_type="not_approved" | Returns fail
  - Requirement: 
  - Type: unit

### Test File: C:\Users\mcwiz\Projects\AgentOS-177\tests\test_issue_177.py

```python
"""Test file for Issue #177.

Tests for LLD approval verification module.
Verifies the implementation workflow gate to ensure LLDs were genuinely approved.
"""

import tempfile
from pathlib import Path

import pytest

from agentos.utils.lld_verification import (
    LLDVerificationError,
    LLDVerificationResult,
    detect_false_approval,
    extract_review_log_verdicts,
    has_gemini_approved_footer,
    run_verification_gate,
    validate_lld_path,
    verify_lld_approval,
)


# Sample LLD content fixtures
@pytest.fixture
def lld_with_gemini_footer():
    """LLD with genuine Gemini APPROVED footer."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177
* **Objective:** Test feature

## 2. Proposed Changes

Some changes here.

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-01 | APPROVED | None |

**Final Status:** APPROVED

<sub>**Gemini Review:** APPROVED | **Model:** gemini-3-pro-preview | **Date:** 2026-02-01</sub>
"""


@pytest.fixture
def lld_with_review_log_approved():
    """LLD with APPROVED as final verdict in review log (no footer)."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-28 | REVISE | Missing details |
| 2 | 2026-01-30 | REVISE | Security concern |
| 3 | 2026-02-01 | APPROVED | None |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_false_approval_revise():
    """LLD with REVISE verdict but APPROVED status (false approval)."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-28 | REVISE | Security issues |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_with_false_approval_pending():
    """LLD with PENDING verdict but APPROVED status (false approval)."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-28 | PENDING | Awaiting review |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_no_approval():
    """LLD with no approval markers."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177
* **Objective:** Test feature

## 2. Proposed Changes

Some changes here.
"""


@pytest.fixture
def lld_multiple_reviews_approved():
    """LLD with multiple reviews, last is APPROVED."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-28 | REVISE | Missing details |
| 2 | 2026-01-30 | REVISE | Security concern |
| 3 | 2026-02-01 | APPROVED | None |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_multiple_reviews_revise():
    """LLD with multiple reviews, last is REVISE."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-01-28 | APPROVED | None |
| 2 | 2026-01-30 | REVISE | New issues found |

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_empty_review_log():
    """LLD with empty review log section."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|

**Final Status:** APPROVED
"""


@pytest.fixture
def lld_approved_no_final_status():
    """LLD with review showing APPROVED but no Final Status line."""
    return """# LLD-177: Test Feature

## 1. Context & Goal

* **Issue:** #177

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-01 | APPROVED | None |

## 3. Implementation Details

Some details here.
"""


# Integration/E2E fixtures
@pytest.fixture
def test_client():
    """Test client for API calls."""
    # Not needed for these tests, just a placeholder
    yield None


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        lld_dir = project_root / "docs" / "lld" / "active"
        lld_dir.mkdir(parents=True)
        yield project_root


# Unit Tests
# -----------

def test_010(lld_with_gemini_footer):
    """
    Genuine footer approval | Auto | LLD with `<sub>**Gemini Review:**
    APPROVED...` | is_valid=True, confidence="high" | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_with_gemini_footer

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["confidence"] == "high"
    assert result["approval_source"] == "footer"
    assert result["error_type"] is None


def test_020(lld_with_review_log_approved):
    r"""
    Review log approval (final) | Auto | LLD with `| APPROVED |` as
    last row | is_valid=True, confidence="medium" | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_with_review_log_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["confidence"] == "medium"
    assert result["approval_source"] == "review_log"


def test_030(lld_with_false_approval_revise):
    """
    False approval - REVISE then APPROVED status | Auto | Review shows
    REVISE, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    lld_content = lld_with_false_approval_revise

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "forgery"
    assert "FALSE APPROVAL" in result["reason"]


def test_040(lld_with_false_approval_pending):
    """
    False approval - PENDING then APPROVED status | Auto | Review shows
    PENDING, status APPROVED | is_valid=False, error_type="forgery" |
    Returns fail with "FALSE APPROVAL"
    """
    # TDD: Arrange
    lld_content = lld_with_false_approval_pending

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "forgery"
    assert "FALSE APPROVAL" in result["reason"]


def test_050(lld_no_approval):
    """
    No approval evidence | Auto | LLD with no approval markers |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_no_approval

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["error_type"] == "not_approved"


def test_060(lld_multiple_reviews_approved):
    """
    Multiple reviews, last is APPROVED | Auto | 3 reviews: REVISE,
    REVISE, APPROVED | is_valid=True | Returns pass
    """
    # TDD: Arrange
    lld_content = lld_multiple_reviews_approved

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["last_verdict"] == "APPROVED"


def test_070(lld_multiple_reviews_revise):
    """
    Multiple reviews, last is REVISE | Auto | 3 reviews: APPROVED, REVISE
    | is_valid=False | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_multiple_reviews_revise

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    assert result["last_verdict"] == "REVISE"


def test_080(lld_empty_review_log):
    """
    Empty review log | Auto | Review log section exists but empty |
    is_valid=False, error_type="not_approved" | Returns fail
    """
    # TDD: Arrange
    lld_content = lld_empty_review_log

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    assert result["is_valid"] is False
    # Empty review log with Final Status APPROVED = no_evidence
    assert result["error_type"] in ("not_approved", "no_evidence")


def test_110(temp_project_dir):
    """
    Path traversal attempt | Auto | Path outside project root | Raises
    exception before read | Security check blocks
    """
    # TDD: Arrange
    project_root = temp_project_dir
    # Path that attempts traversal outside project
    malicious_path = project_root / ".." / ".." / "etc" / "passwd"

    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        validate_lld_path(malicious_path, project_root)

    assert exc_info.value.error_type == "security"
    assert "traversal" in exc_info.value.reason.lower() or "outside" in exc_info.value.reason.lower()


def test_120(lld_approved_no_final_status):
    """
    Status APPROVED but no Final Status line | Auto | LLD missing Final
    Status section | is_valid=False, error_type="not_approved" | Returns
    fail
    """
    # TDD: Arrange
    lld_content = lld_approved_no_final_status

    # TDD: Act
    result = verify_lld_approval(lld_content)

    # TDD: Assert
    # Without the footer and with review log showing APPROVED,
    # this should actually pass as the review_log has APPROVED
    # But we should verify the expected behavior
    assert result["is_valid"] is True  # Review log shows APPROVED
    assert result["approval_source"] == "review_log"


# Integration Tests
# -----------------

def test_090(test_client, temp_project_dir, lld_with_gemini_footer):
    """
    Gate integration - pass | Auto | Valid LLD path | No exception raised
    | Workflow continues
    """
    # TDD: Arrange
    project_root = temp_project_dir
    lld_dir = project_root / "docs" / "lld" / "active"
    lld_path = lld_dir / "LLD-177.md"
    lld_path.write_text(lld_with_gemini_footer, encoding="utf-8")

    # TDD: Act
    result = run_verification_gate(lld_path, project_root)

    # TDD: Assert
    assert result["is_valid"] is True
    assert result["confidence"] == "high"


def test_100(test_client, temp_project_dir, lld_with_false_approval_revise):
    """
    Gate integration - fail | Auto | Invalid LLD path |
    LLDVerificationError raised | Exception has suggestion
    """
    # TDD: Arrange
    project_root = temp_project_dir
    lld_dir = project_root / "docs" / "lld" / "active"
    lld_path = lld_dir / "LLD-177.md"
    lld_path.write_text(lld_with_false_approval_revise, encoding="utf-8")

    # TDD: Act & Assert
    with pytest.raises(LLDVerificationError) as exc_info:
        run_verification_gate(lld_path, project_root)

    assert exc_info.value.suggestion is not None
    assert len(exc_info.value.suggestion) > 0
    assert exc_info.value.error_type == "forgery"

```

### Source Files to Modify

These are the existing files you need to modify:

#### src/utils/lld_verification.py (NEW FILE)

New module containing verification logic

#### tests/test_lld_verification.py (NEW FILE)

Unit tests for verification logic

### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
esting\__init__.py                        3      3     0%   18-21
agentos\workflows\testing\audit.py                          82     82     0%   13-307
agentos\workflows\testing\graph.py                          98     98     0%   41-363
agentos\workflows\testing\knowledge\__init__.py              2      2     0%   8-10
agentos\workflows\testing\knowledge\patterns.py             60     60     0%   7-193
agentos\workflows\testing\nodes\__init__.py                  9      9     0%   19-31
agentos\workflows\testing\nodes\document.py                140    140     0%   13-360
agentos\workflows\testing\nodes\e2e_validation.py           93     93     0%   9-311
agentos\workflows\testing\nodes\finalize.py                103    103     0%   10-249
agentos\workflows\testing\nodes\implement_code.py          221    221     0%   7-631
agentos\workflows\testing\nodes\load_lld.py                204    204     0%   10-602
agentos\workflows\testing\nodes\review_test_plan.py        139    139     0%   9-496
agentos\workflows\testing\nodes\scaffold_tests.py          157    157     0%   9-372
agentos\workflows\testing\nodes\verify_phases.py           160    160     0%   7-497
agentos\workflows\testing\state.py                           9      9     0%   12-36
agentos\workflows\testing\templates\__init__.py              5      5     0%   12-23
agentos\workflows\testing\templates\cp_docs.py              73     73     0%   9-296
agentos\workflows\testing\templates\lessons.py             115    115     0%   8-304
agentos\workflows\testing\templates\runbook.py              94     94     0%   8-259
agentos\workflows\testing\templates\wiki_page.py            74     74     0%   8-207
--------------------------------------------------------------------------------------
TOTAL                                                     4829   4738     2%
FAIL Required test coverage of 95% not reached. Total coverage: 1.88%
============================= 12 passed in 0.36s ==============================


```

Please fix the issues and provide updated implementation.

## Instructions

1. Generate implementation code that makes all tests pass
2. Follow the patterns established in the codebase
3. Ensure proper error handling
4. Add type hints where appropriate
5. Keep the implementation minimal - only what's needed to pass tests

## Output Format (CRITICAL - MUST FOLLOW EXACTLY)

For EACH file you need to create or modify, provide a code block with this EXACT format:

```python
# File: path/to/implementation.py

def function_name():
    ...
```

**Rules:**
- The `# File: path/to/file` comment MUST be the FIRST line inside the code block
- Use the language-appropriate code fence (```python, ```gitignore, ```yaml, etc.)
- Path must be relative to repository root (e.g., `src/module/file.py`)
- Do NOT include "(append)" or other annotations in the path
- Provide complete file contents, not patches or diffs

**Example for .gitignore:**
```gitignore
# File: .gitignore

# Existing patterns...
*.pyc
__pycache__/

# New pattern
.agentos/
```

If multiple files are needed, provide each in a separate code block with its own `# File:` header.
