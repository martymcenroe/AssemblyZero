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
from assemblyzero.workflows.testing.adversarial_gemini import (
    AdversarialGeminiClient,
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


def run_adversarial_node(state: AdversarialNodeState) -> AdversarialNodeState:
    """LangGraph node: Orchestrates adversarial test generation via Gemini.

    1. Collects implementation code and LLD from state.
    2. Builds adversarial analysis prompt.
    3. Invokes Gemini Pro for analysis via adversarial_gemini wrapper.
    4. Parses structured response into AdversarialAnalysis.
    5. Delegates to writer and validator.
    6. Returns updated state with generated tests.

    Fails gracefully on Gemini quota/downgrade errors (sets adversarial_skipped_reason).

    Args:
        state: The current workflow state.

    Returns:
        Updated state with adversarial test results.
    """
    logger.info("[ADV] Starting adversarial test generation node")

    # Check for implementation files
    impl_files = state.get("implementation_files", {})
    if not impl_files:
        logger.info("[ADV] No implementation files in state — skipping")
        return {
            **state,
            "adversarial_skipped_reason": "No implementation files in state",
            "adversarial_verdict": "error",
            "adversarial_test_count": 0,
            "adversarial_error": None,
            "generated_test_files": {},
        }

    # Collect and trim context
    impl_context, lld_context, test_context = _collect_context(state)

    # Invoke Gemini
    client = AdversarialGeminiClient()

    try:
        raw_response = client.generate_adversarial_tests(
            implementation_code=impl_context,
            lld_content=lld_context,
            existing_tests=test_context,
            timeout=120,
        )
    except GeminiQuotaExhaustedError:
        logger.warning("[ADV] Gemini quota exhausted — skipping adversarial tests")
        return {
            **state,
            "adversarial_skipped_reason": "Gemini quota exhausted",
            "adversarial_verdict": "error",
            "adversarial_test_count": 0,
            "adversarial_error": None,
            "generated_test_files": {},
        }
    except GeminiModelDowngradeError as e:
        logger.warning("[ADV] Gemini model downgraded to Flash — skipping: %s", e)
        return {
            **state,
            "adversarial_skipped_reason": f"Gemini model downgraded to Flash: {e}",
            "adversarial_verdict": "error",
            "adversarial_test_count": 0,
            "adversarial_error": None,
            "generated_test_files": {},
        }
    except GeminiTimeoutError:
        # Retry once with extended timeout
        logger.warning("[ADV] Gemini timeout — retrying with 180s timeout")
        try:
            raw_response = client.generate_adversarial_tests(
                implementation_code=impl_context,
                lld_content=lld_context,
                existing_tests=test_context,
                timeout=180,
            )
        except (GeminiTimeoutError, GeminiQuotaExhaustedError, GeminiModelDowngradeError) as e:
            logger.warning("[ADV] Gemini retry failed — skipping: %s", e)
            return {
                **state,
                "adversarial_skipped_reason": f"Gemini timeout after retry: {e}",
                "adversarial_verdict": "error",
                "adversarial_test_count": 0,
                "adversarial_error": None,
                "generated_test_files": {},
            }

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

    # Write test files
    issue_id = state.get("issue_id", 0)
    generated_files = write_adversarial_tests(analysis, issue_id)

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
    impl_files = state.get("implementation_files", {})
    lld_content = state.get("lld_content", "")
    existing_tests = state.get("existing_tests", {})

    # Build raw context strings
    impl_parts: list[str] = []
    for filepath, content in impl_files.items():
        impl_parts.append(f"# {filepath}\n{content}")
    impl_raw = "\n\n".join(impl_parts)

    test_parts: list[str] = []
    for filepath, content in existing_tests.items():
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