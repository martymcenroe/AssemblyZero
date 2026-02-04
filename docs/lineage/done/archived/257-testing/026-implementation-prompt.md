# Implementation Request

## Context

You are implementing code for Issue #257 using TDD.
This is iteration 3 of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

# 1257 - Feature: Review Node Should Update Draft with Resolved Open Questions

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #117 fix
Update Reason: Moved Verification & Testing to Section 10 (was Section 11) to match 0702c review prompt and testing workflow expectations
Previous: Added sections based on 80 blocking issues from 164 governance verdicts (2026-02-01)
-->

## 1. Context & Goal
* **Issue:** #257
* **Objective:** Ensure the review node updates the draft LLD with resolved open questions and Tier 3 suggestions from approved verdicts, eliminating validation blocks caused by stale draft content.
* **Status:** Approved (gemini-3-pro-preview, 2026-02-04)
* **Related Issues:** #180 (example of the problem)

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [ ] Should the original open questions text be preserved with strikethrough, or replaced entirely with resolution text?
- [ ] Should Tier 3 suggestions be added inline to relevant sections or consolidated in a new "Reviewer Suggestions" section?
- [ ] Should we create a backup of the draft before modification for audit/rollback purposes?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/nodes/review.py` | Modify | Add draft update logic after APPROVED verdict |
| `agentos/workflows/requirements/nodes/finalize.py` | Modify | Use updated draft for final LLD generation |
| `agentos/workflows/requirements/parsers/__init__.py` | Add | New module for verdict parsing utilities |
| `agentos/workflows/requirements/parsers/verdict_parser.py` | Add | Parse resolutions and suggestions from verdict |
| `agentos/workflows/requirements/parsers/draft_updater.py` | Add | Update draft with parsed verdict content |

### 2.2 Dependencies

*New p...

### Test Scenarios

- **test_id**: Test Description | Expected Behavior | Status
  - Requirement: 
  - Type: unit

- **test_t010**: Parse APPROVED verdict with resolved questions | Returns VerdictParseResult with resolutions | RED
  - Requirement: 
  - Type: unit

- **test_t020**: Parse APPROVED verdict with Tier 3 suggestions | Returns VerdictParseResult with suggestions | RED
  - Requirement: 
  - Type: unit

- **test_t030**: Parse REJECTED verdict | Returns VerdictParseResult with empty resolutions | RED
  - Requirement: 
  - Type: unit

- **test_t040**: Update draft open questions with resolutions | Checkboxes changed to `- [x]` with resolution text | RED
  - Requirement: 
  - Type: unit

- **test_t050**: Update draft with suggestions (new section) | Reviewer Suggestions section appended | RED
  - Requirement: 
  - Type: unit

- **test_t060**: Handle missing open question in draft | Log warning, continue processing | RED
  - Requirement: 
  - Type: unit

- **test_t070**: End-to-end: review node updates draft on approval | State contains updated_draft after approval | RED
  - Requirement: 
  - Type: e2e

- **test_t080**: End-to-end: finalize uses updated draft | Final LLD contains resolved questions | RED
  - Requirement: 
  - Type: e2e

- **test_t090**: Idempotency: same verdict applied twice | Same result both times | RED
  - Requirement: 
  - Type: unit

- **test_010**: Parse approved verdict with resolutions | Auto | Verdict with "Open Questions: RESOLVED" | List of ResolvedQuestion | Correct questions and resolution text extracted
  - Requirement: 
  - Type: unit

- **test_020**: Parse approved verdict with suggestions | Auto | Verdict with "Tier 3" section | List of Tier3Suggestion | All suggestions captured
  - Requirement: 
  - Type: unit

- **test_030**: Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions list | No resolutions extracted
  - Requirement: 
  - Type: unit

- **test_040**: Update draft checkboxes | Auto | Draft + resolutions | Updated draft
  - Requirement: 
  - Type: unit

- **test_050**: Add suggestions section | Auto | Draft + suggestions | Updated draft | New section at end
  - Requirement: 
  - Type: unit

- **test_060**: Missing question in draft | Auto | Resolution for non-existent question | Warning logged, draft unchanged | No error thrown
  - Requirement: 
  - Type: unit

- **test_070**: Review node integration | Auto | State with APPROVED verdict | State with updated_draft | Draft contains resolutions
  - Requirement: 
  - Type: integration

- **test_080**: Finalize node integration | Auto | State with updated_draft | Final LLD | LLD contains `- [x]`
  - Requirement: 
  - Type: integration

- **test_090**: Idempotent update | Auto | Apply same verdict twice | Same draft | No duplicate markers
  - Requirement: 
  - Type: unit

- **test_100**: Empty Open Questions section | Auto | Verdict resolves nothing | Unchanged draft | No modifications
  - Requirement: 
  - Type: unit

- **test_110**: Malformed verdict | Auto | Verdict missing expected sections | Warning, original draft | Graceful degradation
  - Requirement: 
  - Type: unit

### Test File: C:\Users\mcwiz\Projects\AgentOS-257\tests\test_issue_257.py

```python
"""Test file for Issue #257.

Generated by AgentOS TDD Testing Workflow.
Tests for: Review Node Should Update Draft with Resolved Open Questions

This tests the behavior where:
1. Parse APPROVED verdict with resolved questions
2. Parse APPROVED verdict with Tier 3 suggestions
3. Parse REJECTED verdict (empty resolutions)
4. Update draft open questions with resolutions
5. Update draft with suggestions (new section)
6. Handle missing open question in draft
7. Review node integration with draft updates
8. Finalize node uses updated draft
9. Idempotency - same verdict applied twice
10. Handle edge cases (empty, malformed verdicts)
"""

import pytest
import logging

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from agentos.workflows.requirements.parsers.verdict_parser import (
    parse_verdict,
    VerdictParseResult,
    ResolvedQuestion,
    Tier3Suggestion,
)
from agentos.workflows.requirements.parsers.draft_updater import update_draft


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def approved_verdict_with_resolutions():
    """APPROVED verdict with resolved open questions."""
    return """# LLD Review: #257-test

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Open Questions Resolved
- [x] ~~Should the original open questions text be preserved with strikethrough?~~ **RESOLVED:** Yes, use strikethrough with resolution text appended.
- [x] ~~Should Tier 3 suggestions be added inline or consolidated?~~ **RESOLVED:** Consolidate in a new "Reviewer Suggestions" section.
- [x] ~~Should we create a backup of the draft before modification?~~ **RESOLVED:** No backup needed; Git history provides audit trail.

## Verdict
[X] **APPROVED** - Ready for implementation
"""


@pytest.fixture
def approved_verdict_with_suggestions():
    """APPROVED verdict with Tier 3 suggestions."""
    return """# LLD Review: #257-test

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Tier 3 Suggestions
- **Performance:** Consider caching parsed verdicts for repeated access.
- **Testing:** Add property-based tests for edge cases in parsing.
- Consider adding logging for debug purposes.

## Verdict
[X] **APPROVED** - Ready for implementation
"""


@pytest.fixture
def rejected_verdict():
    """REJECTED/BLOCKED verdict."""
    return """# LLD Review: #257-test

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
FAILED - Missing test coverage section

## Blocking Issues
1. Section 10 (Test Plan) is empty
2. No verification steps defined

## Verdict
[X] **REVISE** - Needs more work
"""


@pytest.fixture
def draft_with_open_questions():
    """Draft content with unchecked open questions."""
    return """# 257 - Feature: Review Node Updates Draft

## 1. Context & Goal
* **Issue:** #257
* **Objective:** Ensure the review node updates the draft LLD with resolved open questions.

### Open Questions
*Questions that need clarification before or during implementation.*

- [ ] Should the original open questions text be preserved with strikethrough?
- [ ] Should Tier 3 suggestions be added inline or consolidated?
- [ ] Should we create a backup of the draft before modification?

## 2. Proposed Changes

Some changes here.

## Definition of Done
- [ ] All tests pass
- [ ] Documentation updated
"""


@pytest.fixture
def draft_without_open_questions():
    """Draft without open questions section."""
    return """# 257 - Feature: Test Feature

## 1. Context & Goal

No questions here.

## 2. Proposed Changes

Some changes.
"""


@pytest.fixture
def verdict_with_discuss():
    """Verdict with DISCUSS checkbox checked."""
    return """# LLD Review: #257-test

## Verdict
[X] **DISCUSS** - Needs clarification from orchestrator
"""


@pytest.fixture
def verdict_with_explicit_approved():
    """Verdict with VERDICT: APPROVED keyword."""
    return """# LLD Review: #257-test

## Summary
The design is sound.

## Conclusion
VERDICT: APPROVED

Ready for implementation.
"""


@pytest.fixture
def verdict_with_qa_format():
    """Verdict using Q/A format for resolutions."""
    return """# LLD Review: #257-test

## Open Questions Resolved
- [x] **Q:** Should we use approach A? **A:** Yes, approach A is recommended.
- [x] **Q:** What timeout value? **A:** Use 30 seconds.

## Verdict
[X] **APPROVED**
"""


@pytest.fixture
def verdict_with_numbered_resolutions():
    """Verdict with numbered question resolutions."""
    return """# LLD Review: #257-test

## Open Questions
**Q1:** What is the retry count?
**Resolution:** Use 3 retries with exponential backoff.

**Q2:** Should we cache results?
**Resolution:** Yes, cache for 5 minutes.

## Verdict
VERDICT: APPROVED
"""


@pytest.fixture
def verdict_with_suggestion_markers():
    """Verdict with SUGGESTION: markers."""
    return """# LLD Review: #257-test

**SUGGESTION:** Consider using async/await for better performance.

**SUGGESTION:** Add rate limiting to prevent abuse.

## Verdict
[X] **APPROVED**
"""


@pytest.fixture
def draft_with_numbered_questions():
    """Draft with numbered questions format."""
    return """# 257 - Feature: Test

## 1. Context & Goal

### Open Questions
1. [ ] Q1: What is the retry count?
2. [ ] Q2: Should we cache results?

## 2. Proposed Changes

Changes here.
"""


@pytest.fixture
def draft_with_already_resolved():
    """Draft with some questions already resolved."""
    return """# 257 - Feature: Test

## 1. Context & Goal

### Open Questions
- [x] Already answered question **RESOLVED:** Previous answer
- [ ] Still needs answering?

## 2. Proposed Changes

Changes here.
"""


@pytest.fixture
def verdict_with_inline_resolutions():
    """Verdict with inline resolution format."""
    return """# LLD Review: #257-test

## Open Questions
- [x] What timeout should we use? **RESOLVED:** Use 30 seconds timeout.

## Verdict
[X] **APPROVED**
"""


@pytest.fixture
def verdict_simple_approved():
    """Simple verdict with just APPROVED word."""
    return """# LLD Review

The design looks good. APPROVED for implementation.
"""


@pytest.fixture
def test_client():
    """Test client for API calls."""
    # Not needed for unit tests
    yield None


# =============================================================================
# Unit Tests
# =============================================================================

def test_id():
    """
    Test that the module can be imported and basic structures exist.
    """
    # TDD: Arrange - verify imports work
    assert VerdictParseResult is not None
    assert ResolvedQuestion is not None
    assert Tier3Suggestion is not None
    assert callable(parse_verdict)
    assert callable(update_draft)

    # TDD: Assert - passed
    assert True


def test_t010(approved_verdict_with_resolutions):
    """
    Parse APPROVED verdict with resolved questions | Returns
    VerdictParseResult with resolutions | RED
    """
    # TDD: Arrange
    verdict_content = approved_verdict_with_resolutions

    # TDD: Act
    result = parse_verdict(verdict_content)

    # TDD: Assert
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 1
    # Check that resolutions have question and answer text
    assert any("strikethrough" in r.question_text.lower() for r in result.resolutions)


def test_t020(approved_verdict_with_suggestions):
    """
    Parse APPROVED verdict with Tier 3 suggestions | Returns
    VerdictParseResult with suggestions | RED
    """
    # TDD: Arrange
    verdict_content = approved_verdict_with_suggestions

    # TDD: Act
    result = parse_verdict(verdict_content)

    # TDD: Assert
    assert result.verdict_status == "APPROVED"
    assert len(result.suggestions) >= 1
    # Check suggestion content
    assert any("caching" in s.suggestion_text.lower() or "performance" in (s.category or "").lower()
               for s in result.suggestions)


def test_t030(rejected_verdict):
    """
    Parse REJECTED verdict | Returns VerdictParseResult with empty
    resolutions | RED
    """
    # TDD: Arrange
    verdict_content = rejected_verdict

    # TDD: Act
    result = parse_verdict(verdict_content)

    # TDD: Assert
    assert result.verdict_status == "BLOCKED"
    assert len(result.resolutions) == 0
    assert len(result.suggestions) == 0


def test_t040(draft_with_open_questions, approved_verdict_with_resolutions):
    """
    Update draft open questions with resolutions | Checkboxes changed to
    `- [x]` with resolution text | RED
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = parse_verdict(approved_verdict_with_resolutions)

    # TDD: Act
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    # Check that at least one checkbox was updated
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft


def test_t050(draft_with_open_questions, approved_verdict_with_suggestions):
    """
    Update draft with suggestions (new section) | Reviewer Suggestions
    section appended | RED
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = parse_verdict(approved_verdict_with_suggestions)

    # TDD: Act
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    assert "## Reviewer Suggestions" in updated_draft
    # Should appear before Definition of Done
    dod_index = updated_draft.find("## Definition of Done")
    suggestions_index = updated_draft.find("## Reviewer Suggestions")
    if dod_index > 0:
        assert suggestions_index < dod_index


def test_t060(draft_with_open_questions, caplog):
    """
    Handle missing open question in draft | Log warning, continue
    processing | RED
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    # Create verdict with a question that doesn't exist in draft
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="This question does not exist in the draft",
                resolution_text="Answer to non-existent question"
            )
        ],
        suggestions=[],
        raw_verdict="test",
        parse_warnings=[]
    )

    # TDD: Act
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    # Draft should be unchanged (question not found)
    assert "This question does not exist" not in updated_draft
    # Should have a warning
    assert len(warnings) >= 1
    assert any("not find" in w.lower() or "could not" in w.lower() for w in warnings)


def test_t090(draft_with_open_questions, approved_verdict_with_resolutions):
    """
    Idempotency: same verdict applied twice | Same result both times |
    RED
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = parse_verdict(approved_verdict_with_resolutions)

    # TDD: Act
    updated_draft_1, warnings_1 = update_draft(draft, verdict_result)
    updated_draft_2, warnings_2 = update_draft(updated_draft_1, verdict_result)

    # TDD: Assert
    # Second application should produce same result (no duplicates)
    assert updated_draft_1 == updated_draft_2


def test_010(approved_verdict_with_resolutions):
    """
    Parse approved verdict with resolutions | Auto | Verdict with "Open
    Questions: RESOLVED" | List of ResolvedQuestion | Correct questions
    and resolution text extracted
    """
    # TDD: Arrange
    verdict_content = approved_verdict_with_resolutions

    # TDD: Act
    result = parse_verdict(verdict_content)

    # TDD: Assert
    assert result.verdict_status == "APPROVED"
    assert isinstance(result.resolutions, list)
    # Check we have resolutions with proper structure
    for resolution in result.resolutions:
        assert isinstance(resolution, ResolvedQuestion)
        assert resolution.question_text
        assert resolution.resolution_text


def test_020(approved_verdict_with_suggestions):
    """
    Parse approved verdict with suggestions | Auto | Verdict with "Tier
    3" section | List of Tier3Suggestion | All suggestions captured
    """
    # TDD: Arrange
    verdict_content = approved_verdict_with_suggestions

    # TDD: Act
    result = parse_verdict(verdict_content)

    # TDD: Assert
    assert isinstance(result.suggestions, list)
    assert len(result.suggestions) >= 1
    for suggestion in result.suggestions:
        assert isinstance(suggestion, Tier3Suggestion)
        assert suggestion.suggestion_text


def test_030(rejected_verdict):
    """
    Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions
    list | No resolutions extracted
    """
    # TDD: Arrange
    verdict_content = rejected_verdict

    # TDD: Act
    result = parse_verdict(verdict_content)

    # TDD: Assert
    assert result.verdict_status == "BLOCKED"
    assert result.resolutions == []


def test_040(draft_with_open_questions, approved_verdict_with_resolutions):
    """
    Update draft checkboxes | Auto | Draft + resolutions | Updated draft
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = parse_verdict(approved_verdict_with_resolutions)

    # TDD: Act
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    # Original had unchecked boxes
    assert "- [ ]" in draft
    # Updated should have some checked boxes
    assert "- [x]" in updated_draft


def test_050(draft_with_open_questions, approved_verdict_with_suggestions):
    """
    Add suggestions section | Auto | Draft + suggestions | Updated draft
    | New section at end
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = parse_verdict(approved_verdict_with_suggestions)

    # Original draft should not have suggestions section
    assert "## Reviewer Suggestions" not in draft

    # TDD: Act
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    assert "## Reviewer Suggestions" in updated_draft


def test_060(draft_with_open_questions):
    """
    Missing question in draft | Auto | Resolution for non-existent
    question | Warning logged, draft unchanged | No error thrown
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Nonexistent question about something random",
                resolution_text="This resolution should not apply"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    # TDD: Act
    # Should not throw an error
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    # Warning should be generated
    assert len(warnings) >= 1


def test_090(draft_with_open_questions, approved_verdict_with_suggestions):
    """
    Idempotent update | Auto | Apply same verdict twice | Same draft | No
    duplicate markers
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = parse_verdict(approved_verdict_with_suggestions)

    # TDD: Act
    updated_1, _ = update_draft(draft, verdict_result)
    updated_2, _ = update_draft(updated_1, verdict_result)

    # TDD: Assert
    # Should be identical (no duplicate sections)
    assert updated_1 == updated_2
    # Should only have one Reviewer Suggestions section
    assert updated_2.count("## Reviewer Suggestions") == 1


def test_100(draft_with_open_questions):
    """
    Empty Open Questions section | Auto | Verdict resolves nothing |
    Unchanged draft | No modifications
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],  # No resolutions
        suggestions=[],  # No suggestions
        raw_verdict="",
        parse_warnings=[]
    )

    # TDD: Act
    updated_draft, warnings = update_draft(draft, verdict_result)

    # TDD: Assert
    assert updated_draft == draft  # No changes


def test_110():
    """
    Malformed verdict | Auto | Verdict missing expected sections |
    Warning, original draft | Graceful degradation
    """
    # TDD: Arrange
    malformed_verdict = """This is not a valid verdict format.

    It doesn't have any of the expected sections.
    Just random text.
    """

    # TDD: Act
    result = parse_verdict(malformed_verdict)

    # TDD: Assert
    # Should not crash, should return empty/default result
    assert result is not None
    assert result.verdict_status in ("UNKNOWN", "BLOCKED")
    assert len(result.resolutions) == 0


def test_discuss_verdict(verdict_with_discuss):
    """Test that DISCUSS checkbox verdict returns BLOCKED status."""
    result = parse_verdict(verdict_with_discuss)
    assert result.verdict_status == "BLOCKED"


def test_explicit_approved_verdict(verdict_with_explicit_approved):
    """Test VERDICT: APPROVED keyword format."""
    result = parse_verdict(verdict_with_explicit_approved)
    assert result.verdict_status == "APPROVED"


def test_qa_format_resolutions(verdict_with_qa_format):
    """Test Q/A format resolution parsing."""
    result = parse_verdict(verdict_with_qa_format)
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 1
    # Check that Q/A pattern was parsed
    assert any("approach" in r.resolution_text.lower() for r in result.resolutions)


def test_numbered_resolutions(verdict_with_numbered_resolutions):
    """Test numbered question resolution parsing."""
    result = parse_verdict(verdict_with_numbered_resolutions)
    assert result.verdict_status == "APPROVED"
    # Check for numbered questions
    assert len(result.resolutions) >= 1


def test_suggestion_markers(verdict_with_suggestion_markers):
    """Test SUGGESTION: marker parsing."""
    result = parse_verdict(verdict_with_suggestion_markers)
    assert result.verdict_status == "APPROVED"
    # Should find suggestions with SUGGESTION: markers
    assert len(result.suggestions) >= 1
    assert any("async" in s.suggestion_text.lower() or "rate" in s.suggestion_text.lower()
               for s in result.suggestions)


def test_update_numbered_questions(draft_with_numbered_questions):
    """Test updating numbered question format."""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="What is the retry count",
                resolution_text="Use 3 retries",
                question_number=1
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_with_numbered_questions, verdict_result)
    # Should handle numbered format
    assert updated_draft is not None


def test_idempotent_already_resolved(draft_with_already_resolved):
    """Test that already resolved questions don't get duplicate markers."""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Already answered question",
                resolution_text="Another answer"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_with_already_resolved, verdict_result)
    # Should not add duplicate RESOLVED markers
    count = updated_draft.count("**RESOLVED:**")
    assert count == 1  # Only the original one


def test_inline_resolution_format(verdict_with_inline_resolutions):
    """Test inline resolution format parsing."""
    result = parse_verdict(verdict_with_inline_resolutions)
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 1
    assert any("30 seconds" in r.resolution_text for r in result.resolutions)


def test_simple_approved_keyword(verdict_simple_approved):
    """Test simple APPROVED keyword without checkbox."""
    result = parse_verdict(verdict_simple_approved)
    assert result.verdict_status == "APPROVED"


def test_empty_verdict():
    """Test empty verdict content."""
    result = parse_verdict("")
    assert result.verdict_status == "UNKNOWN"
    assert len(result.parse_warnings) >= 1


def test_empty_draft():
    """Test empty draft handling."""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )
    updated_draft, warnings = update_draft("", verdict_result)
    assert updated_draft == ""
    assert len(warnings) >= 1


def test_flexible_question_matching(draft_with_open_questions):
    """Test flexible matching when question wording differs slightly."""
    # Use a slightly different wording
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="original open questions text preserved strikethrough",
                resolution_text="Yes, use strikethrough"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_with_open_questions, verdict_result)
    # Should find the question using flexible matching (key words)
    # Check either it matched or generated a warning
    assert updated_draft is not None


def test_existing_suggestions_section():
    """Test adding to existing Reviewer Suggestions section."""
    draft_with_suggestions = """# Test

## 1. Context

Content here.

## Reviewer Suggestions

*Non-blocking recommendations.*

- Existing suggestion.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[
            Tier3Suggestion(suggestion_text="New suggestion to add")
        ],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_with_suggestions, verdict_result)
    # Should append to existing section, not create new
    assert updated_draft.count("## Reviewer Suggestions") == 1
    assert "New suggestion to add" in updated_draft


def test_suggestion_with_category(approved_verdict_with_suggestions):
    """Test suggestions with category prefix."""
    result = parse_verdict(approved_verdict_with_suggestions)
    # Should have at least one suggestion with category
    categorized = [s for s in result.suggestions if s.category]
    assert len(categorized) >= 1
    assert any(s.category == "Performance" for s in categorized)


def test_append_suggestions_at_end():
    """Test suggestions appended at end when no DoD section."""
    draft_no_dod = """# Test

## 1. Context

Content here.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[
            Tier3Suggestion(suggestion_text="Test suggestion")
        ],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_no_dod, verdict_result)
    assert "## Reviewer Suggestions" in updated_draft
    assert "Test suggestion" in updated_draft


def test_rejected_checkbox():
    """Test REJECTED checkbox verdict."""
    verdict = """## Verdict
[X] **REJECTED** - Major issues found
"""
    result = parse_verdict(verdict)
    assert result.verdict_status == "BLOCKED"


def test_verdict_blocked_keyword():
    """Test VERDICT: BLOCKED keyword."""
    verdict = """## Summary
Issues found.

VERDICT: BLOCKED
"""
    result = parse_verdict(verdict)
    assert result.verdict_status == "BLOCKED"


def test_verdict_rejected_keyword():
    """Test VERDICT: REJECTED keyword."""
    verdict = """## Summary
Many issues.

VERDICT: REJECTED
"""
    result = parse_verdict(verdict)
    assert result.verdict_status == "BLOCKED"


def test_simple_arrow_resolution_format():
    """Test 'question' → RESOLVED: answer format."""
    verdict = '''# Review

"What database should we use?" → RESOLVED: Use PostgreSQL for production.

"Should we add caching?" -> RESOLVED: Yes, add Redis caching.

VERDICT: APPROVED
'''
    result = parse_verdict(verdict)
    assert result.verdict_status == "APPROVED"
    assert len(result.resolutions) >= 1


def test_resolution_without_open_questions_section():
    """Test applying resolution when draft has no Open Questions section."""
    draft_no_oq = """# Test Feature

## 1. Context

Just content here, no questions.

## 2. Changes

Changes.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Some question",
                resolution_text="Some answer"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_no_oq, verdict_result)
    # Should have warning about no Open Questions section
    assert any("Open Questions" in w for w in warnings)


def test_exact_match_resolution(draft_with_open_questions, approved_verdict_with_resolutions):
    """Test exact match resolution updating."""
    # Parse the verdict
    verdict_result = parse_verdict(approved_verdict_with_resolutions)

    # Apply to draft
    updated_draft, warnings = update_draft(draft_with_open_questions, verdict_result)

    # Check exact match worked
    assert "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft


def test_flexible_match_already_resolved():
    """Test that flexible match detects already resolved questions."""
    draft = """# Test

### Open Questions
- [x] Some variant of the question? **RESOLVED:** Already answered

## 2. Changes
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="variant of the question",
                resolution_text="New answer attempt"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft, verdict_result)
    # Should not add duplicate resolution (idempotent)
    assert updated_draft.count("**RESOLVED:**") == 1


def test_long_question_text_warning():
    """Test warning message truncation for long question text."""
    draft = """# Test

### Open Questions
- [ ] Short question here

## 2. Changes
"""
    very_long_question = "This is a very long question text that exceeds fifty characters and should be truncated in the warning message"
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text=very_long_question,
                resolution_text="Answer"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft, verdict_result)
    # Should have truncated warning
    assert len(warnings) >= 1
    assert any("..." in w for w in warnings)


def test_keyword_match_resolution():
    """Test resolution matching using key words from question."""
    draft = """# Test

### Open Questions
- [ ] Should we implement authentication using OAuth or JWT tokens?

## 2. Changes
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="implement authentication OAuth JWT",
                resolution_text="Use JWT tokens for simplicity"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft, verdict_result)
    # Should find via keyword matching
    assert "- [x]" in updated_draft or len(warnings) > 0


def test_exact_match_already_resolved():
    """Test exact match idempotency - already resolved question."""
    # This draft has the exact question text already resolved
    draft = """# Test

### Open Questions
- [x] Should the original open questions text be preserved with strikethrough? **RESOLVED:** Yes
- [ ] Other question here?

## 2. Changes
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="Should the original open questions text be preserved with strikethrough?",
                resolution_text="Actually no, replace it completely"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft, verdict_result)
    # Should not add duplicate - already resolved
    assert updated_draft.count("**RESOLVED:**") == 1


def test_pattern2_flexible_match():
    """Test Pattern 2 flexible match that extends beyond exact match."""
    draft = """# Test

### Open Questions
- [ ] Should we use strikethrough formatting for resolved questions?

## 2. Changes
"""
    # Use a shorter phrase that's contained in the question
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[
            ResolvedQuestion(
                question_text="strikethrough formatting",
                resolution_text="Yes, use strikethrough"
            )
        ],
        suggestions=[],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft, verdict_result)
    # Should find via flexible pattern
    assert "- [x]" in updated_draft
    # The original question text should be preserved
    assert "resolved questions" in updated_draft


def test_append_new_suggestion_to_existing():
    """Test appending new suggestion with category to existing section."""
    draft_with_suggestions = """# Test

## 1. Context

Content here.

## Reviewer Suggestions

*Non-blocking recommendations.*

- Existing suggestion here.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[
            Tier3Suggestion(
                suggestion_text="Add more caching",
                category="Performance"
            )
        ],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_with_suggestions, verdict_result)
    # Should append new suggestion
    assert "Add more caching" in updated_draft
    assert "**Performance:**" in updated_draft
    # Should only have one section
    assert updated_draft.count("## Reviewer Suggestions") == 1


def test_duplicate_suggestion_not_added():
    """Test that duplicate suggestions are not added."""
    draft_with_suggestions = """# Test

## Reviewer Suggestions

*Non-blocking recommendations.*

- Consider caching for better performance.
"""
    verdict_result = VerdictParseResult(
        verdict_status="APPROVED",
        resolutions=[],
        suggestions=[
            Tier3Suggestion(
                suggestion_text="Consider caching for better performance."
            )
        ],
        raw_verdict="",
        parse_warnings=[]
    )

    updated_draft, warnings = update_draft(draft_with_suggestions, verdict_result)
    # Should not add duplicate
    assert updated_draft.count("Consider caching for better performance.") == 1


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.integration
def test_070(test_client, draft_with_open_questions, approved_verdict_with_resolutions):
    """
    Review node integration | Auto | State with APPROVED verdict | State
    with updated_draft | Draft contains resolutions
    """
    # TDD: Arrange
    # Simulate what review node does
    verdict_result = parse_verdict(approved_verdict_with_resolutions)

    # TDD: Act
    updated_draft, warnings = update_draft(draft_with_open_questions, verdict_result)

    # TDD: Assert
    # The updated draft should contain resolution markers
    assert "- [x]" in updated_draft or "**RESOLVED:**" in updated_draft


@pytest.mark.integration
def test_080(test_client, draft_with_open_questions, approved_verdict_with_resolutions):
    """
    Finalize node integration | Auto | State with updated_draft | Final
    LLD | LLD contains `- [x]`
    """
    # TDD: Arrange
    verdict_result = parse_verdict(approved_verdict_with_resolutions)
    updated_draft, _ = update_draft(draft_with_open_questions, verdict_result)

    # TDD: Act
    # Finalize would use this updated_draft
    # For this test, we just verify the draft is in the right format

    # TDD: Assert
    # The draft should be usable by finalize (contains resolved questions)
    assert "- [x]" in updated_draft or "**RESOLVED:**" in updated_draft
    # Should still have the structure intact
    assert "## 1. Context & Goal" in updated_draft


# =============================================================================
# E2E Tests
# =============================================================================

@pytest.mark.e2e
def test_t070(test_client, draft_with_open_questions, approved_verdict_with_resolutions):
    """
    End-to-end: review node updates draft on approval | State contains
    updated_draft after approval | RED
    """
    # TDD: Arrange
    from agentos.workflows.requirements.nodes.review import _update_draft_with_verdict

    draft = draft_with_open_questions
    verdict_content = approved_verdict_with_resolutions

    # TDD: Act
    updated_draft = _update_draft_with_verdict(draft, verdict_content)

    # TDD: Assert
    # Draft should be updated with resolutions
    assert updated_draft != draft or "- [x]" in updated_draft
    assert "**RESOLVED:**" in updated_draft or "- [x]" in updated_draft


@pytest.mark.e2e
def test_t080(test_client, draft_with_open_questions, approved_verdict_with_resolutions):
    """
    End-to-end: finalize uses updated draft | Final LLD contains resolved
    questions | RED
    """
    # TDD: Arrange
    from agentos.workflows.requirements.nodes.review import _update_draft_with_verdict

    draft = draft_with_open_questions
    verdict_content = approved_verdict_with_resolutions

    # TDD: Act
    updated_draft = _update_draft_with_verdict(draft, verdict_content)

    # TDD: Assert
    # Updated draft is what finalize would receive
    # It should have resolved questions marked
    assert "- [x]" in updated_draft or "**RESOLVED:**" in updated_draft
    # Still maintains LLD structure
    assert "## 1. Context & Goal" in updated_draft

```

### Source Files to Modify

These are the existing files you need to modify:

#### agentos/workflows/requirements/nodes/review.py (Modify)

Add draft update logic after APPROVED verdict

```python
"""N3: Review node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Add post-review open questions check
Issue #257: Update draft with resolved open questions after approval

Uses the configured reviewer LLM to review the current draft.
Saves verdict to audit trail and updates verdict history.
"""

import re
from pathlib import Path
from typing import Any

from agentos.core.llm_provider import get_provider
from agentos.workflows.requirements.audit import (
    load_review_prompt,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.requirements.state import RequirementsWorkflowState


def review(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N3: Review draft using configured reviewer.

    Steps:
    1. Load review prompt from agentos_root
    2. Build review content (draft + context)
    3. Call reviewer LLM
    4. Save verdict to audit trail
    5. Update verdict_count and verdict_history
    6. Determine lld_status from verdict
    7. Check for open questions resolution (Issue #248)
    8. Update draft with resolutions if APPROVED (Issue #257)

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_verdict, verdict_count, verdict_history,
        open_questions_status, and updated_draft (if APPROVED).
    """
    workflow_type = state.get("workflow_type", "lld")
    agentos_root = Path(state.get("agentos_root", ""))
    mock_mode = state.get("config_mock_mode", False)
    audit_dir = Path(state.get("audit_dir", ""))
    current_draft = state.get("current_draft", "")
    verdict_history = list(state.get("verdict_history", []))

    verdict_count = state.get("verdict_count", 0) + 1
    print(f"\n[N3] Reviewing draft (review #{verdict_count})...")

    # Use mock provider in mock mode, otherwise use configured reviewer
    if mock_mode:
        reviewer_spec = "mock:review"
    else:
        reviewer_spec = state.get("config_reviewer", "gemini:3-pro-preview")

    # Determine review prompt path based on workflow type
    if workflow_type == "issue":
        prompt_path = Path("docs/skills/0701c-Issue-Review-Prompt.md")
    else:
        prompt_path = Path("docs/skills/0702c-LLD-Review-Prompt.md")

    # Load review prompt
    try:
        review_prompt = load_review_prompt(prompt_path, agentos_root)
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Get reviewer provider
    try:
        reviewer = get_provider(reviewer_spec)
    except ValueError as e:
        return {"error_message": f"Invalid reviewer: {e}"}

    # System prompt for reviewing
    system_prompt = """You are a Principal Architect, Systems Engineer, and Test Plan Execution Guru.

Your role is to perform a strict gatekeeper review of design documents before implementation begins.

Key responsibilities:
- Answer any open questions in Section 1 with concrete recommendations
- Evaluate cost, safety, security, and legal concerns
- Verify test coverage meets requirements
- Provide a structured verdict: APPROVED or BLOCKED

Follow the Review Instructions exactly. Be specific about what needs to change for BLOCKED verdicts."""

    # Build review content
    review_content = f"""## Document to Review

{current_draft}

## Review Instructions

{review_prompt}"""

    # Call reviewer
    print(f"    Reviewer: {reviewer_spec}")
    result = reviewer.invoke(system_prompt=system_prompt, content=review_content)

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Reviewer failed: {result.error_message}"}

    verdict_content = result.response or ""

    # Save to audit trail
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        verdict_path = save_audit_file(
            audit_dir, file_num, "verdict.md", verdict_content
        )
    else:
        verdict_path = None

    # Append to verdict history
    verdict_history.append(verdict_content)

    # Determine LLD status from verdict
    lld_status = _parse_verdict_status(verdict_content)

    # Issue #248: Check open questions resolution status
    open_questions_status = _check_open_questions_status(current_draft, verdict_content)

    # Issue #257: Update draft with resolutions if APPROVED
    updated_draft = current_draft
    if lld_status == "APPROVED":
        updated_draft = _update_draft_with_verdict(current_draft, verdict_content)
        if updated_draft != current_draft:
            print("    Draft updated with resolved open questions")

    verdict_lines = len(verdict_content.splitlines()) if verdict_content else 0
    print(f"    Verdict: {lld_status} ({verdict_lines} lines)")
    print(f"    Open Questions: {open_questions_status}")
    if verdict_path:
        print(f"    Saved: {verdict_path.name}")

    return {
        "current_verdict": verdict_content,
        "current_verdict_path": str(verdict_path) if verdict_path else "",
        "verdict_count": verdict_count,
        "verdict_history": verdict_history,
        "file_counter": file_num,
        "lld_status": lld_status,
        "open_questions_status": open_questions_status,
        "current_draft": updated_draft,  # Issue #257: Return updated draft
        "error_message": "",
    }


def _update_draft_with_verdict(draft: str, verdict_content: str) -> str:
    """Update draft with resolutions and suggestions from verdict.

    Issue #257: After APPROVED verdict, update the draft with:
    - Resolved open questions (mark as [x] with resolution text)
    - Tier 3 suggestions (add new section)

    Args:
        draft: Current draft content.
        verdict_content: The APPROVED verdict from reviewer.

    Returns:
        Updated draft content.
    """
    try:
        from agentos.workflows.requirements.parsers.verdict_parser import parse_verdict
        from agentos.workflows.requirements.parsers.draft_updater import update_draft

        verdict_result = parse_verdict(verdict_content)
        updated_draft, warnings = update_draft(draft, verdict_result)

        for warning in warnings:
            print(f"    Warning: {warning}")

        return updated_draft
    except ImportError:
        # Parsers not available (shouldn't happen in production)
        return draft
    except Exception as e:
        print(f"    Warning: Could not update draft with verdict: {e}")
        return draft


def _parse_verdict_status(verdict_content: str) -> str:
    """Parse LLD status from verdict content.

    Args:
        verdict_content: The reviewer's verdict text.

    Returns:
        One of: "APPROVED", "BLOCKED"
    """
    verdict_upper = verdict_content.upper()

    # Check for checked APPROVED checkbox
    if re.search(r"\[X\]\s*\**APPROVED\**", verdict_upper):
        return "APPROVED"
    # Check for checked REVISE checkbox (maps to BLOCKED for workflow purposes)
    elif re.search(r"\[X\]\s*\**REVISE\**", verdict_upper):
        return "BLOCKED"
    # Check for checked DISCUSS checkbox (maps to BLOCKED, needs human)
    elif re.search(r"\[X\]\s*\**DISCUSS\**", verdict_upper):
        return "BLOCKED"
    # Fallback: Look for explicit keywords (legacy/simple responses)
    elif "VERDICT: APPROVED" in verdict_upper:
        return "APPROVED"
    elif "VERDICT: BLOCKED" in verdict_upper or "VERDICT: REVISE" in verdict_upper:
        return "BLOCKED"
    else:
        # Default to BLOCKED if we can't determine status (safe choice)
        return "BLOCKED"


def _check_open_questions_status(draft_content: str, verdict_content: str) -> str:
    """Check whether open questions have been resolved.

    Issue #248: After Gemini review, check if:
    1. Questions were answered (all [x] in verdict's "Open Questions Resolved" section)
    2. Questions marked as HUMAN REQUIRED
    3. Questions remain unanswered

    Args:
        draft_content: The draft that was reviewed.
        verdict_content: Gemini's verdict.

    Returns:
        One of:
        - "RESOLVED": All open questions answered
        - "HUMAN_REQUIRED": One or more questions need human decision
        - "UNANSWERED": Questions exist but weren't answered
        - "NONE": No open questions in the draft
    """
    # Check if draft has open questions
    draft_has_questions = _draft_has_open_questions(draft_content)
    if not draft_has_questions:
        return "NONE"

    # Check for HUMAN REQUIRED in verdict
    if _verdict_has_human_required(verdict_content):
        return "HUMAN_REQUIRED"

    # Check if verdict has "Open Questions Resolved" section with answers
    if _verdict_has_resolved_questions(verdict_content):
        return "RESOLVED"

    # Questions exist but weren't answered
    return "UNANSWERED"


def _draft_has_open_questions(content: str) -> bool:
    """Check if draft has unchecked open questions.

    Args:
        content: Draft content.

    Returns:
        True if unchecked open questions exist.
    """
    if not content:
        return False

    # Extract Open Questions section
    pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        return False

    open_questions_section = match.group(1)

    # Check for unchecked boxes
    unchecked = re.findall(r"^- \[ \]", open_questions_section, re.MULTILINE)
    return len(unchecked) > 0


def _verdict_has_human_required(verdict_content: str) -> bool:
    """Check if verdict contains HUMAN REQUIRED marker.

    Args:
        verdict_content: The verdict text.

    Returns:
        True if HUMAN REQUIRED is present.
    """
    # Look for HUMAN REQUIRED (case insensitive) in various formats
    patterns = [
        r"HUMAN\s+REQUIRED",
        r"\*\*HUMAN\s+REQUIRED\*\*",
        r"REQUIRES?\s+HUMAN",
        r"NEEDS?\s+HUMAN\s+DECISION",
        r"ESCALATE\s+TO\s+HUMAN",
    ]
    verdict_upper = verdict_content.upper()
    for pattern in patterns:
        if re.search(pattern, verdict_upper):
            return True
    return False


def _verdict_has_resolved_questions(verdict_content: str) -> bool:
    """Check if verdict has resolved open questions.

    Looks for the "Open Questions Resolved" section and checks if
    all items are marked as [x] with RESOLVED.

    Args:
        verdict_content: The verdict text.

    Returns:
        True if questions were resolved.
    """
    # Look for "Open Questions Resolved" section
    pattern = r"(?:##\s*Open Questions Resolved\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, verdict_content, re.MULTILINE | re.DOTALL)

    if not match:
        # No explicit section - check if "RESOLVED:" appears in verdict
        return "RESOLVED:" in verdict_content.upper()

    resolved_section = match.group(1)

    # Check for resolved markers: [x] followed by ~~question~~ **RESOLVED:
    resolved_count = len(re.findall(r"\[x\].*?RESOLVED:", resolved_section, re.IGNORECASE))

    # Check for any unchecked items still in the section
    unchecked_count = len(re.findall(r"^- \[ \]", resolved_section, re.MULTILINE))

    # If we have resolutions and no unchecked items, questions are resolved
    return resolved_count > 0 and unchecked_count == 0
```

#### agentos/workflows/requirements/nodes/finalize.py (Modify)

Use updated draft for final LLD generation

```python
"""Finalize node for requirements workflow.

Updates GitHub issue with final draft, commits artifacts to git, and closes workflow.
For LLD workflows, saves LLD file with embedded review evidence.
"""

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from agentos.workflows.requirements.audit import (
    embed_review_evidence,
    next_file_number,
    save_audit_file,
    update_lld_status,
)
from ..git_operations import commit_and_push, GitOperationError

# Constants
GH_TIMEOUT_SECONDS = 30


def _parse_issue_content(draft: str) -> tuple:
    """Parse issue title and body from markdown draft.

    Expects draft in format:
    # Title Here

    Body content...

    Args:
        draft: Markdown draft content.

    Returns:
        Tuple of (title, body).
    """
    lines = draft.strip().split("\n")

    title = ""
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            body_start = i + 1
            break

    # Skip blank lines after title
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    body = "\n".join(lines[body_start:]).strip()

    return title, body


def _finalize_issue(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize issue workflow by filing GitHub issue.

    Args:
        state: Workflow state containing current_draft, target_repo, etc.

    Returns:
        Updated state with issue_url, filed_issue_number.
    """
    target_repo = Path(state.get("target_repo", "."))
    current_draft = state.get("current_draft", "")
    audit_dir = Path(state.get("audit_dir", "."))

    # Parse title and body from draft
    title, body = _parse_issue_content(current_draft)

    if not title:
        return {"error_message": "Could not parse issue title from draft"}

    # File issue using gh CLI
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            capture_output=True,
            text=True,
            encoding="utf-8",  # Fix for Unicode handling on Windows
            timeout=GH_TIMEOUT_SECONDS,
            cwd=str(target_repo),
        )

        if result.returncode != 0:
            return {"error_message": f"Failed to create issue: {result.stderr.strip()}"}

        issue_url = result.stdout.strip()

        # Extract issue number from URL
        # Format: https://github.com/owner/repo/issues/123
        issue_number = 0
        if "/issues/" in issue_url:
            try:
                issue_number = int(issue_url.split("/issues/")[-1])
            except ValueError:
                pass

    except subprocess.TimeoutExpired:
        return {"error_message": "Timeout creating GitHub issue"}
    except FileNotFoundError:
        return {"error_message": "gh CLI not found. Install GitHub CLI."}

    # Save final state to audit
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        final_content = f"# Issue Filed\n\nURL: {issue_url}\n\n---\n\n{current_draft}"
        save_audit_file(audit_dir, file_num, "final.md", final_content)

    return {
        "issue_url": issue_url,
        "filed_issue_number": issue_number,
        "error_message": "",
    }


def _commit_and_push_files(state: Dict[str, Any]) -> Dict[str, Any]:
    """Commit and push created files to git.

    Args:
        state: Current workflow state with created_files list

    Returns:
        Updated state with commit_sha if successful
    """
    created_files = state.get("created_files", [])
    if not created_files:
        return state

    workflow_type = state.get("workflow_type", "lld")
    target_repo = state.get("target_repo", ".")
    issue_number = state.get("issue_number")
    slug = state.get("slug")

    try:
        commit_sha = commit_and_push(
            created_files=created_files,
            workflow_type=workflow_type,
            target_repo=target_repo,
            issue_number=issue_number,
            slug=slug,
        )

        if commit_sha:
            state["commit_sha"] = commit_sha

    except GitOperationError as e:
        # Log error but don't fail the workflow - files are already saved
        state["commit_error"] = str(e)

    return state


def validate_lld_final(content: str, open_questions_resolved: bool = False) -> list[str]:
    """Final structural checks before LLD finalization.

    Issue #235: Mechanical validation gate to catch structural issues
    before saving the final LLD.

    Issue #245: Only checks the 'Open Questions' section for unchecked items,
    ignoring Definition of Done and other sections.

    Issue #259: Skip open questions check if reviewer already resolved them.
    The review node sets open_questions_status="RESOLVED" when Gemini answers
    all questions in the verdict. We trust that determination rather than
    re-checking the draft (which hasn't been updated with the resolutions yet).

    Args:
        content: LLD content to validate.
        open_questions_resolved: If True, skip checking for unchecked open questions
            because the reviewer already resolved them in the verdict.

    Returns:
        List of error messages. Empty list if validation passes.
    """
    errors = []

    if not content:
        return errors

    # Check for unresolved open questions ONLY in the Open Questions section
    # Skip this check if reviewer already resolved them (Issue #259)
    if not open_questions_resolved:
        # Pattern: from "### Open Questions" or "## Open Questions"
        # until the next "##" header or end of document
        pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

        if match:
            open_questions_section = match.group(1)
            if re.search(r"^- \[ \]", open_questions_section, re.MULTILINE):
                errors.append("Unresolved open questions remain")

    # Check for unresolved TODO in table cells
    if re.search(r"\|\s*TODO\s*\|", content):
        errors.append("Unresolved TODO in table cell")

    return errors


def _save_lld_file(state: Dict[str, Any]) -> Dict[str, Any]:
    """Save LLD file with embedded review evidence.

    For workflow_type="lld", saves the draft to docs/lld/active/ with
    the actual Gemini verdict embedded. Also updates lld-status.json tracking.

    Args:
        state: Workflow state with current_draft, lld_status, etc.

    Returns:
        Updated state with created_files populated
    """
    workflow_type = state.get("workflow_type", "lld")
    if workflow_type != "lld":
        return state

    target_repo = Path(state.get("target_repo", "."))
    issue_number = state.get("issue_number")
    current_draft = state.get("current_draft", "")
    lld_status = state.get("lld_status", "BLOCKED")
    verdict_count = state.get("verdict_count", 0)
    audit_dir = Path(state.get("audit_dir", ""))

    # Validate issue_number
    if not issue_number:
        state["error_message"] = "No issue number for LLD finalization"
        return state

    if not current_draft:
        return state

    # Issue #259: Check if reviewer already resolved open questions
    # If so, skip the open questions check (but still check for TODOs)
    open_questions_status = state.get("open_questions_status", "")
    open_questions_resolved = open_questions_status == "RESOLVED"

    # Gate 2: Validate LLD structure before finalization (Issue #235)
    validation_errors = validate_lld_final(current_draft, open_questions_resolved)
    if validation_errors:
        error_msg = "BLOCKED: " + "; ".join(validation_errors)
        print(f"    VALIDATION: {error_msg}")
        state["error_message"] = error_msg
        return state

    # Embed review evidence with ACTUAL verdict (not hardcoded APPROVED!)
    review_date = datetime.now().strftime("%Y-%m-%d")
    lld_content = embed_review_evidence(
        current_draft,
        verdict=lld_status,  # Use actual verdict from Gemini review
        review_date=review_date,
        review_count=verdict_count,
    )

    # Save to docs/lld/active/LLD-{issue_number}.md
    lld_dir = target_repo / "docs" / "lld" / "active"
    lld_dir.mkdir(parents=True, exist_ok=True)
    lld_path = lld_dir / f"LLD-{issue_number:03d}.md"
    lld_path.write_text(lld_content, encoding="utf-8")

    # Output verification guard
    if not lld_path.exists():
        state["error_message"] = f"LLD file not created at {lld_path}"
        return state

    print(f"    Saved LLD to: {lld_path}")
    print(f"    Final Status: {lld_status}")

    # Update lld-status.json tracking
    review_info = {
        "has_gemini_review": verdict_count > 0,
        "final_verdict": lld_status,
        "last_review_date": datetime.now(timezone.utc).isoformat(),
        "review_count": verdict_count,
    }
    update_lld_status(
        issue_number=issue_number,
        lld_path=str(lld_path),
        review_info=review_info,
        target_repo=target_repo,
    )
    print(f"    Updated lld-status.json tracking")

    # Add to created_files for commit
    created_files = list(state.get("created_files", []))
    created_files.append(str(lld_path))

    # Add ALL lineage files to created_files (Issue #241)
    if audit_dir.exists():
        for lineage_file in audit_dir.glob("*"):
            if lineage_file.is_file():
                created_files.append(str(lineage_file))

    state["created_files"] = created_files
    state["final_lld_path"] = str(lld_path)

    # Save to audit trail
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "final.md", lld_content)

    return state


def _cleanup_source_idea(state: Dict[str, Any]) -> None:
    """Move source idea to ideas/done/ after successful issue creation.

    Issue #219: Ideas file not moved to done/ after issue creation.

    Args:
        state: Workflow state with source_idea, filed_issue_number, error_message.
    """
    source_idea = state.get("source_idea", "")
    if not source_idea:
        return

    source_path = Path(source_idea)
    if not source_path.exists():
        return

    # Only cleanup on success (no error and issue was filed)
    if state.get("error_message"):
        return

    # Get issue number from filed_issue_number
    issue_number = state.get("filed_issue_number", 0)
    if not issue_number:
        return

    # Ensure ideas/done/ exists
    done_dir = source_path.parent.parent / "done"
    done_dir.mkdir(exist_ok=True)

    # Move with issue number prefix
    new_name = f"{issue_number}-{source_path.name}"
    dest_path = done_dir / new_name

    shutil.move(str(source_path), str(dest_path))
    print(f"  Moved idea to: {dest_path}")


def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Public interface for finalize node.

    Finalizes the issue (if applicable), saves LLD file (if LLD workflow),
    and commits artifacts to git.

    Args:
        state: Workflow state

    Returns:
        Updated state with finalization status
    """
    workflow_type = state.get("workflow_type", "lld")

    if workflow_type == "lld":
        # For LLD workflow: save LLD file with embedded review evidence
        state = _save_lld_file(state)
    else:
        # For issue workflow: post comment to GitHub issue
        # _finalize_issue returns only updates, merge them into state
        updates = _finalize_issue(state)
        state.update(updates)

    # Then, commit and push artifacts to git
    state = _commit_and_push_files(state)

    # Cleanup source idea after successful issue creation
    if workflow_type == "issue" and not state.get("error_message"):
        _cleanup_source_idea(state)

    return state

```

#### agentos/workflows/requirements/parsers/__init__.py (NEW FILE)

New module for verdict parsing utilities

#### agentos/workflows/requirements/parsers/verdict_parser.py (NEW FILE)

Parse resolutions and suggestions from verdict

#### agentos/workflows/requirements/parsers/draft_updater.py (NEW FILE)

Update draft with parsed verdict content

### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
\testing\graph.py                              98     98     0%   41-363
agentos\workflows\testing\knowledge\__init__.py                  2      2     0%   8-10
agentos\workflows\testing\knowledge\patterns.py                 60     60     0%   7-193
agentos\workflows\testing\nodes\__init__.py                     10     10     0%   19-34
agentos\workflows\testing\nodes\document.py                    140    140     0%   13-360
agentos\workflows\testing\nodes\e2e_validation.py               93     93     0%   9-311
agentos\workflows\testing\nodes\finalize.py                    103    103     0%   10-249
agentos\workflows\testing\nodes\implement_code.py              247    247     0%   7-693
agentos\workflows\testing\nodes\load_lld.py                    204    204     0%   10-602
agentos\workflows\testing\nodes\review_test_plan.py            139    139     0%   9-496
agentos\workflows\testing\nodes\scaffold_tests.py              185    185     0%   9-442
agentos\workflows\testing\nodes\validate_commit_message.py      12     12     0%   7-47
agentos\workflows\testing\nodes\verify_phases.py               160    160     0%   7-497
agentos\workflows\testing\state.py                               9      9     0%   12-36
agentos\workflows\testing\templates\__init__.py                  5      5     0%   12-23
agentos\workflows\testing\templates\cp_docs.py                  73     73     0%   9-296
agentos\workflows\testing\templates\lessons.py                 115    115     0%   8-304
agentos\workflows\testing\templates\runbook.py                  94     94     0%   8-259
agentos\workflows\testing\templates\wiki_page.py                74     74     0%   8-207
------------------------------------------------------------------------------------------
TOTAL                                                         5472   4899    10%
FAIL Required test coverage of 95% not reached. Total coverage: 10.47%
======================= 49 passed, 9 warnings in 1.84s ========================


```

Please fix the issues and provide updated implementation.

## Instructions

1. The tests FAIL because functions/classes they import DO NOT EXIST yet
2. You must CREATE or MODIFY the source files to add the missing functions
3. Look at what the tests import - those functions must be implemented
4. If a file exists but is missing a function, ADD the function to that file
5. Output the COMPLETE file content with the new functions added

CRITICAL: Do NOT say "the code already exists" - if tests fail, the code does NOT exist or is incomplete.

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
