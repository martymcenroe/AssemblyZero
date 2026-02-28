"""N5: Review Spec node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Uses the configured reviewer LLM (Gemini) to perform an implementation
readiness review of the generated spec draft. This is a semantic review
that evaluates whether the spec contains enough concrete detail for
autonomous AI implementation.

This is distinct from N3 (mechanical validation): N3 checks for structural
completeness (excerpts, examples, etc.), while N5 evaluates whether the
spec is actually implementable (clear instructions, consistent patterns,
realistic examples, no ambiguity).

This node populates:
- review_verdict: "APPROVED", "REVISE", or "BLOCKED"
- review_feedback: Gemini's detailed review comments
- review_iteration: Current review round (unchanged; N2 increments on revision)
- error_message: "" on success, error text on failure
"""

import difflib
import re
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider
from assemblyzero.utils.cost_tracker import accumulate_node_cost, accumulate_node_tokens
from assemblyzero.core.verdict_schema import VERDICT_SCHEMA, parse_structured_verdict
from assemblyzero.workflows.requirements.audit import (
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.implementation_spec.state import ImplementationSpecState


# =============================================================================
# Constants
# =============================================================================

# Default reviewer model spec
DEFAULT_REVIEWER = "gemini:3-pro-preview"

# Minimum spec size to be considered valid (bytes)
MIN_SPEC_SIZE = 100

# Maximum spec size to review (prevent prompt blow-up)
MAX_SPEC_SIZE = 200_000

# System prompt for Gemini readiness review
REVIEWER_SYSTEM_PROMPT = """\
You are a Senior Software Architect performing an Implementation Readiness Review.

Your role is to evaluate whether an Implementation Spec provides enough \
concrete detail for an autonomous AI agent to implement the changes with \
>80% first-try success rate.

CRITICAL INSTRUCTIONS:
1. You are reviewing an IMPLEMENTATION SPEC, not source code or a PR.
2. Your focus is EXECUTABILITY: Could an AI agent read this spec and produce \
correct code without asking questions?
3. You must provide a structured verdict: APPROVED, REVISE, or BLOCKED.
4. Be specific about what needs to change for REVISE/BLOCKED verdicts.

You are NOT reviewing:
- Code quality (there is no code yet)
- Test coverage (tests haven't been written yet)
- PR readiness (this is pre-implementation)

You ARE reviewing:
- Completeness: Are all files covered with specific instructions?
- Concreteness: Are there real code excerpts, not just descriptions?
- Specificity: Could someone write exact diffs from the instructions?
- Consistency: Do patterns, naming, and structure match the codebase?
- Feasibility: Are the instructions technically achievable?"""


# =============================================================================
# Main Node
# =============================================================================


def review_spec(state: ImplementationSpecState) -> dict[str, Any]:
    """N5: Send spec to Gemini for implementation readiness review.

    Issue #304: Implementation Readiness Review Workflow

    Steps:
    1. Guard against empty/invalid spec drafts
    2. Build review prompt with spec and LLD context
    3. Call configured reviewer LLM (Gemini)
    4. Parse verdict from response
    5. Save verdict to audit trail
    6. Return state updates

    Args:
        state: Current workflow state. Requires:
            - spec_draft: Generated Implementation Spec markdown (from N2)
            - lld_content: Original LLD for reference
            - issue_number: GitHub issue number
            - assemblyzero_root: Path to AssemblyZero installation

    Returns:
        Dict with state field updates:
        - review_verdict: "APPROVED", "REVISE", or "BLOCKED"
        - review_feedback: Gemini's detailed review comments
        - error_message: "" on success, error text on failure
    """
    # Extract state
    spec_draft = state.get("spec_draft", "")
    lld_content = state.get("lld_content", "")
    issue_number = state.get("issue_number", 0)
    review_iteration = state.get("review_iteration", 0)
    max_iterations = state.get("max_iterations", 3)
    mock_mode = state.get("config_mock_mode", False)

    print(f"\n[N5] Reviewing Implementation Spec (iteration {review_iteration})...")

    # -------------------------------------------------------------------------
    # GUARD: Iteration bounds
    # -------------------------------------------------------------------------
    if review_iteration >= max_iterations:
        print(f"    [GUARD] Max iterations ({max_iterations}) reached")
        return {
            "review_verdict": "BLOCKED",
            "review_feedback": (
                f"Maximum review iterations ({max_iterations}) exceeded. "
                "Spec could not pass readiness review within allowed attempts."
            ),
            "error_message": "",
        }

    # -------------------------------------------------------------------------
    # GUARD: Pre-LLM content validation
    # -------------------------------------------------------------------------
    if not spec_draft or not spec_draft.strip():
        print("    [GUARD] BLOCKED: Spec draft is empty")
        return {
            "review_verdict": "BLOCKED",
            "review_feedback": "Spec draft is empty. Cannot perform readiness review.",
            "error_message": "GUARD: Spec draft is empty",
        }

    content_len = len(spec_draft)
    if content_len < MIN_SPEC_SIZE:
        print(f"    [GUARD] WARNING: Spec suspiciously short ({content_len} chars)")

    if content_len > MAX_SPEC_SIZE:
        print(f"    [GUARD] Truncating spec from {content_len} to {MAX_SPEC_SIZE} chars")
        spec_draft = spec_draft[:MAX_SPEC_SIZE] + "\n\n<!-- Truncated for review -->\n"

    # -------------------------------------------------------------------------
    # Build review content
    # -------------------------------------------------------------------------
    # Issue #491: Pass previous spec draft for diff-aware review
    previous_spec_draft = state.get("previous_spec_draft", "")
    review_content = _build_review_content(
        spec_draft=spec_draft,
        lld_content=lld_content,
        issue_number=issue_number,
        review_iteration=review_iteration,
        previous_spec_draft=previous_spec_draft,
    )

    # -------------------------------------------------------------------------
    # Get reviewer provider
    # -------------------------------------------------------------------------
    if mock_mode:
        reviewer_spec = "mock:review"
    else:
        reviewer_spec = state.get("config_reviewer", DEFAULT_REVIEWER)

    try:
        reviewer = get_provider(reviewer_spec)
    except ValueError as e:
        print(f"    ERROR: Invalid reviewer: {e}")
        return {"error_message": f"Invalid reviewer: {e}"}

    print(f"    Reviewer: {reviewer_spec}")

    # -------------------------------------------------------------------------
    # Call reviewer LLM
    # Issue #492: Pass structured schema when reviewer is Gemini
    # -------------------------------------------------------------------------
    invoke_kwargs: dict = {
        "system_prompt": REVIEWER_SYSTEM_PROMPT,
        "content": review_content,
    }
    is_gemini = reviewer_spec.startswith("gemini:")
    if is_gemini and hasattr(reviewer, "invoke") and not mock_mode:
        invoke_kwargs["response_schema"] = VERDICT_SCHEMA

    cost_before = get_cumulative_cost()
    result = reviewer.invoke(**invoke_kwargs)
    node_cost_usd = get_cumulative_cost() - cost_before

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Reviewer failed: {result.error_message}"}

    # Issue #476: Budget check
    cumulative = get_cumulative_cost()
    budget = state.get("cost_budget_usd", 0.0)
    if budget > 0 and cumulative > budget:
        msg = f"[BUDGET] ${cumulative:.2f} exceeds ${budget:.2f} budget. Halting."
        print(f"    {msg}")
        return {"error_message": msg}

    verdict_content = result.response or ""

    # -------------------------------------------------------------------------
    # Save verdict to audit trail
    # -------------------------------------------------------------------------
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    verdict_path = None

    if audit_dir and audit_dir.exists():
        file_num = next_file_number(audit_dir)
        verdict_path = save_audit_file(
            audit_dir, file_num, "readiness-verdict.md", verdict_content
        )

    # -------------------------------------------------------------------------
    # Parse verdict
    # Issue #492: Try structured JSON parsing first, fall back to regex
    # -------------------------------------------------------------------------
    structured = parse_structured_verdict(verdict_content) if is_gemini else None
    if structured:
        verdict_status = structured["verdict"]
        feedback = structured.get("summary", "")
        blocking = structured.get("blocking_issues", [])
        if blocking:
            feedback += "\n\n## Blocking Issues\n"
            for issue in blocking:
                feedback += f"- [{issue.get('severity', 'HIGH')}] {issue.get('section', '')}: {issue.get('issue', '')}\n"
        suggestions = structured.get("suggestions", [])
        if suggestions:
            feedback += "\n\n## Suggestions\n"
            for s in suggestions:
                feedback += f"- {s}\n"
        print(f"    Parsed structured verdict: {verdict_status}")
    else:
        verdict_status, feedback = parse_review_verdict(verdict_content)

    # -------------------------------------------------------------------------
    # Report results
    # -------------------------------------------------------------------------
    verdict_lines = len(verdict_content.splitlines()) if verdict_content else 0
    print(f"    Verdict: {verdict_status} ({verdict_lines} lines)")
    if verdict_path:
        print(f"    Saved: {verdict_path.name}")

    if verdict_status == "REVISE" and feedback:
        # Show a preview of feedback
        feedback_preview = feedback[:200].replace("\n", " ")
        if len(feedback) > 200:
            feedback_preview += "..."
        print(f"    Feedback: {feedback_preview}")

    # Issue #511: Accumulate per-node cost
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "review_spec", node_cost_usd,
    )
    node_tokens = accumulate_node_tokens(
        dict(state.get("node_tokens", {})),
        "review_spec",
        result.input_tokens,
        result.output_tokens,
    )

    return {
        "review_verdict": verdict_status,
        "review_feedback": feedback,
        "error_message": "",
        "node_costs": node_costs,  # Issue #511
        "node_tokens": node_tokens,  # Issue #511
    }


# =============================================================================
# Review Content Builder
# =============================================================================


def _build_review_content(
    spec_draft: str,
    lld_content: str,
    issue_number: int,
    review_iteration: int,
    previous_spec_draft: str = "",
) -> str:
    """Build the review content for the Gemini reviewer.

    Constructs a structured prompt containing the spec draft, the original
    LLD for reference, and review criteria.

    Issue #491: When previous_spec_draft exists and changes are <20% of total,
    prepend a unified diff to focus the reviewer on what changed.

    Args:
        spec_draft: Generated Implementation Spec markdown.
        lld_content: Original LLD markdown for cross-reference.
        issue_number: GitHub issue number.
        review_iteration: Current review iteration (0-based).
        previous_spec_draft: Previous spec draft for diff comparison.

    Returns:
        Complete review prompt string.
    """
    sections: list[str] = []

    # Context header
    context = f"## Review Context\n\n"
    context += f"- **Issue:** #{issue_number}\n"
    context += f"- **Review Iteration:** {review_iteration}\n"
    if review_iteration > 0:
        context += (
            "- **Note:** This is a REVISED spec. Previous review(s) "
            "requested changes. Focus on whether the revisions address "
            "the prior feedback.\n"
        )
    sections.append(context)

    # Issue #491: Add diff section for revisions with small changes
    if previous_spec_draft and review_iteration > 0:
        prev_lines = previous_spec_draft.splitlines(keepends=True)
        curr_lines = spec_draft.splitlines(keepends=True)
        diff = list(difflib.unified_diff(prev_lines, curr_lines, n=3))

        if diff:
            changed_lines = sum(
                1 for line in diff
                if line.startswith("+")
                and not line.startswith("+++")
            )
            total_lines = max(len(curr_lines), 1)
            change_ratio = changed_lines / total_lines

            if change_ratio <= 0.20:
                diff_text = "".join(diff)
                sections.append(
                    f"## CHANGES SINCE LAST REVIEW (unified diff)\n\n"
                    f"Focus your review on these changes.\n\n"
                    f"```diff\n{diff_text}```"
                )

    # Implementation Spec to review
    sections.append(
        f"## Implementation Spec to Review\n\n{spec_draft}"
    )

    # Original LLD for cross-reference (truncated if very large)
    if lld_content:
        lld_excerpt = lld_content
        if len(lld_excerpt) > 50_000:
            lld_excerpt = lld_excerpt[:50_000] + "\n\n<!-- LLD truncated for review -->\n"
        sections.append(
            f"## Original LLD (for cross-reference)\n\n{lld_excerpt}"
        )

    # Review criteria
    sections.append(_get_review_criteria())

    # Output format instructions
    sections.append(_get_output_format())

    return "\n\n".join(sections)


def _get_review_criteria() -> str:
    """Return the readiness review criteria.

    These criteria are distinct from the 0703c Implementation Review Prompt
    (which reviews actual code). This reviews the SPEC that will guide
    code generation.

    Returns:
        Review criteria as formatted markdown string.
    """
    return """\
## Readiness Review Criteria

Evaluate the Implementation Spec against these criteria:

### 1. File Coverage (BLOCKING)
- Does the spec address EVERY file listed in the LLD's Section 2.1?
- Does each "Modify" file include a current state excerpt?
- Does each "Add" file include the complete expected content or clear generation instructions?

### 2. Specificity (BLOCKING)
- Are change instructions specific enough to generate diffs?
- Do instructions include before/after code snippets where applicable?
- Are line-level references provided for modifications?
- Would an AI agent need to ask clarifying questions?

### 3. Concreteness (HIGH PRIORITY)
- Does every data structure have a concrete JSON/YAML example with realistic values?
- Does every function signature have input/output examples with actual values?
- Are there real code snippets (not pseudocode) for key implementations?

### 4. Pattern Consistency (HIGH PRIORITY)
- Do the patterns referenced actually exist in the codebase?
- Are naming conventions consistent with the existing codebase?
- Does the proposed implementation follow established project patterns?

### 5. Feasibility (HIGH PRIORITY)
- Are the proposed changes technically achievable?
- Are dependencies correctly identified?
- Are there any circular dependencies or ordering issues?
- Is the scope appropriate (not too large for a single implementation)?

### 6. Test Guidance (SUGGESTION)
- Does the spec include test file locations and patterns?
- Are test cases concrete enough to implement?"""


def _get_output_format() -> str:
    """Return the expected output format for the verdict.

    Returns:
        Output format instructions as formatted markdown string.
    """
    return """\
## Required Output Format

You MUST structure your review as follows:

```
## Readiness Review: Issue #{issue_number}

## Summary
{2-3 sentence overall assessment of the spec's readiness for implementation}

## File Coverage Assessment
{For each file in the LLD: covered/not covered, quality of instructions}

## Blocking Issues
{If none: "No blocking issues found."}
{If any: numbered list with specific file/section references}

## High Priority Issues
{If none: "No high-priority issues found."}
{If any: numbered list with specific recommendations}

## Suggestions
{Brief bullet points for improvements}

## Verdict
[ ] **APPROVED** - Spec is ready for implementation
[ ] **REVISE** - Fix blocking/high-priority issues first
[ ] **BLOCKED** - Fundamental issues prevent implementation
```

IMPORTANT:
- Mark EXACTLY ONE verdict checkbox with [X]
- If REVISE or BLOCKED, list SPECIFIC changes needed
- Reference specific sections/files from the spec in your feedback"""


# =============================================================================
# Verdict Parsing
# =============================================================================


def parse_review_verdict(response: str) -> tuple[str, str]:
    """Extract verdict and feedback from Gemini response.

    Parses the structured Gemini response to extract:
    1. The verdict (APPROVED, REVISE, or BLOCKED)
    2. The full feedback content for revision prompts

    The verdict is determined by checked checkboxes in the response:
    - [X] **APPROVED** -> "APPROVED"
    - [X] **REVISE** -> "REVISE"
    - [X] **BLOCKED** -> "BLOCKED"

    Falls back to keyword matching if no checkboxes found.

    Args:
        response: Raw Gemini response text.

    Returns:
        Tuple of (verdict_status, feedback_text).
        verdict_status: One of "APPROVED", "REVISE", "BLOCKED".
        feedback_text: The full response as feedback for revision prompts.
    """
    if not response or not response.strip():
        return "BLOCKED", "Empty review response received."

    response_upper = response.upper()

    # -------------------------------------------------------------------
    # Primary: Check for checked checkboxes (structured verdict)
    # -------------------------------------------------------------------
    if re.search(r"\[X\]\s*\**APPROVED\**", response_upper):
        verdict = "APPROVED"
    elif re.search(r"\[X\]\s*\**REVISE\**", response_upper):
        verdict = "REVISE"
    elif re.search(r"\[X\]\s*\**BLOCKED\**", response_upper):
        verdict = "BLOCKED"
    # -------------------------------------------------------------------
    # Secondary: Check for "Verdict: X" pattern
    # -------------------------------------------------------------------
    elif "VERDICT: APPROVED" in response_upper:
        verdict = "APPROVED"
    elif "VERDICT: REVISE" in response_upper:
        verdict = "REVISE"
    elif "VERDICT: BLOCKED" in response_upper:
        verdict = "BLOCKED"
    # -------------------------------------------------------------------
    # Tertiary: Check for DISCUSS (maps to BLOCKED)
    # -------------------------------------------------------------------
    elif re.search(r"\[X\]\s*\**DISCUSS\**", response_upper):
        verdict = "BLOCKED"
    # -------------------------------------------------------------------
    # Fallback: Default to BLOCKED (safe choice)
    # -------------------------------------------------------------------
    else:
        verdict = "BLOCKED"

    # -------------------------------------------------------------------
    # Extract feedback
    # -------------------------------------------------------------------
    # Use the full response as feedback for the revision prompt.
    # This ensures the drafter has full context when revising.
    feedback = _extract_feedback(response, verdict)

    return verdict, feedback


def _extract_feedback(response: str, verdict: str) -> str:
    """Extract actionable feedback from the review response.

    For APPROVED verdicts, extracts suggestions section if present.
    For REVISE/BLOCKED verdicts, extracts blocking issues, high priority
    issues, and suggestions as combined feedback.

    Args:
        response: Full Gemini review response.
        verdict: Parsed verdict status.

    Returns:
        Extracted feedback text for use in revision prompts.
    """
    if verdict == "APPROVED":
        # For APPROVED, only return suggestions (if any)
        suggestions = _extract_section(response, "Suggestions")
        if suggestions:
            return f"Approved with suggestions:\n{suggestions}"
        return "Approved. No changes needed."

    # For REVISE/BLOCKED, combine all actionable feedback
    feedback_parts: list[str] = []

    blocking = _extract_section(response, "Blocking Issues")
    if blocking:
        feedback_parts.append(f"## Blocking Issues\n{blocking}")

    high_priority = _extract_section(response, "High Priority Issues")
    if high_priority:
        feedback_parts.append(f"## High Priority Issues\n{high_priority}")

    file_coverage = _extract_section(response, "File Coverage Assessment")
    if file_coverage:
        feedback_parts.append(f"## File Coverage Assessment\n{file_coverage}")

    suggestions = _extract_section(response, "Suggestions")
    if suggestions:
        feedback_parts.append(f"## Suggestions\n{suggestions}")

    if feedback_parts:
        return "\n\n".join(feedback_parts)

    # Fallback: return the full response as feedback
    return response


def _extract_section(content: str, section_name: str) -> str:
    """Extract content from a named markdown section.

    Extracts text between a ## heading matching section_name and the
    next ## heading (or end of document).

    Args:
        content: Full markdown content.
        section_name: Name of the section to extract (without ## prefix).

    Returns:
        Section content (without the heading), or empty string if not found.
    """
    # Match section heading (## or ###)
    pattern = (
        rf"^##\s*#?\s*{re.escape(section_name)}\s*\n"
        rf"(.*?)"
        rf"(?=^##\s|\Z)"
    )
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""