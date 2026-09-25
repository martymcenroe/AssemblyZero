"""Core LangGraph node: orchestrates Gemini-based adversarial test generation.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

This node:
1. Collects implementation code and LLD from state
2. Builds adversarial analysis prompt
3. Invokes Gemini Pro for analysis
4. Parses structured response
5. Writes validated test files
6. Returns updated state
"""

import json
import logging
import os
from collections.abc import Mapping
from typing import Any

from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
    ForbiddenModelError,
    GeminiModelDowngradeError,
    GeminiQuotaExhaustedError,
    GeminiTimeoutError,
)
from assemblyzero.workflows.testing.adversarial_state import (
    AdversarialAnalysis,
    AdversarialNodeState,
)
from assemblyzero.workflows.testing.nodes.adversarial_validator import (
    validate_adversarial_tests,
)
from assemblyzero.workflows.testing.nodes.adversarial_writer import (
    write_adversarial_tests,
)

logger = logging.getLogger(__name__)

# Token budget: ~60KB combined (implementation > LLD > existing tests)
_MAX_TOTAL_BYTES = 60_000
_IMPL_BUDGET_RATIO = 0.50  # 50% for implementation
_LLD_BUDGET_RATIO = 0.33   # 33% for LLD
_TEST_BUDGET_RATIO = 0.17  # 17% for existing tests

_REQUIRED_ANALYSIS_CATEGORIES = [
    "uncovered_edge_cases",
    "false_claims",
    "missing_error_handling",
    "implicit_assumptions",
]


def _skipped(state: AdversarialNodeState, reason: str) -> AdversarialNodeState:
    """The review did not run. Recorded, never raised: this node is
    non-blocking by design (route_after_adversarial always proceeds to N8),
    and the reason travels to the run report and the PR body through
    ``adversarial_summary`` (#2926)."""
    return {
        **state,
        "adversarial_skipped_reason": reason,
        "adversarial_verdict": "skipped",
        "adversarial_test_count": 0,
        "adversarial_error": None,
        "generated_test_files": {},
    }


def adversarial_summary(state: Mapping[str, Any]) -> str:
    """One line saying what N7.5 did, for the run report and the PR body.

    #2926: a skipped review used to reach the log and nothing else, so a PR
    could land with the adversarial step silently absent, and did, on every
    run from 2026-07-31 to 2026-09-24.
    """
    verdict = state.get("adversarial_verdict")
    if verdict is None:
        return "Adversarial review (N7.5): did not reach this step"
    reason = state.get("adversarial_skipped_reason")
    if verdict == "skipped" or reason:
        return f"Adversarial review (N7.5): did not run: {reason}"
    if verdict == "error":
        return f"Adversarial review (N7.5): errored: {state.get('adversarial_error')}"
    count = state.get("adversarial_test_count", 0)
    return (
        f"Adversarial review (N7.5): ran; {count} adversarial test(s) written; "
        f"verdict {verdict}"
    )


def run_adversarial_node(state: AdversarialNodeState) -> AdversarialNodeState:
    """LangGraph node: Orchestrates adversarial test generation via Gemini.

    1. Collects implementation code and LLD from state.
    2. Builds adversarial analysis prompt.
    3. Invokes Gemini Pro for analysis via adversarial_gemini wrapper, on the
       sanctioned transport (#2926).
    4. Parses structured response into AdversarialAnalysis.
    5. Delegates to writer and validator.
    6. Returns updated state with generated tests.

    Never blocks the run: a review that cannot run is recorded as "skipped"
    with its reason, and ``adversarial_summary`` carries that to the report.

    Args:
        state: The current workflow state.

    Returns:
        Updated state with adversarial test results.
    """
    logger.info("[ADV] Starting adversarial test generation node")

    # Issue #547: Skip-on-resume — don't re-call Gemini if verdict already exists
    if (
        state.get("adversarial_verdict") in ("pass", "success", "error")
        and state.get("adversarial_test_count", 0) > 0
    ):
        logger.info("[ADV] Adversarial analysis already complete — skipping")
        return state

    # #3546: a mock run makes no network call. The flag reaches this node
    # through AdversarialNodeState now; it used to be filtered out at the
    # LangGraph boundary, and the node decided by whether a client could be
    # built -- which on a machine holding any Gemini key meant a real call to
    # the paid API from a rehearsal.
    if state.get("mock_mode"):
        logger.info("[ADV] Mock run — no adversarial review")
        return _skipped(state, "mock run, no adversarial review is made")

    # Check for implementation files
    impl_files = state.get("implementation_files", [])
    if not impl_files:
        logger.info("[ADV] No implementation files in state — skipping")
        return _skipped(state, "No implementation files in state")

    # Collect and trim context
    impl_context, lld_context, test_context = _collect_context(state)

    # #2926: the sanctioned transport and nothing else. Construction fails
    # only on a forbidden alias or a spec get_provider refuses, and neither
    # blocks the run: the reason is recorded and the run continues.
    try:
        client = AdversarialGeminiClient()
    except (ForbiddenModelError, ValueError) as exc:
        logger.warning("[ADV] No adversarial client — skipping: %s", exc)
        return _skipped(state, f"no adversarial client: {exc}")

    # One call. The transport has already retried and rotated before it
    # reports a failure (#1907); the second lap this node used to take
    # doubled a gauntlet that had run its course, and printed "timeout --
    # retrying" in every run log since 2026-07-31 when the cause was a dead
    # API key (#2926). The transport's own message is what gets recorded.
    try:
        raw_response = client.generate_adversarial_tests(
            implementation_code=impl_context,
            lld_content=lld_context,
            existing_tests=test_context,
            timeout=120,
        )
    except GeminiQuotaExhaustedError as e:
        logger.warning("[ADV] Gemini quota exhausted — skipping: %s", e)
        return _skipped(state, f"Gemini quota exhausted: {e}")
    except ForbiddenModelError as e:
        # #2286: the requested model is checked before the call. The handlers
        # here name specific errors rather than catching broadly, so a new
        # exception type would escape and halt a pipeline that is supposed to
        # continue without adversarial coverage.
        logger.warning("[ADV] Adversarial model not permitted — skipping: %s", e)
        return _skipped(state, f"adversarial model not permitted: {e}")
    except GeminiModelDowngradeError as e:
        logger.warning("[ADV] Gemini model downgraded to Flash — skipping: %s", e)
        return _skipped(state, f"Gemini model downgraded to Flash: {e}")
    except GeminiTimeoutError as e:
        logger.warning("[ADV] Gemini call failed — skipping: %s", e)
        return _skipped(state, f"Gemini call failed: {e}")

    # Parse response
    try:
        analysis = _parse_gemini_response(raw_response)
    except ValueError as e:
        logger.error("[ADV] Malformed Gemini response: %s", e)
        return {
            **state,
            "adversarial_verdict": "error",
            "adversarial_error": f"Malformed Gemini response: {e}",
            "adversarial_test_count": 0,
            "adversarial_skipped_reason": None,
            "generated_test_files": {},
        }

    # Write test files. #1757: root them in the target repo/worktree —
    # the writer's CWD-relative default would land target-repo tests in
    # AssemblyZero's own tests/adversarial/ when workflows run from AZ.
    # #2926: the testing state names the issue `issue_number`; `issue_id` is
    # this node's own older spelling, kept for callers that use it.
    issue_id = state.get("issue_id") or state.get("issue_number", 0)
    repo_root = state.get("repo_root", "")
    output_dir = (
        os.path.join(repo_root, "tests", "adversarial")
        if repo_root
        else "tests/adversarial"
    )
    generated_files = write_adversarial_tests(
        analysis, issue_id, output_dir=output_dir
    )

    # Validate (AST no-mock scan, syntax, assertions)
    validation = validate_adversarial_tests(generated_files)

    # Remove files with mock violations or syntax errors
    clean_files: dict[str, str] = {}
    violation_files: set[str] = set()

    for violation in validation["mock_violations"]:
        # Extract filepath from violation string (format: "filepath:line: message")
        parts = violation.split(":")
        if parts:
            vpath = parts[0]
            violation_files.add(vpath)

    for error in validation["errors"]:
        parts = error.split(":")
        if parts:
            epath = parts[0]
            violation_files.add(epath)

    for filepath, content in generated_files.items():
        if filepath not in violation_files:
            clean_files[filepath] = content
        else:
            logger.warning("[ADV] Rejected test file: %s", filepath)
            # Remove from disk
            try:
                os.remove(filepath)
            except OSError:
                pass

    # Count valid test functions using simple line scan
    test_count = 0
    for content in clean_files.values():
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def test_"):
                test_count += 1

    verdict = "pass" if test_count > 0 else "fail"

    logger.info(
        "[ADV] Adversarial testing complete: %d tests, verdict=%s",
        test_count,
        verdict,
    )

    return {
        **state,
        "adversarial_analysis": analysis,
        "generated_test_files": clean_files,
        "adversarial_verdict": verdict,
        "adversarial_error": None,
        "adversarial_test_count": test_count,
        "adversarial_skipped_reason": None,
    }


def _collect_context(state: AdversarialNodeState) -> tuple[str, str, str]:
    """Extract and token-budget-trim implementation code, LLD content,
    and existing tests from state.

    Priority: implementation code > LLD > existing tests.
    Total budget: ~60KB combined.

    Args:
        state: The current workflow state.

    Returns:
        Tuple of (implementation_context, lld_context, existing_test_context).
    """
    impl_files = state.get("implementation_files", [])
    lld_content = state.get("lld_content", "")
    test_files = state.get("test_files", [])

    # Build raw context strings by reading files from disk
    impl_parts: list[str] = []
    for filepath in impl_files:
        content = _read_file_safe(filepath)
        if content:
            impl_parts.append(f"# {filepath}\n{content}")
    impl_raw = "\n\n".join(impl_parts)

    test_parts: list[str] = []
    for filepath in test_files:
        content = _read_file_safe(filepath)
        if content:
            test_parts.append(f"# {filepath}\n{content}")
    test_raw = "\n\n".join(test_parts)

    # Apply budget
    impl_budget = int(_MAX_TOTAL_BYTES * _IMPL_BUDGET_RATIO)
    lld_budget = int(_MAX_TOTAL_BYTES * _LLD_BUDGET_RATIO)
    test_budget = int(_MAX_TOTAL_BYTES * _TEST_BUDGET_RATIO)

    impl_trimmed = _trim_to_budget(impl_raw, impl_budget)
    lld_trimmed = _trim_to_budget(lld_content, lld_budget)
    test_trimmed = _trim_to_budget(test_raw, test_budget)

    # If one section is under budget, redistribute to others
    impl_used = len(impl_trimmed.encode("utf-8"))
    lld_used = len(lld_trimmed.encode("utf-8"))
    test_used = len(test_trimmed.encode("utf-8"))
    remaining = _MAX_TOTAL_BYTES - impl_used - lld_used - test_used

    if remaining > 0 and len(impl_raw.encode("utf-8")) > impl_used:
        impl_trimmed = _trim_to_budget(impl_raw, impl_budget + remaining)

    return impl_trimmed, lld_trimmed, test_trimmed


def _trim_to_budget(text: str, max_bytes: int) -> str:
    """Trim text to fit within byte budget.

    Tries to trim at function/class boundaries to preserve readability.

    Args:
        text: Raw text to trim.
        max_bytes: Maximum bytes allowed.

    Returns:
        Trimmed text, possibly with truncation marker.
    """
    if not text:
        return ""

    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    # Truncate at byte boundary, then find last newline for clean break
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")

    # Try to find a good break point (end of a function/class)
    last_def = truncated.rfind("\ndef ")
    last_class = truncated.rfind("\nclass ")
    break_point = max(last_def, last_class)

    if break_point > len(truncated) // 2:
        truncated = truncated[:break_point]
    else:
        # Fall back to last newline
        last_newline = truncated.rfind("\n")
        if last_newline > 0:
            truncated = truncated[:last_newline]

    return truncated + "\n\n... [TRUNCATED - token budget exceeded] ..."


def _read_file_safe(filepath: str) -> str:
    """Read a file from disk, returning empty string on failure.

    Args:
        filepath: Path to the file to read.

    Returns:
        File contents, or empty string if the file cannot be read.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("[ADV] Could not read file %s: %s", filepath, e)
        return ""


def _parse_gemini_response(raw_response: str) -> AdversarialAnalysis:
    """Parse Gemini's structured JSON response into AdversarialAnalysis.

    Handles:
    - Raw JSON
    - JSON wrapped in markdown code blocks (```json ... ```)
    - Validates all four required analysis categories are present

    Args:
        raw_response: Raw string response from Gemini.

    Returns:
        Parsed AdversarialAnalysis TypedDict.

    Raises:
        ValueError: If response is malformed or missing required fields.
    """
    if not raw_response or not raw_response.strip():
        raise ValueError("Empty response from Gemini")

    text = raw_response.strip()

    # Strip markdown code blocks if present
    if text.startswith("```"):
        # Remove opening ``` (with optional language tag)
        first_newline = text.find("\n")
        if first_newline > 0:
            text = text[first_newline + 1:]
        # Remove closing ```
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    # Parse JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON response from Gemini: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected JSON object, got {type(data).__name__}"
        )

    # Validate required analysis categories
    for category in _REQUIRED_ANALYSIS_CATEGORIES:
        if category not in data:
            raise ValueError(f"Missing required analysis category: {category}")

    # Validate test_cases field
    if "test_cases" not in data:
        raise ValueError("Missing required field: test_cases")

    if not isinstance(data["test_cases"], list):
        raise ValueError("test_cases must be a list")

    # Validate each test case has required fields
    required_tc_fields = [
        "test_id",
        "target_function",
        "category",
        "description",
        "test_code",
        "claim_challenged",
        "severity",
    ]
    for i, tc in enumerate(data["test_cases"]):
        for field in required_tc_fields:
            if field not in tc:
                raise ValueError(
                    f"Test case {i} missing required field: {field}"
                )

    # Build typed result
    analysis: AdversarialAnalysis = {
        "uncovered_edge_cases": data["uncovered_edge_cases"],
        "false_claims": data["false_claims"],
        "missing_error_handling": data["missing_error_handling"],
        "implicit_assumptions": data["implicit_assumptions"],
        "test_cases": data["test_cases"],
    }

    logger.info(
        "[ADV] Parsed analysis: %d edge cases, %d false claims, "
        "%d missing handlers, %d assumptions, %d test cases",
        len(analysis["uncovered_edge_cases"]),
        len(analysis["false_claims"]),
        len(analysis["missing_error_handling"]),
        len(analysis["implicit_assumptions"]),
        len(analysis["test_cases"]),
    )

    return analysis