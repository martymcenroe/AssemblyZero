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
import sys
from collections.abc import Mapping
from typing import Any

from assemblyzero.workflows.testing.adversarial_gemini import (
    SEAT,
    AdversarialGeminiClient,
    ForbiddenModelError,
    GeminiEmptyResponseError,
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
    AdversarialWriteError,
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
    """A mock run makes no review. The only "skipped" this node returns:
    every other way the review fails to run is ``_review_failed`` (#3725)."""
    return {
        **state,
        "adversarial_skipped_reason": reason,
        "adversarial_verdict": "skipped",
        "adversarial_test_count": 0,
        "adversarial_error": None,
        "generated_test_files": {},
    }


def _review_failed(
    state: AdversarialNodeState,
    what: str,
    exc: BaseException | None = None,
    *,
    spec: str = "",
) -> AdversarialNodeState:
    """The review could not run or did not produce a review: a failure (#3725).

    ADR 0236: loud (an ERROR line on stderr), logged with details (the seat,
    the spec, the exception type and its message), and it stops the run:
    ``error_message`` routes N7.5 to HALT, which alerts the operator (#3724).
    """
    cause = f"{type(exc).__name__}: {exc}" if exc is not None else "no exception"
    message = (
        f"N7.5 adversarial review failed: {what}. Seat {SEAT}, spec "
        f"{spec or '(not resolved)'}; {cause}"
    )
    logger.error("[ADV] %s", message)
    print(f"ERROR [ADV] {message}", file=sys.stderr)
    return {
        **state,
        "adversarial_skipped_reason": None,
        "adversarial_verdict": "error",
        "adversarial_test_count": 0,
        "adversarial_error": message,
        "generated_test_files": {},
        "error_message": message,
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

    A review that cannot run, or runs and produces no valid tests, is a
    failure (ADR 0236, #3725): ``_review_failed`` sets ``error_message``, and
    ``route_after_adversarial`` sends it to HALT. Only a mock run is skipped.

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

    # #3725: no implementation files at N7.5 is a failure, not a declared
    # contract. N7 finalize only routes here after the implementation stage
    # wrote files, so an empty list means that state was lost on the way,
    # and a review with nothing to review would pass the run unexamined.
    impl_files = state.get("implementation_files", [])
    if not impl_files:
        return _review_failed(
            state, "no implementation files in state, so there is nothing to review"
        )

    # #2926: the sanctioned transport and nothing else. Construction fails
    # on a forbidden alias or a spec get_provider refuses; either is a review
    # that cannot run (#3725). #3563: the model is the run profile's
    # `impl.adversarial` seat.
    spec = ""
    try:
        from assemblyzero.core.seats import resolve

        seat = resolve(state, SEAT)
        spec = seat.spec
        client = AdversarialGeminiClient(spec=seat.spec, effort=seat.effort)
    except (ForbiddenModelError, ValueError) as exc:
        return _review_failed(state, "the adversarial client could not be built", exc, spec=spec)

    # #3817: a file that cannot be read is a failure, never an empty context.
    try:
        impl_context, lld_context, test_context = _collect_context(state)
    except (OSError, UnicodeDecodeError) as exc:
        return _review_failed(state, "a file for the review context could not be read", exc, spec=spec)

    # One call. The transport has already retried and rotated before it
    # reports a failure (#1907); the second lap this node used to take
    # doubled a gauntlet that had run its course, and printed "timeout --
    # retrying" in every run log since 2026-07-31 when the cause was a dead
    # API key (#2926). The transport's own message is what gets recorded.
    # #2286: the handlers name specific errors rather than catching broadly.
    # #3725: each one is a review that did not run, and halts the run.
    try:
        raw_response = client.generate_adversarial_tests(
            implementation_code=impl_context,
            lld_content=lld_context,
            existing_tests=test_context,
            timeout=120,
        )
    except GeminiQuotaExhaustedError as e:
        return _review_failed(state, "the Gemini quota is exhausted", e, spec=spec)
    except ForbiddenModelError as e:
        return _review_failed(state, "the adversarial model is not permitted", e, spec=spec)
    except GeminiModelDowngradeError as e:
        return _review_failed(state, "the reply did not come from a Gemini Pro model", e, spec=spec)
    except GeminiTimeoutError as e:
        return _review_failed(state, "the Gemini call failed", e, spec=spec)
    except GeminiEmptyResponseError as e:
        return _review_failed(state, "Gemini returned an empty response", e, spec=spec)

    try:
        analysis = _parse_gemini_response(raw_response)
    except ValueError as e:
        return _review_failed(state, "the Gemini response was malformed", e, spec=spec)

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
    try:
        generated_files = write_adversarial_tests(
            analysis, issue_id, output_dir=output_dir
        )
    except AdversarialWriteError as e:
        return _review_failed(state, "the adversarial tests could not be written", e, spec=spec)

    # Validate (AST no-mock scan, syntax, assertions)
    validation = validate_adversarial_tests(generated_files)

    # #3817: a generated file that fails validation fails the review. It used
    # to be dropped at WARNING, and the review counted with a partial set.
    # The rejected files are removed from disk first, so a halted run leaves
    # no invalid test behind; a file that cannot be removed is named too.
    problems = list(validation["mock_violations"]) + list(validation["errors"])
    if problems:
        rejected = sorted({p.split(":")[0] for p in problems} & set(generated_files))
        not_removed: list[str] = []
        for filepath in rejected:
            try:
                os.remove(filepath)
            except OSError as exc:
                not_removed.append(f"{filepath} ({type(exc).__name__}: {exc})")
        detail = "; ".join(problems[:5]) + (f" (and {len(problems) - 5} more)" if len(problems) > 5 else "")
        if not_removed:
            detail += f"; could not remove: {', '.join(not_removed)}"
        return _review_failed(
            state,
            f"{len(rejected)} generated test file(s) failed validation and were "
            f"rejected: {detail}",
            spec=spec,
        )
    clean_files = dict(generated_files)

    # Count valid test functions using simple line scan
    test_count = 0
    for content in clean_files.values():
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("def test_"):
                test_count += 1

    # #3817: a review that wrote no runnable test has not reviewed anything.
    if test_count == 0:
        return _review_failed(state, "the review produced zero valid tests", spec=spec)
    verdict = "pass"

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
        content = _read_file(filepath)
        if content:
            impl_parts.append(f"# {filepath}\n{content}")
    impl_raw = "\n\n".join(impl_parts)

    test_parts: list[str] = []
    for filepath in test_files:
        content = _read_file(filepath)
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


def _read_file(filepath: str) -> str:
    """Read a file for the review context.

    #3817: an unreadable file used to become "" and the review ran on a
    partial context. It now raises; run_adversarial_node halts on it.

    Raises:
        OSError, UnicodeDecodeError: the file cannot be read as UTF-8.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


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