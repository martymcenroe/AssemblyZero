"""N2: Generate Implementation Spec node for Implementation Spec Workflow.

Issue #304: Implementation Readiness Review Workflow (LLD -> Implementation Spec)

Uses the configured drafter LLM (Gemini in agy by default, per the 2026-09-24 law, ADR 0234) to generate an Implementation Spec
from the approved LLD, codebase analysis results (current state snapshots
and pattern references), and the Implementation Spec template.

Supports revision mode when N3 (validate_completeness) or N5 (review_spec)
routes back with feedback. Revision prompts include cumulative feedback
history to prevent regression.

This node populates:
- spec_draft: Generated Implementation Spec markdown
- spec_path: Path where the draft was saved in the audit trail
- review_iteration: Incremented on revision cycles
- error_message: "" on success, error text on failure

#3585 (ADR 0236): every failure returns an ``error_message`` naming the node
and the issue, which ``route_after_generate_spec`` sends to HALT. A template
that cannot be loaded, a lineage directory that is missing, a verdict the
pinning gate cannot read and a prompt whose required parts exceed the budget
all halt before the drafter is called. An empty draft and a draft that cannot
be saved halt after it. None of them is passed on as a smaller result.
"""

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost, get_provider
from assemblyzero.utils.cost_tracker import accumulate_node_cost, accumulate_node_tokens
from assemblyzero.core.section_utils import (
    build_targeted_prompt,
    extract_sections,
    identify_changed_sections,
)
from assemblyzero.workflows.requirements.audit import (
    get_repo_structure,
    load_template,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.implementation_spec.state import (
    ImplementationSpecState,
    PatternRef,
)
from assemblyzero.workflows.implementation_spec.nodes.edit_script import (
    EDIT_SCRIPT_SYSTEM_PROMPT,
    apply_edit_blocks,
    build_edit_script_prompt,
    parse_edit_blocks,
    unchanged_ratio,
)
from assemblyzero.workflows.implementation_spec.nodes.retry_prompt_builder import (
    RetryContext,
    build_retry_prompt,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    PinningMergeError,
)

logger = logging.getLogger(__name__)


def _spec_injection():
    """The spec-side table injector, imported lazily (#2611).

    NOT a module-level import. `requirements.table_injection` imports
    `implementation_spec.assertion_manifest` for `is_criteria_table`, which
    pulls in this package's `__init__` -> `graph` -> `nodes/__init__` -> this
    module. A module-level import back into `requirements.table_injection`
    therefore re-enters it while it is still initialising and dies with a
    partially-initialised module.

    Do not "tidy" this into a top-level import: the cycle is real, and it is
    invisible to any test that imports the two modules directly -- it appears
    only on entry paths that start in the requirements workflow.
    `test_spec_table_injection.py::TestNoImportCycle` pins both halves.
    """
    from assemblyzero.workflows.implementation_spec import table_injection

    return table_injection

# =============================================================================
# Constants
# =============================================================================

# Template path relative to assemblyzero_root
SPEC_TEMPLATE_PATH = Path("docs/standards/0701-implementation-spec-template.md")

# Maximum characters for pattern reference excerpts in the prompt
MAX_PATTERN_EXCERPT_CHARS = 3_000

# Maximum characters for a single file snapshot in the prompt
MAX_SNAPSHOT_CHARS = 10_000

# Maximum total prompt content chars (to avoid token limits)
MAX_TOTAL_PROMPT_CHARS = 120_000

#: #2569: total edit-script attempts per revision round — the initial call
#: plus re-prompts carrying the exact apply failure. Three covers the
#: observed failure classes: a transport failure (retried on the same
#: prompt) plus one drafter correction. Counted basis: 192 applied vs 16
#: fallbacks across every boostgauge run log, seven of the sixteen the
#: SEARCH-not-found class a single correction recovers.
EDIT_SCRIPT_MAX_ATTEMPTS = 3


class PromptBudgetError(ValueError):
    """The prompt's required parts alone exceed MAX_TOTAL_PROMPT_CHARS (#3585).

    The required parts are the instructions, the LLD, the binding manifest,
    the draft under revision and the round's complaints. The prompt used to be
    cut off mid-content, so the drafter was sent a partial LLD or draft.
    """


class PinningCannotRunError(RuntimeError):
    """The round's verdict names nothing the pinning gate can read (#3585).

    Pinning used to abstain and pass the revision unenforced, which is a gate
    that could not run being read as one that passed.
    """


def _halt(issue_number: Any, reason: str) -> dict[str, Any]:
    """The node's failure result for #3585's halts: loud on stderr, routed to
    HALT by route_after_generate_spec, which alerts."""
    message = f"[N2] generate_spec for issue #{issue_number}: {reason}"
    print(f"ERROR {message}", file=sys.stderr, flush=True)
    return {"error_message": message}


def _pinning_names(
    review_feedback: str, completeness_issues: list[str]
) -> tuple[set[str], tuple[tuple[int, int], ...]]:
    """What this round's verdict and complaints name, as pinning reads them."""
    from assemblyzero.workflows.implementation_spec.revision_pinning import (
        named_line_ranges,
        named_tokens,
    )

    return (
        named_tokens(review_feedback, completeness_issues),
        named_line_ranges(completeness_issues),
    )


#: Why pinning cannot run, for the halt and the raise alike.
_PINNING_UNREADABLE = (
    "the round's verdict and completeness failures name nothing the pinning "
    "gate can read (no backticked span, quoted phrase, test name, manifest "
    "row id, Section reference or line range), so the revision cannot be "
    "held to the content they name (#2532). It used to be passed unenforced"
)


def _spec_edit_halt(reason: str) -> str:
    """Halt message for a revision that could not be applied as edits (#2569).

    Legible on its own in a halt banner (#2197): it names the contract,
    what broke it, and the fact that nothing was lost. Mirrors the lld
    stage's #2200 wording — the two stages carry the same law.
    """
    return (
        f"[EDIT-SCRIPT] spec revision rejected after "
        f"{EDIT_SCRIPT_MAX_ATTEMPTS} attempt(s): {reason}. The prior draft "
        f"is unchanged and remains the working copy. A revision is applied "
        f"as SEARCH/REPLACE edit blocks and is never redrawn wholesale "
        f"(#2569) — the full-regeneration fallback was the vector for every "
        f"mangled draft on the record. Relaunch to resume from this stage."
    )


# =============================================================================
# System Prompt
# =============================================================================

DRAFTER_SYSTEM_PROMPT = """\
You are a technical architect creating an Implementation Specification.

An Implementation Spec bridges the gap between a Low-Level Design (LLD) and \
autonomous code implementation. It must contain enough concrete detail for an \
AI agent to implement the changes with >80% first-try success rate.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the document title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Output ONLY the raw markdown content
- First line MUST be the title starting with #

QUALITY REQUIREMENTS:
- Every "Modify" file MUST include a current state excerpt showing the code \
that will be changed
- Every data structure MUST have at least one concrete JSON/YAML example \
with realistic values (not just TypedDict definitions)
- Every function signature MUST have input/output examples with actual values
- Change instructions MUST be specific enough to generate diffs \
(line-level guidance, before/after snippets)
- Pattern references MUST include file:line locations pointing to real code
- Test code MUST be platform-independent: never assert on hardcoded path \
separators. Compare pathlib.Path objects (path == Path.home() / ".app" / \
"cfg.json"), never separator-laden strings — monkeypatching sys.platform \
does NOT change pathlib's flavour, so on Windows str(path) renders with \
backslashes and endswith("dir/file.json") can never pass (Issue #1841)
- Every assertion in test code MUST trace to behavior this spec's own \
requirements/behavior sections specify. NEVER assert side effects the \
behavior sections do not name — e.g., if CLI flags are specified as \
runtime precedence over the config file, do NOT assert that a CLI \
override is persisted back to disk. An assertion without a specified \
behavior behind it makes the spec self-contradictory and unwinnable \
(Issue #1860)
- If the spec creates or regenerates visual-regression baseline images, \
it MUST also specify property assertions computable WITHOUT any baseline \
(e.g. the needle tip lies at the expected angle for a given value — a few \
lines of trigonometry) in a section explicitly marked \
"baseline-independent". Baselines generated by the same run they test \
validate their own defects: an inverted needle produces an inverted \
baseline and passes forever (Issue #1902)

STRUCTURE:
Follow the provided template exactly. Include ALL sections. \
Do not skip or abbreviate any section."""


# =============================================================================
# Helpers
# =============================================================================


def _drafter_system_prompt(lld_content: str) -> str:
    """The drafter's system prompt, plus the machine-owned notice when one
    applies (#2611).

    Telling the drafter is not decoration. The derivation injects the LLD's
    decision table after the call returns; a drafter that restates it anyway
    produces a second, lossy copy of rows the document already holds
    correctly, and the reader cannot tell which is binding. The mirror of
    #2607's notice on the lld side, and the same reasoning.
    """
    spec_injection = _spec_injection()
    if not spec_injection.build_injection(lld_content or ""):
        return DRAFTER_SYSTEM_PROMPT
    return DRAFTER_SYSTEM_PROMPT + f"""

DO NOT RESTATE THE LLD'S DECISION TABLE (#2611):
- The LLD's decision table is carried into this spec VERBATIM by the
  derivation itself, in a machine-owned block beginning
  `{spec_injection.BEGIN_MARKER}`. You are not writing those rows and must
  not reproduce, paraphrase, summarise or "carry forward" their values
  anywhere.
- Write AROUND that block. In the test mapping, CITE the row IDs
  (S1, S2, ...) and the manifest row ids, and state what each test DOES; do
  not restate the binding values, thresholds, colours or sampling windows the
  rows already carry. The row is the ruling; your assertion points at it.
- Anything you write inside the machine-owned markers is discarded."""


def _normalize_failure_text(text: str) -> str:
    """Lexically normalize a completeness-failure message for clustering.

    Collapses whitespace runs to a single space, strips leading/trailing
    whitespace, lowercases, and trims trailing punctuation. Used by
    `_build_revision_prompt` to detect recurring failures across iterations
    even when the surface text differs by trivial lexical variation.
    Closes #1479.
    """
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[.,;:!?]+$", "", t)
    return t


# =============================================================================
# Main Node
# =============================================================================


def generate_spec(state: ImplementationSpecState) -> dict[str, Any]:
    """N2: Generate Implementation Spec draft using Claude.

    Issue #304: Implementation Readiness Review Workflow

    Steps:
    1. Determine if this is an initial draft or revision
    2. Load Implementation Spec template from assemblyzero_root
    3. Build prompt with LLD content, codebase snapshots, and patterns
    4. Call configured drafter LLM
    5. Strip any preamble from response
    6. Save draft to audit trail
    7. Return state updates

    Args:
        state: Current workflow state. Requires:
            - lld_content: Raw LLD markdown (from N0)
            - current_state_snapshots: File excerpts (from N1)
            - pattern_references: Similar patterns (from N1)
            - assemblyzero_root: Path to AssemblyZero installation
            - repo_root: Target repository root path

    Returns:
        Dict with state field updates:
        - spec_draft: Generated Implementation Spec markdown
        - spec_path: Path where the draft was saved
        - review_iteration: Updated iteration count
        - error_message: "" on success, error text on failure
    """
    # Extract state
    assemblyzero_root = Path(state.get("assemblyzero_root", ""))
    repo_root = state.get("repo_root", "")
    mock_mode = state.get("config_mock_mode", False)
    issue_number = state.get("issue_number", 0)

    # Determine revision state
    review_iteration = state.get("review_iteration", 0)
    existing_draft = state.get("spec_draft", "")
    review_feedback = state.get("review_feedback", "")
    completeness_issues = state.get("completeness_issues", [])
    validation_passed = state.get("validation_passed", False)

    is_revision = bool(
        existing_draft and (review_feedback or completeness_issues)
    )

    # Issue #525: Resume from persisted draft if available (skip expensive LLM call)
    if not is_revision and not existing_draft:
        audit_dir_str = state.get("audit_dir", "")
        if audit_dir_str:
            audit_dir = Path(audit_dir_str)
            if audit_dir.exists():
                # Find most recent spec-draft in lineage
                drafts = sorted(audit_dir.glob("*-spec-draft.md"), reverse=True)
                if drafts:
                    recovered = drafts[0].read_text(encoding="utf-8")
                    if recovered.strip():
                        lines = len(recovered.splitlines())
                        print(f"\n[N2] Recovered existing draft from {drafts[0].name} ({lines} lines) — skipping LLM call")
                        return {
                            "spec_draft": recovered,
                            # #2297: a DRAFT path, so it goes in the draft
                            # field. `spec_path` means "the finalized spec"
                            # (state.py) and only finalize_spec may set it.
                            "spec_draft_path": str(drafts[0]),
                            "review_iteration": review_iteration,
                            "completeness_issues": [],
                            "error_message": "",
                        }

    # #2536: a seeded draft with NO outstanding feedback is one the prior
    # grant generated but never got reviewed (run-issue331-150920: the guard
    # refused its final draft, so the run died with paid work unjudged). Its
    # last verdict's items are already IN it — that verdict fed the revision
    # that produced it — so redrawing here would overwrite paid work with an
    # unreviewed re-roll. Pass it through untouched: the grant's first spend
    # is the review the draft never got, at this grant's iteration counter.
    if not is_revision and existing_draft:
        lines = len(existing_draft.splitlines())
        print(
            f"\n[N2] Seeded draft ({lines} lines) was never reviewed — "
            f"passing it to review untouched (#2536)"
        )
        return {
            "spec_draft": existing_draft,
            "review_iteration": review_iteration,
            "completeness_issues": [],
            "error_message": "",
        }

    if is_revision:
        review_iteration += 1
        print(
            f"\n[N2] Generating Implementation Spec revision "
            f"(iteration {review_iteration})..."
        )
    else:
        print("\n[N2] Generating initial Implementation Spec draft...")

    # -------------------------------------------------------------------------
    # Load template
    # -------------------------------------------------------------------------
    try:
        template = load_template(SPEC_TEMPLATE_PATH, assemblyzero_root)
    except (OSError, UnicodeDecodeError) as e:
        # #3585: the message names the node, the issue and the template, where
        # it used to be the bare exception text.
        message = (
            f"[N2] generate_spec for issue #{issue_number}: cannot load the spec "
            f"template {SPEC_TEMPLATE_PATH} from {assemblyzero_root}: "
            f"{type(e).__name__}: {e}"
        )
        print(f"ERROR {message}", file=sys.stderr, flush=True)
        return {"error_message": message}

    # -------------------------------------------------------------------------
    # #3585: the lineage directory the draft is saved to. A missing one used
    # to skip the save without a word, after the drafter had been paid.
    # -------------------------------------------------------------------------
    audit_dir_str = state.get("audit_dir", "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    if audit_dir is None or not audit_dir.is_dir():
        return _halt(
            issue_number,
            f"the audit directory {audit_dir_str or '(none in state)'} does not "
            f"exist, so the draft cannot be saved to lineage (#2250)",
        )

    # -------------------------------------------------------------------------
    # #3585: a revision is pinned to what its verdict names (#2532). A verdict
    # pinning cannot read halts here, before the drafter is paid; pinning used
    # to abstain and pass the revision unenforced.
    # -------------------------------------------------------------------------
    if is_revision:
        tokens, ranges = _pinning_names(review_feedback, completeness_issues)
        if not tokens and not ranges:
            return _halt(issue_number, _PINNING_UNREADABLE)

    # -------------------------------------------------------------------------
    # Build prompt
    # Issue #642: Use build_retry_prompt() with tiered context pruning when
    # retry_count >= 1 in workflow state.
    # -------------------------------------------------------------------------
    retry_count = state.get("retry_count", 0)

    if retry_count >= 1:
        # Build retry prompt with tiered context pruning (#642)
        retry_ctx = RetryContext(
            lld_content=state.get("lld_content", ""),
            target_file=state.get("target_file", ""),
            error_message=state.get("error_message", ""),
            retry_count=retry_count,
            previous_attempt_snippet=state.get("previous_attempt_snippet", None),
            completed_files=state.get("completed_files", []),
        )
        pruned = build_retry_prompt(retry_ctx)
        prompt = pruned["prompt_text"]
        logger.info(
            "Retry prompt built: tier=%d, tokens=%d, file=%s",
            pruned["tier"],
            pruned["estimated_tokens"],
            state.get("target_file", ""),
        )
    else:
        try:
            prompt = build_drafter_prompt(
                lld_content=state.get("lld_content", ""),
                current_state=state.get("current_state_snapshots", {}),
                patterns=state.get("pattern_references", []),
                template=template,
                issue_number=issue_number,
                existing_draft=existing_draft if is_revision else "",
                review_feedback=review_feedback if is_revision else "",
                completeness_issues=completeness_issues if is_revision else [],
                repo_root=repo_root,
                files_to_modify=state.get("files_to_modify", []),
                project_context=state.get("project_context", ""),
                import_dependencies=state.get("import_dependencies", ""),
                repo_structure=state.get("repo_structure", ""),
                prior_completeness_breakdown=(
                    state.get("prior_completeness_breakdown", []) if is_revision else []
                ),
                assertion_manifest=state.get("assertion_manifest", ""),
            )
        except PromptBudgetError as e:
            return _halt(issue_number, f"the prompt is over budget: {e}")

    # -------------------------------------------------------------------------
    # Issue #486: Pre-flight check — verify Gemini available before expensive Claude call
    # -------------------------------------------------------------------------
    # #3506: only when some node of this run is Gemini, and then the agy
    # transport itself, not the credential file.
    # #3563: the drafter is the run profile's `spec.draft` seat (`mock:draft`
    # under the mock profile); the preflight also sees the `spec.review` seat.
    from assemblyzero.core.seats import resolve

    # A seat that will not resolve and a drafter that cannot be built share
    # the node's one "Invalid drafter" halt site. #3585: the seats, the
    # preflight and the provider sit in one try, so a seat error halts there
    # directly; it used to be held in a variable and raised again below.
    try:
        # #3577: the reviewer first, so the drafter is the last seat resolved
        # before its provider is built and the call record names it.
        reviewer_spec = resolve(state, "spec.review").spec
        drafter_seat = resolve(state, "spec.draft")
        drafter_spec = drafter_seat.spec

        if not mock_mode:
            from assemblyzero.core.preflight import preflight_for_specs
            preflight = preflight_for_specs(drafter_spec, reviewer_spec)
            if preflight is None:
                print("    [PREFLIGHT] no Gemini node in this run; transport check skipped")
            elif not preflight.passed:
                warnings_str = ", ".join(preflight.warnings)
                return {
                    # The head is the registered gate's (spec.preflight).
                    "error_message": f"[PREFLIGHT] Gemini unavailable: {warnings_str}",
                    "previous_review_feedback": review_feedback,
                }
            else:
                print("    [PREFLIGHT] Gemini transport: agy answered")

        # ---------------------------------------------------------------------
        # Get drafter provider
        # ---------------------------------------------------------------------
        drafter = get_provider(drafter_spec, effort=drafter_seat.effort)
    except ValueError as e:
        print(f"    ERROR: Invalid drafter: {e}")
        return {"error_message": f"Invalid drafter: {e}"}

    print(f"    Drafter: {drafter_spec}")

    # -------------------------------------------------------------------------
    # #1528: Edit-script revision — the model emits SEARCH/REPLACE blocks
    # which are applied mechanically, so unflagged content cannot drift
    # (measured regenerations oscillated 1,149→341→1,407 lines; see #1529).
    #
    # #2569: the full-revision FALLBACK is retired. Counted across every
    # boostgauge run log: 192 applied edit-scripts vs 16 fallbacks, and
    # every text disaster (the 458→1296 chimera, the eliding rewrite that
    # deleted 18 tests) traveled through the wide channel the fallback
    # opened, while the edit path only ever failed loudly. A failed script
    # now RE-PROMPTS with its exact failure — the drafter can disambiguate
    # a SEARCH far more reliably than enforcement can un-mangle a rewrite —
    # and on exhaustion the stage halts naming the unappliable blocks,
    # mirroring the lld stage's #2200 contract. The classic path below
    # remains for the initial draft and for mock drafters only.
    #
    # The old `retry_count < 1` gate is dropped: nothing in this workflow
    # ever sets retry_count (verified by grep — it is only ever read), so
    # the gate was dead; a revision is a revision.
    # -------------------------------------------------------------------------
    edit_script_content: str | None = None
    result = None
    #: #2532: pinning refusals, regression-class flags, and unlock grants
    #: from this revision, accumulated across whichever path produced it.
    pinning_events: list[str] = []
    node_cost_usd = 0.0
    if is_revision and not drafter_spec.startswith("mock:"):
        halt_reason = ""
        failure_context = ""
        for attempt in range(1, EDIT_SCRIPT_MAX_ATTEMPTS + 1):
            cost_before = get_cumulative_cost()
            edit_result = drafter.invoke(
                system_prompt=EDIT_SCRIPT_SYSTEM_PROMPT,
                content=build_edit_script_prompt(
                    existing_draft=existing_draft,
                    review_feedback=review_feedback,
                    completeness_issues=completeness_issues,
                    prior_completeness_breakdown=state.get(
                        "prior_completeness_breakdown", []
                    ),
                    apply_failure=failure_context,
                ),
                timeout_seconds=1800,
            )
            node_cost_usd += get_cumulative_cost() - cost_before
            if not edit_result.success:
                # A transport failure is the provider's, not the drafter's:
                # the same prompt goes again (failure_context unchanged).
                halt_reason = (
                    f"drafter call failed: {edit_result.error_message}"
                )
                print(
                    f"    [EDIT-SCRIPT] attempt {attempt}/"
                    f"{EDIT_SCRIPT_MAX_ATTEMPTS} failed ({halt_reason})"
                    + (" -- retrying" if attempt < EDIT_SCRIPT_MAX_ATTEMPTS
                       else "")
                )
                continue
            blocks = parse_edit_blocks(edit_result.response or "")
            if not blocks:
                halt_reason = (
                    "no well-formed SEARCH/REPLACE blocks in the response"
                )
                failure_context = (
                    "Your previous response contained no well-formed "
                    "SEARCH/REPLACE blocks. Emit ONLY edit blocks in the "
                    "exact format specified — no prose, no rewritten "
                    "document."
                )
                print(
                    f"    [EDIT-SCRIPT] attempt {attempt}/"
                    f"{EDIT_SCRIPT_MAX_ATTEMPTS}: {halt_reason} -- "
                    f"re-prompting with the failure"
                )
                continue
            patched, failures = apply_edit_blocks(existing_draft, blocks)
            if failures:
                halt_reason = "; ".join(failures)
                failure_context = (
                    f"Your previous edit blocks did not apply: "
                    f"{halt_reason}. Copy each SEARCH character-for-"
                    f"character from the CURRENT SPEC below. If a SEARCH "
                    f"matched more than once, extend it with surrounding "
                    f"lines until it is unique."
                )
                print(
                    f"    [EDIT-SCRIPT] attempt {attempt}/"
                    f"{EDIT_SCRIPT_MAX_ATTEMPTS}: {halt_reason} -- "
                    f"re-prompting with the failure"
                )
                continue
            if patched == existing_draft:
                halt_reason = (
                    f"{len(blocks)} edit block(s) applied but changed "
                    f"nothing"
                )
                failure_context = (
                    "Your previous edit blocks applied but changed "
                    "nothing. Each REPLACE must differ from its SEARCH, "
                    "and the edits must address the deficiencies listed "
                    "below."
                )
                print(
                    f"    [EDIT-SCRIPT] attempt {attempt}/"
                    f"{EDIT_SCRIPT_MAX_ATTEMPTS}: {halt_reason} -- "
                    f"re-prompting with the failure"
                )
                continue
            # #2532: pin what passed. Edits touching content the verdict
            # did not name are refused mechanically; the locked spans
            # carry forward byte-verbatim.
            try:
                pinned, events = _apply_pinning(
                    state, existing_draft, patched,
                    response=edit_result.response or "",
                    review_feedback=review_feedback,
                    completeness_issues=completeness_issues,
                )
            except PinningMergeError as e:
                # #3585: re-prompting cannot mend the merge; halt.
                return _halt(issue_number, f"pinning cannot hold this revision: {e}")
            pinning_events.extend(events)
            if pinned == existing_draft:
                refusals = [
                    e for e in events if "[PINNING] refused:" in e
                ]
                halt_reason = (
                    f"every edit touched locked content and was refused "
                    f"by pinning ({len(refusals)} refusal(s))"
                )
                failure_context = (
                    "Your previous edits were refused by pinning "
                    "enforcement as locked content the feedback did not "
                    "name: "
                    + "; ".join(refusals[:4])
                    + ". Edit ONLY the content the deficiencies and "
                    "feedback below name."
                )
                print(
                    f"    [EDIT-SCRIPT] attempt {attempt}/"
                    f"{EDIT_SCRIPT_MAX_ATTEMPTS}: {halt_reason} -- "
                    f"re-prompting with the failure"
                )
                continue
            ratio = unchanged_ratio(existing_draft, pinned)
            print(
                f"    [EDIT-SCRIPT] Applied {len(blocks)} edit(s); "
                f"{ratio:.0%} of prior spec preserved byte-identical "
                f"(#1528)"
            )
            edit_script_content = pinned
            result = edit_result
            break
        if edit_script_content is None:
            message = _spec_edit_halt(halt_reason)
            print(f"    {message}")
            return {
                "error_message": message,
                "pinning_events": (
                    list(state.get("pinning_events", [])) + pinning_events
                ),
            }

    # -------------------------------------------------------------------------
    # Call drafter LLM (classic full draft/revision path)
    # -------------------------------------------------------------------------
    if edit_script_content is None:
        cost_before = get_cumulative_cost()
        result = drafter.invoke(
            system_prompt=_drafter_system_prompt(state.get("lld_content", "")),
            content=prompt,
            timeout_seconds=1800,  # 30 min — impl specs are large
        )
        node_cost_usd = get_cumulative_cost() - cost_before

    if not result.success:
        print(f"    ERROR: {result.error_message}")
        return {"error_message": f"Drafter failed: {result.error_message}"}

    # Issue #476: Budget check
    cumulative = get_cumulative_cost()
    budget = state.get("cost_budget_usd", 0.0)
    if budget > 0 and cumulative > budget:
        msg = f"[BUDGET] ${cumulative:.2f} exceeds ${budget:.2f} budget. Halting."
        print(f"    {msg}")
        return {"error_message": msg}

    if edit_script_content is not None:
        # #1528: the patched draft IS the spec — no preamble to strip.
        spec_content = edit_script_content
    else:
        spec_content = result.response or ""
        # ---------------------------------------------------------------------
        # Strip preamble (safety: Claude sometimes adds text before the # heading)
        # ---------------------------------------------------------------------
        spec_content = _strip_preamble(spec_content)

        # #3585: a call that succeeded with nothing in it is a failed draft.
        # The empty string used to be saved and sent to N3 as the spec.
        if not spec_content.strip():
            return _halt(
                issue_number,
                f"the drafter {drafter_spec} reported success but returned an "
                f"empty response ({len(result.response or '')} chars), so there "
                f"is no draft to validate",
            )

        # #2532: the full-regeneration path is the observed regression vector
        # — run-issue331-233939's resumed grant reintroduced the S2 fix by
        # regenerating everything. Pinning applies to the diff exactly as on
        # the edit path: unnamed content carries forward byte-verbatim.
        # The UNLOCK line is read from the RAW response, because the
        # preamble strip above would eat it.
        if is_revision and existing_draft and spec_content.strip():
            try:
                spec_content, events = _apply_pinning(
                    state, existing_draft, spec_content,
                    response=result.response or "",
                    review_feedback=review_feedback,
                    completeness_issues=completeness_issues,
                )
            except PinningMergeError as e:
                return _halt(issue_number, f"pinning cannot hold this revision: {e}")
            pinning_events.extend(events)

    # -------------------------------------------------------------------------
    # #2611: re-assert the LLD's decision table over whatever the draft holds.
    #
    # AFTER pinning, deliberately. Pinning adjudicates a diff and can be argued
    # with; re-assertion does not adjudicate, so running it last means the
    # machine-owned region is never something pinning had to reason about --
    # which is what #2607 asked for on the lld side and this mirrors here.
    # -------------------------------------------------------------------------
    if spec_content.strip():
        spec_content, table_changed = _spec_injection().reassert(
            spec_content, state.get("lld_content", "")
        )
        if table_changed:
            print(
                "    [inject] binding decision table re-asserted from the LLD "
                "(machine-owned; the draft's copy did not match)"
            )

    # -------------------------------------------------------------------------
    # Save to audit trail (the directory was checked before the drafter call)
    # -------------------------------------------------------------------------
    try:
        file_num = next_file_number(audit_dir)
        spec_path = save_audit_file(
            audit_dir, file_num, "spec-draft.md", spec_content
        )
    except OSError as e:
        return _halt(
            issue_number,
            f"cannot save the draft to {audit_dir}: {type(e).__name__}: {e}",
        )

    # -------------------------------------------------------------------------
    # Report results
    # -------------------------------------------------------------------------
    draft_lines = len(spec_content.splitlines()) if spec_content else 0
    print(f"    Generated {draft_lines} lines")
    print(f"    Saved: {spec_path.name}")

    # Issue #511: Accumulate per-node cost
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "generate_spec", node_cost_usd,
    )
    node_tokens = accumulate_node_tokens(
        dict(state.get("node_tokens", {})),
        "generate_spec",
        result.input_tokens,
        result.output_tokens,
    )

    return {
        # #2532: the pinning record travels with the run — refusals,
        # regression-class flags, unlock grants — so the loop's history
        # carries who tried to change what no verdict named.
        "pinning_events": list(state.get("pinning_events", [])) + pinning_events,
        "spec_draft": spec_content,
        # #2297: the audit-trail DRAFT, not the finalized spec. Writing this to
        # `spec_path` made a cap-halted run indistinguishable from a successful
        # one at the stage boundary: run_spec_stage accepts the stage when
        # `spec_path` names an existing file, and after #2250 gave orchestrated
        # runs an audit_dir this draft is always an existing file. Before #2250
        # there was no audit_dir, so this was "" and a halt correctly failed --
        # the lineage repair turned a correct failure into a false success.
        "spec_draft_path": str(spec_path),
        "review_iteration": review_iteration,
        "completeness_issues": [],  # Clear after use
        "previous_review_feedback": review_feedback,  # Issue #486: Save for two-strike
        "previous_spec_draft": state.get("spec_draft", ""),  # Issue #491: Save for diff-aware review
        "review_feedback": "",  # Clear after use
        "error_message": "",
        "node_costs": node_costs,  # Issue #511
        "node_tokens": node_tokens,  # Issue #511
    }


def _apply_pinning(
    state: ImplementationSpecState,
    previous: str,
    revised: str,
    *,
    response: str,
    review_feedback: str,
    completeness_issues: list[str],
) -> tuple[str, list[str]]:
    """Enforce #2532's pinning on one revision; returns (text, events).

    Named = the current verdict plus the current completeness failures.
    Ever-named = those plus every prior round's feedback and every prior
    completeness breakdown — the union the regression flag is judged
    against ("content no verdict EVER objected to").

    When the current verdict names nothing extractable, pinning cannot run.
    Locking the whole document on an unparseable naming would refuse every
    legitimate fix (#2526), and passing the revision unenforced, which this
    used to do, reads a gate that could not run as one that passed. So it
    raises PinningCannotRunError (#3585); ``generate_spec`` checks the same
    condition before the drafter is called and halts there.

    Line-range citations from the current completeness failures count as
    naming (#2555): "lines 81-83" addresses ``previous`` exactly — the
    checks measured that document — so the span a failure demands a change
    in is named content, never a lock refusal, never the regression class.
    """
    from assemblyzero.workflows.implementation_spec.revision_pinning import (
        demands_additions,
        enforce_pinning,
        named_tokens,
        unlock_requested,
    )

    current, ranges = _pinning_names(review_feedback, completeness_issues)
    if not current and not ranges:
        raise PinningCannotRunError(_PINNING_UNREADABLE)

    ever = set(current)
    for prior in state.get("review_feedback_history", []):
        ever |= named_tokens(prior)
    for entry in state.get("prior_completeness_breakdown", []):
        ever |= named_tokens("", [str(f) for f in entry.get("failures", [])])

    result = enforce_pinning(
        previous, revised,
        current_tokens=current,
        ever_tokens=ever,
        current_ranges=ranges,
        additions_demanded=demands_additions(completeness_issues),
        unlock_reason=unlock_requested(response),
    )

    events: list[str] = []
    if result.unlock_reason:
        events.append(
            f"[PINNING] UNLOCK granted — drafter's reason: "
            f"{result.unlock_reason} (#2532)"
        )
    for refusal in result.refusals:
        events.append(
            f"[PINNING] refused: {refusal} — locked content the verdict "
            f"did not name (#2532)"
        )
    for regression in result.regressions:
        events.append(
            f"[PINNING] REGRESSION CLASS: revision modified content no "
            f"verdict ever objected to: {regression} (#2532)"
        )
    for addition in result.additions:
        events.append(
            f"[PINNING] demanded addition passed: {addition} — this round's "
            f"completeness failures demand new tests (#2560)"
        )
    if result.conservation_event:
        events.append(
            f"[PINNING] CONSERVATION: {result.conservation_event} (#2559)"
        )
    for event in events:
        print(f"    {event}")
    return result.text, events


# =============================================================================
# Prompt Building
# =============================================================================


def build_drafter_prompt(
    lld_content: str,
    current_state: dict[str, str],
    patterns: list[PatternRef],
    template: str = "",
    issue_number: int = 0,
    existing_draft: str = "",
    review_feedback: str = "",
    completeness_issues: list[str] | None = None,
    repo_root: str = "",
    files_to_modify: list | None = None,
    project_context: str = "",
    import_dependencies: str = "",
    repo_structure: str = "",
    prior_completeness_breakdown: list[dict] | None = None,
    assertion_manifest: str = "",
) -> str:
    """Build the prompt for Claude spec generation.

    Constructs either an initial draft prompt or a revision prompt
    depending on whether existing_draft and feedback are provided.

    The prompt includes:
    - Full LLD content
    - Project context (CLAUDE.md, README, metadata) — Issue #409
    - Current state snapshots for each file to be modified
    - Import dependencies between files — Issue #409
    - Pattern references with code excerpts
    - Implementation Spec template (if available)
    - Revision feedback (if revising)

    Args:
        lld_content: Raw LLD markdown content.
        current_state: Mapping of file_path -> code excerpt.
        patterns: List of PatternRef for similar implementation patterns.
        template: Implementation Spec template content.
        issue_number: GitHub issue number.
        existing_draft: Current spec draft (for revision mode).
        review_feedback: Feedback from Gemini review (for revision).
        completeness_issues: List of completeness check failures (for revision).
        repo_root: Target repository root path (for repo structure display).
        files_to_modify: List of FileToModify dicts from the LLD.
        project_context: CLAUDE.md/README/metadata context (Issue #409).
        import_dependencies: Cross-file import map (Issue #409).

    Returns:
        Complete prompt string for the drafter LLM.

    Raises:
        PromptBudgetError: the prompt's required parts (the instructions, the
            LLD, the manifest, the draft and the round's complaints) alone
            exceed MAX_TOTAL_PROMPT_CHARS (#3585). Optional context is
            dropped whole to fit, and the prompt says what was dropped.
    """
    if completeness_issues is None:
        completeness_issues = []
    if files_to_modify is None:
        files_to_modify = []
    if prior_completeness_breakdown is None:
        prior_completeness_breakdown = []

    is_revision = bool(existing_draft and (review_feedback or completeness_issues))

    if is_revision:
        return _build_revision_prompt(
            lld_content=lld_content,
            current_state=current_state,
            patterns=patterns,
            template=template,
            issue_number=issue_number,
            existing_draft=existing_draft,
            review_feedback=review_feedback,
            completeness_issues=completeness_issues,
            repo_root=repo_root,
            files_to_modify=files_to_modify,
            repo_structure=repo_structure,
            prior_completeness_breakdown=prior_completeness_breakdown,
            assertion_manifest=assertion_manifest,
        )
    else:
        return _build_initial_prompt(
            lld_content=lld_content,
            current_state=current_state,
            patterns=patterns,
            template=template,
            issue_number=issue_number,
            files_to_modify=files_to_modify,
            project_context=project_context,
            import_dependencies=import_dependencies,
            assertion_manifest=assertion_manifest,
        )


def _manifest_section(assertion_manifest: str) -> str:
    """The BINDING manifest section (#2533): wrap rows, invent nothing."""
    return (
        "## ASSERTION MANIFEST (BINDING)\n\n"
        "The manifest below was compiled deterministically from the LLD's "
        "decision tables and the target contract (#2533). It is BINDING:\n\n"
        "1. Every manifest row becomes exactly ONE test's assertion(s). WRAP "
        "the row's literal expected value in test code — NEVER invent, "
        "derive, or adjust an assertion value.\n"
        "2. Every test that asserts a manifest row MUST cite the row id in a "
        "comment inside the test body, one per line: `# manifest: N4.2`\n"
        "3. Each row is covered by exactly one test; do not assert a row "
        "twice.\n"
        "4. Fixtures, scaffolding, and non-assertion prose remain yours — "
        "the manifest retires assertion INVENTION, not drafting.\n\n"
        + assertion_manifest
    )


# =============================================================================
# Initial Prompt
# =============================================================================


def _build_initial_prompt(
    lld_content: str,
    current_state: dict[str, str],
    patterns: list[PatternRef],
    template: str,
    issue_number: int,
    files_to_modify: list,
    project_context: str = "",
    import_dependencies: str = "",
    assertion_manifest: str = "",
) -> str:
    """Build prompt for initial spec generation.

    Args:
        lld_content: Raw LLD markdown content.
        current_state: File path -> code excerpt mapping.
        patterns: Pattern references from codebase analysis.
        template: Implementation Spec template.
        issue_number: GitHub issue number.
        files_to_modify: List of FileToModify dicts.
        project_context: CLAUDE.md/README/metadata context (Issue #409).
        import_dependencies: Cross-file import map (Issue #409).

    Returns:
        Initial draft prompt string.

    Raises:
        PromptBudgetError: the required parts alone exceed the budget (#3585).
    """
    parts: list[_Part] = []

    parts.append(_Part(
        "instructions",
        "IMPORTANT: Output ONLY the markdown content. "
        "Start with # title. No preamble.",
    ))

    # LLD content
    parts.append(_Part("LLD", f"## LLD Content (Issue #{issue_number})\n\n{lld_content}"))

    # #2533: the compiled assertion manifest is BINDING input, placed right
    # after the LLD so the rows sit beside the criteria they compiled from.
    if assertion_manifest:
        parts.append(_Part("assertion manifest", _manifest_section(assertion_manifest)))

    # Project context (Issue #409 Gap 1)
    if project_context:
        parts.append(_Part("project context", project_context, _DROP_PROJECT_CONTEXT))

    # Current state snapshots
    snapshot_section = _format_current_state_section(current_state, files_to_modify)
    if snapshot_section:
        parts.append(_Part("current state", snapshot_section, _DROP_CURRENT_STATE))

    # Import dependencies (Issue #409 Gap 3)
    if import_dependencies:
        parts.append(_Part("import dependencies", import_dependencies, _DROP_IMPORTS))

    # Pattern references
    pattern_section = _format_patterns_section(patterns)
    if pattern_section:
        parts.append(_Part("patterns", pattern_section, _DROP_PATTERNS))

    # Template
    if template:
        parts.append(_Part(
            "template",
            f"## Implementation Spec Template (follow this structure)\n\n{template}",
            _DROP_TEMPLATE,
        ))

    # Final instruction
    parts.append(_Part(
        "instructions",
        "Create a complete Implementation Spec following the template structure.\n"
        "Ensure EVERY file listed in the LLD has concrete implementation guidance.\n"
        f"This spec is for Issue #{issue_number}.\n"
        "START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE.",
    ))

    return _fit_to_budget(parts)


# =============================================================================
# Revision Prompt
# =============================================================================


def _build_revision_prompt(
    lld_content: str,
    current_state: dict[str, str],
    patterns: list[PatternRef],
    template: str,
    issue_number: int,
    existing_draft: str,
    review_feedback: str,
    completeness_issues: list[str],
    repo_root: str,
    files_to_modify: list,
    repo_structure: str = "",
    prior_completeness_breakdown: list[dict] | None = None,
    assertion_manifest: str = "",
) -> str:
    """Build prompt for spec revision based on feedback.

    Args:
        lld_content: Raw LLD markdown content.
        current_state: File path -> code excerpt mapping.
        patterns: Pattern references from codebase analysis.
        template: Implementation Spec template.
        issue_number: GitHub issue number.
        existing_draft: Current spec draft to revise.
        review_feedback: Gemini review feedback.
        completeness_issues: Completeness check failures.
        repo_root: Target repo root (for structure display).
        files_to_modify: List of FileToModify dicts.

    Returns:
        Revision prompt string.

    Raises:
        PromptBudgetError: the required parts alone exceed the budget (#3585).
    """
    # Issue #489: Try section-level revision for focused changes
    if review_feedback and existing_draft:
        draft_sections = extract_sections(existing_draft)
        changed = identify_changed_sections(review_feedback, draft_sections)
        if changed:
            targeted = build_targeted_prompt(
                sections=draft_sections,
                changed_headings=changed,
                template=template,
                feedback=review_feedback,
            )
            if targeted:
                parts = [
                    "IMPORTANT: Output ONLY the markdown content. "
                    "Start with # title. No preamble.",
                    targeted,
                    f"## Original LLD (Issue #{issue_number})\n\n{lld_content}",
                    *(
                        [_manifest_section(assertion_manifest)]
                        if assertion_manifest else []
                    ),
                    "CRITICAL REVISION INSTRUCTIONS — READ BEFORE WRITING:\n\n"
                    "This is a TARGETED PATCH, not a regeneration. You are "
                    "NOT writing a new spec — you are applying specific fixes "
                    "to the draft above.\n\n"
                    "1. Fix ALL issues named in the feedback\n"
                    "2. Sections marked [UNCHANGED] MUST be reproduced "
                    "byte-identical — copy-paste them verbatim; do NOT "
                    "rephrase, restructure, reformat, or 'improve' even if "
                    "you think you can do better\n"
                    "3. ONLY modify sections marked [REVISE]\n"
                    "4. Keep ALL template sections intact and byte-identical\n\n"
                    "Known failure mode (DO NOT DO THIS — AZ #1521): writer "
                    "addresses the flagged issue but introduces a NEW error "
                    "elsewhere by drifting on unflagged content. If you find "
                    "yourself 'tidying up' an [UNCHANGED] section, STOP — that "
                    "edit is a regression, not a fix.\n\n"
                    "START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE.",
                ]
                prompt = "\n\n".join(parts)
                if len(prompt) <= MAX_TOTAL_PROMPT_CHARS:
                    return prompt

    # Fallback: full revision prompt
    parts: list[_Part] = []

    parts.append(_Part(
        "instructions",
        "IMPORTANT: Output ONLY the markdown content. "
        "Start with # title. No preamble.",
    ))

    # #2533: the manifest binds revisions exactly as it binds first drafts.
    if assertion_manifest:
        parts.append(_Part("assertion manifest", _manifest_section(assertion_manifest)))

    # Completeness issues (highest priority — from N3 mechanical validation)
    if completeness_issues:
        issues_text = "## MECHANICAL COMPLETENESS ERRORS (MUST FIX FIRST)\n\n"
        issues_text += (
            "The following errors were found by automated completeness "
            "validation. These MUST be fixed before the spec can proceed:\n\n"
        )
        for issue in completeness_issues:
            issues_text += f"- **ERROR:** {issue}\n"

        # Show repo structure to help fix path-related issues
        # Issue #490: Use cached repo_structure, fallback to inline call
        if repo_root:
            repo_structure = repo_structure or get_repo_structure(repo_root)
            issues_text += "\n## ACTUAL REPOSITORY STRUCTURE\n\n"
            issues_text += (
                "**Use ONLY these existing directories** "
                "(or explicitly document new ones):\n\n"
            )
            issues_text += f"```\n{repo_structure}\n```\n"

        parts.append(_Part("completeness errors", issues_text))

    # Closes #1465: Cumulative prior-iteration failures. Show the drafter the
    # full history of which checks failed in which iterations, so identical
    # error messages don't yield identical revisions. If the same check has
    # failed K times, the drafter is told explicitly: "your last K attempts
    # did NOT fix this — try a fundamentally different approach."
    if prior_completeness_breakdown:
        history = "## PRIOR ITERATION HISTORY (DO NOT REPEAT)\n\n"
        history += (
            "Each entry shows checks that failed in a prior iteration. "
            "If the same failure recurs across multiple iterations, your "
            "earlier fixes did NOT work — change approach, do not minor-tweak:\n\n"
        )
        for entry in prior_completeness_breakdown:
            iteration = entry.get("iteration", "?")
            failures = entry.get("failures", [])
            history += f"### Iteration {iteration} failures\n"
            for failure in failures:
                history += f"- {failure}\n"
            history += "\n"
        # Synthesize the "tried K times" warning if any check repeats.
        # Closes #1479: cluster by lexically-normalized text so near-duplicate
        # failure messages (extra whitespace, trailing punctuation, case)
        # collapse into a single recurring entry instead of slipping past as
        # distinct.
        all_failures = [
            f
            for entry in prior_completeness_breakdown
            for f in entry.get("failures", [])
        ]
        from collections import Counter
        normalized_pairs = [(_normalize_failure_text(f), f) for f in all_failures]
        repeat_counts = Counter(norm for norm, _ in normalized_pairs)
        # Map each normalized key to the LATEST verbatim text (last occurrence
        # wins) so the warning shows real wording, not the normalized form.
        latest_verbatim: dict[str, str] = {}
        for norm, verbatim in normalized_pairs:
            latest_verbatim[norm] = verbatim
        repeated = [norm for norm, n in repeat_counts.items() if n >= 2]
        if repeated:
            history += "### RECURRING FAILURES (your prior fixes did NOT work)\n\n"
            for norm in repeated:
                count = repeat_counts[norm]
                history += f"- Tried {count} times: {latest_verbatim[norm]}\n"
            history += (
                "\n**Stop refining the prior approach. Change the spec's "
                "structure or strategy fundamentally for these failures.**\n"
            )
        parts.append(_Part("prior iteration history", history, _DROP_HISTORY))

    # Review feedback (from N5 Gemini review)
    if review_feedback:
        parts.append(_Part(
            "review feedback",
            "## Gemini Readiness Review Feedback\n\n"
            f"{review_feedback}",
        ))

    # Current draft to revise
    parts.append(_Part("current draft", f"## Current Draft (to revise)\n\n{existing_draft}"))

    # Current state snapshots (for reference during revision)
    snapshot_section = _format_current_state_section(current_state, files_to_modify)
    if snapshot_section:
        parts.append(_Part("current state", snapshot_section, _DROP_CURRENT_STATE))

    # Original LLD for reference
    parts.append(_Part("LLD", f"## Original LLD (Issue #{issue_number})\n\n{lld_content}"))

    # Template
    if template:
        parts.append(_Part(
            "template",
            f"## Implementation Spec Template (REQUIRED STRUCTURE)\n\n{template}",
            _DROP_TEMPLATE,
        ))

    # Revision instructions
    # Closes #1521: writer was regressing on revision — fixing the flagged
    # syntax error but introducing a new one elsewhere by drifting on
    # unflagged content. The wording below reframes the task as a TARGETED
    # PATCH ("not a regeneration"), explicitly forbids "tidying up" unflagged
    # content, and calls out the known failure mode by name so the LLM sees
    # the anti-pattern it must avoid.
    parts.append(_Part(
        "instructions",
        "CRITICAL REVISION INSTRUCTIONS — READ BEFORE WRITING:\n\n"
        "This is a TARGETED PATCH, not a regeneration. You are applying "
        "specific fixes to an existing draft. You are NOT writing a new spec.\n\n"
        "## What to change\n"
        "1. Fix ALL mechanical completeness errors (missing excerpts, missing "
        "examples)\n"
        "2. Implement EVERY change requested by the review feedback\n\n"
        "## What NOT to change (strict — any violation is a regression)\n"
        "3. Any text NOT named in the feedback above MUST be reproduced "
        "VERBATIM. Copy-paste the original wording. Do NOT rephrase, "
        "restructure, reformat, or 'improve' it — even if you think you "
        "can do better.\n"
        "4. Code blocks, decorators, function signatures, test fixtures, "
        "and data-structure literals NOT flagged by feedback MUST be "
        "byte-identical to the existing draft.\n"
        "5. Template sections, section headings, bullet structure, and "
        "ordering MUST match the existing draft except where feedback "
        "says to change them.\n\n"
        "## Completeness requirements (these MUST hold in the output)\n"
        "6. Every Modify file has a current state excerpt\n"
        "7. Every function has concrete input/output examples\n"
        "8. Every data structure has a concrete JSON/YAML example\n\n"
        "## Known failure mode (DO NOT DO THIS — AZ #1521)\n"
        "Writer addresses the flagged issue but introduces a NEW syntax "
        "error elsewhere by drifting on unflagged content. If you find "
        "yourself 'tidying up' or 'fixing' something not named in the "
        "feedback above, STOP — that edit is a regression, not a fix.\n\n"
        "## Pinning is ENFORCED mechanically (#2532)\n"
        "Content a completed review round passed without objection is "
        "LOCKED: any change you make to text the feedback does not name "
        "will be refused and the previous text restored byte-verbatim. If "
        "a fix genuinely requires restructuring beyond the named items, "
        "put a single line `UNLOCK: <one-line reason>` as the VERY FIRST "
        "line of your response (before the # heading); the unlock is "
        "logged, never silent.\n\n"
        "START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE.",
    ))

    return _fit_to_budget(parts)


# =============================================================================
# Prompt Section Formatters
# =============================================================================


def _format_current_state_section(
    current_state: dict[str, str],
    files_to_modify: list,
) -> str:
    """Format current state snapshots into a prompt section.

    Args:
        current_state: File path -> code excerpt mapping.
        files_to_modify: List of FileToModify dicts for metadata.

    Returns:
        Formatted section string, or empty string if no snapshots.
    """
    if not current_state:
        return ""

    parts: list[str] = ["## Current State of Files to Modify\n"]

    # Build a lookup for change types
    change_types: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    for f in files_to_modify:
        path = f.get("path", "") if isinstance(f, dict) else ""
        change_types[path] = f.get("change_type", "Modify") if isinstance(f, dict) else "Modify"
        descriptions[path] = f.get("description", "") if isinstance(f, dict) else ""

    for file_path, excerpt in current_state.items():
        change_type = change_types.get(file_path, "Modify")
        description = descriptions.get(file_path, "")

        # Truncate very large excerpts
        if len(excerpt) > MAX_SNAPSHOT_CHARS:
            excerpt = excerpt[:MAX_SNAPSHOT_CHARS] + "\n# ... (truncated)\n"

        header = f"### `{file_path}` ({change_type})"
        if description:
            header += f"\n*{description}*"

        parts.append(f"{header}\n\n```python\n{excerpt}\n```")

    return "\n\n".join(parts)


def _format_patterns_section(patterns: list[PatternRef]) -> str:
    """Format pattern references into a prompt section.

    Args:
        patterns: List of PatternRef dicts from codebase analysis.

    Returns:
        Formatted section string, or empty string if no patterns.
    """
    if not patterns:
        return ""

    parts: list[str] = [
        "## Similar Implementation Patterns\n\n"
        "Use these existing patterns as reference for consistent implementation style:"
    ]

    for ref in patterns:
        file_path = ref.get("file_path", "")
        start_line = ref.get("start_line", 0)
        end_line = ref.get("end_line", 0)
        pattern_type = ref.get("pattern_type", "")
        relevance = ref.get("relevance", "")

        parts.append(
            f"- **{pattern_type}** at `{file_path}:{start_line}-{end_line}`"
            f"\n  {relevance}"
        )

    return "\n".join(parts)


# =============================================================================
# Utility Functions
# =============================================================================


def _strip_preamble(content: str) -> str:
    """Strip any preamble text before the first # heading.

    Claude sometimes adds explanatory text before the actual spec content
    despite system prompt instructions. This strips it.

    Args:
        content: Raw LLM response content.

    Returns:
        Content starting from the first # heading.
    """
    if not content:
        return content

    match = re.search(r"^#\s+", content, re.MULTILINE)
    if match:
        heading_pos = match.start()
        if heading_pos > 0:
            stripped = content[:heading_pos].strip()
            if stripped:
                print(
                    f"    [WARN] Stripped {len(stripped)} chars of preamble "
                    f"before # heading"
                )
            return content[heading_pos:]

    return content


#: Drop ranks for a prompt's optional parts: the highest is dropped first.
#: The order is #409's, kept-longest last. A required part (the instructions,
#: the LLD, the binding manifest, the draft under revision, the completeness
#: errors and the review feedback) has rank 0 and is never dropped (#3585).
_DROP_HISTORY = 6
_DROP_PROJECT_CONTEXT = 5
_DROP_PATTERNS = 4
_DROP_IMPORTS = 3
_DROP_CURRENT_STATE = 2
_DROP_TEMPLATE = 1


@dataclass(frozen=True)
class _Part:
    """One part of a drafter prompt, as the builder appended it (#3585).

    The budget works on these, not on the joined text. #409's version split
    the joined prompt on ``## `` lines, so the LLD's, the template's and the
    draft's own ``##`` sections read as unknown sections and were dropped
    first, the binding manifest's header matched no priority and went first
    too, and a prompt still over budget was cut off mid-content.
    """

    name: str
    text: str
    #: 0 for a required part; otherwise its drop rank.
    drop_rank: int = 0


def _fit_to_budget(parts: list[_Part]) -> str:
    """Join the parts, dropping optional ones whole until the prompt fits.

    Dropping optional context to fit is the budget's design, not a failure:
    the prompt says which parts were trimmed, and so does the run log. The
    required parts are never dropped or cut; when they alone exceed the
    budget, this raises (#3585).

    Raises:
        PromptBudgetError: the required parts exceed MAX_TOTAL_PROMPT_CHARS.
    """
    def joined(kept: list[_Part]) -> str:
        return "\n\n".join(part.text for part in kept)

    prompt = joined(parts)
    if len(prompt) <= MAX_TOTAL_PROMPT_CHARS:
        return prompt

    original_len = len(prompt)
    kept = list(parts)
    dropped: list[str] = []
    for victim in sorted(
        (part for part in parts if part.drop_rank),
        key=lambda part: part.drop_rank,
        reverse=True,
    ):
        kept.remove(victim)
        dropped.append(victim.name)
        notice = _Part(
            "trim notice",
            "<!-- CONTEXT TRIMMED: Dropped sections to fit budget: "
            + ", ".join(dropped)
            + " -->",
        )
        if len(joined(kept + [notice])) <= MAX_TOTAL_PROMPT_CHARS:
            break

    result = joined(kept + [notice]) if dropped else prompt
    if len(result) > MAX_TOTAL_PROMPT_CHARS:
        required = [part for part in parts if not part.drop_rank]
        required_len = len(joined(required))
        names = ", ".join(dict.fromkeys(part.name for part in required))
        raise PromptBudgetError(
            f"its required parts ({names}) come to {required_len:,} chars, "
            f"{required_len - MAX_TOTAL_PROMPT_CHARS:,} over the "
            f"{MAX_TOTAL_PROMPT_CHARS:,}-char budget with every optional part "
            f"dropped ({', '.join(dropped) or 'none'}); the prompt used to be "
            f"cut off at the budget, sending the drafter a partial LLD or draft"
        )

    print(
        f"    [BUDGET] Prompt trimmed from {original_len:,} to {len(result):,} "
        f"chars by dropping optional context: {', '.join(dropped)}"
    )
    return result