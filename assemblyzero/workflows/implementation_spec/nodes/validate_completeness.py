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
import tomllib
from pathlib import Path
from typing import Any, NamedTuple

from assemblyzero.workflows.implementation_spec.state import (
    CompletenessCheck,
    FileToModify,
    ImplementationSpecState,
    PatternRef,
)
from assemblyzero.workflows.implementation_spec.base_tree import (
    base_ref,
    exists_on_base,
    read_from_base,
)
from assemblyzero.workflows.implementation_spec.check_classification import (
    advisory_details,
    is_proxy,
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
    # #2667: the tree the run builds on. The checkout is the default branch
    # (#2012) and mid-arc has none of the arc; base_tree reads git instead.
    base_branch = state.get("base_branch", "")

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

    # Check 3: Functions should have I/O examples — PROXY since #2620, so the
    # demotion pass below turns its failure into an advisory. Kept because it
    # grades functions the template's section-5 structure may not cover.
    check_functions = check_functions_have_io_examples(spec_draft)
    checks.append(check_functions)
    _log_check(check_functions)

    # Check 3b (#2620): the structural fact-verifier that carries the gate
    # check 3 used to hold. Bounded by each subsection's own heading, so a
    # neighbouring function's example cannot satisfy it.
    check_func_sections = check_function_spec_sections_have_examples(spec_draft)
    checks.append(check_func_sections)
    _log_check(check_func_sections)

    # Check 4: Change instructions should be specific.
    #
    # #2539 demoted this one check inline, here, by rewriting its result. That
    # hack is gone: #2540 classified every check fact-verifier or
    # proxy-heuristic in one pass, and the demotion below applies the table to
    # all of them uniformly. See `check_classification.py` for this check's
    # entry and the reading that decided it.
    check_instructions = check_change_instructions_specific(spec_draft)
    checks.append(check_instructions)
    _log_check(check_instructions)

    # Check 5: Pattern references should be valid
    check_patterns = check_pattern_references_valid(
        spec_draft, pattern_references, repo_root_str
    )
    checks.append(check_patterns)
    _log_check(check_patterns)

    # Check 6: Import targets should exist (Issue #842; base-aware per #2667)
    check_imports = check_import_targets_exist(
        spec_draft, files_to_modify, repo_root_str, base_branch
    )
    checks.append(check_imports)
    _log_check(check_imports)

    # Check 7: Spec must not call methods absent from target repo (Issue #1527)
    gathered_symbols: list[str] = state.get("gathered_symbols", [])  # type: ignore[assignment]
    check_symbols = check_api_symbols_exist(
        spec_draft, gathered_symbols, repo_root_str
    )
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

    # Check 10b (#2706): Section 10's test functions must survive the
    # scaffolder's validator. The scaffolder emits them verbatim (#2316) and
    # the implementation stage refuses a suite that asserts nothing --
    # run-issue4-163140 lost 605 s of approved spec work to that refusal
    # 3.4 s into the next stage. Same extractor, same rule, one stage earlier.
    check_spec_asserts = check_spec_test_functions_have_assertions(
        spec_draft, state.get("issue_number", 0), files_to_modify
    )
    checks.append(check_spec_asserts)
    _log_check(check_spec_asserts)

    # Check 10c (#2707): every test-function parameter must name a fixture
    # the run can resolve -- a pytest builtin, one defined in the block, or
    # one from a plugin the target repo declares. The same spec took `mocker`
    # with no pytest-mock declared and `live_environment` defined nowhere.
    check_spec_fixtures = check_spec_test_fixtures_resolvable(
        spec_draft, repo_root_str, base_branch
    )
    checks.append(check_spec_fixtures)
    _log_check(check_spec_fixtures)

    # Check 11: Manifest traceability — every manifest row in exactly one
    # test, every test tracing to a real identifier (Issue #2533). A diff, not
    # an LLM judgment; abstains where it cannot parse (#2526).
    #
    # #2633: the LLD is passed because a test may legitimately trace to a
    # requirement or a test-scenario id when the manifest holds no row for it
    # -- the manifest's domain is the injected criteria table alone.
    check_manifest = check_manifest_traceability(
        spec_draft,
        state.get("assertion_manifest_rows", []),
        state.get("lld_content", ""),
    )
    checks.append(check_manifest)
    _log_check(check_manifest)

    # Telemetry (#1812): record detector outcomes for the spec draft (every
    # pass) and the LLD (first pass only). Record-only — the try/except
    # guarantees telemetry can never alter validation_passed.
    try:
        _record_hallucination_telemetry(state, spec_draft, gathered_symbols)
    except Exception as e:  # noqa: BLE001 — record-only contract
        print(f"    [telemetry] WARNING: hallucination telemetry failed: {e}")

    # #2540: a proxy-heuristic never outranks an engaged judge examining the
    # same dimension. Applied here, once, over every check -- so the rule is
    # the table's, not each check's call site's, and a check added tomorrow
    # obeys it without anyone remembering to write the demotion again.
    review_engaged = review_is_engaged(state)
    checks = [_demote_proxies(check, review_engaged) for check in checks]

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
    # Closes #2304: a check that first fails on the FINAL revision receives
    # zero revisions, and the stage dies on a failure the drafter was never
    # asked to fix. Measured on boostgauge #7 -- three iterations on
    # `criteria_have_tests`, and satisfying it surfaced
    # `functions_have_io_examples` with the budget already spent.
    #
    # That loop was CONVERGING. A cap exists to stop a loop repeating itself;
    # killing one at the moment it made progress is the opposite of its
    # purpose. Raising the cap only moves the cliff -- the same run would then
    # die on whatever the next fix surfaces.
    #
    # So the distinction is encoded rather than the number raised: a check that
    # has never been shown to the drafter has not been tried once, and is not
    # evidence of non-convergence. It grants exactly one extra revision, once.
    failing_names = [c["check_name"] for c in checks if not c["passed"]]
    shown = list(state.get("checks_shown_to_drafter", []))
    grace_used = list(state.get("grace_revisions_used", []))

    grace_for: list[str] = []
    cap_message = ""
    if not validation_passed:
        iteration = state.get("review_iteration", 0)
        max_iterations = state.get("max_iterations", 3)
        if iteration >= max_iterations:
            grace_for = grant_grace(failing_names, shown, grace_used)
            # #2536: the ceiling decision has ONE authority. The grace clause
            # checked only the base cap, so a completeness failure at the
            # hard ceiling (run-issue331-150920: iteration 9, reached by
            # eight honest converging rounds) was granted a revision carrying
            # iteration 10 — a state the review guard refuses to review. The
            # grace draft was pure spend with unreviewable output, and the
            # halt was the incoherent "routing should have halted earlier"
            # instead of the clean hard-ceiling report.
            from assemblyzero.workflows.implementation_spec.review_progress import (
                CEILING_MULTIPLIER,
                EXIT_CEILING,
                hard_ceiling,
                regeneration_allowed,
            )

            if not regeneration_allowed(iteration, max_iterations):
                if grace_for:
                    print(
                        f"    [CAP] {', '.join(grace_for)} has never been "
                        f"shown to the drafter, but the grant is at its hard "
                        f"ceiling — the revision it would earn could never be "
                        f"reviewed, so it is not granted (#2536)."
                    )
                    grace_for = []
                ceiling = hard_ceiling(max_iterations)
                listed = "; ".join(completeness_issues[:3])
                cap_message = (
                    f"Spec review stopped [{EXIT_CEILING}]: the grant reached "
                    f"its hard ceiling of {ceiling} ({CEILING_MULTIPLIER}x "
                    f"the base cap of {max_iterations}) during a completeness "
                    f"revision — iteration {iteration}'s draft failed "
                    f"{len(completeness_issues)} completeness check(s) and no "
                    f"further regeneration may be granted. Unfixed: {listed}. "
                    f"The draft and every verdict are in lineage; an explicit "
                    f"relaunch grants a fresh cap regime (#2514)."
                )
            elif grace_for:
                grace_used.extend(grace_for)
                print(
                    f"    [CAP] {max_iterations} revision(s) spent, but "
                    f"{', '.join(grace_for)} has never been shown to the "
                    f"drafter. Granting one revision for it (#2304)."
                )
            else:
                listed = "; ".join(completeness_issues[:3])
                # The two halts read differently on purpose. "N revisions ended
                # with 1 unresolved check" reads as a stubborn drafter; when
                # every failing check HAS been tried, that is the true reading.
                tried = sorted(set(failing_names) & set(shown + grace_used))
                # #2526: within "tried", the drafter FAILING to fix a check and
                # the drafter leaving the code untouched are different facts,
                # and the halt says which. When a check's complaint is
                # byte-identical across every prior revision, the flagged
                # content reached the check unchanged every round — evidence
                # of a false positive in the check. str.isupper died exactly
                # this way: three identical complaints, one dead run.
                #
                # #2556: that inference is only sound when the drafter's
                # output actually SURVIVED to the next check. Pinning
                # enforcement (#2532) broke the assumption the day after the
                # wording landed: a reverted revision re-presents the
                # previous bytes, indistinguishable — from the complaint
                # stream alone — from a drafter that changed nothing.
                # run-issue331-092913 halted claiming "the drafter ... left
                # the flagged code unchanged each time" with six [PINNING]
                # refusal lines in the same log; the drafter had made the
                # mandated fix every round and enforcement restored it. So:
                # an identical complaint reads as drafter-left-unchanged
                # ONLY when no pinning reversion happened in this run's
                # revisions; with reversions on the record, enforcement is
                # named and the drafter is not accused. Never attribute an
                # artifact to an actor without proof.
                prior_iters = prior_breakdown[:-1]
                details_by_name = {
                    c["check_name"]: c["details"] for c in checks if not c["passed"]
                }
                identical = [
                    name for name in tried
                    if prior_iters and all(
                        details_by_name[name] in entry["failures"]
                        for entry in prior_iters
                    )
                ]
                # #2561: a conservation override (#2559) is an enforcement
                # intervention exactly as a refusal is — either way the
                # drafter's revision did not reach the check intact.
                reversions = [
                    event for event in state.get("pinning_events", [])
                    if "[PINNING] refused:" in event
                    or "[PINNING] CONSERVATION:" in event
                ]
                declined = [] if reversions else identical
                reverted = identical if reversions else []
                # #2539: the third class. A complaint whose NUMBERS moved
                # under revision while its verdict never did means the
                # drafter complied with the instruction and the check's
                # counter absorbed the compliance — observed live as "found
                # 7, expected 8, 441 lines" becoming "found 8, expected 9,
                # 454 lines": the snippet was added, the spec grew, and the
                # line-derived threshold moved with it. Three revisions that
                # cannot move a blind counter are evidence against the
                # check, not the draft. Detected by digit-normalized
                # identity: same complaint shape every round, only the
                # counts changed.
                def _shape(text: str) -> str:
                    return re.sub(r"\d+", "N", text)

                complied = [
                    name for name in tried
                    if name not in identical and prior_iters and all(
                        any(
                            _shape(details_by_name[name]) == _shape(failure)
                            for failure in entry["failures"]
                        )
                        for entry in prior_iters
                    )
                ]
                kept_failing = [
                    name for name in tried
                    if name not in identical and name not in complied
                ]
                detail = ""
                if kept_failing:
                    # #2561: "survived a revision" claims the drafter's
                    # output reached this check and still failed. With
                    # enforcement interventions on the record that is
                    # unprovable — run-issue331-111729's halt asserted
                    # survival for criteria_have_tests while pinning had
                    # refused the drafter's demanded addition in the same
                    # granted revision. The survival claim survives only a
                    # clean pinning record, because there it is true.
                    if reversions:
                        detail += (
                            f" Each unresolved check was shown to the "
                            f"drafter, but pinning enforcement refused or "
                            f"overrode revision content in this run "
                            f"({len(reversions)} event(s), e.g. "
                            f"{reversions[0]}) — the drafter's revision may "
                            f"not have reached the check intact; read the "
                            f"[PINNING] events before treating these as "
                            f"drafter failures: {', '.join(kept_failing)}."
                        )
                    else:
                        detail += (
                            f" Each unresolved check was shown to the drafter "
                            f"and survived a revision: "
                            f"{', '.join(kept_failing)}."
                        )
                if declined:
                    detail += (
                        f" NOTE: {', '.join(declined)} drew the IDENTICAL "
                        f"complaint on every revision — the drafter was shown "
                        f"it {len(prior_iters)} time(s), no pinning reversion "
                        f"intervened, and the flagged content reached the "
                        f"check unchanged each time. Flagged content "
                        f"surviving every revision untouched is evidence of "
                        f"a false positive in the check, not of an unfixable "
                        f"spec."
                    )
                if reverted:
                    detail += (
                        f" NOTE: {', '.join(reverted)} drew the IDENTICAL "
                        f"complaint on every revision while pinning "
                        f"enforcement reverted revision content in this "
                        f"run ({len(reversions)} refusal(s), e.g. "
                        f"{reversions[0]}). A reverted revision re-presents "
                        f"the previous bytes to the check, so the recurrence "
                        f"cannot be read as the drafter leaving the flagged "
                        f"content unchanged — the complaint and the pinning "
                        f"vocabulary are deadlocked (#2555): the check's "
                        f"complaint must name its target in terms pinning "
                        f"reads, or the named span must be unlocked."
                    )
                if complied:
                    detail += (
                        f" NOTE: {', '.join(complied)} COMPLIED WITHOUT "
                        f"EFFECT — the complaint kept its exact shape across "
                        f"every revision with only its counts moving, so the "
                        f"drafter did what the check asked and the check's "
                        f"own threshold absorbed it. That is evidence of a "
                        f"false positive in the check, not of an unfixable "
                        f"spec (#2539)."
                    )
                cap_message = (
                    f"Iteration cap: {max_iterations} revision(s) ended with "
                    f"{len(completeness_issues)} unresolved completeness "
                    f"check(s).{detail} Unfixed: {listed}"
                )

    # A failing set that is about to become a revision prompt has, by
    # definition, been shown to the drafter. Recorded whether the revision is
    # the ordinary kind or a grace, so a grace cannot be claimed twice.
    if not validation_passed and (grace_for or not cap_message):
        for name in failing_names:
            if name not in shown:
                shown.append(name)

    return {
        "completeness_issues": completeness_issues,
        "validation_passed": validation_passed,
        "prior_completeness_breakdown": prior_breakdown,
        "checks_shown_to_drafter": shown,
        "grace_revisions_used": grace_used,
        "grace_revision_for": grace_for,
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
            # #2411: the same repo root the gate uses. The docstring's promise
            # that both consumers "measure with the identical yardstick" stops
            # being true the moment one of them can tell first-party from
            # foreign and the other cannot.
            flagged = detect_unknown_method_calls(text, symbol_set, repo)
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


def grant_grace(
    failing_names: list[str], shown: list[str], grace_used: list[str]
) -> list[str]:
    """Which failing checks earn one extra revision past the cap (#2304).

    A pure function per ADR 0224, and deliberately not inlined: a test that
    re-expresses this rule instead of calling it would agree with itself
    forever, which is the #2264 class of green-while-asserting-nothing.

    A check qualifies when it has never reached a revision prompt (`shown`) and
    has never claimed a grace before (`grace_used`). The first condition is the
    whole point -- a check that has not been tried once is not evidence of
    non-convergence. The second bounds it, so a check that alternates pass and
    fail spends its one grace and then meets the wall like anything else.
    """
    return [
        name for name in failing_names
        if name not in shown and name not in grace_used
    ]


#: A Function Specifications subsection: `### 5.2 `compute_needle_angle()``.
#: Template 0701 defines this shape, and both preserved boostgauge specs
#: follow it exactly -- #331's spec carries seven subsections and seven Input
#: Examples, #1's carries two and two.
_FUNC_SPEC_HEADING_RE = re.compile(
    r"^###\s+5\.\d+\s+(.+?)\s*$", re.MULTILINE
)

#: The blocks template 0701 requires inside each such subsection.
_REQUIRED_EXAMPLE_BLOCKS = ("**Input Example:**", "**Output Example:**")

#: A fence delimiter. Same vocabulary `revision_pinning._FENCE_RE` uses, so the
#: two modules agree about where a code block starts and stops (#2681).
_FENCE_LINE_RE = re.compile(r"^```.*$", re.MULTILINE)


def _fenced_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Character spans covered by fenced code blocks, delimiters included.

    An UNTERMINATED fence swallows the remainder of the document. That is the
    generous direction and it is chosen deliberately: this module's consumer
    fails a spec when it cannot find a block, so an over-wide fence costs a
    missed complaint while an over-narrow one costs a false alarm that halts
    the stage (#2687).
    """
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    for match in _FENCE_LINE_RE.finditer(text):
        if open_at is None:
            open_at = match.start()
        else:
            spans.append((open_at, match.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return tuple(spans)


def _outside_fences(pos: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return not any(start <= pos < end for start, end in spans)


def function_spec_sections(spec: str) -> list[tuple[str, str, int, int]]:
    """Every `### 5.N` subsection as (heading, body, first line, last line).

    Both line numbers are 1-based and inclusive, and the subsection owns every
    line between them.

    Bounded by the NEXT heading of any level, so a subsection's body is its
    own -- which is the whole difference between this and a window scan.

    **The end line is measured here, from the offsets (#2686), not derived by
    a caller from `body`.** `_FUNC_SPEC_HEADING_RE` ends in `\\s*$`, and that
    `\\s*` eats the heading's own newline before `$` settles, so `body` opens
    somewhere inside the whitespace after the heading rather than at a
    predictable place. A caller counting newlines in `body` is short by
    however much the regex absorbed -- one line for every subsection whose
    heading is followed by a blank, which is all of them under template 0701.

    **Fences are not prose (#2687).** A Python comment at column zero inside an
    example -- `# Called on a Telltale instance with active history` -- matches
    `^#\\s` exactly as a markdown heading does. Reading it as one ended the
    subsection early and hid the `**Output Example:**` four lines below it, so
    the check reported a block missing that was present; boostgauge #421's
    fifth launch halted on a spec that was already correct. The verdict turned
    on whether the model happened to open a code sample with a comment, which
    is the accident-of-phrasing dependence #2620 demoted the window scan for.

    `revision_pinning._blocks` already tracks fence state for the same reason
    and against the same document. This is the same rule in the one place that
    lacked it -- both for the headings that OPEN a subsection and the heading
    that ENDS one, since a bound that ignored fences on one side only would
    leave a fenced `### 5.N` opening a section nothing inside that fence could
    close.
    """
    text = spec or ""
    fences = _fenced_spans(text)
    matches = [
        m for m in _FUNC_SPEC_HEADING_RE.finditer(text)
        if _outside_fences(m.start(), fences)
    ]
    if not matches:
        return []
    next_heading = re.compile(r"^#{1,6}\s", re.MULTILINE)
    out: list[tuple[str, str, int, int]] = []
    for index, match in enumerate(matches):
        start = match.end()
        limit = (
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        )
        following = next(
            (
                m for m in next_heading.finditer(text, start, limit)
                if _outside_fences(m.start(), fences)
            ),
            None,
        )
        body_end = following.start() if following else limit
        line_no = text.count("\n", 0, match.start()) + 1
        # The line holding the last character the subsection owns. Counting to
        # `body_end` itself would land on the terminating heading whenever the
        # body ends in a newline, which is the ordinary case.
        end_line = max(
            line_no,
            text.count("\n", 0, max(body_end - 1, 0)) + 1,
        )
        out.append((match.group(0).strip(), text[start:body_end], line_no, end_line))
    return out


def check_function_spec_sections_have_examples(spec: str) -> CompletenessCheck:
    """Every Function Specifications subsection carries its example blocks.

    #2620's path back to a hard gate. `functions_have_io_examples` searches a
    +/-2000-character window for vocabulary and any concrete-looking value,
    which cannot tell whether the example belongs to the function it is
    grading -- neighbouring definitions share the window. That is a correlate,
    and the operator demoted it to advisory.

    This asks a bounded, structural question instead: does the subsection that
    documents this function, between its own heading and the next one, contain
    the `**Input Example:**` and `**Output Example:**` blocks template 0701
    requires? Presence within a region is a fact. No neighbour can satisfy it,
    and no repetition of a name can move the verdict.

    Not applicable is not failure: a spec with no `### 5.N` subsections -- a
    spec that adds no functions, or one written before the template -- yields
    no checks and passes, per the #1870 convention.

    The complaint names the subsection HEADING, which occurs verbatim in the
    draft, so revision pinning can read the address (#2555's lesson, swept by
    `test_completeness_message_addressability.py`).

    **It cites the whole subsection, not the heading line (#2686.)** Naming
    `(line 142-142)` addressed the heading and nothing else. `_blocks` splits a
    draft at every top-level `def` inside a fence, and template 0701 opens each
    subsection with a `**Signature:**` fence carrying exactly that -- so the
    cited line named only the six lines from the heading down to `**Signature:**`
    and the remaining sixteen, including the place the missing block has to go,
    stayed locked. Measured on boostgauge run `run-issue41-184913`'s draft with
    one block deleted: 6 of 22 lines free, the insertion point among the locked
    ones. The drafter wrote the demanded edit three times and pinning refused it
    three times, then the edit-script transport rejected the no-op revision and
    the stage halted non-transient.

    A demand to add has no existing line to name, which is the same bind #2560
    found for demanded tests. The address that works is the region the complaint
    already names in prose -- "Add the block inside that subsection" -- so the
    citation now spans it. `named_line_flags` marks every block the range
    overlaps, which is the generous direction it documents, and the span stops
    at the subsection's own end so no neighbouring section is freed.
    """
    sections = function_spec_sections(spec)
    if not sections:
        return CompletenessCheck(
            check_name="function_spec_sections_have_examples",
            passed=True,
            details=(
                "No `### 5.N` function-specification subsections found — "
                "check not applicable."
            ),
        )

    missing: list[str] = []
    for heading, body, line_no, end_line in sections:
        absent = [b for b in _REQUIRED_EXAMPLE_BLOCKS if b not in body]
        if absent:
            missing.append(
                f"{heading} (lines {line_no}-{end_line}) lacks "
                f"{' and '.join(absent)}"
            )

    if missing:
        listed = "; ".join(missing[:5])
        suffix = f" (and {len(missing) - 5} more)" if len(missing) > 5 else ""
        return CompletenessCheck(
            check_name="function_spec_sections_have_examples",
            passed=False,
            details=(
                f"{len(missing)} of {len(sections)} function-specification "
                f"subsection(s) are missing a required example block: "
                f"{listed}{suffix}. Add the block inside that subsection; "
                f"template 0701 section 5 requires both."
            ),
        )

    return CompletenessCheck(
        check_name="function_spec_sections_have_examples",
        passed=True,
        details=(
            f"All {len(sections)} function-specification subsection(s) carry "
            f"an Input Example and an Output Example."
        ),
    )


def check_functions_have_io_examples(spec: str) -> CompletenessCheck:
    """Every non-test function must have input/output examples.

    **Classified a PROXY-heuristic and demoted to advisory (#2620.)** The
    window scan below cannot tell whether the example it finds belongs to the
    function it is grading, so its failure is a correlate rather than a fact.
    `check_function_spec_sections_have_examples` above is the fact-verifier
    that replaces its authority; this stays as an advisory second opinion,
    because it grades functions the template's section-5 structure may not
    cover.

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
        # #2590: the backticked span carries the BARE name; the readable
        # call form sits outside it. `named_tokens` parses what is inside
        # backticks verbatim, so `compute_needle_angle()` -- parens included
        # -- occurs in a draft only when the function happens to take no
        # arguments. Two drafts differing solely in the parameter list drew
        # a byte-identical complaint, one addressable and one not, and the
        # broken case is the ordinary one. The bare name appears verbatim in
        # every `def` line, so the token now lands and the demanded example
        # survives enforcement instead of being reverted as content no
        # verdict named (registry class 3, standard 0029).
        #
        # Dropping the parens rather than adding a second span: the sentence
        # already says "Functions", so the call form earned nothing, and a
        # second `name()` span would parse as a token that matches nothing.
        # Loosening `named_tokens` to strip trailing parens was the other
        # candidate and is rejected -- that vocabulary is shared by every
        # complaint, and a looser token matches more than it should.
        func_list = ", ".join(f"`{f}`" for f in missing_examples[:5])
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
    """Change instructions should be diff-level specific — a DENSITY HEURISTIC.

    #2539: this check is ADVISORY at the node — its failure is printed, never
    gated on. The measurement is a proxy (fence count per ~50 lines, indicator
    count per ~30), and because both thresholds derive from line count, a
    drafter's compliance grows the spec and can move the demand with it —
    observed live as 7-of-8 at 441 lines becoming 8-of-9 at 454. The N5
    adversarial reviewer judges concreteness and executability directly; this
    heuristic only surfaces a hint the operator can read in the log.

    The fence counter counts EVERY fence pair regardless of language tag —
    python, diff, text — so guidance in any fence form registers (verified
    against the run-issue331-200815 draft while refuting the hypothesis that
    non-Python fences were skipped: that scan note belonged to the
    api-symbols checker). Per-tag counts are included in the details so the
    composition is visible at a glance.

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

    # Count code blocks specifically (strong indicator). EVERY fence pair
    # counts, whatever its tag — the check's own advice says "diff-level
    # guidance", so a diff or text fence satisfying that advice must move
    # this number (#2539 ask 2).
    code_blocks = re.findall(r"```[\s\S]*?```", spec)
    code_block_count = len(code_blocks)

    # Per-tag composition, so a reader can see at a glance what kinds of
    # fences the count is made of (#2539: a skip must be visible).
    tag_counts: dict[str, int] = {}
    for block in code_blocks:
        first_line = block.splitlines()[0] if block.splitlines() else "```"
        tag = first_line[3:].strip() or "(untagged)"
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    by_tag = ", ".join(
        f"{tag}={count}" for tag, count in sorted(tag_counts.items())
    ) or "none"

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
                f"{code_block_count} (by tag: {by_tag}), expected at least "
                f"{min_code_blocks} for a {spec_lines}-line spec. Change "
                f"instructions benefit from before/after code snippets, line "
                f"references, or diff-level guidance — every fence tag "
                f"counts."
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
    base_branch: str = "",
) -> CompletenessCheck:
    """Verify that imports referenced in the spec point to existing modules.

    Issue #842: Catches the scenario where the spec instructs code to import
    from modules that don't exist (e.g., `from assemblyzero.core.metrics import X`
    when assemblyzero.core.metrics doesn't exist). Cross-references against
    the spec's Files Changed table for new files the spec itself creates.

    #2667: a first-party import that fails filesystem resolution is probed
    against the run's base ref before being declared missing. The checkout is
    the default branch (#2012); mid-arc, a Modify file can ship only on the
    base — run-issue379-002604 declared `boostgauge.skins.stingray`
    nonexistent while `origin/hardening-run-19` carried it, and the false
    complaint deadlocked with pinning for three revisions.

    Args:
        spec: Implementation Spec markdown content.
        files: List of FileToModify from the LLD.
        repo_root_str: Repository root path string.
        base_branch: The branch the run builds on ("" preserves the
            filesystem-only behaviour for standalone runs).

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

    # #2667: resolve the base ref once; consulted only when the filesystem
    # says no. Empty base_branch keeps today's behaviour exactly.
    base_ref_name = base_ref(repo_root, base_branch) if base_branch else ""

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
                # #2667: absent from the checkout is not absent from the run —
                # the base may ship it. Probe git before declaring it missing.
                if base_ref_name and _resolves_on_base(
                    module_path, repo_root, base_ref_name
                ):
                    continue
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
        # #2667: say what was actually consulted — a complaint that names the
        # base it checked cannot be mistaken for one that never looked.
        base_clause = (
            f", nor exist on the run's base `{base_ref_name}`"
            if base_ref_name
            else ""
        )
        return CompletenessCheck(
            check_name="import_targets_exist",
            passed=False,
            details=(
                f"Imports in spec reference modules that neither exist, nor "
                f"are created by this spec{base_clause}, nor import in the "
                f"target repo's environment: {mod_list}{suffix}. For "
                f"first-party modules, verify the path; for third-party, add "
                f"the dependency to the target repo or fix the import."
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


# ---------------------------------------------------------------------------
# Section 10's test functions, graded by the stage that will run them
# (#2706, #2707)
# ---------------------------------------------------------------------------
#
# Since #2316 the scaffolder emits the spec's Section 10 test functions
# verbatim, and `validate_tests_mechanical` then refuses a suite whose
# functions assert nothing. Both were right on boostgauge run-issue4-163140
# (2026-09-02): the spec passed twelve completeness checks and an APPROVED
# review, and the implementation stage refused it 3.4 s later, deterministic
# on regeneration, because eleven of its thirteen tests were a comment and
# `pass`, and seven took `mocker` (no pytest-mock declared), `benchmark` (no
# pytest-benchmark declared) or `live_environment` (defined nowhere).
#
# These two checks ask the same questions one stage earlier, where the drafter
# can still respond -- with the SAME extractor and the SAME rule the testing
# workflow uses, so the verdicts cannot drift (#1698). Each complaint names the
# function in backticks and cites its `lines N-M` span, the #2686 shape, so
# revision pinning opens exactly the function the drafter has to rewrite and
# nothing beside it.

#: Fixtures a pytest plugin injects by parameter name, keyed by the
#: distribution the target repo would have to declare. A closed map, never a
#: pattern: a name is added only with the plugin that provides it named
#: beside it, and a plugin absent from this map is treated as providing
#: nothing (#2707).
_PLUGIN_FIXTURES: dict[str, frozenset[str]] = {
    "pytest-mock": frozenset({
        "mocker", "class_mocker", "module_mocker", "package_mocker",
        "session_mocker",
    }),
    "pytest-asyncio": frozenset({
        "event_loop", "unused_tcp_port", "unused_tcp_port_factory",
        "unused_udp_port", "unused_udp_port_factory",
    }),
    "pytest-httpx": frozenset({"httpx_mock"}),
    "pytest-benchmark": frozenset({"benchmark", "benchmark_weave"}),
    "pytest-xdist": frozenset({"worker_id", "testrun_uid"}),
    "pytest-cov": frozenset({"cov"}),
}

#: The leading distribution name of a PEP 508 requirement string
#: (``pytest-mock>=3``, ``pytest_mock (>=3,<4)``, ``pytest-mock[extra]``).
_REQUIREMENT_NAME_RE = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

#: The validator's per-function complaint, ``Function 'test_x' <what>``.
_VALIDATOR_FUNCTION_RE = re.compile(r"^Function '(test_\w+)' (.+)$")


def _normalise_distribution(name: str) -> str:
    """PEP 503 normalisation: case-insensitive, `_` and `.` read as `-`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared_dependencies(pyproject_text: str) -> set[str] | None:
    """Every distribution a pyproject declares, normalised; None if not TOML.

    Reads the three shapes in use: PEP 621 lists (``[project] dependencies``,
    ``[project.optional-dependencies]``), Poetry tables
    (``[tool.poetry.dependencies]``, ``[tool.poetry.group.*.dependencies]``)
    and PEP 735 ``[dependency-groups]``. Under any key ending in
    ``dependencies`` (or ``dependency-groups``), a table contributes the keys
    whose values are a version string or a spec table, and a list contributes
    the leading name of each string. Nothing else in the file is read.
    """
    if not pyproject_text:
        return set()
    try:
        data = tomllib.loads(pyproject_text)
    except tomllib.TOMLDecodeError:
        # fail-open: an unparseable pyproject declares no plugins, which makes
        # the fixture check STRICTER, never quieter -- every plugin fixture is
        # then reported as undeclared -- and None lets the report say "could
        # not be parsed" rather than "declares none".
        return None

    names: set[str] = set()

    def in_scope(path: tuple[str, ...]) -> bool:
        return any(
            part.endswith("dependencies") or part == "dependency-groups"
            for part in path
        )

    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if in_scope(path) and isinstance(value, (str, dict)):
                    names.add(_normalise_distribution(key))
                    continue
                walk(value, path + (key,))
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str):
                    if in_scope(path):
                        match = _REQUIREMENT_NAME_RE.match(item)
                        if match:
                            names.add(_normalise_distribution(match.group(1)))
                else:
                    walk(item, path)

    walk(data, ())
    return names


def _pyproject_for_run(repo_root_str: str, base_branch: str) -> tuple[str, str]:
    """The target repo's pyproject as the run's base ships it (#2684, #2668),
    and where it came from -- so a fallback is named in the report rather
    than taken silently. Falls to the checkout when the run names no base or
    the base has none; ``("", <why>)`` when nothing can be read."""
    if not repo_root_str:
        return "", "no repo root given"
    repo_root = Path(repo_root_str)
    if base_branch:
        ref = ""
        try:
            ref = base_ref(repo_root, base_branch)
            text = read_from_base(repo_root, ref, "pyproject.toml")
        except (OSError, subprocess.SubprocessError) as exc:
            # fail-open: a base that cannot be read falls to the checkout's
            # own pyproject, and the fallback is printed here and named in
            # the report. The direction is stricter (fewer declared plugins),
            # never quieter.
            print(
                f"    [FIXTURES] pyproject unreadable on base {base_branch!r} "
                f"({exc}); reading the checkout's instead"
            )
            text = ""
        if text:
            return text, f"read from {ref}"
    try:
        checkout = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        # fail-open: no pyproject anywhere means no declared plugins, which
        # the report states outright; the check gets stricter, not quieter.
        return "", "no pyproject could be read"
    return checkout, "read from the checkout"


def _spec_test_functions(spec: str) -> dict[str, Any]:
    """Section 10's executable test functions, by the testing workflow's own
    extractor -- a second parser here would be the #1698 class."""
    from assemblyzero.workflows.testing.nodes.load_lld import (
        extract_spec_test_functions,
    )

    return extract_spec_test_functions(spec)


def _test_function_spans(
    spec: str, functions: list[dict[str, str]]
) -> dict[str, tuple[int, int]]:
    """1-based line span of each extracted function in the draft.

    The extractor slices sources verbatim out of the draft, so each is found
    by text; the cursor advances so two identical bodies map to their own
    positions rather than both to the first.
    """
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for fn in functions:
        source = fn["source"]
        idx = spec.find(source, cursor)
        if idx < 0:
            idx = spec.find(source)
        if idx < 0:
            continue
        start = spec.count("\n", 0, idx) + 1
        spans[fn["name"]] = (start, start + source.count("\n"))
        cursor = idx + len(source)
    return spans


def check_spec_test_functions_have_assertions(
    spec: str,
    issue_number: int = 0,
    files_to_modify: list[dict] | None = None,
) -> CompletenessCheck:
    """Section 10's test functions must survive the scaffolder's validator (#2706).

    Builds the file exactly as `scaffold_tests.generate_spec_test_file_content`
    will and grades it with `validate_tests_mechanical.validate_test_structure`
    -- the implementation stage's own transcription and its own rule -- so
    this check and that stage cannot disagree. Not applicable when the spec
    ships no executable functions (the table-derived path).

    The complaint backticks nothing but function names: a backticked word is a
    pinning token that unlocks every line carrying it, and `pass` or `assert`
    as tokens would open half the draft.
    """
    suite = _spec_test_functions(spec)
    functions = suite["functions"]
    if not functions:
        return CompletenessCheck(
            check_name="spec_test_functions_have_assertions",
            passed=True,
            details=(
                "Section 10 carries no executable test functions — check not "
                "applicable (the scaffolder falls back to table-derived scenarios)."
            ),
        )

    from assemblyzero.workflows.testing.nodes.load_lld import (
        scenarios_from_spec_functions,
    )
    from assemblyzero.workflows.testing.nodes.scaffold_tests import (
        generate_spec_test_file_content,
    )
    from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
        validate_test_structure,
    )

    content = generate_spec_test_file_content(
        suite, issue_number, files_to_modify or []
    )
    errors = validate_test_structure(content, scenarios_from_spec_functions(functions))
    if not errors:
        return CompletenessCheck(
            check_name="spec_test_functions_have_assertions",
            passed=True,
            details=(
                f"All {len(functions)} Section 10 test function(s) carry an "
                f"assertion; the scaffolder will emit them verbatim (#2316)."
            ),
        )

    spans = _test_function_spans(spec, functions)
    by_function: list[str] = []
    other: list[str] = []
    for error in errors:
        match = _VALIDATOR_FUNCTION_RE.match(error)
        if match and match.group(1) in spans:
            start, end = spans[match.group(1)]
            by_function.append(
                f"`{match.group(1)}` (lines {start}-{end}) {match.group(2)}"
            )
        else:
            other.append(error)

    parts: list[str] = []
    if by_function:
        # Every refused function is cited, never a truncated list: the span
        # is what pinning unlocks, and a function left off the list stays
        # locked against the very edit this complaint demands.
        listed = "; ".join(by_function)
        parts.append(
            f"{len(by_function)} of {len(functions)} §10 test function(s) "
            f"would be refused by the implementation stage's scaffolder: {listed}. "
            "Replace each pass body with the setup and at least one assert "
            "statement (or a pytest.raises block) that checks the value its "
            "comment states — the scaffolder emits these functions verbatim "
            "(#2316) and the implementation stage refuses a suite that asserts "
            "nothing."
        )
    if other:
        parts.append("Also refused by that validator: " + "; ".join(other))
    return CompletenessCheck(
        check_name="spec_test_functions_have_assertions",
        passed=False,
        details=" ".join(parts),
    )


def _is_fixture_decorated(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _parametrized_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names a ``@pytest.mark.parametrize`` decorator supplies as parameters."""
    names: set[str] = set()
    for decorator in node.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "parametrize"
            and decorator.args
        ):
            continue
        first = decorator.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.update(n.strip() for n in first.value.split(",") if n.strip())
        elif isinstance(first, (ast.List, ast.Tuple)):
            names.update(
                element.value
                for element in first.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
    return names


def check_spec_test_fixtures_resolvable(
    spec: str, repo_root_str: str = "", base_branch: str = ""
) -> CompletenessCheck:
    """Every parameter of a Section 10 test function must name a fixture (#2707).

    Three routes satisfy it: a pytest builtin, a ``@pytest.fixture`` function
    in the same block, or a fixture from a plugin the target repo's pyproject
    declares (`_PLUGIN_FIXTURES`, read from the run's base branch). A name
    that takes none of them errors at setup one stage later, before any
    assertion runs. Abstains when the block does not parse --
    `python_fences_parse` reports that (#2526's unknown-is-not-guilty).
    """
    suite = _spec_test_functions(spec)
    functions = suite["functions"]
    if not functions:
        return CompletenessCheck(
            check_name="spec_test_fixtures_resolvable",
            passed=True,
            details=(
                "Section 10 carries no executable test functions — check not "
                "applicable."
            ),
        )

    block = "\n\n".join([suite["imports"]] + [fn["source"] for fn in functions])
    try:
        tree = ast.parse(block)
    except SyntaxError:
        # fail-open: abstains audibly -- the details say not applicable, the
        # summary counts it as such, and python_fences_parse fails the same
        # draft on the same syntax (#2526's unknown-is-not-guilty).
        return CompletenessCheck(
            check_name="spec_test_fixtures_resolvable",
            passed=True,
            details=(
                "Section 10 test block does not parse — check not applicable; "
                "python_fences_parse reports the syntax."
            ),
        )

    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_fixture_decorated(node)
    }
    pyproject_text, pyproject_source = _pyproject_for_run(repo_root_str, base_branch)
    declared = _declared_dependencies(pyproject_text)
    if declared is None:
        pyproject_source = "the repo's pyproject could not be parsed"
        declared = set()
    from_declared_plugins: set[str] = set()
    from_undeclared_plugins: dict[str, str] = {}
    for distribution, fixtures in _PLUGIN_FIXTURES.items():
        if distribution in declared:
            from_declared_plugins |= fixtures
        else:
            for fixture in fixtures:
                from_undeclared_plugins[fixture] = distribution

    spans = _test_function_spans(spec, functions)
    failures: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        supplied = _parametrized_names(node)
        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            param = arg.arg
            if (
                param in _NON_RECEIVER_PARAMS
                or param in _PYTEST_BUILTIN_FIXTURES
                or param in defined
                or param in from_declared_plugins
                or param in supplied
            ):
                continue
            start, end = spans.get(node.name, (0, 0))
            where = f" (lines {start}-{end})" if start else ""
            if param in from_undeclared_plugins:
                why = (
                    f" — provided by {from_undeclared_plugins[param]}, which the "
                    "repo's pyproject does not declare"
                )
            else:
                why = (
                    " — not a pytest builtin, not decorated as a fixture in "
                    "§10, and no declared plugin provides it"
                )
            failures.append(f"`{node.name}`{where} takes `{param}`{why}")

    if not failures:
        return CompletenessCheck(
            check_name="spec_test_fixtures_resolvable",
            passed=True,
            details=(
                f"Every parameter of the {len(functions)} Section 10 test "
                "function(s) resolves to a fixture."
            ),
        )

    # Every failure is cited, never a truncated list -- the span unlocks the
    # function, and an uncited one stays locked against its own repair.
    listed = "; ".join(failures)
    declared_plugins = sorted(d for d in _PLUGIN_FIXTURES if d in declared)
    declared_note = (
        f" (declared: {', '.join(declared_plugins)}; {pyproject_source})"
        if declared_plugins
        else f" (the repo declares none; {pyproject_source})"
    )
    return CompletenessCheck(
        check_name="spec_test_fixtures_resolvable",
        passed=False,
        details=(
            f"{len(failures)} test-function parameter(s) name no fixture and "
            f"would error at setup in the implementation stage: {listed}. A "
            "parameter must be a pytest builtin fixture (monkeypatch, tmp_path, "
            "capsys, ...), a function decorated with pytest.fixture inside the "
            "§10 test block, or a fixture from a plugin the repo's pyproject "
            f"declares{declared_note}. Drop the parameter, define the fixture "
            "in §10, or use monkeypatch or unittest.mock instead."
        ),
    )


#: An explicit traceability citation: ``# manifest: S1.1``, ``# manifest:
#: REQ-3``, ``# manifest: row 010``. The trailing text is captured whole so an
#: unrecognised citation can be QUOTED BACK (#2633) rather than reported as
#: absent.
_CITATION_RE = re.compile(r"#\s*manifest:\s*(.+)")


def _citation_namespaces(lld_content: str) -> tuple[set[str], set[str]]:
    """(requirement ids, LLD test-scenario ids) a citation may name (#2633).

    Both come from readers this module already depends on -- a second parser
    of either would be the #1698 class -- and both are checked against the
    upstream LLD rather than accepted on faith.
    """
    if not lld_content:
        return (set(), set())

    from assemblyzero.core.validation.test_plan_validator import (
        extract_requirements,
    )
    from assemblyzero.workflows.implementation_spec.criteria_coverage import (
        lld_criteria,
    )

    reqs = {r["id"] for r in extract_requirements(lld_content) if r.get("id")}
    scenarios = {c.row_id for c in lld_criteria(lld_content) if c.row_id}
    return (reqs, scenarios)


def _classify_citation(
    cited: str, row_ids: set[str], reqs: set[str], scenarios: set[str]
) -> str | None:
    """Which namespace ``cited`` belongs to, or None when it belongs to none."""
    text = cited.strip().rstrip(".,;")
    # `row 010` and a bare `010` are the same citation.
    bare = re.sub(r"^row\s+", "", text, flags=re.IGNORECASE).strip()
    for candidate in (text, bare):
        if candidate in row_ids:
            return "manifest"
        if candidate in reqs:
            return "requirement"
        if candidate in scenarios:
            return "scenario"
    return None


def check_manifest_traceability(
    spec: str, manifest_rows: list[dict], lld_content: str = ""
) -> CompletenessCheck:
    """Every manifest row in a test; every test traced to a real identifier.

    Rows-to-tests bookkeeping as a mechanical diff — the two minutes of
    per-round LLM traceability adjudication this check retires.

    ## Two domains, because the document has two (#2633)

    The manifest compiles the injected criteria table only: visual assertions
    with sample points and expected literals. A spec's test suite rightly
    covers more — base generation, a size floor, cache persistence, constant
    isolation, artifact emission — and no manifest row can ever exist for
    "cache persistence", which has no sample point and never will. Demanding a
    manifest citation from those tests demanded the impossible, and on
    boostgauge's `run-issue331-182658` it cost three revisions and a cap.

    The drafter's response was not sloppiness. It cited LLD **test-scenario**
    ids -- `row 010`, `row 020`, `row 030`, `row 100`, `row 110`, every one a
    real row of LLD-331's Test Scenarios table and exactly the five non-visual
    scenarios -- plus a valid `REQ-N` on every test. It partitioned the LLD's
    eleven scenarios perfectly: a manifest row where one existed, a scenario
    id where none could. The check knew one namespace of three and reported
    the other two as nothing, so the halt read *"test(s) citing no manifest
    row"* about five tests that visibly cited two identifiers each.

    Three namespaces are therefore legal, and all three are checkable against
    artifacts already in hand: manifest row ids, the LLD's requirement ids,
    the LLD's test-scenario ids.

    ## Which way each direction fails

    * **Row to test is unchanged** -- every manifest row must be cited, and a
      row cited by more than one test still fails. That half catches real gaps
      and nothing here loosens it.
    * **Test to identifier** passes on at least ONE valid citation. An
      unrecognised extra is REPORTED, never fatal on its own: failing a test
      that has traced itself correctly because it also carries a redundant
      annotation is the false-alarm disease #2540 removed.
    * A test whose citations are **all** unrecognised fails, with each invalid
      citation quoted and the namespaces enumerated, so the complaint names
      something the draft actually contains (#2555).

    Abstention (#2526: unknown is not guilty): a fence that will not parse is
    not judged here — it is already a hard failure of the api-symbols check
    (#2392), and judging text this check could not read would be static
    analysis of arbitrary code, which is not its job. The details name how
    many fences went unjudged, so "checked" never overstates what was
    verified (#1870).
    """
    if not manifest_rows:
        return CompletenessCheck(
            check_name="manifest_traceability",
            passed=True,
            details=(
                "No assertion manifest for this run — traceability not "
                "applicable."
            ),
        )

    row_ids = [r.get("row_id", "") for r in manifest_rows if r.get("row_id")]
    id_patterns = {
        rid: re.compile(rf"(?<![\w.]){re.escape(rid)}(?![\w.])")
        for rid in row_ids
    }

    tests: list[tuple[str, str]] = []  # (test name, source segment)
    unparsed = 0
    for match in _CODE_FENCE_RE.finditer(spec):
        tag = (match.group(1) or "").lower()
        if tag and tag not in _PYTHON_FENCE_TAGS and tag not in _UNDECLARED_FENCE_TAGS:
            continue
        block = _normalize_fence(match.group(2))
        try:
            tree = ast.parse(block)
        except (SyntaxError, ValueError, RecursionError):
            # fail-open: #2533's ruled abstention (#2526: unknown is not
            # guilty). A fence that will not parse is the api-symbols
            # check's HARD failure (#2392) — the draft is already blocked
            # for it — and this check counts what it could not read into
            # the details line, so the abstention is visible, never silent.
            unparsed += 1
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name.startswith("test_")
            ):
                segment = ast.get_source_segment(block, node) or ""
                tests.append((node.name, segment))

    abstain_note = (
        f" ({unparsed} unparseable fence(s) not judged — abstained, not "
        f"guilty)"
        if unparsed else ""
    )

    if not tests:
        # No parseable test functions at all: with a binding manifest this is
        # a real gap, not an abstention — every row is untested.
        #
        # #2593: NAME the rows. This branch reported a COUNT while holding the
        # ids, and a count addresses nothing: `_ROW_ID_RE` (`\b[A-Z]\d{0,3}
        # [a-z]?\.\d+\b`) reads `N4.1` exactly, so the one vocabulary pinning
        # has for this artifact was being withheld by the only check that has
        # the artifact. The `problems` branch below already lists them under
        # `manifest rows are ...`; this branch was the odd one out. Truncated
        # at twelve to match it.
        listed = ", ".join(row_ids[:12]) if row_ids else "none"
        more = f" (and {len(row_ids) - 12} more)" if len(row_ids) > 12 else ""
        return CompletenessCheck(
            check_name="manifest_traceability",
            passed=False,
            details=(
                f"The assertion manifest binds {len(row_ids)} row(s) but the "
                f"spec contains no parseable test functions citing them. "
                f"Manifest rows are {listed}{more}. Section 10 owes each a "
                f"test."
                + abstain_note
            ),
        )

    reqs, scenarios = _citation_namespaces(lld_content)
    row_id_set = set(row_ids)

    cited_by: dict[str, list[str]] = {rid: [] for rid in row_ids}
    uncited_tests: list[str] = []
    #: (test name, the citations it made that match no namespace)
    invalid_only: list[tuple[str, list[str]]] = []
    unrecognised_extras: list[str] = []

    for name, segment in tests:
        hits = [rid for rid, pat in id_patterns.items() if pat.search(segment)]
        for rid in hits:
            cited_by[rid].append(name)

        # #2633: an explicit citation may name any of the three namespaces.
        cited = [c.strip() for c in _CITATION_RE.findall(segment)]
        good: list[str] = []
        bad: list[str] = []
        for citation in cited:
            if _classify_citation(citation, row_id_set, reqs, scenarios):
                good.append(citation)
            else:
                bad.append(citation)

        if hits or good:
            # Traced. An unrecognised extra is visible but not fatal.
            unrecognised_extras.extend(f"{name}: `{b}`" for b in bad)
        elif bad:
            invalid_only.append((name, bad))
        else:
            uncited_tests.append(name)

    problems: list[str] = []
    missing = [rid for rid in row_ids if not cited_by[rid]]
    if missing:
        problems.append(
            f"manifest row(s) cited by NO test: {', '.join(missing[:8])}"
            + (f" (and {len(missing) - 8} more)" if len(missing) > 8 else "")
        )
    duplicated = {
        rid: names for rid, names in cited_by.items() if len(names) > 1
    }
    if duplicated:
        listed = "; ".join(
            f"{rid} in {', '.join(names)}"
            for rid, names in list(duplicated.items())[:4]
        )
        problems.append(f"manifest row(s) cited by MORE than one test: {listed}")
    if uncited_tests:
        problems.append(
            f"test(s) tracing to nothing: "
            f"{', '.join(uncited_tests[:8])}"
            + (
                f" (and {len(uncited_tests) - 8} more)"
                if len(uncited_tests) > 8 else ""
            )
        )
    if invalid_only:
        # #2633: quote the citation back. Reporting "cites nothing" at a test
        # that visibly cites something is the complaint that cost three
        # revisions -- the drafter cannot act on a demand that contradicts the
        # draft in front of it.
        listed = "; ".join(
            f"{name} cites {', '.join(repr(b) for b in bad)}"
            for name, bad in invalid_only[:4]
        )
        problems.append(
            f"test(s) whose every citation matches no known identifier: "
            f"{listed}"
            + (f" (and {len(invalid_only) - 4} more)"
               if len(invalid_only) > 4 else "")
        )

    if problems:
        namespaces = [f"manifest rows are {', '.join(row_ids[:12])}"]
        if reqs:
            namespaces.append(
                f"LLD requirements are {', '.join(sorted(reqs)[:12])}"
            )
        if scenarios:
            namespaces.append(
                f"LLD test-scenario ids are {', '.join(sorted(scenarios)[:12])}"
            )
        return CompletenessCheck(
            check_name="manifest_traceability",
            passed=False,
            details=(
                "Manifest traceability is a mechanical diff (#2533) and it "
                "does not balance: " + " | ".join(problems)
                + ". Cite with a `# manifest: <id>` comment; valid ids: "
                + "; ".join(namespaces) + "."
                + abstain_note
            ),
        )

    return CompletenessCheck(
        check_name="manifest_traceability",
        passed=True,
        details=(
            f"All {len(row_ids)} manifest row(s) are each cited by exactly "
            f"one of {len(tests)} test(s), and every test traces to a "
            f"manifest row, an LLD requirement, or an LLD test-scenario id."
            + (
                f" Unrecognised extra citation(s), not fatal: "
                f"{'; '.join(unrecognised_extras[:6])}."
                if unrecognised_extras else ""
            )
            + abstain_note
        ),
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
# A fence that will not parse used to fall back to regex collectors. #2392
# retired that: standard 0028 is absolute that "regex is not a safety fallback",
# and §4 that no function "returns ... a silent downgrade because it could not
# read its input". The fallback did not provide resilience, it provided silence —
# it fed the symbol check a confident, wrong call list and converted "this spec
# contains code that does not parse", a first-class defect in an implementation
# spec, into a footnote.
#
# What replaces it is the fence's own LANGUAGE TAG, which is a declaration:
#
#   python/py/python3  the fence CLAIMS to be Python. It must parse. A parse
#                      failure is a named completeness failure carrying the
#                      fence's line span and the parse error.
#   text/json/bash/... the fence declares it is something else. Skipped by tag,
#                      never parsed, never a failure.
#   diff, untagged     undeclared. Parsed opportunistically for facts; a parse
#                      failure is counted and reported, never a hard failure,
#                      because nothing claimed it was Python.
#
# The tag filter is load-bearing and must come FIRST. The rejected boostgauge #1
# draft carries three correctly-authored ```text fences (lines 75-77, 134-136,
# 347-359) holding bodyless class declarations. They are not malformed Python;
# they were never Python. Killing the fallback without filtering on the tag
# would convert an otherwise clean draft into a hard failure — replacing a
# silent wrong answer with a loud one.

_CODE_FENCE_RE = re.compile(r"```([\w]*)\s*\n(.*?)```", re.DOTALL)

#: Tags whose fence CLAIMS to be Python. Parse failure here is a named failure.
_PYTHON_FENCE_TAGS: frozenset[str] = frozenset({"python", "py", "python3"})

#: Tags that declare a fence is Python-adjacent but not a Python claim. A diff
#: fence normalizes into parseable Python often enough to be worth reading
#: (#1954), and legitimately does not when it diffs a non-Python file.
_UNDECLARED_FENCE_TAGS: frozenset[str] = frozenset({"", "diff"})

# Diff decoration has to come off before a fence can parse: the spec template
# REQUIRES before/after snippets (#1954). Drop the ---/+++ file headers, DELETE
# a single leading +/- (deleting rather than blanking keeps the snippet's own
# indentation intact), then dedent so the body sits at column zero.
_DIFF_HEADER_RE = re.compile(r"(?m)^(?:\+\+\+|---).*$")
_DIFF_MARKER_RE = re.compile(r"(?m)^[+-](?![+-])")

# A spec snippet legitimately omits its import header (#1952), so stdlib module
# names are exempt receivers whether or not any fence shows the import.
_STDLIB_MODULE_NAMES: frozenset[str] = frozenset(sys.stdlib_module_names)

# ---- framework-injected parameters: a fourth wrong universe (#2391) ---------
#
# #1948 named three universes the target repo's symbol table has no authority
# over — imports, stdlib, spec-defined names. This is the fourth: a parameter
# the FRAMEWORK supplies, whose type the target repo does not own and never
# will.
#
# The founding case is pytest's own plugin API. boostgauge ruling #271 mandates
# registering custom flags via `pytest_addoption`, and the spec reviewer duly
# demanded it; the symbol check then rejected `parser.addoption(` because
# `parser` — injected by pytest, of type `_pytest.config.argparsing.Parser` —
# resolves to nothing in the target repo's 21 gathered symbols. One gate
# demanded the line and the other forbade it, so no draft could satisfy both
# and the stage died at the iteration cap three times over.
#
# The exemption is deliberately narrow. It does NOT say "parameters are
# unresolvable", which is true but useless: every true positive this check has
# ever caught arrives as a bare parameter receiver — #1527's founding
# `state.model_dump()`, and `win.model_dump()` in #1952's regression set.
# Exempting all of them would widen the check into uselessness. What is exempt
# is the parameter of a function whose NAME declares the framework owns the
# call: pluggy's `pytest_*` hook convention, and pytest's builtin fixture names
# wherever they appear as parameters.
_PYTEST_HOOK_PREFIX = "pytest_"

#: Fixtures pytest injects by parameter name. A test taking `tmp_path` is
#: handed a `pathlib.Path` by pytest; the target repo has no say in its API.
_PYTEST_BUILTIN_FIXTURES: frozenset[str] = frozenset({
    "request", "monkeypatch", "pytestconfig", "cache",
    "tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory",
    "capsys", "capsysbinary", "capfd", "capfdbinary",
    "caplog", "recwarn", "doctest_namespace",
    "record_property", "record_testsuite_property", "record_xml_attribute",
})

#: Never treated as receivers carrying an exemption. `self` is the spec's own
#: object — exempting it would hand the whole target-repo surface a free pass,
#: which is precisely the check's jurisdiction.
_NON_RECEIVER_PARAMS: frozenset[str] = frozenset({"self", "cls"})

class _CallSite(NamedTuple):
    """One ``<receiver>.<method>(...)`` call found inside a fence."""

    receiver: str
    method: str
    site: str
    #: Leftmost name the receiver chain is rooted in (#2396). For
    #: ``request.config.getoption(...)`` the receiver key is ``config`` but the
    #: root is ``request`` — and ownership travels with the root, not the last
    #: attribute. None when the chain bottoms out in a call, subscript, or
    #: literal rather than a name.
    root: str | None


class _FenceFacts(NamedTuple):
    """What one code fence says about names, definitions, and calls."""

    imported: frozenset[str]
    defined: frozenset[str]
    # (names bound, names the bound value derives from) — drives receiver
    # exemption once every fence has been read.
    assignments: tuple[tuple[frozenset[str], frozenset[str]], ...]
    calls: tuple[_CallSite, ...]
    # Parameters a framework injects, whose type the target repo does not own
    # (#2391) — `parser` in `def pytest_addoption(parser)`, `tmp_path` in a test.
    framework_params: frozenset[str]
    # (function name, root name of its return annotation) for functions the SPEC
    # itself defines (#2399). `def render(...) -> Image.Image` yields
    # ("render", "Image"), which is how a binding from render() learns it holds
    # a Pillow object rather than one of the target repo's.
    returns: tuple[tuple[str, str], ...]
    # Classes the spec defines (#2399). A class is the one callee whose return
    # type is known without an annotation: `Gauge()` is a Gauge.
    classes: frozenset[str]
    # Names bound in forms whose type is unknowable by construction (#2526):
    # lambda parameters, and `except:` targets with no exception class. These
    # seed the unresolved set directly — a method on one is a method on an
    # unknown type, and unknown is not guilty.
    opaque: frozenset[str] = frozenset()


class _FenceParseFailure(NamedTuple):
    """A fence that CLAIMED to be Python and would not parse (#2392).

    Carries what a revision needs to act: which fence, and why the parser
    refused. There is no third option where the content gets read anyway.
    """

    start_line: int
    end_line: int
    tag: str
    error: str


class _ScanResult(NamedTuple):
    """Everything one pass over a document's fences established."""

    facts: list[_FenceFacts]
    #: Declared-Python fences that would not parse — named failures.
    failures: list[_FenceParseFailure]
    #: Fences skipped because their tag declares a non-Python language.
    skipped_by_tag: int
    #: Undeclared fences (untagged, diff) that would not parse. Counted and
    #: reported, never a failure: nothing claimed they were Python.
    undeclared_unparsed: int


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
        self.framework_params: set[str] = set()
        self.returns: dict[str, str] = {}
        self.classes: set[str] = set()
        self.opaque: set[str] = set()

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
        self._record_framework_params(node)
        self._record_return(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.defined.add(node.name)
        self._record_framework_params(node)
        self._record_return(node)
        self.generic_visit(node)

    def _record_return(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """What a spec-defined function declares it returns (#2399).

        `def render(...) -> Image.Image` records ("render", "Image"). The root
        of the annotation is what matters: whoever owns `Image` owns what
        `render()` hands back, which is the question a binding from that call
        needs answered.

        Only spec-declared annotations are read. Nothing is inferred from a
        function body, and an unannotated function records nothing — it is left
        unresolved rather than guessed at.
        """
        if node.returns is None:
            return
        root = _leftmost_name(node.returns)
        if root is not None:
            self.returns[node.name] = root

    def _record_framework_params(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Parameters this function receives from a framework, not the repo (#2391).

        Two sources, both declared by naming convention rather than inferred:

        * a pluggy hook (``pytest_addoption``, ``pytest_collection_modifyitems``)
          receives every one of its parameters from pytest;
        * a pytest builtin fixture name (``tmp_path``, ``monkeypatch``) is
          framework-supplied in whatever function requests it.

        An ordinary function's ordinary parameter is NOT recorded. ``state`` in
        ``def apply(state)`` stays judged, which is what keeps #1527's founding
        true positive — pydantic methods on a plain dataclass — catchable.
        """
        args = node.args
        collected = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        if args.vararg is not None:
            collected.append(args.vararg)
        if args.kwarg is not None:
            collected.append(args.kwarg)
        names = {a.arg for a in collected} - _NON_RECEIVER_PARAMS

        if node.name.startswith(_PYTEST_HOOK_PREFIX):
            self.framework_params |= names
        else:
            self.framework_params |= names & _PYTEST_BUILTIN_FIXTURES

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defined.add(node.name)
        # #2399: a class is the one callee whose return type is known without an
        # annotation — `Gauge()` is a Gauge. Recorded separately from `defined`,
        # which mixes classes, functions and self-attributes.
        self.classes.add(node.name)
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

    # #2526: comprehension targets are bindings exactly as `for` targets are —
    # `[node.id for node in ast.walk(tree)]` binds `node` from `ast.walk`, so
    # provenance places it in stdlib territory. The live kill was this binding
    # form going unrecorded: `node` had no provenance at all, fell into no
    # category, and its builtin-method call was judged against the target
    # repo's symbols.

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._record_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._record_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._record_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._record_comprehension(node)

    def _record_comprehension(self, node) -> None:
        # Chained generators resolve through the same fixed point an ordinary
        # binding chain does: `for row in grid for x in row` records row←grid
        # and x←row, and whoever owns grid owns both.
        for gen in node.generators:
            self._record_binding([gen.target], gen.iter)
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # #2526: a lambda parameter's type is unknowable by construction — no
        # annotation syntax even exists for it. `key=lambda g: g.rank()` says
        # nothing about what `g` holds, so a method on it abstains.
        args = node.args
        collected = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        if args.vararg is not None:
            collected.append(args.vararg)
        if args.kwarg is not None:
            collected.append(args.kwarg)
        self.opaque |= {a.arg for a in collected}
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # #2526: `except ValueError as e` binds `e` from the exception class,
        # so provenance answers what it holds; a bare `except ... as e` binds a
        # value of no stated type at all, which is opaque.
        if node.name:
            if node.type is not None:
                self.assignments.append(
                    (frozenset({node.name}), _value_provenance(node.type))
                )
            else:
                self.opaque.add(node.name)
        self.generic_visit(node)

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
                    _CallSite(
                        receiver,
                        node.func.attr,
                        self._site(node),
                        _leftmost_name(node.func.value),
                    )
                )
        self.generic_visit(node)

    def _site(self, node: ast.AST) -> str:
        """The source line a call sits on, for the failure message."""
        index = getattr(node, "lineno", 0) - 1
        if 0 <= index < len(self._lines):
            return self._lines[index].strip()[:80]
        return ""


def _fence_facts_ast(block: str) -> _FenceFacts:
    """Facts from a parsed fence.

    Raises whatever ``ast.parse`` raises. #2392: a parse failure is not a value —
    the caller decides whether this fence claimed to be Python, and names the
    failure if it did. It never degrades to a guess.
    """
    tree = ast.parse(block)
    visitor = _FenceVisitor(block)
    visitor.visit(tree)
    return _FenceFacts(
        imported=frozenset(visitor.imported),
        defined=frozenset(visitor.defined),
        assignments=tuple(visitor.assignments),
        calls=tuple(visitor.calls),
        framework_params=frozenset(visitor.framework_params),
        returns=tuple(sorted(visitor.returns.items())),
        classes=frozenset(visitor.classes),
        opaque=frozenset(visitor.opaque),
    )


def _scan_fences(text: str) -> _ScanResult:
    """Read every code fence in ``text``, routed by its language tag (#2392).

    There is no fallback. A fence is parsed as Python, skipped because its tag
    says it is not Python, or named as a failure — never pattern-scraped into a
    confident guess.
    """
    facts: list[_FenceFacts] = []
    failures: list[_FenceParseFailure] = []
    skipped_by_tag = 0
    undeclared_unparsed = 0

    for match in _CODE_FENCE_RE.finditer(text):
        tag = (match.group(1) or "").lower()
        declares_python = tag in _PYTHON_FENCE_TAGS
        undeclared = tag in _UNDECLARED_FENCE_TAGS

        if not declares_python and not undeclared:
            # ```text, ```json, ```bash — the tag is the author telling us this
            # is not Python. Believe it.
            skipped_by_tag += 1
            continue

        block = _normalize_fence(match.group(2))
        try:
            facts.append(_fence_facts_ast(block))
        except (SyntaxError, ValueError, RecursionError) as e:
            if declares_python:
                failures.append(
                    _FenceParseFailure(
                        start_line=text.count("\n", 0, match.start()) + 1,
                        end_line=text.count("\n", 0, match.end()) + 1,
                        tag=tag,
                        error=f"{type(e).__name__}: {e}",
                    )
                )
            else:
                undeclared_unparsed += 1

    return _ScanResult(
        facts=facts,
        failures=failures,
        skipped_by_tag=skipped_by_tag,
        undeclared_unparsed=undeclared_unparsed,
    )


def _flag_calls(
    facts: list[_FenceFacts],
    symbol_set: set[str],
    first_party_tops: frozenset[str] = frozenset(),
) -> dict[str, list[str]]:
    """Judge every collected call against the target repo's symbol table.

    Facts are pooled across ALL fences before anything is judged: a spec
    routinely shows its imports in one snippet and the usage in another.

    Args:
        facts: Pooled per-fence facts from :func:`_scan_fences`.
        symbol_set: Identifier names gathered from the target repo.
        first_party_tops: Top-level package names the target repo itself owns
            (#2411). A chain rooted in one of these is the repo's to be right
            or wrong about; a chain rooted in any other imported name is not.
            Empty means "cannot tell", which deliberately treats every imported
            root as foreign — see the note on the foreign-root set below.
    """
    # #1948: three universes the target repo's symbol table has no authority
    # over — the phase-5 kill was this check rejecting Pillow's documented API
    # (ImageDraw.Draw, alpha_composite), pathlib, and a method the spec itself
    # defined. Same wrong-universe disease #1901 fixed for imports.
    # #2391 adds the fourth: parameters a framework injects. `parser` inside
    # `def pytest_addoption(parser)` is pytest's object, so `parser.addoption(`
    # is pytest's API to be right or wrong about — not the target repo's.
    exempt: set[str] = set(_STDLIB_MODULE_NAMES) - first_party_tops
    spec_defined: set[str] = set()
    framework_roots: set[str] = set()
    imported_roots: set[str] = set()
    for fence in facts:
        # #2411: `- first_party_tops` is the same discrimination the root test
        # below makes, applied one level up. The blanket import exemption was
        # written for #1948's third-party universes; it was never meant to
        # exempt the target repo's OWN package, and doing so blinded the check
        # to `import gauge; gauge.no_such_marker()` — a one-hop first-party
        # chain, which is the founding true positive of #1527 wearing an import.
        exempt |= fence.imported - first_party_tops
        exempt |= fence.framework_params
        framework_roots |= fence.framework_params
        imported_roots |= fence.imported
        spec_defined |= fence.defined

    # #2411: the fifth kill of this class, and the first that was not positional.
    # `@pytest.mark.parametrize(...)` flagged `parametrize` because ownership was
    # only ever rooted for framework-INJECTED PARAMETERS. `_receiver_key` returns
    # the last attribute by design, so a two-hop chain keys on `mark`, which is
    # exempt in nobody's book, while the root `pytest` sits in `exempt` as an
    # import and was never consulted. Any call rooted in an imported name and
    # reached through more than one hop fell through to the symbol test.
    #
    # It was never about decorators: measured 16 of 16 AST positions collecting
    # the call and 16 of 16 flagging it. One hop had always cleared because the
    # receiver IS the import (`pytest.raises`), and the obvious stdlib instance
    # `os.path.join` was masked only by `join` sitting in the allowlist.
    #
    # The line 1717 objection below stands and is why this is not simply
    # `call.root in exempt`: a chain rooted in the target repo's OWN package is
    # the one case where its symbol table has authority, so first-party roots
    # stay judged and `boostgauge.gauge.nonexistent()` remains a true positive.
    #
    # An empty `first_party_tops` means the caller could not tell us (the #1812
    # telemetry consumer has no repo root). That treats every imported root as
    # foreign, which fails OPEN — the direction this class's governing principle
    # has ruled correct four times: unresolved is not hallucinated.
    foreign_roots: set[str] = set(framework_roots)
    foreign_roots |= imported_roots - first_party_tops
    foreign_roots |= set(_STDLIB_MODULE_NAMES) - first_party_tops

    # Exemption propagates through bindings to a fixed point rather than the
    # single level the old regex managed: `self.root = tk.Tk()` exempts `root`,
    # and `frame = self.root.frame()` then exempts `frame`. Whoever owns the
    # root owns everything derived from it, so the target repo's symbols have
    # no authority anywhere down that chain. Terminates because `exempt` only
    # grows and the set of bound names is finite.
    assignments = [
        (bound, source) for fence in facts for bound, source in fence.assignments
    ]
    # #2399: a spec-defined function's DECLARED return type answers what a
    # binding from it holds. `def render(...) -> Image.Image` means
    # `img = render(...)` holds a Pillow object, so `img.getpixel(...)` is
    # Pillow's API to be right or wrong about — even though `render` itself is
    # the target repo's. Only declared annotations are read; nothing is inferred
    # from a body, and an unannotated function resolves to nothing.
    return_root: dict[str, str] = {}
    for fence in facts:
        for func_name, annotation_root in fence.returns:
            return_root[func_name] = annotation_root

    changed = True
    while changed:
        changed = False
        for bound, source in assignments:
            if bound <= exempt:
                continue
            if source & exempt:
                exempt |= bound
                changed = True
                continue
            # The value came from calling a spec-defined function that declares
            # it returns something the target repo does not own.
            if any(return_root.get(name) in exempt for name in source):
                exempt |= bound
                changed = True

    # #2399, the honest default. `unresolved is not hallucinated` is the
    # principle #2391 was titled for; this is its third shape. A binding whose
    # provenance the checker cannot place AT ALL — not an import, not stdlib,
    # not a framework injection, not a gathered symbol, not something the spec
    # defines — holds a value of unknown type, and a method on an unknown type
    # cannot be called absent from anything.
    #
    # Note what stays JUDGED. `gauge = GaugeWindow()` where `GaugeWindow` is a
    # gathered symbol resolves to the target repo, so `gauge.model_dump()` is
    # still #1527's founding true positive. So does `g = Gauge()` for a class
    # the spec itself defines. The rule removes guesses, not jurisdiction.
    # What "resolvable" means for a binding from a call. The target repo owning
    # the CALLEE is not the test — it owns `render`, and `render` returns a
    # Pillow image. What resolves a binding is knowing the TYPE it holds:
    #
    #   * a constructor: `Gauge()` is a Gauge, no annotation needed;
    #   * a declared return: `def render(...) -> Image.Image`, handled above.
    #
    # Classes the spec defines are known exactly. For the gathered surface the
    # symbols are bare strings carrying no kind, so class-hood is read from the
    # PEP 8 CapWords convention — which holds across the whole of the live run's
    # 21 (`AppConfig`, `SessionState`, `WindowsCollector` against `load_config`,
    # `start`, `stop`). A lowercase class would be missed and its instances left
    # unresolved, which fails OPEN — the direction this issue's own title rules
    # correct, since unresolved is not hallucinated.
    spec_classes: set[str] = set()
    for fence in facts:
        spec_classes |= fence.classes
    constructor_like = spec_classes | {s for s in symbol_set if s[:1].isupper()}

    unresolved: set[str] = set()
    # #2526: names bound in type-unknowable forms (lambda parameters, bare
    # `except ... as e`) are unresolved by construction — no fixed point can
    # place them, so they seed the set directly rather than falling through
    # to judgment as if the checker knew what they hold.
    for fence in facts:
        unresolved |= fence.opaque - exempt
    changed = True
    while changed:
        changed = False
        for bound, source in assignments:
            if bound <= unresolved or bound <= exempt or not source:
                continue
            # Resolved, so judged: a constructor names its own type, and a
            # declared return names some type. WHICH type decides the verdict,
            # and the exemption loop above already applied it — an annotation
            # rooted in an import exempts the binding, one rooted in a gathered
            # symbol leaves it in jurisdiction. Either way it is not a guess.
            if source & constructor_like or any(n in return_root for n in source):
                continue
            if not (source & exempt) or source <= unresolved:
                unresolved |= bound
                changed = True

    flagged: dict[str, list[str]] = {}  # method_name -> list of call sites
    for fence in facts:
        for call in fence.calls:
            if call.receiver in exempt:
                continue
            # #2396: ownership travels with the ROOT of the receiver chain, not
            # its last attribute. `_receiver_key` returns the last attribute by
            # design — `self.root.attributes(...)` must key on `root`, which is
            # what `self.root = tk.Tk()` exempts (#1952) — but that same rule
            # loses a framework exemption at the first hop:
            # `request.config.getoption(...)` keys on `config` while the
            # exemption holds `request`. pytest owns `request.config` exactly as
            # it owns `request`, and it owns everything further down that chain.
            #
            # Deliberately NOT the full `exempt` set. Rooting the test in
            # `exempt` would also clear `boostgauge.gauge.nonexistent()`
            # whenever the target repo's own package is imported in a fence — a
            # real false-clearance surface, since a first-party import is the
            # one case where the target repo's symbol table DOES have authority.
            #
            # #2411 widened this from framework parameters to every FOREIGN
            # root: framework injections, plus imported names the target repo
            # does not own, plus stdlib. First-party roots are excluded from the
            # set above, so the false-clearance surface this comment names stays
            # closed while `pytest.mark.parametrize` clears.
            if call.root is not None and call.root in foreign_roots:
                continue
            # #2399: the receiver holds a value of unknown type. Unresolved is a
            # distinct, honest category from wrong, and only wrong is a finding.
            if call.receiver in unresolved or (
                call.root is not None and call.root in unresolved
            ):
                continue
            if call.method in symbol_set or call.method in spec_defined:
                continue
            # #2526: a method every Python object of a builtin type carries is
            # never a hallucinated PROJECT API, whoever the receiver is.
            # `str.isupper` on an AST walk killed a run that had passed the
            # visual gate because the hand-curated allowlist held `upper` but
            # not `isupper` — so the builtin surface is now derived, not typed.
            if (
                call.method in _API_SYMBOL_ALLOWLIST
                or call.method in _BUILTIN_TYPE_METHODS
            ):
                continue
            flagged.setdefault(call.method, []).append(call.site)
    return flagged


def detect_unknown_method_calls(
    text: str,
    symbol_set: set[str],
    repo_root_str: str = "",
) -> dict[str, list[str]]:
    """Scan code fences in ``text`` for method calls absent from ``symbol_set``.

    The detection core shared by :func:`check_api_symbols_exist` (which
    gates the spec) and the hallucination telemetry (#1812, which records
    the same signal for both the spec draft and the LLD, record-only).
    Extracted so both consumers measure with the identical yardstick.

    Args:
        text: Markdown to scan. Only content inside ``` fences is examined.
        symbol_set: Real symbol names extracted from the target repo.
        repo_root_str: Target repo root, used to tell the repo's own packages
            from foreign ones (#2411). Optional because the telemetry consumer
            has no repo root; omitting it treats every imported root as foreign,
            which fails open rather than manufacturing findings.

    Returns:
        Mapping of unknown method name -> truncated example call sites.
        Empty when every call resolves to a known or allowlisted symbol.
    """
    return _flag_calls(
        _scan_fences(text).facts, symbol_set, _first_party_tops_for(repo_root_str)
    )


def _first_party_tops_for(repo_root_str: str) -> frozenset[str]:
    """First-party package names for a repo root string, empty when unknown.

    Never raises: a symbol check must not fail because a path was unreadable,
    and an empty answer is the fail-open direction (#2411).
    """
    if not repo_root_str:
        return frozenset()
    try:
        return frozenset(_first_party_tops(Path(repo_root_str)))
    except OSError:
        return frozenset()


def check_api_symbols_exist(
    spec: str,
    gathered_symbols: list[str],
    repo_root_str: str = "",
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
        repo_root_str: Target repo root. Used to tell the repo's own top-level
            packages from foreign ones, so a chain rooted in an import the repo
            does not own is not judged against the repo's symbols (#2411).

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
    scan = _scan_fences(spec)

    # #2392: a fence that CLAIMED to be Python and would not parse is a
    # first-class defect in an implementation spec, and it is reported before
    # anything else. It used to be scraped with regex and mentioned in a
    # footnote, which fed this very check a confident, wrong call list.
    #
    # #2556: it reports under its OWN name. When this precondition failure
    # shared check_name with the symbol check, the run-issue331-092913 cap
    # halt sent the operator cross-checking api_symbols_exist against
    # per-iteration hallucination-check artifacts that all said passed —
    # the artifacts belong to the symbol half, which never ran.
    #
    # #2555: the "lines N-M" citation is load-bearing beyond legibility —
    # it is the address revision pinning reads (named_line_ranges), so the
    # span this failure demands a change in is named content a revision may
    # edit. The advice clause deliberately writes its tag examples WITHOUT
    # backticks: "(```text, ```json, ```bash)" fed named_tokens the garbage
    # spans between the fence runs ("text,", "json,"), which defeated
    # pinning's names-nothing-extractable abstention while naming zero
    # draft lines — the exact deadlock that produced four byte-identical
    # drafts on run-issue331-092913.
    if scan.failures:
        listed = "; ".join(
            f"lines {f.start_line}-{f.end_line} (```{f.tag}) — {f.error}"
            for f in scan.failures[:5]
        )
        suffix = (
            f" (and {len(scan.failures) - 5} more)"
            if len(scan.failures) > 5
            else ""
        )
        return CompletenessCheck(
            check_name="python_fences_parse",
            passed=False,
            details=(
                f"{len(scan.failures)} code fence(s) tagged as Python do not "
                f"parse as Python: {listed}{suffix}. Fix the snippet, or "
                f"retag the fence with the language it actually contains "
                f"(text, json, bash) if it was never meant to be Python."
            ),
        )

    flagged = _flag_calls(
        scan.facts, symbol_set, _first_party_tops_for(repo_root_str)
    )

    # #1870's honesty rule applied to the scan itself: say what was NOT read,
    # so "checked" never overstates what was verified.
    notes: list[str] = []
    if scan.skipped_by_tag:
        notes.append(
            f"{scan.skipped_by_tag} fence(s) skipped by language tag "
            f"(not Python)"
        )
    if scan.undeclared_unparsed:
        notes.append(
            f"{scan.undeclared_unparsed} untagged/diff fence(s) did not parse "
            f"and were not read (no Python was claimed, so this is not a "
            f"failure)"
        )
    scan_note = f" {'; '.join(notes)}." if notes else ""

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


#: Every method of every Python builtin type, derived by introspection (#2526).
#: The hand-curated list above held `upper` but not `isupper`, and the gap
#: killed run-issue331-083839 at the completeness cap on correct, idiomatic
#: code (`node.id.isupper()` in an AST walk). A typed list lags the language
#: forever; `dir()` cannot. The curated list stays for the stdlib idioms and
#: third-party conventions that are not builtin-type methods.
_BUILTIN_TYPE_METHODS: frozenset[str] = frozenset(
    name
    for builtin_type in (
        object, type, str, bytes, bytearray, memoryview, list, tuple,
        dict, set, frozenset, int, float, complex, bool, range, slice,
        BaseException, BaseExceptionGroup,
    )
    for name in dir(builtin_type)
)


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


def _resolves_on_base(
    module_path: str, repo_root: Path, base_ref_name: str
) -> bool:
    """Mirror of `_import_resolves` against the run's base ref (#2667).

    Same candidate set (module and package forms, parent-forgiveness for the
    attribute-import shape), same source-root prefixes — probed with
    `git cat-file -e` instead of the filesystem, because the checkout is the
    default branch and mid-arc the base carries files the checkout does not.
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
    prefixes = _SOURCE_ROOT_PREFIXES + _discover_pyproject_source_roots(repo_root)
    for candidate in candidates:
        for prefix in prefixes:
            rel = (Path(prefix) / candidate) if prefix else candidate
            if exists_on_base(repo_root, base_ref_name, rel.as_posix()):
                return True
    return False


# Common stdlib top-level module names (subset for fast rejection)
def _pyproject_declared_package(repo_root: Path) -> set[str]:
    """Package names the repo DECLARES it ships (#2412).

    The authoritative signal, and the one that needs no filesystem heuristic:
    `[tool.poetry.packages].include`, `[project].name` and `[tool.poetry].name`
    all name the package the repo is. A distribution name uses dashes where the
    import name uses underscores, so both spellings are returned.
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return set()
    try:
        import tomllib

        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return set()

    names: set[str] = set()

    def _add(value: object) -> None:
        if isinstance(value, str) and value:
            names.add(value)
            names.add(value.replace("-", "_"))

    tool = data.get("tool", {}) if isinstance(data.get("tool"), dict) else {}
    poetry = tool.get("poetry", {}) if isinstance(tool.get("poetry"), dict) else {}
    _add(poetry.get("name"))
    project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
    _add(project.get("name"))

    packages = poetry.get("packages", [])
    if isinstance(packages, list):
        for pkg in packages:
            if isinstance(pkg, dict):
                _add(pkg.get("include"))
    return names


def _first_party_tops(repo_root: Path) -> set[str]:
    """Top-level package names that belong to the target repo itself (#1901).

    A dotted import whose top level is one of these gets the strict
    exists-or-created-by-this-spec rule (#842); anything else is
    third-party and validates against the target environment instead.
    Covers flat layout (pkg at repo root) and src layout.

    #2412: recognising a package ONLY by `__init__.py` made a mid-build repo
    blind to itself. Measured on boostgauge 2026-08-15: `src/boostgauge/`
    existed, `src/boostgauge/__init__.py` did not, and this returned the empty
    set -- so `boostgauge.gauge.nonexistent()` cleared instead of flagging,
    which is the #1527 founding true positive. Greenfield repos are the
    population this campaign runs against, so "no `__init__.py` yet" is the
    normal early state rather than an anomaly.

    Widening is not free in the other direction: a first-party top gets the
    STRICTER exists-or-created-by-this-spec rule, and over-strictness is what
    killed five rolls of the receiver-resolution class. So each signal is
    narrow on its own terms rather than "any directory with a .py in it":

      1. `__init__.py` present -- the original, unchanged;
      2. the name the repo DECLARES in pyproject.toml -- authoritative, no
         heuristic;
      3. a directory under `src/` -- in a src layout its children ARE the
         packages by definition, which is not true of the repo root, where
         `tests/`, `scripts/` and `docs/` all sit beside the package.

    Signal 3 is deliberately not applied at the repo root. A flat-layout
    mid-build repo is covered by signal 2 instead.
    """
    tops: set[str] = set()
    for base in (repo_root, repo_root / "src"):
        try:
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if not child.is_dir():
                    continue
                if (child / "__init__.py").is_file():
                    tops.add(child.name)
                elif base.name == "src" and any(child.glob("*.py")):
                    tops.add(child.name)
        except OSError:
            continue

    try:
        tops |= _pyproject_declared_package(repo_root)
    except OSError:
        pass
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


def review_is_engaged(state: ImplementationSpecState) -> bool:
    """Is the adversarial reviewer going to judge this draft? (#2540)

    True for this graph, and that is a fact about its routing rather than an
    assumption: `route_after_validation` sends a passing draft to N5 directly,
    or to N4's human gate, which routes onward to N5 when the human approves.
    `test_check_classification.py::TestReviewIsReallyEngaged` reads both
    routers and pins those paths, so this cannot quietly become a lie.

    The one exit that reaches no reviewer is the human REJECTING the draft at
    N4, which ends the run. A demoted proxy goes unjudged there and nothing
    ships either, so the demotion costs nothing on that path.

    A state may say `review_engaged: False` explicitly, for a future graph that
    runs these checks WITHOUT a reviewer. There, proxies re-arm and gate again,
    because the demotion's whole justification is that a better judge is about
    to look at the same dimension. Absent that judge, a weak check is better
    than none.
    """
    declared = state.get("review_engaged")
    if declared is None:
        return True
    return bool(declared)


def _demote_proxies(
    check: CompletenessCheck, review_engaged: bool
) -> CompletenessCheck:
    """A failed proxy-heuristic reports instead of blocking (#2540).

    Only a FAILED check is touched, and only a declared proxy. A passing check
    is returned unchanged so the pass/na accounting downstream is unaffected,
    and an unclassified check keeps its authority -- the exhaustiveness lint,
    not a silent demotion, is what catches a check nobody classified.
    """
    if check["passed"] or not review_engaged:
        return check
    if not is_proxy(check["check_name"]):
        return check
    print(f"    [ADVISORY] {check['details']}")
    return CompletenessCheck(
        check_name=check["check_name"],
        passed=True,
        details=advisory_details(check["details"]),
    )


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