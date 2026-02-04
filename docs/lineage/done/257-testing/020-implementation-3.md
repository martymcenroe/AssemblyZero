# File: tests/test_issue_257.py

```python
"""Test file for Issue #257.

Tests for verdict parsing and draft updating functionality.
"""

import pytest
import logging

from agentos.workflows.requirements.parsers.verdict_parser import (
    VerdictParseResult,
    ResolvedQuestion,
    Tier3Suggestion,
    parse_verdict,
)
from agentos.workflows.requirements.parsers.draft_updater import update_draft


# Sample test data
SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS = """
## Verdict

[x] **APPROVED**

## Open Questions Resolved

- [x] ~~Should we use Redis or in-memory caching?~~ **RESOLVED:** Use Redis for production scalability, with in-memory fallback for development.
- [x] ~~What's the timeout for API calls?~~ **RESOLVED:** 30 seconds with exponential backoff retry.

## Tier 3 Suggestions

- **Performance:** Consider adding connection pooling for database connections
- Add metrics collection for monitoring cache hit rates
"""

SAMPLE_APPROVED_VERDICT_WITH_NUMBERED_QUESTIONS = """
## Verdict

[x] **APPROVED**

**Q1:** Should we preserve original text with strikethrough?
**Resolution:** Yes, use strikethrough for the original question text.

**Q2:** Where should Tier 3 suggestions go?
**Resolution:** Add a new "Reviewer Suggestions" section at the end.
"""

SAMPLE_REJECTED_VERDICT = """
## Verdict

[x] **REJECTED**

## Blocking Issues

- Missing security analysis
- No test coverage for edge cases
"""

SAMPLE_DRAFT_WITH_OPEN_QUESTIONS = """# LLD-257: Review Node Updates

## 1. Context & Goal

This document describes the feature implementation.

### Open Questions

- [ ] Should we use Redis or in-memory caching?
- [ ] What's the timeout for API calls?
- [ ] Should we create backups before modification?

## 2. Proposed Changes

Implementation details here.

## Definition of Done

- [ ] Tests pass
- [ ] Documentation updated
"""

SAMPLE_EMPTY_VERDICT = ""

SAMPLE_MALFORMED_VERDICT = """
This is just some random text without proper structure.
No verdict markers here.
Maybe APPROVED is mentioned but not properly.
"""


# Fixtures
@pytest.fixture
def sample_approved_verdict():
    return SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS


@pytest.fixture
def sample_rejected_verdict():
    return SAMPLE_REJECTED_VERDICT


@pytest.fixture
def sample_draft():
    return SAMPLE_DRAFT_WITH_OPEN_QUESTIONS


@pytest.fixture
def test_client():
    """Test client for API calls - placeholder for integration tests."""
    yield None


# Unit Tests
# -----------

def test_id():
    """Basic sanity test that the module loads correctly."""
    # Verify we can create the basic data structures
    result = VerdictParseResult()
    assert result.verdict_status == "UNKNOWN"
    assert result.resolutions == []
    assert result.suggestions == []


def test_t010(sample_approved_verdict):
    """
    Parse APPROVED verdict with resolved questions | Returns
    VerdictParseResult with resolutions | RED
    """
    result = parse_verdict(sample_approved_verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 2
    
    # Check first resolution
    redis_resolution = next(
        (r for r in result.resolutions if "Redis" in r.resolution_text or "redis" in r.resolution_text.lower()),
        None
    )
    assert redis_resolution is not None
    assert "caching" in redis_resolution.question_text.lower() or "Redis" in redis_resolution.resolution_text


def test_t020(sample_approved_verdict):
    """
    Parse APPROVED verdict with Tier 3 suggestions | Returns
    VerdictParseResult with suggestions | RED
    """
    result = parse_verdict(sample_approved_verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.suggestions) >= 1
    
    # Check for performance suggestion
    perf_suggestion = next(
        (s for s in result.suggestions if s.category == "Performance" or "pool" in s.suggestion_text.lower()),
        None
    )
    assert perf_suggestion is not None


def test_t030(sample_rejected_verdict):
    """
    Parse REJECTED verdict | Returns VerdictParseResult with empty
    resolutions | RED
    """
    result = parse_verdict(sample_rejected_verdict)
    
    assert result.verdict_status == "BLOCKED"
    assert len(result.resolutions) == 0
    assert len(result.suggestions) == 0


def test_t040(sample_draft):
    """
    Update draft open questions with resolutions | Checkboxes changed to
    `- [x]` with resolution text | RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should we use Redis or in-memory caching?",
                resolution_text="Use Redis for production."
            )
        ]
    )
    
    updated_draft, warnings = update_draft(sample_draft, verdict_result)
    
    # Check that the checkbox is now checked
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft
    assert "Use Redis for production" in updated_draft


def test_t050(sample_draft):
    """
    Update draft with suggestions (new section) | Reviewer Suggestions
    section appended | RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        suggestions=[
            Tier3Suggestion(
                suggestion_text="Consider adding connection pooling",
                category="Performance"
            )
        ]
    )
    
    updated_draft, warnings = update_draft(sample_draft, verdict_result)
    
    assert "## Reviewer Suggestions" in updated_draft
    assert "connection pooling" in updated_draft


def test_t060(sample_draft, caplog):
    """
    Handle missing open question in draft | Log warning, continue
    processing | RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="This question does not exist in the draft at all xyz123",
                resolution_text="Some resolution"
            )
        ]
    )
    
    updated_draft, warnings = update_draft(sample_draft, verdict_result)
    
    # Should have a warning about missing question
    assert len(warnings) > 0
    assert any("Could not find" in w or "not found" in w.lower() for w in warnings)
    
    # Draft should be mostly unchanged (no resolution applied)
    # But should not raise an error


def test_t090(sample_draft):
    """
    Idempotency: same verdict applied twice | Same result both times |
    RED
    """
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should we use Redis or in-memory caching?",
                resolution_text="Use Redis for production."
            )
        ]
    )
    
    # Apply once
    updated_draft_1, _ = update_draft(sample_draft, verdict_result)
    
    # Apply again to the already-updated draft
    updated_draft_2, _ = update_draft(updated_draft_1, verdict_result)
    
    # Should be the same
    assert updated_draft_1 == updated_draft_2


def test_010():
    """
    Parse approved verdict with resolutions | Auto | Verdict with "Open
    Questions: RESOLVED" | List of ResolvedQuestion | Correct questions
    and resolution text extracted
    """
    verdict = """
## Verdict
[x] **APPROVED**

## Open Questions Resolved
- [x] ~~Should we use async?~~ **RESOLVED:** Yes, use async for all I/O operations.
"""
    result = parse_verdict(verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 1
    
    async_resolution = result.resolutions[0]
    assert "async" in async_resolution.question_text.lower()
    assert "async" in async_resolution.resolution_text.lower()


def test_020():
    """
    Parse approved verdict with suggestions | Auto | Verdict with "Tier
    3" section | List of Tier3Suggestion | All suggestions captured
    """
    verdict = """
[x] **APPROVED**

## Tier 3 Suggestions
- Add logging for debugging
- **Security:** Consider rate limiting
"""
    result = parse_verdict(verdict)
    
    assert result.verdict_status == "APPROVED"
    assert len(result.suggestions) >= 2


def test_030():
    """
    Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions
    list | No resolutions extracted
    """
    verdict = """
[x] **REVISE**

## Issues
- Needs more testing
"""
    result = parse_verdict(verdict)
    
    assert result.verdict_status == "BLOCKED"
    assert len(result.resolutions) == 0


def test_040():
    """
    Update draft checkboxes | Auto | Draft + resolutions | Updated draft
    """
    draft = """## Open Questions
- [ ] Use sync or async?
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Use sync or async?",
                resolution_text="Use async."
            )
        ]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    assert "- [x]" in updated
    assert "**RESOLVED:**" in updated


def test_050():
    """
    Add suggestions section | Auto | Draft + suggestions | Updated draft
    | New section at end
    """
    draft = """# My Document

## Content
Some content here.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        suggestions=[
            Tier3Suggestion(suggestion_text="Add error handling")
        ]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    assert "## Reviewer Suggestions" in updated
    assert "Add error handling" in updated


def test_060(caplog):
    """
    Missing question in draft | Auto | Resolution for non-existent
    question | Warning logged, draft unchanged | No error thrown
    """
    draft = """## Open Questions
- [ ] Question A?
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Completely different question XYZ",
                resolution_text="Answer"
            )
        ]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    # Should not raise, should return warnings
    assert len(warnings) > 0


def test_090():
    """
    Idempotent update | Auto | Apply same verdict twice | Same draft | No
    duplicate markers
    """
    draft = """## Open Questions
- [ ] Question A?
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Question A?",
                resolution_text="Answer A"
            )
        ]
    )
    
    updated1, _ = update_draft(draft, verdict_result)
    updated2, _ = update_draft(updated1, verdict_result)
    
    assert updated1 == updated2
    # Should only have one RESOLVED marker
    assert updated2.count("**RESOLVED:**") == 1


def test_100():
    """
    Empty Open Questions section | Auto | Verdict resolves nothing |
    Unchanged draft | No modifications
    """
    draft = """# Document
## Open Questions
*No questions at this time.*

## Content
Here is some content.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[]
    )
    
    updated, warnings = update_draft(draft, verdict_result)
    
    # Draft should be unchanged
    assert updated == draft


def test_110():
    """
    Malformed verdict | Auto | Verdict missing expected sections |
    Warning, original draft | Graceful degradation
    """
    result = parse_verdict(SAMPLE_MALFORMED_VERDICT)
    
    # Should not crash, should return something sensible
    assert result is not None
    assert result.verdict_status in ["UNKNOWN", "APPROVED", "BLOCKED"]
    
    # Resolutions might be empty since format is unrecognized
    # The key is it doesn't crash


# Integration Tests
# -----------------

@pytest.mark.integration
def test_070(test_client):
    """
    Review node integration | Auto | State with APPROVED verdict | State
    with updated_draft | Draft contains resolutions
    """
    # This is a simplified integration test
    # Full integration would require the review node
    
    verdict = SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS
    draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    
    # Parse verdict
    verdict_result = parse_verdict(verdict)
    assert verdict_result.verdict_status == "APPROVED"
    
    # Update draft
    updated_draft, warnings = update_draft(draft, verdict_result)
    
    # Verify integration
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft


@pytest.mark.integration
def test_080(test_client):
    """
    Finalize node integration | Auto | State with updated_draft | Final
    LLD | LLD contains `- [x]`
    """
    # Simplified integration test
    draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should we use Redis or in-memory caching?",
                resolution_text="Use Redis."
            )
        ]
    )
    
    updated_draft, _ = update_draft(draft, verdict_result)
    
    # The final LLD should have resolved questions
    assert "- [x]" in updated_draft
    

# E2E Tests
# ---------

@pytest.mark.e2e
def test_t070(test_client):
    """
    End-to-end: review node updates draft on approval | State contains
    updated_draft after approval | RED
    """
    # Simulate the full flow
    original_draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    verdict = SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS
    
    # Step 1: Parse verdict
    verdict_result = parse_verdict(verdict)
    assert verdict_result.verdict_status == "APPROVED"
    
    # Step 2: Update draft
    updated_draft, warnings = update_draft(original_draft, verdict_result)
    
    # Step 3: Verify state would have updated_draft
    assert updated_draft != original_draft
    assert "- [x]" in updated_draft


@pytest.mark.e2e
def test_t080(test_client):
    """
    End-to-end: finalize uses updated draft | Final LLD contains resolved
    questions | RED
    """
    # Simulate the workflow
    draft = SAMPLE_DRAFT_WITH_OPEN_QUESTIONS
    verdict = SAMPLE_APPROVED_VERDICT_WITH_RESOLUTIONS
    
    # Parse and update
    verdict_result = parse_verdict(verdict)
    updated_draft, _ = update_draft(draft, verdict_result)
    
    # Finalize would use this updated_draft
    # The final LLD should contain resolved questions
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft
```