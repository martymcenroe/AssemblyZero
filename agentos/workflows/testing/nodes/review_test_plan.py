"""N1: Review Test Plan node for TDD Testing Workflow.

Submits the test plan to Gemini for coverage analysis:
- Checks 100% requirement coverage (ADR 0207)
- Ensures no human delegation (real tests required)
- Validates test types match LLD content
"""

import re
from pathlib import Path
from typing import Any

from agentos.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.testing.knowledge.patterns import (
    get_mock_guidance,
    get_required_tools,
)
from agentos.workflows.testing.state import TestingWorkflowState


# Path to the review prompt template
REVIEW_PROMPT_PATH = Path("docs/skills/0706c-Test-Plan-Review-Prompt.md")


# =============================================================================
# Requirement Coverage Utilities (ADR 0207)
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
[x] **APPROVED** - Test plan is ready for implementation
OR
[x] **BLOCKED** - Test plan needs revision

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


def review_test_plan(state: TestingWorkflowState) -> dict[str, Any]:
    """N1: Submit test plan to Gemini for review.

    Args:
        state: Current workflow state.

    Returns:
        State updates with review verdict.
    """
    print("\n[N1] Reviewing test plan...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_review_test_plan(state)

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
    # GUARD: Pre-LLM validation
    # --------------------------------------------------------------------------
    test_scenarios = state.get("test_scenarios", [])
    if not test_scenarios:
        print("    [GUARD] BLOCKED: No test scenarios found in test plan")
        log_workflow_execution(
            target_repo=repo_root,
            issue_number=state.get("issue_number", 0),
            workflow_type="testing",
            event="guard_block",
            details={"reason": "no_test_scenarios", "node": "N1_review_test_plan"},
        )
        return {
            "test_plan_status": "BLOCKED",
            "error_message": "GUARD: No test scenarios found - LLD Section 10 may be missing or malformed",
            "gemini_feedback": "No test scenarios were found in the LLD. Please add Section 10 (Test Plan) with specific test scenarios.",
        }
    # --------------------------------------------------------------------------

    # Call Gemini for review
    try:
        from agentos.core.config import REVIEWER_MODEL
        from agentos.core.gemini_client import GeminiClient

        client = GeminiClient(model=REVIEWER_MODEL)
        result = client.invoke(
            system_instruction="You are a senior QA engineer reviewing a test plan for coverage and quality.",
            content=full_prompt,
        )

        if not result.success:
            print(f"    [ERROR] Gemini review failed: {result.error_message}")
            return {
                "error_message": f"Gemini review failed: {result.error_message}",
                "test_plan_status": "BLOCKED",
            }

        verdict_content = result.response

    except ImportError as e:
        print(f"    [ERROR] Gemini client not available: {e}")
        return {
            "error_message": f"Gemini client not available: {e}",
            "test_plan_status": "BLOCKED",
        }
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

    # Parse verdict
    test_plan_status = _parse_verdict(verdict_content)
    print(f"    Verdict: {test_plan_status}")

    # Log review result
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="test_plan_reviewed",
        details={
            "status": test_plan_status,
            "scenario_count": len(test_scenarios),
        },
    )

    if test_plan_status == "BLOCKED":
        gemini_feedback = _extract_feedback(verdict_content)
        return {
            "test_plan_status": "BLOCKED",
            "test_plan_verdict": verdict_content,
            "gemini_feedback": gemini_feedback,
            "file_counter": file_num,
            "error_message": "Test plan review BLOCKED - requires LLD revision",
        }

    return {
        "test_plan_status": "APPROVED",
        "test_plan_verdict": verdict_content,
        "test_plan_review_prompt": full_prompt,
        "file_counter": file_num,
        "error_message": "",
    }


def _parse_verdict(verdict_content: str) -> str:
    """Parse verdict from Gemini response.

    Args:
        verdict_content: Gemini response text.

    Returns:
        "APPROVED" or "BLOCKED".
    """
    content_upper = verdict_content.upper()

    # Look for explicit verdict markers
    if "[X] **APPROVED**" in content_upper or "[X] APPROVED" in content_upper:
        return "APPROVED"

    if "[X] **BLOCKED**" in content_upper or "[X] BLOCKED" in content_upper:
        return "BLOCKED"

    if "APPROVED" in content_upper and "BLOCKED" not in content_upper:
        return "APPROVED"

    # Default to BLOCKED if unclear
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
        "test_plan_verdict": verdict_content,
        "gemini_feedback": gemini_feedback,
        "file_counter": file_num,
        "error_message": "" if test_plan_status == "APPROVED" else "Test plan review BLOCKED",
    }
