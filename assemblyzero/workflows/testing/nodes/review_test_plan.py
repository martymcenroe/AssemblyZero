"""N1: Review Test Plan node for TDD Testing Workflow.

Submits the test plan to Gemini for coverage analysis:
- Checks 100% requirement coverage (ADR 0207)
- Ensures no human delegation (real tests required)
- Validates test types match LLD content

Issue #166: Requirement coverage utilities moved to shared module
at assemblyzero.core.validation. Legacy functions preserved as
thin wrappers for backward compatibility.

Issue #496: Mechanical gates before Gemini calls — fail fast on
structural issues (missing scenarios, requirements, duplicate names,
insufficient LLD content) to avoid wasting Gemini API calls.
"""

import re
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider
from assemblyzero.core.verdict_schema import VERDICT_SCHEMA, parse_structured_verdict
from assemblyzero.utils.cost_tracker import accumulate_node_cost, accumulate_node_tokens
from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.knowledge.patterns import (
    get_mock_guidance,
    get_required_tools,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Path to the review prompt template
REVIEW_PROMPT_PATH = Path("docs/skills/0706c-Test-Plan-Review-Prompt.md")


# =============================================================================
# Requirement Coverage Utilities (ADR 0207)
# Issue #166: Core logic now in assemblyzero.core.validation.test_plan_validator
# =============================================================================


def extract_requirement_ids(requirements: list[str]) -> set[str]:
    """Extract requirement IDs from a list of requirement strings.

    Handles formats:
    - "REQ-1: Description" -> REQ-1
    - "req-2: Description" -> REQ-2 (normalized)
    - "1. Description" -> REQ-1 (numbered list)

    Args:
        requirements: List of requirement strings.

    Returns:
        Set of normalized requirement IDs (uppercase REQ-X format).
    """
    result = set()

    for req in requirements:
        # Try to match REQ-X pattern (case insensitive)
        req_match = re.match(r"(req-[\w.]+)", req.strip(), re.IGNORECASE)
        if req_match:
            result.add(req_match.group(1).upper())
            continue

        # Try to match numbered list format (1., 2., etc.)
        num_match = re.match(r"(\d+)\.\s", req.strip())
        if num_match:
            result.add(f"REQ-{num_match.group(1)}")

    return result


def extract_covered_requirements(scenarios: list[dict]) -> set[str]:
    """Extract requirement refs from test scenarios.

    Args:
        scenarios: List of test scenario dicts with optional 'requirement_ref' key.

    Returns:
        Set of normalized requirement IDs that have test coverage.
    """
    result = set()

    for scenario in scenarios:
        ref = scenario.get("requirement_ref", "")
        if ref:
            # Normalize to uppercase
            result.add(ref.upper())

    return result


def check_requirement_coverage(
    requirements: list[str], scenarios: list[dict]
) -> dict[str, Any]:
    """Check if all requirements have test coverage.

    Per ADR 0207, LLM-driven development requires 100% requirement coverage.

    Args:
        requirements: List of requirement strings.
        scenarios: List of test scenario dicts.

    Returns:
        Dict with keys: passed, total, covered, coverage_pct, missing
    """
    all_ids = extract_requirement_ids(requirements)
    covered_ids = extract_covered_requirements(scenarios)

    total = len(all_ids)

    if total == 0:
        return {
            "passed": False,
            "total": 0,
            "covered": 0,
            "coverage_pct": 0.0,
            "missing": [],
        }

    # Find which requirements have coverage
    covered = len(all_ids & covered_ids)
    missing = sorted(all_ids - covered_ids)
    coverage_pct = (covered / total) * 100

    return {
        "passed": coverage_pct >= 100.0,
        "total": total,
        "covered": covered,
        "coverage_pct": round(coverage_pct, 2),
        "missing": missing,
    }


def load_review_prompt(repo_root: Path) -> str:
    """Load the test plan review prompt template.

    Args:
        repo_root: Repository root path.

    Returns:
        Review prompt content.
    """
    prompt_path = repo_root / REVIEW_PROMPT_PATH

    if not prompt_path.exists():
        # Use default prompt if file doesn't exist
        return _default_review_prompt()

    return prompt_path.read_text(encoding="utf-8")


def _default_review_prompt() -> str:
    """Default review prompt if file not found."""
    return """# Test Plan Review Prompt

You are reviewing a test plan extracted from a Low-Level Design (LLD) document.
Your goal is to ensure the test plan provides adequate coverage and uses real, executable tests.

## Review Criteria

### 1. Coverage Analysis (CRITICAL)
- [ ] 100% of requirements have corresponding tests (ADR 0207)
- [ ] Each requirement maps to at least one test scenario
- [ ] Edge cases are covered (empty inputs, error conditions, boundaries)

### 2. Test Reality Check (CRITICAL)
- [ ] Tests are executable code, not human manual steps
- [ ] No test delegates to "manual verification"
- [ ] No test says "verify by inspection" or similar
- [ ] Each test has clear assertions

### 3. Test Type Appropriateness
- [ ] Unit tests are truly isolated (mock dependencies)
- [ ] Integration tests test real component interactions
- [ ] E2E tests cover critical user paths

### 4. Mock Strategy
- [ ] External dependencies (APIs, DB) are mocked appropriately
- [ ] Mocks are realistic and don't hide bugs

## Output Format

Provide your verdict in this exact format:

```
## Coverage Analysis
- Requirements covered: X/Y (Z%)
- Missing coverage: [list any gaps]

## Test Reality Issues
- [list any tests that aren't real executable tests]

## Verdict
[ ] **APPROVED** - Test plan is ready for implementation
[ ] **BLOCKED** - Test plan needs revision

Mark EXACTLY ONE option with [X].

## Required Changes (if BLOCKED)
1. [specific change needed]
2. [specific change needed]
```
"""


def build_review_context(state: TestingWorkflowState) -> str:
    """Build the context for Gemini review.

    Args:
        state: Current workflow state.

    Returns:
        Formatted context string.
    """
    test_scenarios = state.get("test_scenarios", [])
    requirements = state.get("requirements", [])
    detected_types = state.get("detected_test_types", [])
    coverage_target = state.get("coverage_target", 90)

    context = f"""# Test Plan for Issue #{state.get("issue_number", 0)}

## Requirements to Cover

{chr(10).join(f"- {req}" for req in requirements)}

## Detected Test Types

{chr(10).join(f"- {t}" for t in detected_types)}

## Required Tools

{chr(10).join(f"- {t}" for t in get_required_tools(detected_types))}

## Mock Guidance

{get_mock_guidance(detected_types)}

## Coverage Target

{coverage_target}%

## Test Scenarios

"""
    for scenario in test_scenarios:
        context += f"""### {scenario.get("name", "Unknown")}
- **Type:** {scenario.get("test_type", "unit")}
- **Requirement:** {scenario.get("requirement_ref", "N/A")}
- **Description:** {scenario.get("description", "N/A")}
- **Mock needed:** {scenario.get("mock_needed", False)}
- **Assertions:** {", ".join(scenario.get("assertions", []))}

"""

    # Include original test plan section
    test_plan_section = state.get("test_plan_section", "")
    if test_plan_section:
        context += f"""## Original Test Plan Section

{test_plan_section}
"""

    return context


def _run_mechanical_gates(state: TestingWorkflowState) -> list[str]:
    """Run mechanical pre-checks before Gemini review.

    Issue #496: Fail fast on structural issues to avoid wasting Gemini
    API calls (~$0.05-0.10 each). Each gate is independent — all errors
    are collected and returned together.

    Args:
        state: Current workflow state.

    Returns:
        List of error messages. Empty list means all gates passed.
    """
    errors: list[str] = []

    # Gate 1: Test scenarios exist
    test_scenarios = state.get("test_scenarios", [])
    if not test_scenarios:
        errors.append(
            "No test scenarios found — LLD Section 10 may be missing or malformed"
        )
        return errors  # Nothing else to check without scenarios

    # Gate 2: Requirements exist
    requirements = state.get("requirements", [])
    if not requirements:
        errors.append(
            "No requirements extracted from LLD — cannot verify coverage"
        )

    # Gate 3: Scenario-to-requirement coverage ratio
    # Each requirement should have at least one scenario covering it
    if requirements and test_scenarios:
        scenario_count = len(test_scenarios)
        req_count = len(requirements)
        if scenario_count < req_count:
            errors.append(
                f"Only {scenario_count} scenario(s) for {req_count} requirement(s) "
                f"— coverage ratio {scenario_count/req_count:.0%} is below 100%"
            )

    # Gate 4: No duplicate scenario names
    if test_scenarios:
        scenario_names = []
        for s in test_scenarios:
            name = s.get("name", "") if isinstance(s, dict) else str(s)
            if name:
                scenario_names.append(name.strip().lower())
        seen = set()
        dupes = set()
        for name in scenario_names:
            if name in seen:
                dupes.add(name)
            seen.add(name)
        if dupes:
            errors.append(
                f"Duplicate scenario name(s): {', '.join(sorted(dupes))}"
            )

    # Gate 5: LLD content has minimum substance
    lld_content = state.get("lld_content", "")
    MIN_LLD_WORDS = 50
    if lld_content:
        word_count = len(lld_content.split())
        if word_count < MIN_LLD_WORDS:
            errors.append(
                f"LLD content too short ({word_count} words, minimum {MIN_LLD_WORDS})"
            )
    else:
        errors.append("No LLD content available for review")

    return errors


def review_test_plan(state: TestingWorkflowState) -> dict[str, Any]:
    """N1: Submit test plan to Gemini for review.

    Args:
        state: Current workflow state.

    Returns:
        State updates with review verdict.
    """
    gate_log("[N1] Reviewing test plan...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_review_test_plan(state)

    # Issue #547: Skip-on-resume — don't re-call Gemini if already approved
    if state.get("test_plan_status") == "APPROVED":
        gate_log("[N1] Test plan already approved — skipping Gemini review")
        return {}

    # Get repo root
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Load review prompt
    review_prompt = load_review_prompt(repo_root)

    # Build review context
    context = build_review_context(state)

    # Combine prompt and context
    full_prompt = f"{review_prompt}\n\n---\n\n{context}"

    # Save prompt to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "review-prompt.md", full_prompt)
    else:
        file_num = state.get("file_counter", 0)

    print(f"    Scenarios: {len(state.get('test_scenarios', []))}")
    print(f"    Requirements: {len(state.get('requirements', []))}")

    # --------------------------------------------------------------------------
    # GUARD: Pre-LLM mechanical gates (Issue #496)
    # Fail fast before expensive Gemini calls
    # --------------------------------------------------------------------------
    guard_errors = _run_mechanical_gates(state)
    if guard_errors:
        reason = "; ".join(guard_errors)
        print(f"    [GUARD] BLOCKED: {reason}")
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="guard_block",
            details={
                "reason": "mechanical_gate_failure",
                "errors": guard_errors,
                "node": "N1_review_test_plan",
            },
        )
        return {
            "test_plan_status": "BLOCKED",
            "error_message": f"GUARD: Mechanical pre-checks failed — {reason}",
            "gemini_feedback": "\n".join(f"- {e}" for e in guard_errors),
        }
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # Issue #509: Pre-flight fast-path — skip Gemini when mechanical checks
    # pass at 100% coverage. Saves ~$0.05-0.10 per call.
    # --------------------------------------------------------------------------
    test_scenarios = state.get("test_scenarios", [])
    requirements = state.get("requirements", [])
    coverage_result = check_requirement_coverage(requirements, test_scenarios)

    if coverage_result["passed"]:
        print(f"    [FAST-PATH] 100% requirement coverage ({coverage_result['covered']}/{coverage_result['total']}) — skipping Gemini review")
        fast_verdict = (
            f"## Mechanical Review (auto-approved)\n\n"
            f"- Requirements covered: {coverage_result['covered']}/{coverage_result['total']} "
            f"({coverage_result['coverage_pct']}%)\n"
            f"- Scenarios: {len(test_scenarios)}\n"
            f"- Gate: All mechanical pre-checks passed\n\n"
            f"## Verdict\n[x] **APPROVED** — 100% coverage, mechanical gates passed\n"
        )

        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "verdict-mechanical.md", fast_verdict)

        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="test_plan_reviewed",
            details={
                "status": "APPROVED",
                "method": "mechanical_fast_path",
                "scenario_count": len(test_scenarios),
                "coverage_pct": coverage_result["coverage_pct"],
            },
        )

        return {
            "test_plan_status": "APPROVED",
            "test_plan_verdict": fast_verdict,
            "test_plan_review_prompt": full_prompt,
            "file_counter": file_num,
            "error_message": "",
            "node_costs": dict(state.get("node_costs", {})),
            "node_tokens": dict(state.get("node_tokens", {})),
        }
    # --------------------------------------------------------------------------

    # Issue #773: Use unified LLM provider instead of hardcoded GeminiClient
    reviewer_spec = state.get("config_reviewer", "claude:opus")
    if state.get("mock_mode", False):
        reviewer_spec = "mock:review"
    print(f"    Reviewer: {reviewer_spec}")

    # Issue #773: Pass effort level to Claude reviewer
    effort = state.get("config_effort")
    try:
        reviewer = get_provider(reviewer_spec, effort=effort)
    except ValueError as e:
        return {
            "error_message": f"Invalid reviewer: {e}",
            "test_plan_status": "BLOCKED",
        }

    cost_before = get_cumulative_cost()
    try:
        import time

        # N1 Retry: 2 attempts with exponential backoff
        max_attempts = 2
        last_error = ""
        result = None

        for attempt in range(1, max_attempts + 1):
            # Issue #773: Pass response_schema to all providers uniformly
            result = reviewer.invoke(
                system_prompt="You are a senior QA engineer reviewing a test plan for coverage and quality.",
                content=full_prompt,
                response_schema=VERDICT_SCHEMA,
            )

            if result.success:
                break

            last_error = result.error_message or "Unknown error"
            print(f"    [N1] Reviewer attempt {attempt}/{max_attempts} failed: {last_error}")

            if attempt < max_attempts:
                backoff = 2 ** attempt  # 2s, 4s
                print(f"    [N1] Retrying in {backoff}s...")
                time.sleep(backoff)

        if not result or not result.success:
            error_msg = f"Reviewer failed after {max_attempts} attempts: {last_error}"
            print(f"    [ERROR] {error_msg}")

            # Save error to audit trail
            if audit_dir.exists():
                file_num = next_file_number(audit_dir)
                save_audit_file(
                    audit_dir,
                    file_num,
                    "reviewer-error.md",
                    f"# Review Error\n\nAttempts: {max_attempts}\nLast error: {last_error}\n",
                )

            return {
                "error_message": error_msg,
                "test_plan_status": "BLOCKED",
            }

        verdict_content = result.response
        node_cost_usd = get_cumulative_cost() - cost_before

    except Exception as e:
        print(f"    [ERROR] Unexpected error during review: {e}")
        return {
            "error_message": f"Review error: {e}",
            "test_plan_status": "BLOCKED",
        }

    # Save verdict to audit trail
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "verdict.md", verdict_content)

    # Issue #494: Parse verdict — structured JSON first, regex fallback
    structured = parse_structured_verdict(verdict_content)
    verdict_method = "regex"
    if structured:
        test_plan_status = structured["verdict"]
        # Map REVISE -> BLOCKED for workflow purposes
        if test_plan_status == "REVISE":
            test_plan_status = "BLOCKED"
        verdict_method = "structured"
        print(f"    Verdict: {test_plan_status} (structured JSON)")
    else:
        test_plan_status = _parse_verdict(verdict_content)
        print(f"    Verdict: {test_plan_status} (regex fallback)")

    # Log review result
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="test_plan_reviewed",
        details={
            "status": test_plan_status,
            "scenario_count": len(test_scenarios),
            "verdict_method": verdict_method,
        },
    )

    # Issue #511: Accumulate per-node cost
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "review_test_plan", node_cost_usd,
    )
    node_tokens = accumulate_node_tokens(
        dict(state.get("node_tokens", {})),
        "review_test_plan",
        getattr(result, "input_tokens", 0) if result else 0,
        getattr(result, "output_tokens", 0) if result else 0,
    )

    if test_plan_status == "BLOCKED":
        # Issue #494: Extract feedback from structured data if available
        if structured:
            feedback_parts = []
            if structured.get("summary"):
                feedback_parts.append(structured["summary"])
            for issue in structured.get("blocking_issues", []):
                feedback_parts.append(
                    f"[{issue.get('severity', 'BLOCKING')}] {issue.get('section', '?')}: {issue.get('issue', '?')}"
                )
            gemini_feedback = "\n".join(feedback_parts) if feedback_parts else _extract_feedback(verdict_content)
        else:
            gemini_feedback = _extract_feedback(verdict_content)
        return {
            "test_plan_status": "BLOCKED",
            "test_plan_verdict": f"BLOCKED: {gemini_feedback[:200]}",
            "gemini_feedback": gemini_feedback,
            "file_counter": file_num,
            "error_message": "Test plan review BLOCKED - requires LLD revision",
            "node_costs": node_costs,  # Issue #511
            "node_tokens": node_tokens,  # Issue #511
        }

    return {
        "test_plan_status": "APPROVED",
        "test_plan_verdict": (
            f"APPROVED: {structured.get('summary', 'Test plan approved')[:200]}"
            if structured
            else "APPROVED"
        ),
        "test_plan_review_prompt": full_prompt,
        "file_counter": file_num,
        "error_message": "",
        "node_costs": node_costs,  # Issue #511
        "node_tokens": node_tokens,  # Issue #511
    }


def _parse_verdict(verdict_content: str) -> str:
    """Parse verdict from Gemini response.

    Issue #385: More robust parsing to avoid false BLOCKED results.
    Checks checked checkboxes first, then verdict keyword patterns,
    then falls back to keyword presence with priority to APPROVED.

    Args:
        verdict_content: Gemini response text.

    Returns:
        "APPROVED" or "BLOCKED".
    """
    content_upper = verdict_content.upper()

    # Primary: Look for checked checkboxes [X] or [x]
    has_approved_checked = bool(
        re.search(r"\[X\]\s*\**APPROVED\**", content_upper)
    )
    has_blocked_checked = bool(
        re.search(r"\[X\]\s*\**BLOCKED\**", content_upper)
    )

    # If only one is checked, use it
    if has_approved_checked and not has_blocked_checked:
        return "APPROVED"
    if has_blocked_checked and not has_approved_checked:
        return "BLOCKED"

    # Secondary: Look for "Verdict: X" pattern
    verdict_match = re.search(
        r"VERDICT[:\s]+\**\s*(APPROVED|BLOCKED)\b", content_upper
    )
    if verdict_match:
        return verdict_match.group(1)

    # Tertiary: If both or neither checkbox found, check verdict section
    # Look for the ## Verdict section and see what's checked there
    verdict_section = re.search(
        r"##\s*VERDICT\s*\n(.*?)(?=\n##|\Z)", content_upper, re.DOTALL
    )
    if verdict_section:
        section_text = verdict_section.group(1)
        if "APPROVED" in section_text and "BLOCKED" not in section_text:
            return "APPROVED"
        if "BLOCKED" in section_text and "APPROVED" not in section_text:
            return "BLOCKED"

    # Fallback: presence of keywords (APPROVED gets priority)
    if "APPROVED" in content_upper:
        return "APPROVED"

    # Default to BLOCKED if truly unclear
    return "BLOCKED"


def _extract_feedback(verdict_content: str) -> str:
    """Extract required changes from verdict.

    Args:
        verdict_content: Gemini response text.

    Returns:
        Feedback string.
    """
    # Look for "Required Changes" section
    import re

    pattern = r"##\s*Required Changes[^\n]*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, verdict_content, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    # Fallback: look for numbered items after "BLOCKED"
    pattern = r"BLOCKED[^\n]*\n((?:\d+\.[^\n]+\n?)+)"
    match = re.search(pattern, verdict_content, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return "See full verdict for details."


def _mock_review_test_plan(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing.

    Actually checks requirement coverage to generate realistic mock responses.
    """
    audit_dir = Path(state.get("audit_dir", ""))
    requirements = state.get("requirements", [])
    test_scenarios = state.get("test_scenarios", [])

    # Actually check requirement coverage
    coverage = check_requirement_coverage(requirements, test_scenarios)

    if coverage["passed"]:
        verdict_content = f"""## Coverage Analysis
- Requirements covered: {coverage['covered']}/{coverage['total']} ({coverage['coverage_pct']}%)
- Missing coverage: None

## Test Reality Issues
- None found

## Verdict
[x] **APPROVED** - Test plan is ready for implementation
"""
        test_plan_status = "APPROVED"
        gemini_feedback = ""
    else:
        missing_str = ", ".join(coverage["missing"])
        verdict_content = f"""## Coverage Analysis
- Requirements covered: {coverage['covered']}/{coverage['total']} ({coverage['coverage_pct']}%)
- Missing coverage: {missing_str}

## Test Reality Issues
- None found

## Verdict
[x] **BLOCKED** - Test plan needs revision

## Required Changes
1. Add tests for missing requirements: {missing_str}
"""
        test_plan_status = "BLOCKED"
        gemini_feedback = f"Add tests for missing requirements: {missing_str}"

    # Save to audit
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "verdict.md", verdict_content)
    else:
        file_num = state.get("file_counter", 0)

    print(f"    [MOCK] Verdict: {test_plan_status}")

    return {
        "test_plan_status": test_plan_status,
        "test_plan_verdict": f"{test_plan_status}: {gemini_feedback[:200]}" if gemini_feedback else test_plan_status,
        "gemini_feedback": gemini_feedback,
        "file_counter": file_num,
        "error_message": "" if test_plan_status == "APPROVED" else "Test plan review BLOCKED",
    }
