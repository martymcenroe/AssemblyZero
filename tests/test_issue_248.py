"""Test file for Issue #248.

Tests for: Gemini Answers Open Questions Before Human Escalation

This tests the behavior where:
1. Drafts with open questions proceed to review (not blocked pre-review)
2. Gemini can answer open questions in the review
3. Unanswered questions loop back for revision
4. HUMAN REQUIRED escalates to human gate
5. Max iterations prevents infinite loops
6. Resolved questions proceed to finalize
7. The 0702c prompt includes question instructions
"""

import re
from pathlib import Path

import pytest

from agentos.workflows.requirements.nodes.generate_draft import (
    validate_draft_structure,
)
from agentos.workflows.requirements.nodes.review import (
    _check_open_questions_status,
    _draft_has_open_questions,
    _verdict_has_human_required,
    _verdict_has_resolved_questions,
)
from agentos.workflows.requirements.graph import (
    route_after_generate_draft,
    route_after_review,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def draft_with_open_questions():
    """Draft content with unchecked open questions."""
    return """# 248 - Feature: Test Feature

## 1. Context & Goal

### Open Questions
*Questions that need clarification before or during implementation.*

- [ ] Should we use approach A or B?
- [ ] What is the max retry count?
- [ ] How should errors be handled?

## 2. Proposed Changes

Some proposed changes here.
"""


@pytest.fixture
def draft_without_open_questions():
    """Draft content with no open questions section."""
    return """# 248 - Feature: Test Feature

## 1. Context & Goal

All questions resolved.

## 2. Proposed Changes

Some proposed changes here.
"""


@pytest.fixture
def draft_with_resolved_questions():
    """Draft content with all questions checked."""
    return """# 248 - Feature: Test Feature

## 1. Context & Goal

### Open Questions
*Questions that need clarification before or during implementation.*

- [x] ~~Should we use approach A or B?~~ **RESOLVED: Use approach A.**
- [x] ~~What is the max retry count?~~ **RESOLVED: Use existing max_iterations.**

## 2. Proposed Changes

Some proposed changes here.
"""


@pytest.fixture
def verdict_with_resolved_questions():
    """Verdict content where Gemini resolved questions."""
    return """# LLD Review: #248-test

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Open Questions Resolved
- [x] ~~Should we use approach A or B?~~ **RESOLVED: Use approach A for simplicity.**
- [x] ~~What is the max retry count?~~ **RESOLVED: Reuse max_iterations budget.**
- [x] ~~How should errors be handled?~~ **RESOLVED: Log and continue.**

## Verdict
[X] **APPROVED** - Ready for implementation
"""


@pytest.fixture
def verdict_with_human_required():
    """Verdict content with HUMAN REQUIRED marker."""
    return """# LLD Review: #248-test

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Open Questions Resolved
- [x] ~~Question 1~~ **RESOLVED: Answer here.**
- [ ] Question 2 - **HUMAN REQUIRED**: This requires business decision.

## Verdict
[X] **DISCUSS** - Needs Orchestrator decision
"""


@pytest.fixture
def verdict_without_resolved_section():
    """Verdict content without Open Questions Resolved section."""
    return """# LLD Review: #248-test

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD looks good but open questions were not addressed.

## Verdict
[X] **APPROVED** - Ready for implementation
"""


@pytest.fixture
def mock_state_base():
    """Base workflow state for testing."""
    return {
        "workflow_type": "lld",
        "agentos_root": "C:\\Users\\mcwiz\\Projects\\AgentOS",
        "target_repo": "C:\\Users\\mcwiz\\Projects\\TestRepo",
        "config_gates_draft": False,
        "config_gates_verdict": False,
        "config_mock_mode": True,
        "iteration_count": 1,
        "max_iterations": 20,
        "error_message": "",
        "current_draft": "",
        "lld_status": "PENDING",
        "open_questions_status": "NONE",
    }


# =============================================================================
# Unit Tests - Core Test Scenarios
# =============================================================================

def test_id():
    """
    Test that the module can be imported and basic structures exist.
    """
    # TDD: Arrange - verify imports work
    from agentos.workflows.requirements.nodes.review import review
    from agentos.workflows.requirements.graph import create_requirements_graph

    # TDD: Act - verify functions exist
    assert callable(review)
    assert callable(create_requirements_graph)

    # TDD: Assert - passed
    assert True


def test_t010(draft_with_open_questions, mock_state_base):
    """
    test_draft_with_questions_proceeds_to_review | Draft not blocked pre-review

    Issue #248: Pre-review validation gate was removed. Drafts with open
    questions should now proceed to review where Gemini can answer them.
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["current_draft"] = draft_with_open_questions

    # TDD: Act
    # With gates disabled, route_after_generate_draft should go to N3_review
    result = route_after_generate_draft(state)

    # TDD: Assert
    # Draft with open questions should NOT be blocked - goes to review
    assert result == "N3_review"


def test_t020(draft_with_open_questions, verdict_with_resolved_questions):
    """
    test_gemini_answers_questions | Questions resolved in verdict

    Issue #248: Gemini should answer open questions in the verdict.
    The _check_open_questions_status function should return RESOLVED.
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict = verdict_with_resolved_questions

    # TDD: Act
    status = _check_open_questions_status(draft, verdict)

    # TDD: Assert
    assert status == "RESOLVED"


def test_t030(draft_with_open_questions, verdict_without_resolved_section, mock_state_base):
    """
    test_unanswered_triggers_loop | Loop back to N1 with followup

    Issue #248: If questions are unanswered, loop back to drafter (N1).
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["current_draft"] = draft_with_open_questions
    state["open_questions_status"] = "UNANSWERED"
    state["iteration_count"] = 1

    # TDD: Act
    result = route_after_review(state)

    # TDD: Assert
    # Unanswered questions should loop back to drafter
    assert result == "N1_generate_draft"


def test_t040(mock_state_base):
    """
    test_human_required_escalates | Goes to human gate

    Issue #248: If Gemini marks questions as HUMAN REQUIRED,
    workflow should escalate to human gate (N4).
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["open_questions_status"] = "HUMAN_REQUIRED"

    # TDD: Act
    result = route_after_review(state)

    # TDD: Assert
    assert result == "N4_human_gate_verdict"


def test_t050(mock_state_base):
    """
    test_max_iterations_respected | Terminates after limit

    Issue #248: Respect max_iterations to prevent infinite loops.
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["open_questions_status"] = "UNANSWERED"
    state["iteration_count"] = 20
    state["max_iterations"] = 20

    # TDD: Act
    result = route_after_review(state)

    # TDD: Assert
    # Max iterations reached - should go to human gate instead of looping
    assert result == "N4_human_gate_verdict"


def test_t060(mock_state_base):
    """
    test_all_answered_proceeds_to_finalize | N5 reached when resolved

    Issue #248: When all questions are resolved and approved,
    proceed to finalize (N5).
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["open_questions_status"] = "RESOLVED"
    state["lld_status"] = "APPROVED"
    state["config_gates_verdict"] = False  # Auto-route

    # TDD: Act
    result = route_after_review(state)

    # TDD: Assert
    assert result == "N5_finalize"


def test_t070():
    """
    test_prompt_includes_question_instructions | 0702c has new section

    Issue #248: The 0702c prompt should include Open Questions Protocol.
    """
    # TDD: Arrange
    # Try multiple possible paths
    possible_paths = [
        Path("docs/skills/0702c-LLD-Review-Prompt.md"),
        Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md",
    ]

    content = None
    for p in possible_paths:
        if p.exists():
            content = p.read_text()
            break

    # TDD: Act & Assert
    if content is None:
        # File not found at test location - skip with informative message
        pytest.skip("0702c prompt file not found in expected locations")

    # TDD: Assert
    assert "Open Questions Protocol" in content, "0702c should contain 'Open Questions Protocol' section"
    assert "RESOLVED:" in content, "0702c should contain 'RESOLVED:' format instruction"


# =============================================================================
# Unit Tests - Duplicate IDs (same tests, alternative naming)
# =============================================================================

def test_010(draft_with_open_questions, mock_state_base):
    """
    Draft with open questions proceeds | Auto | Draft with 3 unchecked
    questions | Reaches N3_review | No BLOCKED status pre-review
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["current_draft"] = draft_with_open_questions

    # TDD: Act
    # Verify draft has open questions
    has_questions = _draft_has_open_questions(draft_with_open_questions)

    # Route should go to review, not be blocked
    route = route_after_generate_draft(state)

    # TDD: Assert
    assert has_questions, "Draft should have unchecked open questions"
    assert route == "N3_review", "Should proceed to review despite open questions"


def test_020(draft_with_open_questions, verdict_with_resolved_questions):
    """
    Gemini answers questions | Auto | Review with question instructions |
    All questions [x] | Verdict contains resolutions
    """
    # TDD: Arrange
    draft = draft_with_open_questions
    verdict = verdict_with_resolved_questions

    # TDD: Act
    resolved = _verdict_has_resolved_questions(verdict)
    status = _check_open_questions_status(draft, verdict)

    # TDD: Assert
    assert resolved, "Verdict should have resolved questions"
    assert status == "RESOLVED", "Status should be RESOLVED"


def test_030(draft_with_open_questions, verdict_without_resolved_section, mock_state_base):
    """
    Unanswered triggers loop | Auto | Verdict approves but questions
    unchecked | Loop to N3 | Followup prompt sent
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["current_draft"] = draft_with_open_questions

    # Check that questions are unanswered
    status = _check_open_questions_status(draft_with_open_questions, verdict_without_resolved_section)
    state["open_questions_status"] = status

    # TDD: Act
    route = route_after_review(state)

    # TDD: Assert
    assert status == "UNANSWERED", "Questions should be marked as unanswered"
    assert route == "N1_generate_draft", "Should loop back to drafter"


def test_040(verdict_with_human_required, draft_with_open_questions, mock_state_base):
    """
    HUMAN REQUIRED escalates | Auto | Verdict with HUMAN REQUIRED | Goes
    to N4 | Human gate invoked
    """
    # TDD: Arrange
    has_human_required = _verdict_has_human_required(verdict_with_human_required)
    status = _check_open_questions_status(draft_with_open_questions, verdict_with_human_required)

    state = mock_state_base.copy()
    state["open_questions_status"] = status

    # TDD: Act
    route = route_after_review(state)

    # TDD: Assert
    assert has_human_required, "Verdict should have HUMAN REQUIRED marker"
    assert status == "HUMAN_REQUIRED", "Status should be HUMAN_REQUIRED"
    assert route == "N4_human_gate_verdict", "Should escalate to human gate"


def test_050(mock_state_base):
    """
    Max iterations respected | Auto | 20 loops without resolution |
    Terminates | Exit with current state
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["open_questions_status"] = "UNANSWERED"
    state["iteration_count"] = 20
    state["max_iterations"] = 20

    # TDD: Act
    route = route_after_review(state)

    # TDD: Assert
    # At max iterations, should stop looping and go to human gate
    assert route == "N4_human_gate_verdict"


def test_060(mock_state_base):
    """
    Resolved proceeds to finalize | Auto | All questions answered |
    Reaches N5 | APPROVED status
    """
    # TDD: Arrange
    state = mock_state_base.copy()
    state["open_questions_status"] = "NONE"  # No questions or all resolved
    state["lld_status"] = "APPROVED"
    state["config_gates_verdict"] = False

    # TDD: Act
    route = route_after_review(state)

    # TDD: Assert
    assert route == "N5_finalize"


def test_070():
    """
    Prompt updated | Auto | Load 0702c | Contains question instructions |
    Regex match
    """
    # TDD: Arrange
    # Look for the prompt content pattern
    possible_paths = [
        Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md",
    ]

    content = None
    for p in possible_paths:
        if p.exists():
            content = p.read_text()
            break

    # TDD: Assert
    if content:
        assert "Open Questions Protocol" in content
        assert "RESOLVED:" in content
    else:
        # File not found at test location - skip
        pytest.skip("Prompt file not found in expected location")
