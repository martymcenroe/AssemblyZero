"""N3: Validate Completeness node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Runs mechanical completeness checks on the generated Implementation Spec
draft to catch issues before expensive Gemini review (N5). Each check
verifies one aspect of spec quality:

- Every "Modify" file must have a current state excerpt
- Every data structure must have a concrete JSON/YAML example
- Every function must have input/output examples
- Change instructions must be specific (diff-level guidance)
- Pattern references must point to existing code locations

This node populates:
- completeness_issues: List of issue descriptions from failed checks
- validation_passed: Whether all checks passed
- error_message: "" on success, error text on failure
"""

import ast
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, NamedTuple

from assemblyzero.workflows.implementation_spec.state import (
    CompletenessCheck,
    FileToModify,
    ImplementationSpecState,
    PatternRef,
)
from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    criteria_coverage,
    format_report as format_coverage_report,
)
from assemblyzero.workflows.implementation_spec.error_path_coverage import (
    error_path_coverage,
    format_report as format_error_path_report,
)
from assemblyzero.workflows.telemetry import (
    build_hallucination_event,
    record_hallucination_event,
)


# =============================================================================
# Constants
# =============================================================================

# Minimum number of characters for a meaningful excerpt
MIN_EXCERPT_CHARS = 50

# Minimum number of characters for an example to be considered concrete
MIN_EXAMPLE_CHARS = 20

# Patterns that indicate diff-level specificity in change instructions
SPECIFICITY_INDICATORS = [
    r"```",                           # Code blocks (before/after snippets)
    r"line\s+\d+",                    # Line number references
    r"lines?\s+\d+\s*[-–]\s*\d+",    # Line range references
    r"before:.*after:",               # Before/after pattern
    r"replace\s+.*\s+with",          # Replace X with Y
    r"add\s+(after|before|above|below)",  # Positional add instructions
    r"delete\s+(line|function|class|method|block)",  # Delete targets
    r"import\s+",                     # Import statements (specific)
    r"def\s+\w+",                     # Function definitions
    r"class\s+\w+",                   # Class definitions
]


# =============================================================================
# Main Node
# =============================================================================


def validate_completeness(state: ImplementationSpecState) -> dict[str, Any]:
    """N3: Check that spec meets mechanical completeness criteria.

    Issue #304: Implementation Readiness Review Workflow

    Runs a series of mechanical checks on the generated spec draft to
    verify it has sufficient detail for autonomous implementation. Failed
    checks produce actionable error messages that guide N2 revision.

    Steps:
    1. Verify spec_draft exists and is non-trivial
    2. Run each completeness check independently
    3. Collect results and determine pass/fail
    4. Return state updates with check results

    Args:
        state: Current workflow state. Requires:
            - spec_draft: Generated Implementation Spec markdown (from N2)
            - files_to_modify: List[FileToModify] from N0
            - pattern_references: List[PatternRef] from N1
            - repo_root: Repository root path (for pattern validation)

    Returns:
        Dict with state field updates:
        - completeness_issues: List of issue descriptions (empty if all passed)
        - validation_passed: True if all checks passed
        - error_message: "" on success, error text on failure
    """
    print("\n[N3] Validating mechanical completeness...")

    spec_draft = state.get("spec_draft", "")
    files_to_modify = state.get("files_to_modify", [])
    pattern_references = state.get("pattern_references", [])
    repo_root_str = state.get("repo_root", "")

    # --------------------------------------------------------------------------
    # GUARD: Must have a spec draft to validate
    # --------------------------------------------------------------------------
    if not spec_draft or len(spec_draft.strip()) < 100:
        print("    [GUARD] BLOCKED: Spec draft is empty or too short")
        return {
            "completeness_issues": [
                "Spec draft is empty or too short (< 100 chars). "
                "N2 must generate a substantive Implementation Spec."
            ],
            "validation_passed": False,
            "error_message": "",
        }
    # --------------------------------------------------------------------------

    # Run all checks
    checks: list[CompletenessCheck] = []

    # Check 1: Every "Modify" file must have current state excerpt
    check_excerpts = check_modify_files_have_excerpts(spec_draft, files_to_modify)
    checks.append(check_excerpts)
    _log_check(check_excerpts)

    # Check 2: Data structures should have concrete examples
    check_data = check_data_structures_have_examples(spec_draft)
    checks.append(check_data)
    _log_check(check_data)

    # Check 3: Functions should have I/O examples
    check_functions = check_functions_have_io_examples(spec_draft)
    checks.append(check_functions)
    _log_check(check_functions)

    # Check 4: Change instructions should be specific
    check_instructions = check_change_instructions_specific(spec_draft)
    checks.append(check_instructions)
    _log_check(check_instructions)

    # Check 5: Pattern references should be valid
    check_patterns = check_pattern_references_valid(
        spec_draft, pattern_references, repo_root_str
    )
    checks.append(check_patterns)
    _log_check(check_patterns)

    # Check 6: Import targets should exist (Issue #842)
    check_imports = check_import_targets_exist(
        spec_draft, files_to_modify, repo_root_str
    )
    checks.append(check_imports)
    _log_check(check_imports)

    # Check 7: Spec must not call methods absent from target repo (Issue #1527)
    gathered_symbols: list[str] = state.get("gathered_symbols", [])  # type: ignore[assignment]
    check_symbols = check_api_symbols_exist(spec_draft, gathered_symbols)
    checks.append(check_symbols)
    _log_check(check_symbols)

    # Check 8: Visual baselines the run itself makes need a baseline-free
    # oracle (Issue #1902)
    check_baselines = check_visual_baselines_not_self_referential(
        spec_draft, files_to_modify
    )
    checks.append(check_baselines)
    _log_check(check_baselines)

    # Check 9: Every LLD pass criterion must have a test (Issue #2239)
    check_criteria = check_criteria_have_tests(spec_draft, state.get("lld_content", ""))
    checks.append(check_criteria)
    _log_check(check_criteria)

    # Check 10: Error paths the spec mandates must have tests (Issue #2333)
    check_error_paths = check_error_paths_have_tests(spec_draft)
    checks.append(check_error_paths)
    _log_check(check_error_paths)

    # Telemetry (#1812): record detector outcomes for the spec draft (every
    # pass) and the LLD (first pass only). Record-only — the try/except
    # guarantees telemetry can never alter validation_passed.
    try:
        _record_hallucination_telemetry(state, spec_draft, gathered_symbols)
    except Exception as e:  # noqa: BLE001 — record-only contract
        print(f"    [telemetry] WARNING: hallucination telemetry failed: {e}")

    # Collect issues from failed checks
    completeness_issues = [
        check["details"] for check in checks if not check["passed"]
    ]

    validation_passed = len(completeness_issues) == 0

    # Report summary. #1870: a check with nothing to check reports passed=True
    # with "not applicable" in its details, so a spec that verified almost
    # nothing still printed "7/7 checks passed" — which read as thorough
    # validation in the run-11 logs. Count and name those separately; they are
    # still not failures, they are just not evidence.
    n_a_count = sum(
        1 for c in checks if c["passed"] and "not applicable" in c["details"].lower()
    )
    passed_count = sum(1 for c in checks if c["passed"]) - n_a_count
    total_count = len(checks)
    summary = f"\n    Results: {passed_count}/{total_count} checks passed"
    if n_a_count:
        summary += f", {n_a_count} not applicable (nothing to check)"
    print(summary)

    if validation_passed:
        if n_a_count:
            print(
                f"    PASSED: {passed_count} check(s) verified, "
                f"{n_a_count} had nothing to verify"
            )
        else:
            print("    PASSED: All completeness checks passed")
    else:
        print(f"    BLOCKED: {len(completeness_issues)} check(s) failed")
        for issue in completeness_issues:
            print(f"      - {issue[:120]}...")

    # Closes #1465: Persist this iteration's failures into a cumulative
    # breakdown so the next N2 revision sees "we already tried fixing this
    # K times" history. Without it, identical failure text yields identical
    # revisions and the spec-revision loop never converges.
    prior_breakdown = list(state.get("prior_completeness_breakdown", []))
    if not validation_passed:
        iteration = state.get("review_iteration", 0)
        prior_breakdown.append({
            "iteration": iteration,
            "failures": list(completeness_issues),
        })

    # Closes #2197: when this failure is the LAST one the budget allows, the
    # router sends it to HALT -- and a router's state writes are discarded at
    # the graph boundary (#2018), so the halt recorded nothing and the banner
    # read "Error: unknown". Below the cap the message stays empty: the run is
    # still going, and a pending revision is not a failure.
    cap_message = ""
    if not validation_passed:
        iteration = state.get("review_iteration", 0)
        max_iterations = state.get("max_iterations", 3)
        if iteration >= max_iterations:
            listed = "; ".join(completeness_issues[:3])
            cap_message = (
                f"Iteration cap: {max_iterations} revision(s) ended with "
                f"{len(completeness_issues)} unresolved completeness check(s). "
                f"Unfixed: {listed}"
            )

    return {
        "completeness_issues": completeness_issues,
        "validation_passed": validation_passed,
        "prior_completeness_breakdown": prior_breakdown,
        "error_message": cap_message,
    }


def _record_hallucination_telemetry(
    state: ImplementationSpecState,
    spec_draft: str,
    gathered_symbols: list[str],
) -> None:
    """Emit hallucination-detector events for this validation pass (#1812).

    Runs the shared detector against the spec draft on every pass, and
    against the LLD once per run — on the first pass, before any revision
    has bumped ``review_iteration`` past 0. The LLD does not change across
    revision cycles, so one measurement per run is the honest count.

    When no symbols were gathered, the detector cannot run; a ``skipped``
    event is recorded instead of silence, so "not checked" is never
    mistaken for "checked, clean".

    Record-only: this function writes events and returns nothing. It is
    called inside a try/except in the node; sink failures degrade to
    warnings inside the telemetry module itself.
    """
    iteration: int = state.get("review_iteration", 0)  # type: ignore[assignment]
    repo: str = state.get("repo_root", "")  # type: ignore[assignment]
    issue: int = state.get("issue_number", 0)  # type: ignore[assignment]

    audit_dir_str: str = state.get("audit_dir", "")  # type: ignore[assignment]
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    az_root_str: str = state.get("assemblyzero_root", "")  # type: ignore[assignment]
    az_root = Path(az_root_str) if az_root_str else None

    symbol_set = set(gathered_symbols)

    artifacts: list[tuple[str, str]] = [("spec_draft", spec_draft)]
    if iteration == 0:
        lld_content: str = state.get("lld_content", "")  # type: ignore[assignment]
        artifacts.insert(0, ("lld", lld_content))

    for artifact_name, text in artifacts:
        if not symbol_set:
            event = build_hallucination_event(
                repo=repo,
                issue=issue,
                artifact=artifact_name,
                iteration=iteration,
                symbols_checked=0,
                flagged={},
                skipped=True,
            )
        else:
            flagged = detect_unknown_method_calls(text, symbol_set)
            event = build_hallucination_event(
                repo=repo,
                issue=issue,
                artifact=artifact_name,
                iteration=iteration,
                symbols_checked=len(symbol_set),
                flagged=flagged,
            )
        record_hallucination_event(event, audit_dir, az_root)


# =============================================================================
# Individual Checks
# =============================================================================


def check_modify_files_have_excerpts(
    spec: str, files: list[FileToModify]
) -> CompletenessCheck:
    """Every 'Modify' file must have current state excerpt.

    Scans the spec for references to each Modify file and verifies that
    there is a code block or excerpt showing the current state of the code
    that will be changed.

    Args:
        spec: Implementation Spec markdown content.
        files: List of FileToModify from the LLD.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    modify_files = [
        f for f in files if f.get("change_type") == "Modify"
    ]

    if not modify_files:
        return CompletenessCheck(
            check_name="modify_files_have_excerpts",
            passed=True,
            details="No Modify files in LLD — check not applicable.",
        )

    missing: list[str] = []

    for file_spec in modify_files:
        file_path = file_spec.get("path", "")
        if not file_path:
            continue

        # Look for the file path referenced in the spec
        # Accept both full path and basename references
        basename = Path(file_path).name
        file_mentioned = (
            file_path in spec or basename in spec
        )

        if not file_mentioned:
            missing.append(file_path)
            continue

        # Check for a code block near the file reference
        # Find the position of the file reference and look for a code block
        # within ~2000 chars after it
        pos = spec.find(file_path)
        if pos == -1:
            pos = spec.find(basename)
        if pos == -1:
            missing.append(file_path)
            continue

        # Look for a code block (``` ... ```) within a reasonable range
        search_region = spec[pos : pos + 3000]
        has_code_block = "```" in search_region

        if not has_code_block:
            missing.append(file_path)

    if missing:
        file_list = ", ".join(f"`{f}`" for f in missing[:5])
        suffix = f" (and {len(missing) - 5} more)" if len(missing) > 5 else ""
        return CompletenessCheck(
            check_name="modify_files_have_excerpts",
            passed=False,
            details=(
                f"Missing current state excerpts for Modify files: "
                f"{file_list}{suffix}. Each Modify file MUST include a "
                f"code block showing the current code that will be changed."
            ),
        )

    return CompletenessCheck(
        check_name="modify_files_have_excerpts",
        passed=True,
        details=f"All {len(modify_files)} Modify files have current state excerpts.",
    )


def check_data_structures_have_examples(spec: str) -> CompletenessCheck:
    """Every data structure must have concrete JSON/YAML example.

    Looks for data structure definitions (TypedDict, dataclass, dict schemas)
    in the spec and verifies each has at least one concrete example with
    realistic values, not just the type definition.

    Args:
        spec: Implementation Spec markdown content.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    # Find data structure definitions in the spec
    # Look for TypedDict, dataclass, dict, Pydantic model patterns
    structure_patterns = [
        r"(?:class\s+\w+\s*\(.*?TypedDict.*?\))",
        r"(?:class\s+\w+\s*\(.*?BaseModel.*?\))",
        r"(?:@dataclass[^\n]*\n\s*class\s+\w+)",
    ]

    structures_found: list[str] = []
    for pattern in structure_patterns:
        matches = re.findall(pattern, spec, re.IGNORECASE)
        for match in matches:
            # Extract name from "class FooBar(...)"
            name_match = re.search(r"class\s+(\w+)", match)
            if name_match:
                structures_found.append(name_match.group(1))

    if not structures_found:
        # No data structures found — check passes (nothing to validate)
        return CompletenessCheck(
            check_name="data_structures_have_examples",
            passed=True,
            details="No data structure definitions found in spec — check not applicable.",
        )

    # For each structure, look for a concrete example
    # Examples can be JSON blocks, YAML blocks, or Python dict literals
    missing_examples: list[str] = []

    for struct_name in structures_found:
        # Find where this structure is defined/discussed in the spec
        pos = spec.find(struct_name)
        if pos == -1:
            continue

        # Look in a reasonable region after the structure reference
        search_region = spec[pos : pos + 5000]

        # Check for concrete examples: JSON, YAML, or Python dict/instance
        has_json = bool(re.search(r"\{[^}]*[\"'][\w]+[\"']\s*:", search_region))
        has_yaml = bool(re.search(r"^\s+\w+:\s+\S+", search_region, re.MULTILINE))
        has_python_dict = bool(
            re.search(r"\{[^}]*[\"']\w+[\"']\s*:", search_region)
        )
        has_instance = bool(
            re.search(
                rf"{struct_name}\s*\(", search_region
            )
        )
        has_code_example = bool(
            re.search(r"```(?:json|yaml|python|py)?\s*\n.{20,}", search_region)
        )

        if not any([has_json, has_yaml, has_python_dict, has_instance, has_code_example]):
            missing_examples.append(struct_name)

    if missing_examples:
        struct_list = ", ".join(f"`{s}`" for s in missing_examples[:5])
        suffix = (
            f" (and {len(missing_examples) - 5} more)"
            if len(missing_examples) > 5
            else ""
        )
        return CompletenessCheck(
            check_name="data_structures_have_examples",
            passed=False,
            details=(
                f"Data structures missing concrete examples: "
                f"{struct_list}{suffix}. Each data structure MUST have at "
                f"least one JSON/YAML/Python example with realistic values."
            ),
        )

    return CompletenessCheck(
        check_name="data_structures_have_examples",
        passed=True,
        details=(
            f"All {len(structures_found)} data structures have concrete examples."
        ),
    )


#: Words that mark a region as stating a function's inputs or outputs.
#:
#: `expected` is here because it is what drafters actually write (#2302). Draft
#: 008 of the 2026-08-13 boostgauge #7 roll documented every test stub as
#: `-- expected: File contains "position": {"x": 250, "y": 350}` -- a concrete
#: input and a concrete output, three characters from the signature, invisible
#: to a vocabulary that did not include the word.
_IO_WORDS = re.compile(
    r"(?:input|output|returns?|result|example|usage|call|expected|asserts?)",
    re.IGNORECASE,
)

_CONCRETE_VALUES = re.compile(r'(?:\d+|"[^"]+"|True|False|None|\[.*\]|\{.*\})')

#: How far either side of a definition to look for its example.
_WINDOW = 2000


def _is_inside_code_fence(spec: str, offset: int) -> bool:
    """Is `offset` inside a fenced code block?

    Counted by fence parity up to the offset, which is the question the check
    is actually asking. The previous implementation searched FORWARD for a
    fence, which answers "is there a fence later in the document" -- a
    different question that diverges exactly when the block is long, and long
    blocks are what specs with many functions have (#2302).
    """
    return spec.count("```", 0, offset) % 2 == 1


def _is_test_function(name: str) -> bool:
    """Test stubs are documented by their own body, not by example blocks.

    `check_criteria_have_tests` (#2239) requires one test function per LLD pass
    criterion, and the drafter duly writes them. Template 0701 specifies tests
    as a TABLE (its section 8), never as functions carrying the
    `**Input Example:**` / `**Output Example:**` blocks section 5 demands of API
    functions -- so grading a test stub by section 5's rule fails the drafter
    for following its instructions (#2303).

    A test's body IS its input and its assertion IS its expected output, which
    is the documentation this check exists to require. They are exempt, and the
    report says so out loud rather than passing them silently.
    """
    return name.startswith("test_") or name.endswith("_test")


def check_functions_have_io_examples(spec: str) -> CompletenessCheck:
    """Every non-test function must have input/output examples.

    Judged at each function's DEFINITION SITE, once per function. The previous
    implementation scanned a forward-only window from every textual occurrence
    of the name and passed the function if any one of them looked documented,
    which made the verdict depend on how often a name happened to be repeated:
    in draft 008 `save_on_exit` occurred 34 times and passed on the strength of
    a few lucky windows, while each `test_req_N` occurred exactly once and
    failed. Same documentation, opposite verdicts (#2302).

    Args:
        spec: Implementation Spec markdown content.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    definitions = [
        (m.group(1), m.start())
        for m in re.finditer(r"(?:async\s+)?def\s+(\w+)\s*\(", spec)
    ]

    graded: list[tuple[str, int]] = []
    exempt_tests: set[str] = set()
    for name, pos in definitions:
        if name.startswith("_") or name in ("__init__", "__str__", "__repr__"):
            continue
        if _is_test_function(name):
            exempt_tests.add(name)
            continue
        graded.append((name, pos))

    def _exempt_note() -> str:
        if not exempt_tests:
            return ""
        return (
            f" {len(exempt_tests)} test function(s) were NOT checked: a test's "
            f"body is its input and its assertion is its expected output "
            f"(template 0701 section 8 specifies tests as a table, not as "
            f"functions carrying example blocks)."
        )

    if not graded:
        return CompletenessCheck(
            check_name="functions_have_io_examples",
            passed=True,
            details=(
                "No public non-test function signatures found in spec — check "
                "not applicable." + _exempt_note()
            ),
        )

    missing_examples: list[str] = []
    seen: set[str] = set()

    for func_name, pos in graded:
        if func_name in seen:
            continue
        seen.add(func_name)

        # Both directions: an example placed ABOVE the signature counts, and a
        # function inside a long fenced block can no longer be judged by
        # whether the closing fence happens to fall within reach.
        region = spec[max(0, pos - _WINDOW) : pos + _WINDOW]

        has_values = bool(_CONCRETE_VALUES.search(region))
        if not has_values:
            missing_examples.append(func_name)
            continue

        if _is_inside_code_fence(spec, pos) or "```" in region:
            continue
        if _IO_WORDS.search(region):
            continue

        missing_examples.append(func_name)

    if missing_examples:
        func_list = ", ".join(f"`{f}()`" for f in missing_examples[:5])
        suffix = (
            f" (and {len(missing_examples) - 5} more)"
            if len(missing_examples) > 5
            else ""
        )
        return CompletenessCheck(
            check_name="functions_have_io_examples",
            passed=False,
            details=(
                f"Functions missing input/output examples: "
                f"{func_list}{suffix}. Each function MUST have at least one "
                f"example with concrete input values and expected output."
                + _exempt_note()
            ),
        )

    return CompletenessCheck(
        check_name="functions_have_io_examples",
        passed=True,
        details=(
            f"All {len(seen)} public non-test functions have I/O examples."
            + _exempt_note()
        ),
    )


def check_change_instructions_specific(spec: str) -> CompletenessCheck:
    """Change instructions must be diff-level specific.

    Verifies that the spec contains specific change instructions rather
    than vague directives. Looks for indicators of specificity such as
    code blocks, line references, before/after snippets, and precise
    modification instructions.

    Args:
        spec: Implementation Spec markdown content.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    # Count specificity indicators in the spec
    indicator_counts: dict[str, int] = {}
    total_indicators = 0

    for pattern in SPECIFICITY_INDICATORS:
        matches = re.findall(pattern, spec, re.IGNORECASE)
        count = len(matches)
        if count > 0:
            indicator_counts[pattern] = count
            total_indicators += count

    # Count code blocks specifically (strong indicator)
    code_blocks = re.findall(r"```[\s\S]*?```", spec)
    code_block_count = len(code_blocks)

    # The spec should have substantial code blocks for specificity
    # Minimum thresholds based on spec size
    spec_lines = len(spec.splitlines())

    # At least 1 code block per 50 lines of spec, minimum 3
    min_code_blocks = max(3, spec_lines // 50)

    if code_block_count < min_code_blocks:
        return CompletenessCheck(
            check_name="change_instructions_specific",
            passed=False,
            details=(
                f"Insufficient code blocks for specificity: found "
                f"{code_block_count}, expected at least {min_code_blocks} "
                f"for a {spec_lines}-line spec. Change instructions MUST "
                f"include before/after code snippets, line references, or "
                f"diff-level guidance."
            ),
        )

    # Also check for minimum total specificity indicators
    min_indicators = max(5, spec_lines // 30)

    if total_indicators < min_indicators:
        return CompletenessCheck(
            check_name="change_instructions_specific",
            passed=False,
            details=(
                f"Change instructions lack specificity: found "
                f"{total_indicators} specificity indicators, expected at "
                f"least {min_indicators}. Include line references, "
                f"before/after snippets, and precise modification targets."
            ),
        )

    return CompletenessCheck(
        check_name="change_instructions_specific",
        passed=True,
        details=(
            f"Change instructions have adequate specificity: "
            f"{code_block_count} code blocks, "
            f"{total_indicators} specificity indicators."
        ),
    )


def check_pattern_references_valid(
    spec: str,
    pattern_refs: list[PatternRef],
    repo_root_str: str = "",
) -> CompletenessCheck:
    """Verify referenced patterns exist at specified locations.

    Checks that pattern references included in the spec (file:line
    locations) point to real code in the repository. This prevents
    the implementation agent from following stale or incorrect references.

    Args:
        spec: Implementation Spec markdown content.
        pattern_refs: List of PatternRef from N1 (codebase analysis).
        repo_root_str: Repository root path string.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    if not pattern_refs:
        return CompletenessCheck(
            check_name="pattern_references_valid",
            passed=True,
            details="No pattern references provided — check not applicable.",
        )

    if not repo_root_str:
        # Can't validate without repo root — pass with warning
        return CompletenessCheck(
            check_name="pattern_references_valid",
            passed=True,
            details=(
                "No repo_root available for pattern validation — "
                "skipping file existence checks."
            ),
        )

    repo_root = Path(repo_root_str)
    invalid_refs: list[str] = []

    for ref in pattern_refs:
        file_path = ref.get("file_path", "")
        start_line = ref.get("start_line", 0)
        end_line = ref.get("end_line", 0)

        if not file_path:
            continue

        # Check if this pattern is actually referenced in the spec
        if file_path not in spec:
            # Pattern from N1 not used in spec — skip validation
            continue

        # Verify the file exists
        full_path = repo_root / file_path
        if not full_path.exists():
            invalid_refs.append(
                f"`{file_path}` — file does not exist"
            )
            continue

        # Verify the line range is valid
        if start_line > 0 or end_line > 0:
            try:
                content = full_path.read_text(encoding="utf-8")
                total_lines = len(content.splitlines())

                if start_line > total_lines:
                    invalid_refs.append(
                        f"`{file_path}:{start_line}` — line {start_line} "
                        f"exceeds file length ({total_lines} lines)"
                    )
                elif end_line > total_lines:
                    invalid_refs.append(
                        f"`{file_path}:{start_line}-{end_line}` — "
                        f"end line {end_line} exceeds file length "
                        f"({total_lines} lines)"
                    )
            except (OSError, UnicodeDecodeError) as e:
                invalid_refs.append(
                    f"`{file_path}` — cannot read file: {e}"
                )

    if invalid_refs:
        ref_list = "; ".join(invalid_refs[:5])
        suffix = (
            f" (and {len(invalid_refs) - 5} more)"
            if len(invalid_refs) > 5
            else ""
        )
        return CompletenessCheck(
            check_name="pattern_references_valid",
            passed=False,
            details=(
                f"Invalid pattern references in spec: {ref_list}{suffix}. "
                f"Pattern references MUST point to existing files at valid "
                f"line ranges."
            ),
        )

    return CompletenessCheck(
        check_name="pattern_references_valid",
        passed=True,
        details=(
            f"All pattern references validated "
            f"({len(pattern_refs)} references checked)."
        ),
    )


def check_import_targets_exist(
    spec: str,
    files: list[FileToModify],
    repo_root_str: str = "",
) -> CompletenessCheck:
    """Verify that imports referenced in the spec point to existing modules.

    Issue #842: Catches the scenario where the spec instructs code to import
    from modules that don't exist (e.g., `from assemblyzero.core.metrics import X`
    when assemblyzero.core.metrics doesn't exist). Cross-references against
    the spec's Files Changed table for new files the spec itself creates.

    Args:
        spec: Implementation Spec markdown content.
        files: List of FileToModify from the LLD.
        repo_root_str: Repository root path string.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    if not repo_root_str:
        return CompletenessCheck(
            check_name="import_targets_exist",
            passed=True,
            details="No repo_root available for import validation — skipping.",
        )

    repo_root = Path(repo_root_str)

    # Collect paths of files the spec is creating (new "Add" files)
    new_file_paths: set[str] = set()
    for f in files:
        if f.get("change_type", "").lower() == "add":
            path = f.get("path", "")
            if path:
                new_file_paths.add(path)

    # Extract `from X import Y` and `import X` patterns from code blocks in spec
    # Only look inside code blocks to avoid matching prose
    code_block_pattern = re.compile(r"```[\w]*\s*\n(.*?)```", re.DOTALL)
    import_pattern = re.compile(
        r"(?:from\s+([\w.]+)\s+import|^import\s+([\w.]+))", re.MULTILINE
    )

    unresolvable: list[str] = []
    checked: set[str] = set()
    # #1901: dotted imports that are neither stdlib nor first-party are
    # third-party (PIL.Image, psutil.*, google.genai). Walking the repo
    # tree for those flagged Pillow as "nonexistent" and cost a revision
    # cycle per affected spec. They validate against the TARGET repo's
    # own environment instead — grouped by top-level for one batched probe.
    first_party_tops = _first_party_tops(repo_root)
    third_party: dict[str, list[str]] = {}

    for block_match in code_block_pattern.finditer(spec):
        block_content = block_match.group(1)
        for imp_match in import_pattern.finditer(block_content):
            module_path = imp_match.group(1) or imp_match.group(2)
            if not module_path or module_path in checked:
                continue
            checked.add(module_path)

            # Skip stdlib and common third-party
            top_level = module_path.split(".")[0]
            if top_level in _KNOWN_STDLIB_TOPS:
                continue

            # Only validate internal imports (heuristic: contains a dot
            # suggesting it's a project-internal path, or starts with a
            # known project package directory)
            if "." not in module_path:
                continue

            # Check if it resolves on disk
            if _import_resolves(module_path, repo_root, new_file_paths):
                continue

            if top_level in first_party_tops:
                unresolvable.append(module_path)
            else:
                third_party.setdefault(top_level, []).append(module_path)

    env_note = ""
    if third_party:
        probe = _probe_target_env(repo_root, sorted(third_party))
        if probe is None:
            # Cannot validate ≠ missing. The target env is the only honest
            # authority for third-party imports (#1904: wrong-environment
            # answers are worse than none); without it, give the benefit
            # of the doubt and say so.
            env_note = (
                f" Target environment unavailable — {len(third_party)} "
                f"third-party top-level import(s) not validated."
            )
        else:
            for top, modules in sorted(third_party.items()):
                if not probe.get(top, False):
                    unresolvable.extend(modules)

    if unresolvable:
        mod_list = ", ".join(f"`{m}`" for m in unresolvable[:5])
        suffix = f" (and {len(unresolvable) - 5} more)" if len(unresolvable) > 5 else ""
        return CompletenessCheck(
            check_name="import_targets_exist",
            passed=False,
            details=(
                f"Imports in spec reference modules that neither exist, nor "
                f"are created by this spec, nor import in the target repo's "
                f"environment: {mod_list}{suffix}. For first-party modules, "
                f"verify the path; for third-party, add the dependency to "
                f"the target repo or fix the import."
            ),
        )

    return CompletenessCheck(
        check_name="import_targets_exist",
        passed=True,
        details=f"All {len(checked)} import targets validated.{env_note}",
    )


# Literal marker a spec must carry when it touches visual baselines (#1902).
# The drafter prompt teaches it; this check enforces it mechanically.
_BASELINE_INDEPENDENT_MARKER = "baseline-independent"

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".gif")


def check_visual_baselines_not_self_referential(
    spec: str,
    files: list[FileToModify],
) -> CompletenessCheck:
    """Baselines made by the run under test must not be the only oracle.

    Issue #1902: the pipeline generated tests/visual/baselines/*.png in
    the same run that generated the renderer, then compared the renderer
    against them — a systematically wrong first render (inverted needle,
    mirrored dial) becomes its own reference and passes forever. Any spec
    that adds or regenerates baseline images must declare property
    assertions computable WITHOUT a baseline, in a section carrying the
    literal marker "baseline-independent". The revise loop can heal this
    (#1892), so it fails the completeness gate rather than halting.
    """
    baseline_touches: list[str] = []
    for f in files:
        change_type = f.get("change_type", "").lower()
        if change_type not in ("add", "modify"):
            continue
        raw_path = f.get("path", "")
        if not raw_path:
            continue
        path = raw_path.lower().replace("\\", "/")
        in_baseline_dir = "/baselines/" in f"/{path}"
        is_test_image = path.endswith(_IMAGE_SUFFIXES) and "/tests/" in f"/{path}"
        if in_baseline_dir or is_test_image:
            baseline_touches.append(raw_path)

    if not baseline_touches:
        return CompletenessCheck(
            check_name="visual_baselines_not_self_referential",
            passed=True,
            details="Spec touches no visual baseline images.",
        )

    if _BASELINE_INDEPENDENT_MARKER in spec.lower():
        return CompletenessCheck(
            check_name="visual_baselines_not_self_referential",
            passed=True,
            details=(
                f"{len(baseline_touches)} baseline image(s) touched with a "
                f"declared {_BASELINE_INDEPENDENT_MARKER} section."
            ),
        )

    path_list = ", ".join(f"`{p}`" for p in baseline_touches[:5])
    suffix = (
        f" (and {len(baseline_touches) - 5} more)"
        if len(baseline_touches) > 5
        else ""
    )
    return CompletenessCheck(
        check_name="visual_baselines_not_self_referential",
        passed=False,
        details=(
            f"Spec creates/regenerates visual baseline images that the run "
            f"itself produces: {path_list}{suffix}. A systematically wrong "
            f"first render would become its own reference and pass forever. "
            f"Add property assertions computable WITHOUT a baseline (e.g. "
            f"needle tip at the expected angle for a discriminating value) "
            f"in a section explicitly marked '{_BASELINE_INDEPENDENT_MARKER}', "
            f"or name an independent reference source for the baselines in "
            f"such a section."
        ),
    )


def check_criteria_have_tests(spec: str, lld_content: str) -> CompletenessCheck:
    """Every LLD pass criterion must have a test in the spec (Issue #2239).

    The counting job the adversarial reviewer was doing. In run-issue7-082047 it
    cost three iterations and the stage still died at the cap with "completely
    omits 12 required state matrix tests" among the reasons; here it is free and
    names all twelve at iteration zero, so one revision can fix the whole set.

    An LLD with no pass-criteria table is not applicable rather than a failure --
    the #1870 convention, so a spec that verified almost nothing cannot report a
    full house.
    """
    if not lld_content.strip():
        return CompletenessCheck(
            check_name="criteria_have_tests",
            passed=True,
            details=(
                "Criterion coverage not applicable: the LLD was not available to "
                "this node, so its pass criteria could not be read."
            ),
        )

    report = criteria_coverage(spec, lld_content)
    return CompletenessCheck(
        check_name="criteria_have_tests",
        passed=report.ok,
        details=format_coverage_report(report),
    )


def check_error_paths_have_tests(spec: str) -> CompletenessCheck:
    """Error paths the spec mandates must have tests (Issue #2333).

    A spec can pass every check above, report full requirement coverage, and
    still be unable to clear the 95 percent statement gate it is graded
    against two stages later. run-issue7-153937 did exactly that: twenty-three
    tests, all green, 80 percent statements, and every missed statement an
    error path or a platform branch its Section 11.1 conventions had mandated.

    The failure surfaced at N5, in a loop that can add tests but cannot add
    the requirement that justifies them. Here it surfaces at iteration zero,
    where the drafter is still writing Section 10.
    """
    report = error_path_coverage(spec)
    return CompletenessCheck(
        check_name="error_paths_have_tests",
        passed=report.ok,
        details=format_error_path_report(report),
    )


# =============================================================================
# Fence analysis — how the symbol checker reads Python (#1956)
# =============================================================================
#
# #1948 (receivers) -> #1950 (callbacks and docstrings) -> #1952 (self-attribute
# handles, import-less stdlib) -> #1954 (diff markers): four false-positive
# families in a single night, each patch correct and each followed by another,
# because the collectors modelled Python with line-anchored regexes. A regex
# cannot tell a call from a comment, a string, or a diff marker, and cannot
# resolve what a name is bound to — so every new snippet shape was a new
# family. `ast` answers all four questions by construction: string and comment
# content carries no nodes at all, which is why docstring stripping stops being
# a special case here.
#
# A fence that will not parse (a genuinely malformed snippet, or a diff whose
# context lines cannot be reconciled into valid Python) falls back to the
# original regex collectors below, so it degrades to the previous behaviour
# instead of going unscanned.

_CODE_FENCE_RE = re.compile(r"```[\w]*\s*\n(.*?)```", re.DOTALL)

# Diff decoration has to come off before a fence can parse: the spec template
# REQUIRES before/after snippets (#1954). Drop the ---/+++ file headers, DELETE
# a single leading +/- (deleting rather than blanking keeps the snippet's own
# indentation intact), then dedent so the body sits at column zero.
_DIFF_HEADER_RE = re.compile(r"(?m)^(?:\+\+\+|---).*$")
_DIFF_MARKER_RE = re.compile(r"(?m)^[+-](?![+-])")

# A spec snippet legitimately omits its import header (#1952), so stdlib module
# names are exempt receivers whether or not any fence shows the import.
_STDLIB_MODULE_NAMES: frozenset[str] = frozenset(sys.stdlib_module_names)

# ---- regex fallback collectors: pre-#1956 behaviour, unchanged --------------
_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import\s+([\w ,]+)|import\s+([\w.]+)(?:\s+as\s+(\w+))?)",
    re.MULTILINE,
)
_DEF_RE = re.compile(r"^\s*(?:def|class)\s+(\w+)", re.MULTILINE)
_SELF_ASSIGN_RE = re.compile(r"^\s*self\.(\w+)\s*=", re.MULTILINE)
_ASSIGN_RE = re.compile(r"^\s*(?:self\.)?(\w+)\s*=\s*(\w+)[.(]", re.MULTILINE)
_METHOD_CALL_RE = re.compile(r"\b(\w+)\.(\w+)\s*\(")
_DOCSTRING_RE = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL)


class _CallSite(NamedTuple):
    """One ``<receiver>.<method>(...)`` call found inside a fence."""

    receiver: str
    method: str
    site: str


class _FenceFacts(NamedTuple):
    """What one code fence says about names, definitions, and calls."""

    imported: frozenset[str]
    defined: frozenset[str]
    # (names bound, names the bound value derives from) — drives receiver
    # exemption once every fence has been read.
    assignments: tuple[tuple[frozenset[str], frozenset[str]], ...]
    calls: tuple[_CallSite, ...]
    parsed: bool  # False when this fence fell back to the regex collectors


def _normalize_fence(block: str) -> str:
    """Strip diff decoration so a before/after snippet can parse as Python."""
    block = _DIFF_HEADER_RE.sub("", block)
    block = _DIFF_MARKER_RE.sub("", block)
    return textwrap.dedent(block)


def _receiver_key(node: ast.expr) -> str | None:
    """The name a call's receiver is looked up under, or None if unresolvable.

    ``q.Queue()`` keys on ``q``. ``self.root.attributes(...)`` keys on ``root``
    — the attribute holding the handle, which is what ``self.root = tk.Tk()``
    exempts (#1952). Receivers that are call results, subscripts, or literals
    (``Image.open(p).convert()``, ``d["k"].foo()``) stay unjudged, exactly as
    the old call regex could not see past a ``)`` or ``]``.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _value_provenance(node: ast.expr) -> frozenset[str]:
    """Names a bound value derives from, for propagating receiver exemption.

    ``tk.Tk()`` derives from ``tk``; ``Path(d).iterdir()`` from ``Path``;
    ``self.root.nametowidget(".")`` from ``root`` — the handle that
    ``self.root = tk.Tk()`` already exempted (#1952), which the leftmost name
    (``self``) would miss. Both the immediate receiver and the leftmost name are
    offered, because either can be the one carrying the exemption.
    """
    keys: set[str] = set()
    inner = node.func if isinstance(node, ast.Call) else node
    if isinstance(inner, ast.Attribute):
        receiver = _receiver_key(inner.value)
        if receiver is not None:
            keys.add(receiver)
    leftmost = _leftmost_name(node)
    if leftmost is not None:
        keys.add(leftmost)
    return frozenset(keys)


def _leftmost_name(node: ast.expr) -> str | None:
    """Leftmost name an expression is rooted in: ``tk.Canvas(self.root)`` -> ``tk``."""
    while True:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred)):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Await):
            node = node.value
        else:
            return None


def _bound_names(target: ast.expr) -> set[str]:
    """Receiver keys an assignment target binds.

    A plain name binds itself; ``self.root = ...`` binds ``root``, because that
    is the key ``self.root.attributes(...)`` looks up (#1952). Tuple and list
    targets bind each element.
    """
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Attribute):
        return {target.attr}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names |= _bound_names(element)
        return names
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return set()


def _self_attributes(target: ast.expr) -> set[str]:
    """Attribute names assigned onto ``self`` — spec-defined symbols (#1950).

    ``self._on_quit_cb = on_quit`` then ``self._on_quit_cb()`` is how the
    drafter writes GUI callbacks; a def-only collector could not see the
    definition and drove a rename-oscillation across revise cycles.
    """
    if isinstance(target, ast.Attribute):
        if isinstance(target.value, ast.Name) and target.value.id == "self":
            return {target.attr}
        return set()
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names |= _self_attributes(element)
        return names
    if isinstance(target, ast.Starred):
        return _self_attributes(target.value)
    return set()


class _FenceVisitor(ast.NodeVisitor):
    """Collects imports, definitions, bindings, and method calls from a fence."""

    def __init__(self, source: str) -> None:
        self._lines = source.splitlines()
        self.imported: set[str] = set()
        self.defined: set[str] = set()
        self.assignments: list[tuple[frozenset[str], frozenset[str]]] = []
        self.calls: list[_CallSite] = []

    # ---- imports: receivers the target repo has no authority over (#1948) ----

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imported.add(alias.asname or alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imported.add(node.module.split(".")[0])
        for alias in node.names:
            if alias.name != "*":
                self.imported.add(alias.asname or alias.name)
        self.generic_visit(node)

    # ---- definitions the spec itself supplies ----

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.defined.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.defined.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defined.add(node.name)
        self.generic_visit(node)

    # ---- bindings: what each name actually holds ----

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record_binding(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record_binding([node.target], node.value)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._record_binding([node.target], node.iter)
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._record_binding([node.target], node.iter)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self._record_with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._record_with(node)

    def _record_with(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._record_binding([item.optional_vars], item.context_expr)
        self.generic_visit(node)

    def _record_binding(
        self, targets: list[ast.expr], value: ast.expr | None
    ) -> None:
        bound: set[str] = set()
        for target in targets:
            bound |= _bound_names(target)
            self.defined |= _self_attributes(target)
        if value is not None and bound:
            self.assignments.append((frozenset(bound), _value_provenance(value)))

    # ---- calls: the only thing actually judged ----

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            receiver = _receiver_key(node.func.value)
            if receiver is not None:
                self.calls.append(
                    _CallSite(receiver, node.func.attr, self._site(node))
                )
        self.generic_visit(node)

    def _site(self, node: ast.AST) -> str:
        """The source line a call sits on, for the failure message."""
        index = getattr(node, "lineno", 0) - 1
        if 0 <= index < len(self._lines):
            return self._lines[index].strip()[:80]
        return ""


def _fence_facts_ast(block: str) -> _FenceFacts | None:
    """Facts from a parsed fence, or None when the snippet will not parse."""
    try:
        tree = ast.parse(block)
    except (SyntaxError, ValueError, RecursionError):
        return None
    visitor = _FenceVisitor(block)
    visitor.visit(tree)
    return _FenceFacts(
        imported=frozenset(visitor.imported),
        defined=frozenset(visitor.defined),
        assignments=tuple(visitor.assignments),
        calls=tuple(visitor.calls),
        parsed=True,
    )


def _fence_facts_regex(block: str) -> _FenceFacts:
    """The pre-#1956 collectors, kept as the fallback for unparseable fences."""
    # #1950: docstrings inside fences quote code ('No tkinter.Tk() instantiated'
    # — the test-strategy rule itself). The AST path never needs this; a string
    # holds no call nodes.
    block = _DOCSTRING_RE.sub("", block)

    imported: set[str] = set()
    for imp in _IMPORT_RE.finditer(block):
        if imp.group(1):  # from X import a, b — names land in scope
            imported.add(imp.group(1).split(".")[0])
            for raw_name in imp.group(2).split(","):
                name = raw_name.strip().split(" as ")[-1].strip()
                if name:
                    imported.add(name)
        elif imp.group(3):  # import X [as y]
            imported.add(imp.group(4) or imp.group(3).split(".")[0])

    defined = {m.group(1) for m in _DEF_RE.finditer(block)}
    defined |= {m.group(1) for m in _SELF_ASSIGN_RE.finditer(block)}

    assignments = tuple(
        (frozenset({m.group(1)}), frozenset({m.group(2)}))
        for m in _ASSIGN_RE.finditer(block)
    )

    calls: list[_CallSite] = []
    for call in _METHOD_CALL_RE.finditer(block):
        site = (
            block[max(0, call.start() - 10) : call.end() + 20]
            .strip()
            .replace("\n", " ")[:80]
        )
        calls.append(_CallSite(call.group(1), call.group(2), site))

    return _FenceFacts(
        imported=frozenset(imported),
        defined=frozenset(defined),
        assignments=assignments,
        calls=tuple(calls),
        parsed=False,
    )


def _scan_fences(text: str) -> list[_FenceFacts]:
    """Read every code fence in ``text`` — AST where it parses, regex where not."""
    facts: list[_FenceFacts] = []
    for match in _CODE_FENCE_RE.finditer(text):
        block = _normalize_fence(match.group(1))
        parsed = _fence_facts_ast(block)
        facts.append(parsed if parsed is not None else _fence_facts_regex(block))
    return facts


def _flag_calls(
    facts: list[_FenceFacts],
    symbol_set: set[str],
) -> dict[str, list[str]]:
    """Judge every collected call against the target repo's symbol table.

    Facts are pooled across ALL fences before anything is judged: a spec
    routinely shows its imports in one snippet and the usage in another.
    """
    # #1948: three universes the target repo's symbol table has no authority
    # over — the phase-5 kill was this check rejecting Pillow's documented API
    # (ImageDraw.Draw, alpha_composite), pathlib, and a method the spec itself
    # defined. Same wrong-universe disease #1901 fixed for imports.
    exempt: set[str] = set(_STDLIB_MODULE_NAMES)
    spec_defined: set[str] = set()
    for fence in facts:
        exempt |= fence.imported
        spec_defined |= fence.defined

    # Exemption propagates through bindings to a fixed point rather than the
    # single level the old regex managed: `self.root = tk.Tk()` exempts `root`,
    # and `frame = self.root.frame()` then exempts `frame`. Whoever owns the
    # root owns everything derived from it, so the target repo's symbols have
    # no authority anywhere down that chain. Terminates because `exempt` only
    # grows and the set of bound names is finite.
    assignments = [
        (bound, source) for fence in facts for bound, source in fence.assignments
    ]
    changed = True
    while changed:
        changed = False
        for bound, source in assignments:
            if source & exempt and not bound <= exempt:
                exempt |= bound
                changed = True

    flagged: dict[str, list[str]] = {}  # method_name -> list of call sites
    for fence in facts:
        for call in fence.calls:
            if call.receiver in exempt:
                continue
            if call.method in symbol_set or call.method in spec_defined:
                continue
            if call.method in _API_SYMBOL_ALLOWLIST:
                continue
            flagged.setdefault(call.method, []).append(call.site)
    return flagged


def detect_unknown_method_calls(
    text: str,
    symbol_set: set[str],
) -> dict[str, list[str]]:
    """Scan code fences in ``text`` for method calls absent from ``symbol_set``.

    The detection core shared by :func:`check_api_symbols_exist` (which
    gates the spec) and the hallucination telemetry (#1812, which records
    the same signal for both the spec draft and the LLD, record-only).
    Extracted so both consumers measure with the identical yardstick.

    Args:
        text: Markdown to scan. Only content inside ``` fences is examined.
        symbol_set: Real symbol names extracted from the target repo.

    Returns:
        Mapping of unknown method name -> truncated example call sites.
        Empty when every call resolves to a known or allowlisted symbol.
    """
    return _flag_calls(_scan_fences(text), symbol_set)


def check_api_symbols_exist(
    spec: str,
    gathered_symbols: list[str],
) -> CompletenessCheck:
    """Spec must not call methods absent from the target project's gathered symbols.

    Closes #1527: Catches hallucinated API calls like ``question.model_dump()``
    and ``Question.model_validate(...)`` when the target class is a plain
    dataclass that exposes only ``to_dict`` / ``from_dict``.

    Strategy:
    - Scan only inside code fences (``` blocks) to avoid prose false positives.
    - Extract method/attribute calls of the form ``<ident>.<method>(`` (the
      opening paren ensures we capture method *calls*, not attribute accesses
      in prose or type annotations).
    - Flag any method name that is (a) absent from ``gathered_symbols`` AND
      (b) not in the false-positive allowlist of common Python builtins, stdlib
      idioms, dunder methods, and well-known third-party conventions.

    Conservative design:
    - Only flags method CALLS (trailing ``(``), not bare attribute access.
    - Only scans inside code fences.
    - Has a broad allowlist to keep false positives low.
    - Skips the check when ``gathered_symbols`` is empty (N1 didn't gather any
      Python content, so we have nothing to check against).

    Args:
        spec: Implementation Spec markdown content.
        gathered_symbols: Sorted list of identifier names extracted by N1 from
            the target repo's gathered .py files.

    Returns:
        CompletenessCheck with pass/fail result and details.
    """
    if not gathered_symbols:
        return CompletenessCheck(
            check_name="api_symbols_exist",
            passed=True,
            details=(
                "No gathered symbols from target repo — "
                "API symbol check skipped (N1 found no Python files to analyze)."
            ),
        )

    symbol_set: set[str] = set(gathered_symbols)
    facts = _scan_fences(spec)
    flagged = _flag_calls(facts, symbol_set)

    # #1870's honesty rule applied to the scan itself: a fence that fell back
    # to the regex collectors was read with the weaker instrument, and saying
    # so keeps "checked" from overstating what was verified.
    fell_back = sum(1 for fence in facts if not fence.parsed)
    scan_note = (
        f" {fell_back} of {len(facts)} fence(s) would not parse as Python and "
        f"were read with the regex fallback."
        if fell_back
        else ""
    )

    if not flagged:
        return CompletenessCheck(
            check_name="api_symbols_exist",
            passed=True,
            details=(
                f"All method calls in spec code fences are present in the "
                f"target repo's gathered symbols "
                f"({len(symbol_set)} symbols checked).{scan_note}"
            ),
        )

    # Build a readable summary of the flagged calls
    flag_items: list[str] = []
    for method_name, sites in sorted(flagged.items()):
        site_preview = sites[0] if sites else ""
        flag_items.append(f"`{method_name}` (e.g. `{site_preview}`)")

    flag_list = "; ".join(flag_items[:5])
    suffix = f" (and {len(flagged) - 5} more)" if len(flagged) > 5 else ""

    return CompletenessCheck(
        check_name="api_symbols_exist",
        passed=False,
        details=(
            f"Spec calls methods not found in the target project's gathered "
            f"symbols: {flag_list}{suffix}. These may be hallucinated APIs "
            f"(e.g., pydantic methods on a plain dataclass). Verify these "
            f"symbols exist in the target repo or replace with the actual API "
            f"the target class exposes.{scan_note}"
        ),
    )


# Allowlist of method/function names that are NEVER flagged as hallucinated.
# Covers: Python builtins, common stdlib idioms, dunder methods, and a small
# set of near-universal third-party conventions.
_API_SYMBOL_ALLOWLIST: frozenset[str] = frozenset({
    # ---- dunder / special methods ----
    "__init__", "__repr__", "__str__", "__eq__", "__lt__", "__le__",
    "__gt__", "__ge__", "__ne__", "__hash__", "__bool__", "__len__",
    "__iter__", "__next__", "__contains__", "__getitem__", "__setitem__",
    "__delitem__", "__enter__", "__exit__", "__call__", "__class__",
    "__dict__", "__doc__", "__module__", "__slots__", "__annotations__",
    "__new__",
    # ---- built-in type methods — dict ----
    "get", "items", "keys", "values", "update", "pop", "setdefault",
    "copy", "clear", "fromkeys",
    # ---- built-in type methods — list ----
    "append", "extend", "insert", "remove", "reverse", "sort", "count",
    # ---- built-in type methods — str ----
    "strip", "lstrip", "rstrip", "split", "rsplit", "splitlines",
    "join", "replace", "startswith", "endswith", "upper", "lower",
    "title", "capitalize", "format", "encode", "decode", "find",
    "rfind", "rindex", "partition", "rpartition", "zfill",
    "center", "ljust", "rjust",
    # ---- built-in type methods — set ----
    "add", "discard", "difference", "intersection", "union",
    "issubset", "issuperset",
    # ---- built-in type methods — bytes / bytearray ----
    "hex", "fromhex",
    # ---- pathlib ----
    "read_text", "write_text", "read_bytes", "write_bytes", "mkdir",
    "exists", "is_file", "is_dir", "glob", "rglob", "unlink", "rename",
    "stat", "open", "parent", "name", "stem", "suffix", "relative_to",
    "resolve",
    # ---- json / stdlib ----
    "loads", "dumps", "load", "dump",
    # ---- logging ----
    "info", "debug", "warning", "error", "exception", "critical",
    "getLogger",
    # ---- common built-ins ----
    "close", "flush", "read", "write", "seek", "tell", "readline",
    "readlines", "writelines",
    # ---- subprocess / os ----
    "run", "check_output", "check_call", "Popen", "communicate",
    "getenv",
    # ---- typing / dataclasses ----
    "field", "fields", "asdict", "astuple",
    # ---- collections ----
    "deque", "OrderedDict", "defaultdict", "Counter",
    # ---- itertools / functools ----
    "chain", "product", "combinations", "permutations", "partial",
    "reduce", "wraps",
    # ---- datetime ----
    "now", "utcnow", "strftime", "strptime", "isoformat",
    # ---- re / regex ----
    "match", "search", "findall", "finditer", "sub", "subn", "compile",
    "fullmatch", "group", "groups", "groupdict", "start", "end", "span",
    # ---- enum ----
    "value",
    # ---- contextlib ----
    "contextmanager",
    # ---- uuid ----
    "uuid4", "UUID",
    # ---- hashlib ----
    "sha256", "md5", "hexdigest", "digest",
    # ---- asyncio ----
    "gather", "sleep", "create_task", "ensure_future", "get_event_loop",
    "run_until_complete",
    # ---- threading ----
    "Thread", "Lock", "Event", "set", "wait",
    # ---- common pytest/mock patterns ----
    "assert_called", "assert_called_once", "assert_called_with",
    "assert_any_call", "call_count", "called",
})


_SOURCE_ROOT_PREFIXES: tuple[str, ...] = (
    "", "src", "lib", "source", "python", "apps",
)


def _candidate_matches_new_file(candidate: Path, new_file_paths: set[str]) -> bool:
    """Suffix-match a candidate module path against the spec's Add file paths.

    Honors src-layout: `chiron/provenance.py` matches `src/chiron/provenance.py`
    in new_file_paths because the latter ends with `/` + the former.
    Closes #1461.
    """
    cand_str = str(candidate).replace("\\", "/")
    for new_path in new_file_paths:
        np = new_path.replace("\\", "/")
        if np == cand_str or np.endswith("/" + cand_str):
            return True
    return False


def _discover_pyproject_source_roots(repo_root: Path) -> tuple[str, ...]:
    """Best-effort discovery of source roots from pyproject.toml.

    Reads `[tool.poetry.packages]` (with `from = "X"`) and
    `[tool.setuptools.packages.find]` (with `where = ["X"]`) entries.
    Malformed pyproject files return (); the caller falls back to the
    static prefix list. Closes #1477.
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return ()
    try:
        import tomllib
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return ()
    roots: list[str] = []
    poetry_packages = (
        data.get("tool", {}).get("poetry", {}).get("packages", [])
    )
    if isinstance(poetry_packages, list):
        for pkg in poetry_packages:
            if isinstance(pkg, dict):
                src = pkg.get("from")
                if isinstance(src, str) and src:
                    roots.append(src)
    setuptools_where = (
        data.get("tool", {}).get("setuptools", {})
            .get("packages", {}).get("find", {}).get("where", [])
    )
    if isinstance(setuptools_where, list):
        for w in setuptools_where:
            if isinstance(w, str) and w:
                roots.append(w)
    return tuple(roots)


def _candidate_exists_under_source_roots(
    candidate: Path, repo_root: Path
) -> bool:
    """Probe `repo_root / {prefix} / candidate` for common source-root prefixes
    plus any prefixes discovered from `pyproject.toml`. Closes #1461, #1477.
    """
    discovered = _discover_pyproject_source_roots(repo_root)
    all_prefixes = _SOURCE_ROOT_PREFIXES + discovered
    for prefix in all_prefixes:
        probe = (repo_root / prefix / candidate) if prefix else (repo_root / candidate)
        if probe.exists():
            return True
    return False


def _import_resolves(
    module_path: str, repo_root: Path, new_file_paths: set[str]
) -> bool:
    """Check if an import resolves to an existing file or a new file in the spec.

    Recognizes both flat-layout (`chiron/provenance.py` at repo root) and
    src-layout (`src/chiron/provenance.py`). Closes #1461.

    Filters empty segments from the dotted path before constructing
    candidate file paths. A leading dot (`from . import X` → `module_path="."`)
    or doubled dot (`foo..bar`) would otherwise produce `Path("")` which
    pathlib treats as `Path(".")`, and `.with_suffix(".py")` raises
    ValueError on a path with no name. Closes #1513.
    """
    parts = [p for p in module_path.split(".") if p]
    if not parts:
        return False
    candidates: list[Path] = [
        Path(*parts).with_suffix(".py"),
        Path(*parts) / "__init__.py",
    ]
    if len(parts) > 1:
        candidates.extend([
            Path(*parts[:-1]).with_suffix(".py"),
            Path(*parts[:-1]) / "__init__.py",
        ])

    for candidate in candidates:
        if _candidate_exists_under_source_roots(candidate, repo_root):
            return True
        if _candidate_matches_new_file(candidate, new_file_paths):
            return True

    return False


# Common stdlib top-level module names (subset for fast rejection)
def _first_party_tops(repo_root: Path) -> set[str]:
    """Top-level package names that belong to the target repo itself (#1901).

    A dotted import whose top level is one of these gets the strict
    exists-or-created-by-this-spec rule (#842); anything else is
    third-party and validates against the target environment instead.
    Covers flat layout (pkg at repo root) and src layout.
    """
    tops: set[str] = set()
    for base in (repo_root, repo_root / "src"):
        try:
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if child.is_dir() and (child / "__init__.py").is_file():
                    tops.add(child.name)
        except OSError:
            continue
    return tops


def _target_env_python(repo_root: Path) -> str | None:
    """Absolute python path of the TARGET repo's poetry venv, or None.

    Asks poetry for the env path explicitly instead of `poetry run python`
    — poetry silently falls through to PATH when no venv exists (#1904),
    which would answer the probe from the WRONG environment.
    """
    try:
        proc = subprocess.run(
            ["poetry", "env", "info", "--path"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    env_path = Path(proc.stdout.strip())
    for candidate in (env_path / "Scripts" / "python.exe", env_path / "bin" / "python"):
        if candidate.is_file():
            return str(candidate)
    return None


def _probe_target_env(repo_root: Path, tops: list[str]) -> dict[str, bool] | None:
    """One batched find_spec probe inside the target repo's venv (#1901).

    Returns {top_level: importable} — or None when the environment cannot
    answer (no venv, timeout, bad output). Callers MUST treat None as
    "cannot validate", never as "missing": a wrong-environment verdict is
    worse than no verdict (#1904).
    """
    if not tops:
        return {}
    python = _target_env_python(repo_root)
    if python is None:
        return None
    script = (
        "import importlib.util, json, sys; "
        "print(json.dumps({n: importlib.util.find_spec(n) is not None "
        "for n in sys.argv[1:]}))"
    )
    try:
        proc = subprocess.run(
            [python, "-c", script, *tops],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        result = json.loads(proc.stdout.strip().splitlines()[-1])
        if not isinstance(result, dict):
            return None
        return {str(k): bool(v) for k, v in result.items()}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


_KNOWN_STDLIB_TOPS: frozenset[str] = frozenset({
    "abc", "argparse", "ast", "asyncio", "base64", "builtins", "collections",
    "contextlib", "copy", "csv", "dataclasses", "datetime", "decimal",
    "difflib", "email", "enum", "functools", "glob", "gzip", "hashlib",
    "hmac", "html", "http", "importlib", "inspect", "io", "itertools",
    "json", "logging", "math", "mimetypes", "multiprocessing", "operator",
    "os", "pathlib", "pickle", "platform", "pprint", "queue", "random",
    "re", "secrets", "shlex", "shutil", "signal", "socket", "sqlite3",
    "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "timeit", "tomllib", "traceback", "types",
    "typing", "unittest", "urllib", "uuid", "warnings", "xml", "zipfile",
})


# =============================================================================
# Utility
# =============================================================================


def _log_check(check: CompletenessCheck) -> None:
    """Log a single check result.

    Args:
        check: CompletenessCheck to log.
    """
    # #1870: a check with nothing to check is not a pass. Saying so keeps the
    # console honest about how much of the spec was actually verified.
    if not check["passed"]:
        status = "FAIL"
    elif "not applicable" in check["details"].lower():
        status = "N/A "
    else:
        status = "PASS"
    name = check["check_name"]
    print(f"    [{status}] {name}")