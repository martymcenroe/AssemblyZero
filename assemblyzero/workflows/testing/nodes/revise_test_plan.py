"""N1.5: Revise Test Plan node — recover from BLOCKED at N1 (#1072).

When N1 (review_test_plan) returns BLOCKED, the workflow used to END.
With this node in the graph, the BLOCKED feedback is fed back to an
LLM revisor that produces a fresh Test Scenarios table; the loop then
returns to N1 for re-review. Hard cap: 2 revision cycles before END.

The revisor is invoked via the same provider abstraction as N1 with
the #1071 retry policy, so transient failures during revision retry
in line with the operator's --retry-policy flag.

Mock mode produces deterministic scenarios from the requirements list,
identical to _mock_review_test_plan's coverage shape — used by tests.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from assemblyzero.workflows.testing.state import TestingWorkflowState

logger = logging.getLogger(__name__)


# Maximum revision cycles before END. Hard cap prevents infinite loops
# when the LLM cannot fix the underlying issue. Per #1072 acceptance.
MAX_REVISION_CYCLES = 2


# Pattern: T001 / T1 / 001 — captured by the same regex used in
# extract_test_scenarios (test_plan_validator.py). Mirroring that here
# so revisions produce IDs the validator will recognize.
_SCENARIO_ID_PATTERN = re.compile(r"^(?:T?\d+)$", re.IGNORECASE)


def _build_revision_prompt(
    lld_content: str,
    feedback: str,
    requirements: list[str],
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the test-plan revisor."""
    requirement_block = "\n".join(f"- {r}" for r in requirements) or "(none)"
    system_prompt = (
        "You are revising the Test Scenarios table in a Low-Level Design "
        "(LLD) document. The previous test plan was rejected with the "
        "feedback below. Output ONLY a markdown table with columns: "
        "ID | Scenario | Type | Requirements. Use IDs T001, T002, ... "
        "Use types: unit | integration | e2e | benchmark | smoke. "
        "Reference requirements as 'Req N' or 'REQ-N' in the Requirements "
        "column. Cover EVERY requirement listed; the table must have at "
        "least one row per requirement. Address every BLOCKING issue "
        "called out in the feedback. Do NOT add prose, explanations, or "
        "commentary — only the table."
    )
    user_prompt = (
        f"## Reviewer feedback (BLOCKED — must be addressed)\n\n"
        f"{feedback or '(no feedback provided)'}\n\n"
        f"## Requirements to cover\n\n"
        f"{requirement_block}\n\n"
        f"## Current LLD content (for context)\n\n"
        f"{lld_content[:8000]}"  # cap to avoid bloating the prompt
    )
    return system_prompt, user_prompt


def _parse_scenarios_from_table(table_md: str) -> list[dict[str, Any]]:
    """Parse a revised scenarios table into [scenario] dicts.

    Mirrors the parsing logic in
    test_plan_validator.extract_test_scenarios so the gate logic at
    N1 sees the same shape regardless of whether the scenarios came
    from the LLD or from a revision.

    Each row produces:

        {
            "name": "T001_short_name",
            "test_type": "unit",
            "requirement_ref": "REQ-1",  # primary req for fast-path
            "description": "...",
            "assertions": [],
            "mock_needed": False,
        }
    """
    scenarios: list[dict[str, Any]] = []
    for raw_line in table_md.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        # Skip separator rows
        if all(set(c) <= set("-: ") for c in cells):
            continue
        # Skip header rows
        if cells[0].lower() in ("id", "test id", "#"):
            continue
        if not _SCENARIO_ID_PATTERN.match(cells[0]):
            continue

        scenario_id = cells[0].upper()
        if not scenario_id.startswith("T"):
            scenario_id = f"T{scenario_id.zfill(3)}"

        description = cells[1] if len(cells) > 1 else ""
        test_type = (cells[2] if len(cells) > 2 else "unit").lower()

        # Find first requirement reference in the row text
        full_row = " ".join(cells)
        req_match = re.search(
            r"\b(?:req(?:uirement)?)\s*[-.]?\s*(\d+)\b",
            full_row,
            re.IGNORECASE,
        )
        requirement_ref = f"REQ-{req_match.group(1)}" if req_match else ""

        # Build a name out of the ID + a slug of the description
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", description).strip("_").lower()
        slug = (slug[:40]) if slug else "scenario"
        name = f"{scenario_id.lower()}_{slug}"

        scenarios.append({
            "name": name,
            "test_type": test_type,
            "requirement_ref": requirement_ref,
            "description": description,
            "assertions": [],
            "mock_needed": False,
        })
    return scenarios


def _mock_revise(state: TestingWorkflowState) -> dict[str, Any]:
    """Deterministic revision used in test mode.

    Produces one scenario per requirement, satisfying both the gate-3
    (scenario count >= requirement count) and the fast-path (100%
    coverage by requirement_ref) checks.
    """
    requirements = state.get("requirements", [])
    revision_count = state.get("test_plan_revision_count", 0) + 1

    scenarios: list[dict[str, Any]] = []
    table_lines = ["| ID | Scenario | Type | Requirements |", "|---|---|---|---|"]
    for i, req_text in enumerate(requirements, start=1):
        sid = f"T{i:03d}"
        # Extract REQ-N from the requirement string if present
        req_match = re.match(r"(req-[\w.]+)", req_text.strip(), re.IGNORECASE)
        req_ref = req_match.group(1).upper() if req_match else f"REQ-{i}"
        scenarios.append({
            "name": f"{sid.lower()}_revised",
            "test_type": "unit",
            "requirement_ref": req_ref,
            "description": f"Revised scenario for {req_ref}",
            "assertions": [],
            "mock_needed": False,
        })
        table_lines.append(
            f"| {sid} | Revised scenario for {req_ref} | unit | {req_ref} |"
        )

    return {
        "test_plan_status": "PENDING",
        "test_plan_section": "\n".join(table_lines),
        "test_scenarios": scenarios,
        "test_plan_revision_count": revision_count,
        "error_message": "",
        "gemini_feedback": "",
    }


def revise_test_plan(state: TestingWorkflowState) -> dict[str, Any]:
    """N1.5: Revise the test plan based on BLOCKED feedback.

    Args:
        state: Current workflow state. Reads `gemini_feedback`,
            `lld_content`, `requirements`, `test_plan_revision_count`,
            `config_drafter`, `config_effort`, `config_retry_policy`,
            `mock_mode`.

    Returns:
        Dict of state updates:
        - On success (parseable revision): clears test_plan_status to
          PENDING, replaces test_scenarios + test_plan_section,
          increments revision count, clears error / feedback.
        - On failure (LLM error or no scenarios parsed): increments
          revision count + sets error_message so the router routes
          the workflow to END after the next pass.
    """
    revision_count = state.get("test_plan_revision_count", 0) + 1
    print(f"\n[N1.5] Revising test plan (cycle {revision_count}/{MAX_REVISION_CYCLES})")

    if state.get("mock_mode", False):
        return _mock_revise(state)

    feedback = state.get("gemini_feedback", "") or ""
    lld_content = state.get("lld_content", "") or ""
    requirements = state.get("requirements", []) or []

    if not requirements:
        # Without requirements, can't produce scenario rows. Emit a
        # blocking error so the router ends gracefully.
        return {
            "test_plan_revision_count": revision_count,
            "error_message": (
                "Test plan revision blocked: no requirements available "
                "to map scenarios against."
            ),
        }

    # Lazy imports — keeps the test surface trivial when mock_mode is on.
    from assemblyzero.core.llm_provider import get_provider
    from assemblyzero.utils.retry import get_policy, with_retry

    revisor_spec = state.get("config_drafter", "claude:opus")
    effort = state.get("config_effort")
    try:
        revisor = get_provider(revisor_spec, effort=effort)
    except ValueError as e:
        return {
            "test_plan_revision_count": revision_count,
            "error_message": f"Test plan revision: invalid revisor spec: {e}",
        }

    system_prompt, user_prompt = _build_revision_prompt(
        lld_content, feedback, requirements,
    )

    retry_policy = get_policy(state.get("config_retry_policy", "default"))
    result = with_retry(
        lambda: revisor.invoke(
            system_prompt=system_prompt,
            content=user_prompt,
        ),
        policy=retry_policy,
        description=f"N1.5 test plan revision #{revision_count}",
    )

    if not result.success:
        return {
            "test_plan_revision_count": revision_count,
            "error_message": (
                f"Test plan revision LLM call failed: {result.error_message}"
            ),
        }

    revised_table = (result.response or "").strip()
    scenarios = _parse_scenarios_from_table(revised_table)

    if len(scenarios) < len(requirements):
        # Couldn't produce enough scenarios — increment count and let
        # the router decide whether to retry or END.
        return {
            "test_plan_revision_count": revision_count,
            "test_plan_section": revised_table,
            "error_message": (
                f"Revised plan covers only {len(scenarios)}/{len(requirements)} "
                "requirements — needs another revision cycle"
            ),
        }

    # Success: hand back the revised plan and clear the BLOCKED state.
    print(f"    Parsed {len(scenarios)} revised scenarios from revision.")
    return {
        "test_plan_status": "PENDING",
        "test_plan_section": revised_table,
        "test_scenarios": scenarios,
        "test_plan_revision_count": revision_count,
        "error_message": "",
        "gemini_feedback": "",
    }
