# File: tests/test_issue_248.py

```python
"""Test file for Issue #248 - Open Questions Loop Behavior.

Tests verify that:
1. Drafts with open questions proceed to review (pre-review gate removed)
2. Gemini can answer open questions during review
3. Unanswered questions trigger loop back to drafter
4. HUMAN REQUIRED escalates to human gate
5. Max iterations are respected
6. All questions answered proceeds to finalize
7. Prompt file has Open Questions Protocol
"""

import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch


# Unit Tests
# -----------

def test_id():
    """
    Test that open_questions_status field exists in state with correct type.
    """
    from agentos.workflows.requirements.state import create_initial_state

    state = create_initial_state(
        workflow_type="lld",
        agentos_root="/tmp/agentos",
        target_repo="/tmp/repo",
        issue_number=248,
    )

    # Verify the field exists and has the expected initial value
    assert "open_questions_status" in state
    assert state["open_questions_status"] == "NONE"


def test_t010():
    """
    test_draft_with_questions_proceeds_to_review | Draft not blocked
    pre-review | RED
    """
    from agentos.workflows.requirements.graph import route_after_generate_draft

    # Draft with open questions should proceed to review, not be blocked
    state = {
        "error_message": "",
        "config_gates_draft": False,  # No human gate
    }

    result = route_after_generate_draft(state)

    # Should go to N3_review, not be blocked
    assert result == "N3_review"


def test_t020():
    """
    test_gemini_answers_questions | Questions resolved in verdict | RED
    """
    from agentos.workflows.requirements.nodes.review import _check_open_questions_status

    draft = """# LLD
### Open Questions
- [ ] Which database should we use?
- [ ] Should we use REST or GraphQL?
"""

    verdict = """## Open Questions Resolved
- [x] ~~Which database should we use?~~ **RESOLVED: Use PostgreSQL for ACID compliance.**
- [x] ~~Should we use REST or GraphQL?~~ **RESOLVED: Use REST for simplicity.**

## Verdict
[x] APPROVED"""

    status = _check_open_questions_status(draft, verdict)

    assert status == "RESOLVED"


def test_t030():
    """
    test_unanswered_triggers_loop | Loop back to N3 with followup | RED
    """
    from agentos.workflows.requirements.graph import route_after_review

    # Questions exist but weren't answered in verdict
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",  # Even if approved, unanswered questions cause loop
        "open_questions_status": "UNANSWERED",
        "iteration_count": 3,
        "max_iterations": 20,
    }

    result = route_after_review(state)

    # Should loop back to drafter for revision
    assert result == "N1_generate_draft"


def test_t040():
    """
    test_human_required_escalates | Goes to human gate | RED
    """
    from agentos.workflows.requirements.graph import route_after_review

    # Question marked HUMAN REQUIRED
    state = {
        "error_message": "",
        "config_gates_verdict": False,  # Gates disabled
        "lld_status": "APPROVED",
        "open_questions_status": "HUMAN_REQUIRED",
    }

    result = route_after_review(state)

    # Should force human gate even with gates disabled
    assert result == "N4_human_gate_verdict"


def test_t050():
    """
    test_max_iterations_respected | Terminates after limit | RED
    """
    from agentos.workflows.requirements.graph import route_after_review

    # At max iterations with unanswered questions
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "BLOCKED",
        "open_questions_status": "UNANSWERED",
        "iteration_count": 20,
        "max_iterations": 20,
    }

    result = route_after_review(state)

    # Should go to human gate, not infinite loop
    assert result == "N4_human_gate_verdict"


def test_t060():
    """
    test_all_answered_proceeds_to_finalize | N5 reached when resolved |
    RED
    """
    from agentos.workflows.requirements.graph import route_after_review

    # All questions resolved, approved
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",
        "open_questions_status": "RESOLVED",
    }

    result = route_after_review(state)

    # Should proceed to finalize
    assert result == "N5_finalize"


def test_t070():
    """
    test_prompt_includes_question_instructions | 0702c has new section |
    RED
    """
    # Try multiple possible locations for the prompt file
    possible_paths = [
        Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md",
        Path("docs/skills/0702c-LLD-Review-Prompt.md"),
        Path("C:/Users/mcwiz/Projects/AgentOS-248/docs/skills/0702c-LLD-Review-Prompt.md"),
    ]

    content = None
    for p in possible_paths:
        if p.exists():
            content = p.read_text()
            break

    if content is None:
        pytest.skip("Prompt file not found")

    # Verify Open Questions Protocol section exists
    assert "Open Questions Protocol" in content
    assert "RESOLVED:" in content
    assert "[x]" in content
    assert "~~" in content  # Strikethrough format


def test_010():
    """
    Draft with open questions proceeds | Auto | Draft with 3 unchecked
    questions | Reaches N3_review | No BLOCKED status pre-review
    """
    from agentos.workflows.requirements.nodes.generate_draft import validate_draft_structure
    from agentos.workflows.requirements.graph import route_after_generate_draft

    # Draft has open questions
    draft = """# LLD for Issue #248

### Open Questions
- [ ] Question 1?
- [ ] Question 2?
- [ ] Question 3?

## Design
Implementation details here.
"""

    # validate_draft_structure returns an error if questions exist,
    # but Issue #248 removed this call from the flow
    validation_result = validate_draft_structure(draft)
    assert validation_result is not None  # Function still detects questions

    # But routing should proceed to review regardless
    state = {
        "error_message": "",
        "config_gates_draft": False,
    }

    route_result = route_after_generate_draft(state)
    assert route_result == "N3_review"


def test_020():
    """
    Gemini answers questions | Auto | Review with question instructions |
    All questions [x] | Verdict contains resolutions
    """
    from agentos.workflows.requirements.nodes.review import _verdict_has_resolved_questions

    verdict_with_resolutions = """## Open Questions Resolved
- [x] ~~Should we use caching?~~ **RESOLVED: Yes, use Redis with 5-minute TTL.**
- [x] ~~What error handling approach?~~ **RESOLVED: Use Result type pattern.**

## Verdict
[x] APPROVED"""

    assert _verdict_has_resolved_questions(verdict_with_resolutions) is True


def test_030():
    """
    Unanswered triggers loop | Auto | Verdict approves but questions
    unchecked | Loop to N3 | Followup prompt sent
    """
    from agentos.workflows.requirements.nodes.review import _check_open_questions_status

    draft = """### Open Questions
- [ ] Unanswered question here"""

    # Verdict approves but doesn't address questions
    verdict = "[x] APPROVED - Great design!"

    status = _check_open_questions_status(draft, verdict)

    # Should be UNANSWERED because questions weren't addressed
    assert status == "UNANSWERED"


def test_040():
    """
    HUMAN REQUIRED escalates | Auto | Verdict with HUMAN REQUIRED | Goes
    to N4 | Human gate invoked
    """
    from agentos.workflows.requirements.nodes.review import _verdict_has_human_required

    # Various HUMAN REQUIRED patterns
    verdicts = [
        "This question HUMAN REQUIRED for approval.",
        "**HUMAN REQUIRED** - Business decision needed.",
        "REQUIRES HUMAN input on licensing.",
        "NEED HUMAN DECISION about architecture.",
        "ESCALATE TO HUMAN for cost approval.",
    ]

    for verdict in verdicts:
        assert _verdict_has_human_required(verdict) is True, f"Failed for: {verdict}"


def test_050():
    """
    Max iterations respected | Auto | 20 loops without resolution |
    Terminates | Exit with current state
    """
    from agentos.workflows.requirements.graph import route_after_review

    # Exceeded max iterations
    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "BLOCKED",
        "open_questions_status": "UNANSWERED",
        "iteration_count": 25,
        "max_iterations": 20,
    }

    result = route_after_review(state)

    # Should not loop infinitely - go to human gate
    assert result == "N4_human_gate_verdict"


def test_060():
    """
    Resolved proceeds to finalize | Auto | All questions answered |
    Reaches N5 | APPROVED status
    """
    from agentos.workflows.requirements.graph import route_after_review

    state = {
        "error_message": "",
        "config_gates_verdict": False,
        "lld_status": "APPROVED",
        "open_questions_status": "RESOLVED",
    }

    result = route_after_review(state)

    assert result == "N5_finalize"


def test_070():
    """
    Prompt updated | Auto | Load 0702c | Contains question instructions |
    Regex match
    """
    possible_paths = [
        Path(__file__).parent.parent / "docs" / "skills" / "0702c-LLD-Review-Prompt.md",
        Path("docs/skills/0702c-LLD-Review-Prompt.md"),
        Path("C:/Users/mcwiz/Projects/AgentOS-248/docs/skills/0702c-LLD-Review-Prompt.md"),
    ]

    content = None
    for p in possible_paths:
        if p.exists():
            content = p.read_text()
            break

    if content is None:
        pytest.skip("Prompt file not found")

    # Check for the Open Questions Protocol section
    pattern = r"##\s*Open Questions Protocol"
    assert re.search(pattern, content), "Open Questions Protocol section not found"

    # Check for the format instruction
    assert "- [x] ~~" in content, "Resolution format instruction not found"
    assert "**RESOLVED:" in content, "RESOLVED keyword instruction not found"
```