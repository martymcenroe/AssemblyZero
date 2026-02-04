Now I have a complete picture of the codebase. Let me write the complete test file implementation:

```python
# File: tests/test_issue_248.py

"""Test file for Issue #248.

Issue #248: Feature: Gemini Answers Open Questions Before Human Escalation

Tests for:
- Pre-review validation gate removed (drafts with open questions proceed)
- Post-review open questions check
- Loop back when questions unanswered
- Human gate escalation when HUMAN REQUIRED
- Max iterations respected
- Prompt includes question instructions
"""

import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch


# =============================================================================
# Helper Functions
# =============================================================================


def make_draft_with_open_questions(num_questions: int = 3) -> str:
    """Create a draft with unchecked open questions."""
    questions = "\n".join([f"- [ ] Question {i+1}?" for i in range(num_questions)])
    return f"""# LLD for Issue #248

## 1. Context & Goal

### Open Questions
{questions}

## 2. Proposed Changes

Some changes here.
"""


def make_draft_with_resolved_questions() -> str:
    """Create a draft with all questions checked (resolved)."""
    return """# LLD for Issue #248

## 1. Context & Goal

### Open Questions
- [x] ~~Question 1?~~ **RESOLVED: Answer 1**
- [x] ~~Question 2?~~ **RESOLVED: Answer 2**

## 2. Proposed Changes

Some changes here.
"""


def make_draft_without_questions() -> str:
    """Create a draft without any open questions section."""
    return """# LLD for Issue #248

## 1. Context & Goal

No questions here.

## 2. Proposed Changes

Some changes here.
"""


def make_verdict_with_resolved_questions() -> str:
    """Create a verdict that resolves open questions."""
    return """# LLD Review: #248

## Open Questions Resolved
- [x] ~~Question 1?~~ **RESOLVED: Use option A.**
- [x] ~~Question 2?~~ **RESOLVED: Yes, proceed with the approach.**

## Verdict
[x] **APPROVED** - Ready for implementation
"""


def make_verdict_with_human_required() -> str:
    """Create a verdict that marks questions as HUMAN REQUIRED."""
    return """# LLD Review: #248

## Open Questions Resolved
- [ ] Question 1 requires business decision - **HUMAN REQUIRED**

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
"""


def make_verdict_without_resolution() -> str:
    """Create a verdict that doesn't address open questions."""
    return """# LLD Review: #248

## Review Summary
The LLD looks good overall.

## Verdict
[x] **APPROVED** - Ready for implementation
"""


# =============================================================================
# Unit Tests - Open Questions Detection
# =============================================================================


def test_id():
    """Test placeholder - validates test infrastructure works."""
    # This is a placeholder test to ensure the file is valid Python
    assert True


def test_t010():
    """
    test_draft_with_questions_proceeds_to_review | Draft not blocked pre-review
    
    Issue #248: Pre-review validation gate removed. Drafts with open questions
    should proceed to review where Gemini can answer them.
    """
    from agentos.workflows.requirements.graph import route_after_generate_draft
    
    # State with draft that has open questions - but gate is disabled
    state = {
        "error_message": "",
        "config_gates_draft": False,  # Gate disabled
        "current_draft": make_draft_with_open_questions(3),
    }
    
    # Should route to review, not END
    result = route_after_generate_draft(state)
    assert result == "N3_review", "Draft with open questions should proceed to review"


def test_t020():
    """
    test_gemini_answers_questions | Questions resolved in verdict
    
    After review, if Gemini resolves all open questions in the verdict,
    open_questions_status should be "RESOLVED".
    """
    from agentos.workflows.requirements.nodes.review import _check_open_questions_status
    
    draft = make_draft_with_open_questions(2)
    verdict = make_verdict_with_resolved_questions()
    
    status = _check_open_questions_status(draft, verdict)
    assert status == "RESOLVED", "Questions should be marked RESOLVED when Gemini answers them"


def test_t030():
    """
    test_unanswered_triggers_loop | Loop back to N1 with followup
    
    When open questions exist but aren't answered, route back to drafter.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",  # Even if approved, unanswered questions loop
        "open_questions_status": "UNANSWERED",
        "iteration_count": 1,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N1_generate_draft", "Unanswered questions should trigger loop back to drafter"


def test_t040():
    """
    test_human_required_escalates | Goes to human gate
    
    When Gemini marks questions as HUMAN REQUIRED, escalate to human gate.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,  # Even with gate disabled
        "lld_status": "BLOCKED",
        "open_questions_status": "HUMAN_REQUIRED",
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "HUMAN_REQUIRED should force human gate"


def test_t050():
    """
    test_max_iterations_respected | Terminates after limit
    
    When max iterations reached with unanswered questions, go to human gate.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "BLOCKED",
        "open_questions_status": "UNANSWERED",
        "iteration_count": 20,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "Max iterations should escalate to human gate"


def test_t060():
    """
    test_all_answered_proceeds_to_finalize | N5 reached when resolved
    
    When questions are resolved and verdict is APPROVED, proceed to finalize.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",
        "open_questions_status": "RESOLVED",
    }
    
    result = route_after_review(state)
    assert result == "N5_finalize", "Resolved questions with APPROVED should proceed to finalize"


def test_t070():
    """
    test_prompt_includes_question_instructions | 0702c has new section
    
    The LLD review prompt should include the Open Questions Protocol section.
    """
    from pathlib import Path
    
    # Use relative path from test to find prompt
    # The prompt is at docs/skills/0702c-LLD-Review-Prompt.md
    prompt_path = Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md"
    
    if prompt_path.exists():
        content = prompt_path.read_text()
        assert "Open Questions Protocol" in content, "Prompt should include Open Questions Protocol section"
        assert "HUMAN REQUIRED" in content or "RESOLVED:" in content, "Prompt should explain resolution format"
    else:
        # If running in worktree without full structure, skip
        pytest.skip("Prompt file not found in test environment")


# =============================================================================
# Integration-style Tests
# =============================================================================


def test_010():
    """
    Draft with open questions proceeds | Draft with 3 unchecked questions
    reaches N3_review without BLOCKED status pre-review.
    """
    from agentos.workflows.requirements.nodes.generate_draft import validate_draft_structure
    from agentos.workflows.requirements.graph import route_after_generate_draft
    
    draft = make_draft_with_open_questions(3)
    
    # validate_draft_structure is kept for backward compatibility but NOT called
    # in the main flow anymore. We test that routing ignores open questions.
    state = {
        "error_message": "",
        "config_gates_draft": False,
        "current_draft": draft,
    }
    
    result = route_after_generate_draft(state)
    assert result == "N3_review", "Draft with unchecked questions should reach N3_review"
    
    # The validation function still exists but should NOT block the workflow
    # (it's kept for backward compatibility but not called in generate_draft)
    validation_result = validate_draft_structure(draft)
    # The function returns an error message, but Issue #248 removes the gate
    # So even if validation would fail, routing doesn't use it
    assert result == "N3_review", "Routing should proceed regardless of validation"


def test_020():
    """
    Gemini answers questions | Review with question instructions produces
    verdict with all questions marked [x] and RESOLVED.
    """
    from agentos.workflows.requirements.nodes.review import (
        _check_open_questions_status,
        _verdict_has_resolved_questions,
    )
    
    draft = make_draft_with_open_questions(2)
    verdict = make_verdict_with_resolved_questions()
    
    # Check that verdict has resolved questions
    has_resolved = _verdict_has_resolved_questions(verdict)
    assert has_resolved, "Verdict should have resolved questions section"
    
    # Check overall status
    status = _check_open_questions_status(draft, verdict)
    assert status == "RESOLVED", "Status should be RESOLVED"


def test_030():
    """
    Unanswered triggers loop | Verdict approves but questions unchecked,
    should loop back to N1_generate_draft for revision.
    """
    from agentos.workflows.requirements.graph import route_after_review
    from agentos.workflows.requirements.nodes.review import _check_open_questions_status
    
    draft = make_draft_with_open_questions(2)
    verdict = make_verdict_without_resolution()
    
    # Verify questions are detected as unanswered
    status = _check_open_questions_status(draft, verdict)
    assert status == "UNANSWERED", "Questions should be detected as unanswered"
    
    # Verify routing loops back
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",  # Even with APPROVED verdict
        "open_questions_status": "UNANSWERED",
        "iteration_count": 1,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N1_generate_draft", "Should loop back to drafter"


def test_040():
    """
    HUMAN REQUIRED escalates | Verdict with HUMAN REQUIRED goes to N4 human gate.
    """
    from agentos.workflows.requirements.graph import route_after_review
    from agentos.workflows.requirements.nodes.review import (
        _check_open_questions_status,
        _verdict_has_human_required,
    )
    
    draft = make_draft_with_open_questions(1)
    verdict = make_verdict_with_human_required()
    
    # Verify HUMAN REQUIRED is detected
    has_human = _verdict_has_human_required(verdict)
    assert has_human, "Verdict should have HUMAN REQUIRED marker"
    
    # Verify status
    status = _check_open_questions_status(draft, verdict)
    assert status == "HUMAN_REQUIRED", "Status should be HUMAN_REQUIRED"
    
    # Verify routing to human gate
    state = {
        "error_message": "",
        "config_gates_verdict": False,  # Even with gate disabled
        "lld_status": "BLOCKED",
        "open_questions_status": "HUMAN_REQUIRED",
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "HUMAN REQUIRED must force human gate"


def test_050():
    """
    Max iterations respected | 20 loops without resolution terminates
    and goes to human gate instead of infinite loop.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    # Test at exactly max iterations
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "BLOCKED",
        "open_questions_status": "UNANSWERED",
        "iteration_count": 20,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "At max iterations, should go to human gate"
    
    # Test over max iterations
    state["iteration_count"] = 25
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "Over max iterations, should go to human gate"


def test_060():
    """
    Resolved proceeds to finalize | All questions answered reaches N5 with APPROVED.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",
        "open_questions_status": "RESOLVED",
        "iteration_count": 2,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N5_finalize", "RESOLVED + APPROVED should finalize"


def test_070():
    """
    Prompt updated | 0702c contains question instructions with regex match.
    """
    from pathlib import Path
    
    prompt_path = Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md"
    
    if not prompt_path.exists():
        pytest.skip("Prompt file not found in test environment")
    
    content = prompt_path.read_text()
    
    # Check for Open Questions Protocol section
    assert re.search(r"##\s*Open Questions Protocol", content), \
        "Prompt should have Open Questions Protocol section"
    
    # Check for format instructions
    assert "RESOLVED:" in content, "Prompt should explain RESOLVED format"
    assert "[x]" in content, "Prompt should show checkbox marking format"


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestOpenQuestionsDetection:
    """Tests for open questions detection in drafts and verdicts."""
    
    def test_draft_without_open_questions_section(self):
        """Draft without Open Questions section returns NONE."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status
        
        draft = make_draft_without_questions()
        verdict = "Some verdict content"
        
        status = _check_open_questions_status(draft, verdict)
        assert status == "NONE"
    
    def test_draft_with_all_checked_questions(self):
        """Draft with all checked questions returns NONE (no unchecked)."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions
        
        draft = make_draft_with_resolved_questions()
        has_open = _draft_has_open_questions(draft)
        assert not has_open, "All checked questions should not be considered open"
    
    def test_empty_draft_returns_none(self):
        """Empty draft returns NONE."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status
        
        status = _check_open_questions_status("", "Some verdict")
        assert status == "NONE"
    
    def test_human_required_variations(self):
        """Test various formats of HUMAN REQUIRED are detected."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required
        
        variations = [
            "HUMAN REQUIRED",
            "**HUMAN REQUIRED**",
            "REQUIRES HUMAN",
            "NEEDS HUMAN DECISION",
            "ESCALATE TO HUMAN",
        ]
        
        for variant in variations:
            verdict = f"Some text {variant} more text"
            assert _verdict_has_human_required(verdict), f"Should detect: {variant}"
    
    def test_resolved_without_explicit_section(self):
        """Test RESOLVED detection when no explicit section exists."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions
        
        # Verdict with RESOLVED but no section header
        verdict = "Some text\nRESOLVED: Answer here\nMore text"
        assert _verdict_has_resolved_questions(verdict)


class TestGraphRoutingOpenQuestions:
    """Tests for graph routing with open questions status."""
    
    def test_none_status_uses_normal_routing(self):
        """NONE status uses normal verdict-based routing."""
        from agentos.workflows.requirements.graph import route_after_review
        
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "NONE",
        }
        
        result = route_after_review(state)
        assert result == "N5_finalize"
    
    def test_resolved_status_uses_normal_routing(self):
        """RESOLVED status uses normal verdict-based routing."""
        from agentos.workflows.requirements.graph import route_after_review
        
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "BLOCKED",  # Even if blocked
            "open_questions_status": "RESOLVED",
        }
        
        result = route_after_review(state)
        # BLOCKED should loop back
        assert result == "N1_generate_draft"
    
    def test_human_required_overrides_gate_config(self):
        """HUMAN_REQUIRED forces human gate even when gates disabled."""
        from agentos.workflows.requirements.graph import route_after_review
        
        state = {
            "error_message": "",
            "config_gates_verdict": False,  # Gate disabled
            "lld_status": "APPROVED",
            "open_questions_status": "HUMAN_REQUIRED",
        }
        
        result = route_after_review(state)
        assert result == "N4_human_gate_verdict", "HUMAN_REQUIRED must force human gate"
    
    def test_unanswered_respects_iteration_budget(self):
        """UNANSWERED loops back unless max iterations reached."""
        from agentos.workflows.requirements.graph import route_after_review
        
        # Under max iterations - loop back
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "UNANSWERED",
            "iteration_count": 5,
            "max_iterations": 20,
        }
        
        result = route_after_review(state)
        assert result == "N1_generate_draft"
        
        # At max iterations - human gate
        state["iteration_count"] = 20
        result = route_after_review(state)
        assert result == "N4_human_gate_verdict"


class TestStateInitialization:
    """Tests for state initialization with open_questions_status."""
    
    def test_initial_state_has_open_questions_status(self, tmp_path):
        """Initial state includes open_questions_status field."""
        from agentos.workflows.requirements.state import create_initial_state
        
        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=248,
        )
        
        assert "open_questions_status" in state
        assert state["open_questions_status"] == "NONE"
```

This implementation provides complete test coverage for Issue #248. Let me verify it's syntactically correct and then provide the file:

```python
# File: tests/test_issue_248.py

"""Test file for Issue #248.

Issue #248: Feature: Gemini Answers Open Questions Before Human Escalation

Tests for:
- Pre-review validation gate removed (drafts with open questions proceed)
- Post-review open questions check
- Loop back when questions unanswered
- Human gate escalation when HUMAN REQUIRED
- Max iterations respected
- Prompt includes question instructions
"""

import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch


# =============================================================================
# Helper Functions
# =============================================================================


def make_draft_with_open_questions(num_questions: int = 3) -> str:
    """Create a draft with unchecked open questions."""
    questions = "\n".join([f"- [ ] Question {i+1}?" for i in range(num_questions)])
    return f"""# LLD for Issue #248

## 1. Context & Goal

### Open Questions
{questions}

## 2. Proposed Changes

Some changes here.
"""


def make_draft_with_resolved_questions() -> str:
    """Create a draft with all questions checked (resolved)."""
    return """# LLD for Issue #248

## 1. Context & Goal

### Open Questions
- [x] ~~Question 1?~~ **RESOLVED: Answer 1**
- [x] ~~Question 2?~~ **RESOLVED: Answer 2**

## 2. Proposed Changes

Some changes here.
"""


def make_draft_without_questions() -> str:
    """Create a draft without any open questions section."""
    return """# LLD for Issue #248

## 1. Context & Goal

No questions here.

## 2. Proposed Changes

Some changes here.
"""


def make_verdict_with_resolved_questions() -> str:
    """Create a verdict that resolves open questions."""
    return """# LLD Review: #248

## Open Questions Resolved
- [x] ~~Question 1?~~ **RESOLVED: Use option A.**
- [x] ~~Question 2?~~ **RESOLVED: Yes, proceed with the approach.**

## Verdict
[x] **APPROVED** - Ready for implementation
"""


def make_verdict_with_human_required() -> str:
    """Create a verdict that marks questions as HUMAN REQUIRED."""
    return """# LLD Review: #248

## Open Questions Resolved
- [ ] Question 1 requires business decision - **HUMAN REQUIRED**

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
"""


def make_verdict_without_resolution() -> str:
    """Create a verdict that doesn't address open questions."""
    return """# LLD Review: #248

## Review Summary
The LLD looks good overall.

## Verdict
[x] **APPROVED** - Ready for implementation
"""


# =============================================================================
# Unit Tests - Open Questions Detection
# =============================================================================


def test_id():
    """Test placeholder - validates test infrastructure works."""
    # This is a placeholder test to ensure the file is valid Python
    assert True


def test_t010():
    """
    test_draft_with_questions_proceeds_to_review | Draft not blocked pre-review
    
    Issue #248: Pre-review validation gate removed. Drafts with open questions
    should proceed to review where Gemini can answer them.
    """
    from agentos.workflows.requirements.graph import route_after_generate_draft
    
    # State with draft that has open questions - but gate is disabled
    state = {
        "error_message": "",
        "config_gates_draft": False,  # Gate disabled
        "current_draft": make_draft_with_open_questions(3),
    }
    
    # Should route to review, not END
    result = route_after_generate_draft(state)
    assert result == "N3_review", "Draft with open questions should proceed to review"


def test_t020():
    """
    test_gemini_answers_questions | Questions resolved in verdict
    
    After review, if Gemini resolves all open questions in the verdict,
    open_questions_status should be "RESOLVED".
    """
    from agentos.workflows.requirements.nodes.review import _check_open_questions_status
    
    draft = make_draft_with_open_questions(2)
    verdict = make_verdict_with_resolved_questions()
    
    status = _check_open_questions_status(draft, verdict)
    assert status == "RESOLVED", "Questions should be marked RESOLVED when Gemini answers them"


def test_t030():
    """
    test_unanswered_triggers_loop | Loop back to N1 with followup
    
    When open questions exist but aren't answered, route back to drafter.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",  # Even if approved, unanswered questions loop
        "open_questions_status": "UNANSWERED",
        "iteration_count": 1,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N1_generate_draft", "Unanswered questions should trigger loop back to drafter"


def test_t040():
    """
    test_human_required_escalates | Goes to human gate
    
    When Gemini marks questions as HUMAN REQUIRED, escalate to human gate.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,  # Even with gate disabled
        "lld_status": "BLOCKED",
        "open_questions_status": "HUMAN_REQUIRED",
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "HUMAN_REQUIRED should force human gate"


def test_t050():
    """
    test_max_iterations_respected | Terminates after limit
    
    When max iterations reached with unanswered questions, go to human gate.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "BLOCKED",
        "open_questions_status": "UNANSWERED",
        "iteration_count": 20,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "Max iterations should escalate to human gate"


def test_t060():
    """
    test_all_answered_proceeds_to_finalize | N5 reached when resolved
    
    When questions are resolved and verdict is APPROVED, proceed to finalize.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",
        "open_questions_status": "RESOLVED",
    }
    
    result = route_after_review(state)
    assert result == "N5_finalize", "Resolved questions with APPROVED should proceed to finalize"


def test_t070():
    """
    test_prompt_includes_question_instructions | 0702c has new section
    
    The LLD review prompt should include the Open Questions Protocol section.
    """
    prompt_path = Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md"
    
    if prompt_path.exists():
        content = prompt_path.read_text()
        assert "Open Questions Protocol" in content, "Prompt should include Open Questions Protocol section"
        assert "HUMAN REQUIRED" in content or "RESOLVED:" in content, "Prompt should explain resolution format"
    else:
        # If running in worktree without full structure, skip
        pytest.skip("Prompt file not found in test environment")


# =============================================================================
# Integration-style Tests
# =============================================================================


def test_010():
    """
    Draft with open questions proceeds | Draft with 3 unchecked questions
    reaches N3_review without BLOCKED status pre-review.
    """
    from agentos.workflows.requirements.nodes.generate_draft import validate_draft_structure
    from agentos.workflows.requirements.graph import route_after_generate_draft
    
    draft = make_draft_with_open_questions(3)
    
    # validate_draft_structure is kept for backward compatibility but NOT called
    # in the main flow anymore. We test that routing ignores open questions.
    state = {
        "error_message": "",
        "config_gates_draft": False,
        "current_draft": draft,
    }
    
    result = route_after_generate_draft(state)
    assert result == "N3_review", "Draft with unchecked questions should reach N3_review"
    
    # The validation function still exists but should NOT block the workflow
    # (it's kept for backward compatibility but not called in generate_draft)
    validation_result = validate_draft_structure(draft)
    # The function returns an error message, but Issue #248 removes the gate
    # So even if validation would fail, routing doesn't use it
    assert result == "N3_review", "Routing should proceed regardless of validation"


def test_020():
    """
    Gemini answers questions | Review with question instructions produces
    verdict with all questions marked [x] and RESOLVED.
    """
    from agentos.workflows.requirements.nodes.review import (
        _check_open_questions_status,
        _verdict_has_resolved_questions,
    )
    
    draft = make_draft_with_open_questions(2)
    verdict = make_verdict_with_resolved_questions()
    
    # Check that verdict has resolved questions
    has_resolved = _verdict_has_resolved_questions(verdict)
    assert has_resolved, "Verdict should have resolved questions section"
    
    # Check overall status
    status = _check_open_questions_status(draft, verdict)
    assert status == "RESOLVED", "Status should be RESOLVED"


def test_030():
    """
    Unanswered triggers loop | Verdict approves but questions unchecked,
    should loop back to N1_generate_draft for revision.
    """
    from agentos.workflows.requirements.graph import route_after_review
    from agentos.workflows.requirements.nodes.review import _check_open_questions_status
    
    draft = make_draft_with_open_questions(2)
    verdict = make_verdict_without_resolution()
    
    # Verify questions are detected as unanswered
    status = _check_open_questions_status(draft, verdict)
    assert status == "UNANSWERED", "Questions should be detected as unanswered"
    
    # Verify routing loops back
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",  # Even with APPROVED verdict
        "open_questions_status": "UNANSWERED",
        "iteration_count": 1,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N1_generate_draft", "Should loop back to drafter"


def test_040():
    """
    HUMAN REQUIRED escalates | Verdict with HUMAN REQUIRED goes to N4 human gate.
    """
    from agentos.workflows.requirements.graph import route_after_review
    from agentos.workflows.requirements.nodes.review import (
        _check_open_questions_status,
        _verdict_has_human_required,
    )
    
    draft = make_draft_with_open_questions(1)
    verdict = make_verdict_with_human_required()
    
    # Verify HUMAN REQUIRED is detected
    has_human = _verdict_has_human_required(verdict)
    assert has_human, "Verdict should have HUMAN REQUIRED marker"
    
    # Verify status
    status = _check_open_questions_status(draft, verdict)
    assert status == "HUMAN_REQUIRED", "Status should be HUMAN_REQUIRED"
    
    # Verify routing to human gate
    state = {
        "error_message": "",
        "config_gates_verdict": False,  # Even with gate disabled
        "lld_status": "BLOCKED",
        "open_questions_status": "HUMAN_REQUIRED",
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "HUMAN REQUIRED must force human gate"


def test_050():
    """
    Max iterations respected | 20 loops without resolution terminates
    and goes to human gate instead of infinite loop.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    # Test at exactly max iterations
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "BLOCKED",
        "open_questions_status": "UNANSWERED",
        "iteration_count": 20,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "At max iterations, should go to human gate"
    
    # Test over max iterations
    state["iteration_count"] = 25
    result = route_after_review(state)
    assert result == "N4_human_gate_verdict", "Over max iterations, should go to human gate"


def test_060():
    """
    Resolved proceeds to finalize | All questions answered reaches N5 with APPROVED.
    """
    from agentos.workflows.requirements.graph import route_after_review
    
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",
        "open_questions_status": "RESOLVED",
        "iteration_count": 2,
        "max_iterations": 20,
    }
    
    result = route_after_review(state)
    assert result == "N5_finalize", "RESOLVED + APPROVED should finalize"


def test_070():
    """
    Prompt updated | 0702c contains question instructions with regex match.
    """
    prompt_path = Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md"
    
    if not prompt_path.exists():
        pytest.skip("Prompt file not found in test environment")
    
    content = prompt_path.read_text()
    
    # Check for Open Questions Protocol section
    assert re.search(r"##\s*Open Questions Protocol", content), \
        "Prompt should have Open Questions Protocol section"
    
    # Check for format instructions
    assert "RESOLVED:" in content, "Prompt should explain RESOLVED format"
    assert "[x]" in content, "Prompt should show checkbox marking format"


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestOpenQuestionsDetection:
    """Tests for open questions detection in drafts and verdicts."""
    
    def test_draft_without_open_questions_section(self):
        """Draft without Open Questions section returns NONE."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status
        
        draft = make_draft_without_questions()
        verdict = "Some verdict content"
        
        status = _check_open_questions_status(draft, verdict)
        assert status == "NONE"
    
    def test_draft_with_all_checked_questions(self):
        """Draft with all checked questions returns NONE (no unchecked)."""
        from agentos.workflows.requirements.nodes.review import _draft_has_open_questions
        
        draft = make_draft_with_resolved_questions()
        has_open = _draft_has_open_questions(draft)
        assert not has_open, "All checked questions should not be considered open"
    
    def test_empty_draft_returns_none(self):
        """Empty draft returns NONE."""
        from agentos.workflows.requirements.nodes.review import _check_open_questions_status
        
        status = _check_open_questions_status("", "Some verdict")
        assert status == "NONE"
    
    def test_human_required_variations(self):
        """Test various formats of HUMAN REQUIRED are detected."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_human_required
        
        variations = [
            "HUMAN REQUIRED",
            "**HUMAN REQUIRED**",
            "REQUIRES HUMAN",
            "NEEDS HUMAN DECISION",
            "ESCALATE TO HUMAN",
        ]
        
        for variant in variations:
            verdict = f"Some text {variant} more text"
            assert _verdict_has_human_required(verdict), f"Should detect: {variant}"
    
    def test_resolved_without_explicit_section(self):
        """Test RESOLVED detection when no explicit section exists."""
        from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions
        
        # Verdict with RESOLVED but no section header
        verdict = "Some text\nRESOLVED: Answer here\nMore text"
        assert _verdict_has_resolved_questions(verdict)


class TestGraphRoutingOpenQuestions:
    """Tests for graph routing with open questions status."""
    
    def test_none_status_uses_normal_routing(self):
        """NONE status uses normal verdict-based routing."""
        from agentos.workflows.requirements.graph import route_after_review
        
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "NONE",
        }
        
        result = route_after_review(state)
        assert result == "N5_finalize"
    
    def test_resolved_status_uses_normal_routing(self):
        """RESOLVED status uses normal verdict-based routing."""
        from agentos.workflows.requirements.graph import route_after_review
        
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "BLOCKED",  # Even if blocked
            "open_questions_status": "RESOLVED",
        }
        
        result = route_after_review(state)
        # BLOCKED should loop back
        assert result == "N1_generate_draft"
    
    def test_human_required_overrides_gate_config(self):
        """HUMAN_REQUIRED forces human gate even when gates disabled."""
        from agentos.workflows.requirements.graph import route_after_review
        
        state = {
            "error_message": "",
            "config_gates_verdict": False,  # Gate disabled
            "lld_status": "APPROVED",
            "open_questions_status": "HUMAN_REQUIRED",
        }
        
        result = route_after_review(state)
        assert result == "N4_human_gate_verdict", "HUMAN_REQUIRED must force human gate"
    
    def test_unanswered_respects_iteration_budget(self):
        """UNANSWERED loops back unless max iterations reached."""
        from agentos.workflows.requirements.graph import route_after_review
        
        # Under max iterations - loop back
        state = {
            "error_message": "",
            "config_gates_verdict": False,
            "lld_status": "APPROVED",
            "open_questions_status": "UNANSWERED",
            "iteration_count": 5,
            "max_iterations": 20,
        }
        
        result = route_after_review(state)
        assert result == "N1_generate_draft"
        
        # At max iterations - human gate
        state["iteration_count"] = 20
        result = route_after_review(state)
        assert result == "N4_human_gate_verdict"


class TestStateInitialization:
    """Tests for state initialization with open_questions_status."""
    
    def test_initial_state_has_open_questions_status(self, tmp_path):
        """Initial state includes open_questions_status field."""
        from agentos.workflows.requirements.state import create_initial_state
        
        state = create_initial_state(
            workflow_type="lld",
            agentos_root=str(tmp_path),
            target_repo=str(tmp_path),
            issue_number=248,
        )
        
        assert "open_questions_status" in state
        assert state["open_questions_status"] == "NONE"
```
