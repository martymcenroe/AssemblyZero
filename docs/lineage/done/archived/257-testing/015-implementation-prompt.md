# Implementation Request

## Context

You are implementing code for Issue #257 using TDD.
This is iteration 1 of the implementation.

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
Tests will fail with ImportError until implementation exists (TDD RED phase).
"""

import pytest

# TDD: This import fails until implementation exists (RED phase)
# Once implemented, tests can run (GREEN phase)
from agentos.workflows.requirements.parsers.verdict_parser import *  # noqa: F401, F403


# Integration/E2E fixtures
@pytest.fixture
def test_client():
    """Test client for API calls."""
    # TODO: Implement test client
    yield None


# Unit Tests
# -----------

def test_id():
    """
    Test Description | Expected Behavior | Status
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_id works correctly
    assert False, 'TDD RED: test_id not implemented'


def test_t010():
    """
    Parse APPROVED verdict with resolved questions | Returns
    VerdictParseResult with resolutions | RED
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
    Parse APPROVED verdict with Tier 3 suggestions | Returns
    VerdictParseResult with suggestions | RED
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
    Parse REJECTED verdict | Returns VerdictParseResult with empty
    resolutions | RED
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
    Update draft open questions with resolutions | Checkboxes changed to
    `- [x]` with resolution text | RED
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
    Update draft with suggestions (new section) | Reviewer Suggestions
    section appended | RED
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
    Handle missing open question in draft | Log warning, continue
    processing | RED
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t060 works correctly
    assert False, 'TDD RED: test_t060 not implemented'


def test_t090():
    """
    Idempotency: same verdict applied twice | Same result both times |
    RED
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t090 works correctly
    assert False, 'TDD RED: test_t090 not implemented'


def test_010():
    """
    Parse approved verdict with resolutions | Auto | Verdict with "Open
    Questions: RESOLVED" | List of ResolvedQuestion | Correct questions
    and resolution text extracted
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_010 works correctly
    assert False, 'TDD RED: test_010 not implemented'


def test_020():
    """
    Parse approved verdict with suggestions | Auto | Verdict with "Tier
    3" section | List of Tier3Suggestion | All suggestions captured
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_020 works correctly
    assert False, 'TDD RED: test_020 not implemented'


def test_030():
    """
    Parse rejected verdict | Auto | REJECTED verdict | Empty resolutions
    list | No resolutions extracted
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_030 works correctly
    assert False, 'TDD RED: test_030 not implemented'


def test_040():
    """
    Update draft checkboxes | Auto | Draft + resolutions | Updated draft
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_040 works correctly
    assert False, 'TDD RED: test_040 not implemented'


def test_050():
    """
    Add suggestions section | Auto | Draft + suggestions | Updated draft
    | New section at end
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
    Missing question in draft | Auto | Resolution for non-existent
    question | Warning logged, draft unchanged | No error thrown
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_060 works correctly
    assert False, 'TDD RED: test_060 not implemented'


def test_090():
    """
    Idempotent update | Auto | Apply same verdict twice | Same draft | No
    duplicate markers
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_090 works correctly
    assert False, 'TDD RED: test_090 not implemented'


def test_100():
    """
    Empty Open Questions section | Auto | Verdict resolves nothing |
    Unchanged draft | No modifications
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_100 works correctly
    assert False, 'TDD RED: test_100 not implemented'


def test_110():
    """
    Malformed verdict | Auto | Verdict missing expected sections |
    Warning, original draft | Graceful degradation
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_110 works correctly
    assert False, 'TDD RED: test_110 not implemented'



# Integration Tests
# -----------------

@pytest.mark.integration
def test_070(test_client):
    """
    Review node integration | Auto | State with APPROVED verdict | State
    with updated_draft | Draft contains resolutions
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_070 works correctly
    assert False, 'TDD RED: test_070 not implemented'


@pytest.mark.integration
def test_080(test_client):
    """
    Finalize node integration | Auto | State with updated_draft | Final
    LLD | LLD contains `- [x]`
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_080 works correctly
    assert False, 'TDD RED: test_080 not implemented'



# E2E Tests
# ---------

@pytest.mark.e2e
def test_t070(test_client):
    """
    End-to-end: review node updates draft on approval | State contains
    updated_draft after approval | RED
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t070 works correctly
    assert False, 'TDD RED: test_t070 not implemented'


@pytest.mark.e2e
def test_t080(test_client):
    """
    End-to-end: finalize uses updated draft | Final LLD contains resolved
    questions | RED
    """
    # TDD: Arrange
    # Set up test data

    # TDD: Act
    # Call the function under test

    # TDD: Assert
    # Verify test_t080 works correctly
    assert False, 'TDD RED: test_t080 not implemented'


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
                                                  90     68    24%
FAIL Required test coverage of 95% not reached. Total coverage: 24.44%
=========================== short test summary info ===========================
FAILED tests/test_issue_257.py::test_id - AssertionError: TDD RED: test_id no...
FAILED tests/test_issue_257.py::test_t010 - AssertionError: TDD RED: test_t01...
FAILED tests/test_issue_257.py::test_t020 - AssertionError: TDD RED: test_t02...
FAILED tests/test_issue_257.py::test_t030 - AssertionError: TDD RED: test_t03...
FAILED tests/test_issue_257.py::test_t040 - AssertionError: TDD RED: test_t04...
FAILED tests/test_issue_257.py::test_t050 - AssertionError: TDD RED: test_t05...
FAILED tests/test_issue_257.py::test_t060 - AssertionError: TDD RED: test_t06...
FAILED tests/test_issue_257.py::test_t090 - AssertionError: TDD RED: test_t09...
FAILED tests/test_issue_257.py::test_010 - AssertionError: TDD RED: test_010 ...
FAILED tests/test_issue_257.py::test_020 - AssertionError: TDD RED: test_020 ...
FAILED tests/test_issue_257.py::test_030 - AssertionError: TDD RED: test_030 ...
FAILED tests/test_issue_257.py::test_040 - AssertionError: TDD RED: test_040 ...
FAILED tests/test_issue_257.py::test_050 - AssertionError: TDD RED: test_050 ...
FAILED tests/test_issue_257.py::test_060 - AssertionError: TDD RED: test_060 ...
FAILED tests/test_issue_257.py::test_090 - AssertionError: TDD RED: test_090 ...
FAILED tests/test_issue_257.py::test_100 - AssertionError: TDD RED: test_100 ...
FAILED tests/test_issue_257.py::test_110 - AssertionError: TDD RED: test_110 ...
FAILED tests/test_issue_257.py::test_070 - AssertionError: TDD RED: test_070 ...
FAILED tests/test_issue_257.py::test_080 - AssertionError: TDD RED: test_080 ...
FAILED tests/test_issue_257.py::test_t070 - AssertionError: TDD RED: test_t07...
FAILED tests/test_issue_257.py::test_t080 - AssertionError: TDD RED: test_t08...
======================= 21 failed, 18 warnings in 1.09s =======================


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
