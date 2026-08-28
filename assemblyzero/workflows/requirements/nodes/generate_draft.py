"""N1: Generate draft node for Requirements Workflow.

Issue #101: Unified Requirements Workflow
Issue #248: Remove pre-review validation gate - Gemini answers open questions
Issue #497: Bounded Verdict History in LLD Revision Loop
Issue #508: Prompt-size awareness — cap total prompt chars

Uses the configured drafter LLM to generate a draft based on:
- Issue workflow: brief content + template
- LLD workflow: issue content + context + template

Supports revision mode with bounded verdict feedback window.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Issue #508: Maximum total prompt content chars (to avoid token limits)
MAX_TOTAL_PROMPT_CHARS = 120_000
# Warn at 80% of the cap
PROMPT_SIZE_WARNING_THRESHOLD = 0.8

from assemblyzero.core.interface_surface import (
    build_interface_map_for_paths,
    format_interface_map_section,
)
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
from assemblyzero.workflows.requirements.best_of_n import (  # noqa: E402
    SERIAL,
    clamp_candidates,
    render_score_table,
    score_candidate,
    select_winner,
)
from assemblyzero.workflows.requirements.state import RequirementsWorkflowState
from assemblyzero.workflows.requirements.feedback_window import (
    build_feedback_block,
    render_feedback_markdown,
)
from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
    parse_files_changed_table,
)
from assemblyzero.workflows.requirements.nodes.lld_revision import (
    EDIT_SCRIPT_SYSTEM_PROMPT,
    apply_edit_blocks,
    build_lld_edit_prompt,
    parse_edit_blocks,
    removed_required_sections,
    unchanged_ratio,
)
from assemblyzero.core.verdict_schema import (
    DraftQuestionsResult,
    scan_open_questions_section,
)


def _edit_script_halt(reason: str) -> str:
    """Halt message for a revision that could not be applied as edits (#2200).

    Legible on its own in a halt banner (#2197): it names the contract, what
    broke it, and the fact that nothing was lost.
    """
    return (
        f"[EDIT-SCRIPT] LLD revision rejected: {reason}. The prior draft is "
        f"unchanged and remains the working copy. A revision is applied as "
        f"SEARCH/REPLACE edit blocks and is never redrawn wholesale (#2200), "
        f"so there is no full-regeneration fallback to take. Relaunch to "
        f"resume from this stage."
    )


#: A conventional-commit type at the head of a title: ``feat:``, ``fix(api):``,
#: ``refactor!:``. Only the eleven standard types are stripped, so an issue
#: titled ``config: reload on SIGHUP`` keeps its first word — that is prose,
#: not a commit convention, and guessing at it would silently rewrite titles.
_CONVENTIONAL_COMMIT_PREFIX = re.compile(
    r"^\s*(?:feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)"
    r"(?:\([^)]*\))?!?:\s*",
    re.IGNORECASE,
)


def strip_conventional_commit_prefix(title: str) -> str:
    """Drop a leading conventional-commit type from an issue title (#2234).

    The LLD template's title line is ``# {IssueID} - Feature: {Title}``, so it
    supplies the label itself. Handing it a title that already begins with
    ``feat:`` produced ``Feature: feat: configuration file and CLI arguments``
    on every draft of run-issue7-234943.

    Only the leading type is removed, and only once: a title is not a commit
    message and the second colon in ``feat: fix: thing`` is the author's.
    """
    if not title:
        return title
    return _CONVENTIONAL_COMMIT_PREFIX.sub("", title, count=1).strip()


def _extract_open_questions(
    provider,
    response: str,
    system_prompt: str,
) -> DraftQuestionsResult:
    """Extract open questions from the drafter's document response.

    Standard 0028: the drafter's response is a markdown DOCUMENT (its prompt
    demands "emit ONLY the revised markdown"), so this was never a
    structured-JSON contract — the old "structured parse with regex
    fallback" failed the JSON step on every draft by construction and the
    section scrape was the actual mechanism. Now the deterministic section
    scan is the named mechanism. The provider and system_prompt params are
    retained for signature compatibility; they are not used.
    """
    return scan_open_questions_section(response)


def _generate_best_of_n(
    *,
    state: RequirementsWorkflowState,
    drafter,
    system_prompt: str,
    prompt: str,
    candidates: int,
    audit_dir: Path,
    draft_count: int,
    cost_before: float,
) -> dict[str, Any]:
    """N independent drafts, scored by the real gates, best one forward (#2573).

    Generation is SEQUENTIAL. The issue asks for parallel and the wall-clock
    win is real, but cumulative cost accounting (`get_cumulative_cost`), the
    prompt-failure telemetry and the provider's own retry state are process
    globals that no test here can prove safe under concurrency. The COST
    argument -- three drafter calls against loops that reached seven and
    nine rounds -- holds either way, and it is the decisive one. Parallel
    generation is filed as #2604.

    Every candidate is preserved to lineage whether it wins or loses: the
    losers are the evidence for whether best-of-N is worth keeping, and
    discarding them would make that question unanswerable the same way the
    serial loop's discarded drafts did.
    """
    from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
        validate_lld_mechanical,
    )
    from assemblyzero.workflows.requirements.nodes.validate_test_plan import (
        validate_test_plan_node,
    )

    print(
        f"    [BEST-OF-N] generating {candidates} independent candidate(s) "
        f"(#2573; serial generation, see #2604)"
    )

    scores = []
    file_num = state.get("file_counter", 0)
    last_result = None
    for index in range(1, candidates + 1):
        result = drafter.invoke(system_prompt=system_prompt, content=prompt)
        last_result = result
        if not result.success:
            # A failed candidate is scored unusable, not fatal: the point of
            # N drafts is that one failing does not end the round.
            scores.append(
                _unusable(index, f"drafter failed: {result.error_message}")
            )
            continue

        candidate = result.response or ""
        score = score_candidate(
            index, candidate, state,
            mechanical=validate_lld_mechanical,
            test_plan=validate_test_plan_node,
        )
        scores.append(score)

        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(
                audit_dir, file_num, f"candidate-{index}-draft.md", candidate
            )

        if score.clears:
            # A draft that passes every gate outright short-circuits: the
            # remaining candidates cannot beat zero failures, and spending
            # their calls to confirm that is the waste this replaces.
            print(
                f"    [BEST-OF-N] candidate {index} clears every gate; "
                f"stopping early"
            )
            break

    winner = select_winner(scores)
    if winner is None:
        return {
            "error_message": (
                f"BEST-OF-N: all {len(scores)} candidate(s) were unusable. "
                + "; ".join(s.unusable for s in scores)
            )
        }

    print(render_score_table(scores, winner.index))

    draft_content = winner.draft
    node_cost_usd = get_cumulative_cost() - cost_before
    iteration_count = state.get("iteration_count", 0) + 1

    draft_path = None
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        draft_path = save_audit_file(audit_dir, file_num, "draft.md", draft_content)

    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "generate_draft", node_cost_usd,
    )
    node_tokens = accumulate_node_tokens(
        dict(state.get("node_tokens", {})),
        "generate_draft",
        getattr(last_result, "input_tokens", 0) or 0,
        getattr(last_result, "output_tokens", 0) or 0,
    )

    return {
        "current_draft": draft_content,
        "current_draft_path": str(draft_path) if draft_path else "",
        "draft_count": draft_count,
        "iteration_count": iteration_count,
        "file_counter": file_num,
        "user_feedback": "",
        "previous_review_feedback": state.get("current_verdict", ""),
        "previous_draft": state.get("current_draft", ""),
        # The winner has NOT been through the gates as the live draft yet --
        # it was scored on a probe copy. Clearing here matches the serial
        # path, and N1.5 re-runs against the real state immediately after.
        "validation_errors": [],
        "finalize_repair_pending": False,
        "error_message": "",
        "node_costs": node_costs,
        "node_tokens": node_tokens,
        # #2573: the scored table, in state as well as the log, so a report
        # can count best-of-N rounds without parsing prose.
        "draft_candidate_scores": [
            {
                "index": s.index,
                "failures": s.failure_count,
                "summary": s.summary(),
                "winner": s.index == winner.index,
            }
            for s in scores
        ],
    }


def _unusable(index: int, reason: str):
    from assemblyzero.workflows.requirements.best_of_n import CandidateScore

    score = CandidateScore(index=index, draft="")
    score.unusable = reason
    return score


def generate_draft(state: RequirementsWorkflowState) -> dict[str, Any]:
    """N1: Generate draft using configured drafter.

    Steps:
    1. Load template from assemblyzero_root
    2. Build prompt (initial or revision)
    3. Call drafter LLM
    4. Save draft to audit trail
    5. Increment draft_count

    Note (Issue #248): Pre-review validation gate removed.
    Open questions now proceed to review where Gemini can answer them.

    Args:
        state: Current workflow state.

    Returns:
        State updates with current_draft, draft_count.
    """
    workflow_type = state.get("workflow_type", "lld")
    assemblyzero_root = Path(state.get("assemblyzero_root", ""))
    target_repo = Path(state.get("target_repo", ""))
    mock_mode = state.get("config_mock_mode", False)
    audit_dir = Path(state.get("audit_dir", ""))

    draft_count = state.get("draft_count", 0) + 1
    # #2042: the same predicate the prompt builder uses. This one drives only
    # the log line, and requiring verdict_history made every mechanical-validation
    # retry announce "Generating initial draft" while it was in fact revising --
    # so a loop that was working looked like one that had reset each time.
    is_revision = bool(
        state.get("current_draft")
        and (
            state.get("verdict_history")
            or state.get("validation_errors")
            or state.get("user_feedback")
        )
    )

    if is_revision:
        print(f"\n[N1] Generating revision (draft #{draft_count})...")
    else:
        print(f"\n[N1] Generating initial draft...")

    # Use mock provider in mock mode, otherwise use configured drafter
    if mock_mode:
        drafter_spec = "mock:draft"
    else:
        drafter_spec = state.get("config_drafter", "gemini:3.1-pro")

    # Determine template path based on workflow type
    if workflow_type == "issue":
        template_path = Path("docs/templates/0101-issue-template.md")
    else:
        template_path = Path("docs/templates/0102-feature-lld-template.md")

    # Load template
    try:
        template = load_template(template_path, assemblyzero_root)
    except FileNotFoundError as e:
        return {"error_message": str(e)}

    # Build prompt
    prompt = _build_prompt(state, template, workflow_type)

    # Issue #508: Prompt-size awareness
    prompt_len = len(prompt)
    if prompt_len > MAX_TOTAL_PROMPT_CHARS:
        logger.warning(
            "[N1] Prompt exceeds cap: %d > %d chars. Truncating.",
            prompt_len, MAX_TOTAL_PROMPT_CHARS,
        )
        print(f"    [WARN] Prompt {prompt_len:,} chars exceeds {MAX_TOTAL_PROMPT_CHARS:,} cap — truncating")
        prompt = _truncate_prompt(prompt)
    elif prompt_len > MAX_TOTAL_PROMPT_CHARS * PROMPT_SIZE_WARNING_THRESHOLD:
        pct = prompt_len / MAX_TOTAL_PROMPT_CHARS * 100
        print(f"    [WARN] Prompt at {pct:.0f}% of cap ({prompt_len:,} / {MAX_TOTAL_PROMPT_CHARS:,} chars)")

    # Issue #486: Pre-flight check — verify Gemini available before expensive Claude call
    if not mock_mode:
        from assemblyzero.core.preflight import check_gemini_available
        preflight = check_gemini_available()
        print(f"    [PREFLIGHT] Gemini: {preflight.available_credentials}/{preflight.total_credentials} credentials")
        if not preflight.passed:
            warnings_str = ", ".join(preflight.warnings)
            return {"error_message": f"[PREFLIGHT] Gemini unavailable: {warnings_str}"}

    # Get drafter provider
    try:
        drafter = get_provider(drafter_spec)
    except ValueError as e:
        return {"error_message": f"Invalid drafter: {e}"}

    # System prompt for drafting
    if workflow_type == "issue":
        system_prompt = """You are a technical writer creating a GitHub issue.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the issue title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Output ONLY the raw markdown content that will be pasted into GitHub
- First line MUST be the issue title starting with #

Use the template structure provided. Fill in all sections. Be specific and actionable."""
    else:
        system_prompt = """You are a technical architect creating a Low-Level Design document.

CRITICAL FORMATTING RULES:
- Start DIRECTLY with the document title (# heading)
- Do NOT include any preamble, explanation, or meta-commentary
- Output ONLY the raw markdown content
- First line MUST be the title starting with #

CRITICAL — REQUIREMENT/TEST MAPPING (failure to follow halts the workflow):
- Section 3 (Requirements) MUST be a plain numbered markdown list (1. 2. 3. ...). NO REQ-ID prefixes, NO tables, NO bullets.
- Section 10.1 (Test Scenarios) MUST be a markdown table. Each scenario's `Scenario` column MUST end with `(REQ-N)` where N is the requirement number from Section 3 the scenario covers. Example: `| 010 | Happy path object creation (REQ-1) | Auto | ... |`
- EVERY requirement in Section 3 MUST be covered by at least one test scenario via the `(REQ-N)` suffix. A mechanical validator counts coverage by regex-matching `(REQ-N)` patterns in Section 10.1 against the numbered list in Section 3. Missing coverage halts the workflow.
- Multiple scenarios may cover the same requirement (e.g. two error-case scenarios both ending in `(REQ-2)`). That's fine. What's NOT fine: a requirement with zero matching `(REQ-N)` references.

COVERAGE TARGETS MUST BE REACHABLE BY THE PLANNED TESTS (Issue #1940):
- If the target repo declares a coverage gate (pyproject `fail_under`), use \
THAT number as the LLD's coverage target. Do NOT invent a stricter one \
unless the issue itself demands it — a live run died holding generated \
code to an invented 95% while the repo's own gate said 89%.
- Every percentage you promise must be arithmetically reachable by the \
tests you plan. If your design includes defensive branches — queue-full \
eviction, race-window except blocks, abstract method bodies — the test \
plan MUST either include a deterministic scenario that exercises each one \
(prefill the queue to force eviction; inject the exception) or explicitly \
name the lines as coverage exclusions with a one-line justification. A \
target with unplanned-for defensive branches is an unwinnable spec.

Use the template structure provided. Include all sections. Be specific about:
- Files to be created/modified
- Function signatures
- Data structures
- Error handling approach"""

    # #1443: Revise-with-context — when the orchestrator's stage runner has
    # populated previous_draft_path and/or previous_verdict_text (set on retry
    # of a stage that previously failed), augment the system prompt so the
    # drafter REVISES instead of regenerating. Without this, each retry rolls
    # dice on a fresh prompt and can't converge on what the reviewer / human
    # flagged.
    previous_draft_path = state.get("previous_draft_path", "")
    previous_verdict_text = state.get("previous_verdict_text", "")
    if previous_draft_path or previous_verdict_text:
        previous_draft_text = ""
        if previous_draft_path:
            try:
                previous_draft_text = Path(previous_draft_path).read_text(
                    encoding="utf-8"
                )
            except OSError:
                previous_draft_text = (
                    f"(unable to read previous draft at {previous_draft_path})"
                )
        system_prompt += (
            "\n\n========================================================\n"
            "REVISION MODE — you have a prior attempt to learn from.\n"
            "========================================================\n\n"
            "This stage previously failed. Do NOT regenerate from scratch. "
            "Produce a revision that:\n"
            "  - Addresses every concrete reviewer-flagged issue below\n"
            "  - Preserves content the reviewer did NOT flag\n"
            "  - Keeps the same overall document shape (sections, ordering)\n"
            "  - Improves the issues; does not paraphrase the whole document\n\n"
        )
        if previous_draft_text:
            system_prompt += (
                "PRIOR DRAFT (begin):\n"
                "```markdown\n"
                f"{previous_draft_text}\n"
                "```\n"
                "PRIOR DRAFT (end).\n\n"
            )
        if previous_verdict_text:
            system_prompt += (
                "REVIEWER FEEDBACK ON PRIOR DRAFT (begin):\n\n"
                f"{previous_verdict_text}\n\n"
                "REVIEWER FEEDBACK (end).\n\n"
            )
        system_prompt += (
            "Now produce the revised document. Emit ONLY the revised markdown, "
            "starting with the # title — same rules as before.\n"
        )

    # Call drafter
    print(f"    Drafter: {drafter_spec}")

    cost_before = get_cumulative_cost()

    # Standard 0028: one ask, one contract. The drafter's contract is a
    # markdown document ("emit ONLY the revised markdown") enforced by
    # mechanical validation downstream — the old code ALSO sent
    # DRAFT_QUESTIONS_SCHEMA as the response schema, demanding JSON from
    # the same call. Two contradictory contracts on one ask is how drafts
    # come back malformed; the schema is gone and the open questions are
    # scanned from the document it was actually asked to produce.
    # #2200: an LLD revision is applied as edit blocks, never redrawn. The
    # model names its edits and the harness applies them, so content it does
    # not name cannot change. Two measured regenerations lost required
    # sections from drafts that had already passed validation; the prompt had
    # asked for preservation both times.
    use_edit_script = (
        workflow_type == "lld"
        and is_revision
        and not drafter_spec.startswith("mock:")
    )

    # #2573: best-of-N. Only on the INITIAL draft of an lld run, and only
    # when the operator asked for it -- the serial path stays the default.
    # A revision is deliberately excluded: revisions travel as edit scripts
    # (#2569) against a specific prior draft, so N independent revisions
    # would be N different documents with no common parent to merge.
    candidates_requested = clamp_candidates(
        state.get("config_draft_candidates", SERIAL)
    )
    use_best_of_n = (
        candidates_requested > SERIAL
        and workflow_type == "lld"
        and not is_revision
    )

    if use_best_of_n:
        return _generate_best_of_n(
            state=state,
            drafter=drafter,
            system_prompt=system_prompt,
            prompt=prompt,
            candidates=candidates_requested,
            audit_dir=audit_dir,
            draft_count=draft_count,
            cost_before=cost_before,
        )

    if use_edit_script:
        edit_context = build_revision_context(state)
        # #1443's cross-run context rides in the classic system prompt, which
        # the edit path does not use. Carry the prior attempt's verdict across
        # explicitly so a resumed stage revises with everything it had before.
        # The prior draft itself needs no carrying: it IS the patch target.
        if previous_verdict_text:
            edit_context += (
                "## REVIEWER FEEDBACK ON A PRIOR ATTEMPT AT THIS STAGE\n\n"
                f"{previous_verdict_text}\n\n"
            )
        edit_prompt = build_lld_edit_prompt(
            existing_draft=state.get("current_draft", ""),
            revision_context=edit_context,
        )
        result = drafter.invoke(
            system_prompt=EDIT_SCRIPT_SYSTEM_PROMPT, content=edit_prompt
        )
    else:
        result = drafter.invoke(system_prompt=system_prompt, content=prompt)
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

    response = result.response or ""
    draft_content = response

    if use_edit_script:
        # #2200: apply the named edits, or halt. There is no fall back to a
        # full redraw -- wholesale regeneration is the defect being removed,
        # so a revision that cannot be expressed as edits stops and names the
        # contract it broke (standard 0028). The prior draft is untouched on
        # disk and stays in state, and a relaunch resumes this stage (#2193).
        prior_draft = state.get("current_draft", "")
        blocks = parse_edit_blocks(response)
        if not blocks:
            return {
                "error_message": _edit_script_halt(
                    "the drafter returned no well-formed SEARCH/REPLACE blocks"
                )
            }

        patched, failures = apply_edit_blocks(prior_draft, blocks)
        if failures:
            return {"error_message": _edit_script_halt("; ".join(failures))}
        if patched == prior_draft:
            return {
                "error_message": _edit_script_halt(
                    f"{len(blocks)} edit block(s) applied but changed nothing"
                )
            }

        # The guard runs BEFORE the draft is saved, so a lossy revision never
        # becomes the working copy and is never discovered downstream by
        # mechanical validation.
        removed = removed_required_sections(prior_draft, patched, template)
        if removed:
            return {
                "error_message": _edit_script_halt(
                    f"the edits would remove template-required section(s) "
                    f"{', '.join(removed)}, which the prior draft carried"
                )
            }

        ratio = unchanged_ratio(prior_draft, patched)
        print(
            f"    [EDIT-SCRIPT] Applied {len(blocks)} edit(s); "
            f"{ratio:.0%} of prior draft preserved byte-identical (#2200)"
        )
        draft_content = patched

    # Issue #775: Use structured parse for open questions extraction (REQ-1, REQ-2).
    # parse_structured_draft_questions tries JSON first, falls back to regex.
    # #2200: scans the document, so on the edit path it must see the patched
    # draft rather than the edit blocks that produced it.
    dq_result = _extract_open_questions(drafter, draft_content, system_prompt)
    open_questions = dq_result["open_questions"]

    # Save to audit trail
    iteration_count = state.get("iteration_count", 0) + 1
    file_num = next_file_number(audit_dir)
    if audit_dir.exists():
        draft_path = save_audit_file(audit_dir, file_num, "draft.md", draft_content)
    else:
        draft_path = None

    draft_lines = len(draft_content.splitlines()) if draft_content else 0
    print(f"    Generated {draft_lines} lines")
    if draft_path:
        print(f"    Saved: {draft_path.name}")

    # Issue #248: Pre-review validation gate REMOVED
    # Open questions now proceed to review where Gemini can answer them.
    # The post-review check in review.py handles the loop-back logic.

    # Issue #511: Accumulate per-node cost
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "generate_draft", node_cost_usd,
    )
    node_tokens = accumulate_node_tokens(
        dict(state.get("node_tokens", {})),
        "generate_draft",
        result.input_tokens,
        result.output_tokens,
    )

    return {
        "current_draft": draft_content,
        "current_draft_path": str(draft_path) if draft_path else "",
        "draft_count": draft_count,
        "iteration_count": iteration_count,
        "file_counter": file_num,
        "user_feedback": "",  # Clear feedback after use
        "previous_review_feedback": state.get("current_verdict", ""),  # Issue #486: Save for two-strike
        "previous_draft": state.get("current_draft", ""),  # Issue #491: Save for diff-aware review
        "validation_errors": [],  # Clear validation errors after use (Issue #294)
        # #2233: the repair request is consumed here. Leaving it set would
        # send the next finalize straight back to this node no matter what
        # finalize decided, and finalize_repair_count is what bounds the loop
        # — so it is deliberately NOT reset.
        "finalize_repair_pending": False,
        "error_message": "",
        "node_costs": node_costs,  # Issue #511
        "node_tokens": node_tokens,  # Issue #511
    }


def build_revision_context(state: RequirementsWorkflowState) -> str:
    """Assemble the feedback a revision must act on.

    Extracted from ``_build_prompt`` by #2200 so the classic revision prompt
    and the edit-script prompt are fed from one place. Behavior is unchanged;
    the assembly order (mechanical errors first, then repository structure,
    the Tiphys interface refresh, the bounded verdict window, and finally
    human feedback) is preserved exactly as the issues that added each piece
    established it.

    Args:
        state: Current workflow state.

    Returns:
        Markdown feedback block, empty when there is nothing to say.
    """
    current_draft = state.get("current_draft", "")
    verdict_history = state.get("verdict_history", [])
    user_feedback = state.get("user_feedback", "")
    validation_errors = state.get("validation_errors", [])

    revision_context = ""

    # Issue #294: Include mechanical validation errors FIRST (highest priority)
    # Issue #339: Include repo structure so drafter knows what directories exist
    # #2233: finalize's own errors arrive on the same channel, so say which
    # gate spoke. The document reaching a finalize repair has already passed
    # mechanical and test-plan validation and usually carries an APPROVED
    # verdict; telling the model it failed "mechanical validation" invites it
    # to go looking for structural faults that are not there.
    finalize_repair = bool(state.get("finalize_repair_pending"))
    if validation_errors:
        if finalize_repair:
            revision_context += "## FINALIZE VALIDATION ERRORS (MUST FIX FIRST)\n\n"
            revision_context += (
                "This document has already passed structural and test-plan "
                "validation and been reviewed. It is blocked only by the "
                "final gate below. Fix exactly these errors and change "
                "nothing else:\n\n"
            )
        else:
            revision_context += "## MECHANICAL VALIDATION ERRORS (MUST FIX FIRST)\n\n"
            revision_context += "The following errors were found by automated validation. "
            revision_context += "These MUST be fixed before the LLD can proceed:\n\n"
        for error in validation_errors:
            revision_context += f"- **ERROR:** {error}\n"
        revision_context += "\n"

        # Issue #339: Show actual repo structure so drafter can use real paths
        # Issue #490: Use cached repo_structure from state, fallback to inline call
        # #2233: skipped on a finalize repair — the repo dump exists to fix
        # bad file paths in Section 2.1, which this document's paths already
        # cleared, so here it is a large prompt for a question nobody asked.
        if not finalize_repair:
            target_repo = state.get("target_repo", "")
            if target_repo:
                repo_structure = state.get("repo_structure") or get_repo_structure(target_repo)
                revision_context += "## ACTUAL REPOSITORY STRUCTURE\n\n"
                revision_context += "**Use ONLY these existing directories** (or explicitly Add new ones):\n\n"
                revision_context += f"```\n{repo_structure}\n```\n\n"
                revision_context += "**To add files in a NEW directory:**\n"
                revision_context += "1. First add the directory itself with Change Type: `Add (Directory)`\n"
                revision_context += "2. Then add files inside it with Change Type: `Add`\n\n"
            else:
                revision_context += "**CRITICAL:** Check that all file paths in Section 2.1 are correct:\n"
                revision_context += "- 'Modify' files MUST exist in the repository\n"
                revision_context += "- 'Add' files must have existing parent directories\n"
                revision_context += "- Use actual file names from the codebase, not generic names\n\n"

    # Tiphys (#1688): revision feedback loop — the draft's own Files
    # Changed table declares the change's actual blast radius; refresh
    # signatures for exactly those files (plus one-hop imports). Any
    # draft-one selection miss becomes a one-iteration transient. Falls
    # back to the N0b-computed map when the table yields nothing.
    refreshed_map: dict = {}
    revision_target_repo = state.get("target_repo", "")
    if revision_target_repo and current_draft:
        try:
            entries, _parse_errors = parse_files_changed_table(current_draft)
            draft_paths = [
                e.get("path", "") for e in entries
                if e.get("path", "").endswith(".py")
            ]
            if draft_paths:
                refreshed_map = build_interface_map_for_paths(
                    draft_paths, Path(revision_target_repo)
                )
        except Exception:  # noqa: BLE001 — Tiphys must never block revision
            logger.warning("Tiphys revision refresh failed", exc_info=True)
    interface_section = format_interface_map_section(
        refreshed_map or state.get("interface_map") or {}
    )
    if interface_section:
        revision_context += interface_section + "\n\n"

    # Issue #497: Bounded feedback window replaces cumulative verdict history
    if verdict_history:
        window = build_feedback_block(verdict_history)
        feedback_section = render_feedback_markdown(window)
        if feedback_section:
            revision_context += feedback_section + "\n\n"

    if user_feedback:
        revision_context += f"## Additional Human Feedback\n\n{user_feedback}\n\n"

    return revision_context


def _build_prompt(
    state: RequirementsWorkflowState,
    template: str,
    workflow_type: str,
) -> str:
    """Build prompt for drafter based on workflow type and revision state.

    Args:
        state: Current workflow state.
        template: Template content.
        workflow_type: Either "issue" or "lld".

    Returns:
        Complete prompt string.
    """
    current_draft = state.get("current_draft", "")
    verdict_history = state.get("verdict_history", [])
    user_feedback = state.get("user_feedback", "")
    validation_errors = state.get("validation_errors", [])  # Issue #294

    # Revision detection, computed early: Tiphys injection placement depends
    # on it (Issue #294 originally defined this after input assembly).
    is_revision = bool(
        current_draft and (verdict_history or validation_errors or user_feedback)
    )

    if workflow_type == "issue":
        input_content = state.get("brief_content", "")
        input_label = "Brief (user's ideation notes)"
    else:
        issue_number = state.get("issue_number", 0)
        # #2234: the template's title slot already reads "Feature: {Title}", so
        # an issue titled "feat: configuration file" produced
        # "Feature: feat: configuration file" on every draft. The label is the
        # template's to supply; the conventional-commit type is the commit
        # convention's and carries nothing the drafter needs.
        issue_title = strip_conventional_commit_prefix(state.get("issue_title", ""))
        issue_body = state.get("issue_body", "")
        context_content = state.get("context_content", "")

        # CRITICAL: Explicitly include issue number to prevent LLM confusion
        input_content = f"# Issue #{issue_number}: {issue_title}\n\n{issue_body}"
        if context_content:
            input_content += f"\n\n## Context\n\n{context_content}"

        # Tiphys (#1688): real interface surface, placed BEFORE the
        # codebase-context sections — _truncate_prompt sacrifices those
        # first under token pressure, and ground truth that exists to
        # prevent hallucination must not be the first thing dropped. On
        # revision passes the refreshed surface rides in revision_context
        # instead — never both.
        if not is_revision:
            interface_section = format_interface_map_section(
                state.get("interface_map") or {}
            )
            if interface_section:
                input_content += f"\n\n{interface_section}"

        # Issue #401: Inject codebase context from N0b analyze_codebase node
        codebase_ctx = state.get("codebase_context")
        if codebase_ctx and isinstance(codebase_ctx, dict):
            codebase_section = _format_codebase_context(codebase_ctx)
            if codebase_section:
                input_content += f"\n\n{codebase_section}"

        input_content += f"\n\n**CRITICAL: This LLD is for GitHub Issue #{issue_number}. Use this exact issue number in all references.**"
        input_label = f"GitHub Issue #{issue_number}"

    # is_revision computed above, before input assembly (Issue #294 origin;
    # moved for Tiphys injection placement).
    if is_revision:
        # Revision mode. #2200 extracted the context assembly so the
        # edit-script path feeds the drafter exactly the same feedback this
        # prompt does; two assemblies would drift.
        revision_context = build_revision_context(state)

        # Issue #489: Try section-level revision for focused changes
        targeted = ""
        all_feedback = revision_context
        if verdict_history:
            latest_verdict = verdict_history[-1] if verdict_history else ""
            draft_sections = extract_sections(current_draft)
            changed = identify_changed_sections(latest_verdict, draft_sections)
            if changed:
                targeted = build_targeted_prompt(
                    sections=draft_sections,
                    changed_headings=changed,
                    template=template,
                    feedback=all_feedback,
                )

        if targeted:
            prompt = f"""IMPORTANT: Output ONLY the markdown content. Start with # title. No preamble.

{targeted}

## Original {input_label}
{input_content}

CRITICAL REVISION INSTRUCTIONS:
1. Fix ALL mechanical validation errors FIRST (invalid file paths, missing sections)
2. Implement EVERY change requested by feedback
3. PRESERVE sections marked [UNCHANGED] exactly as-is
4. ONLY modify sections marked [REVISE]
5. Keep ALL template sections intact

Revise the draft to address ALL feedback above.
START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."""
        else:
            # Issue #499: On iteration 3+, replace static sections with
            # skeleton references to reduce token waste. The current draft
            # already contains the full structure from the template + input.
            draft_count_now = state.get("draft_count", 0) + 1
            if draft_count_now >= 3:
                # Skeleton: just the issue reference, not full body
                skeleton_input = f"[See {input_label} — unchanged from iteration 1. Issue #{state.get('issue_number', 0)}: {state.get('issue_title', '')}]"
                skeleton_template = "[Template structure unchanged — already embedded in the current draft. Preserve all section headings.]"
                prompt = f"""IMPORTANT: Output ONLY the markdown content. Start with # title. No preamble.

{revision_context}## Current Draft (to revise)
{current_draft}

## Original {input_label}
{skeleton_input}

## Template (REQUIRED STRUCTURE)
{skeleton_template}

CRITICAL REVISION INSTRUCTIONS:
1. Fix ALL mechanical validation errors FIRST (invalid file paths, missing sections)
2. Implement EVERY change requested by Gemini feedback
3. PRESERVE sections that weren't flagged
4. ONLY modify sections that need changes
5. Keep ALL template sections intact — the draft already has the correct structure

Revise the draft to address ALL feedback above.
START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."""
            else:
                prompt = f"""IMPORTANT: Output ONLY the markdown content. Start with # title. No preamble.

{revision_context}## Current Draft (to revise)
{current_draft}

## Original {input_label}
{input_content}

## Template (REQUIRED STRUCTURE)
{template}

CRITICAL REVISION INSTRUCTIONS:
1. Fix ALL mechanical validation errors FIRST (invalid file paths, missing sections)
2. Implement EVERY change requested by Gemini feedback
3. PRESERVE sections that weren't flagged
4. ONLY modify sections that need changes
5. Keep ALL template sections intact

Revise the draft to address ALL feedback above.
START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."""

    else:
        # Initial draft mode
        # Issue #389: Include repo structure so drafter uses real paths
        # Issue #490: Use cached repo_structure from state, fallback to inline call
        repo_context = ""
        target_repo = state.get("target_repo", "")
        if target_repo:
            repo_structure = state.get("repo_structure") or get_repo_structure(target_repo)
            repo_context = f"""## TARGET REPOSITORY STRUCTURE

**Use ONLY these existing directories** (or explicitly Add new ones in Section 2.1):

```
{repo_structure}
```

**To add files in a NEW directory:**
1. First add the directory itself with Change Type: `Add (Directory)`
2. Then add files inside it with Change Type: `Add`

"""

        prompt = f"""IMPORTANT: Output ONLY the markdown content. Start with # title. No preamble.

## {input_label}
{input_content}

{repo_context}## Template (follow this structure)
{template}

Create a complete document following the template structure.
START YOUR RESPONSE WITH THE # HEADING. NO PREAMBLE."""

    return prompt


def _format_codebase_context(ctx: dict) -> str:
    """Format CodebaseContext dict into a markdown section for the drafter prompt.

    Issue #401: Converts the structured codebase analysis into a human-readable
    section that helps the drafter produce grounded LLDs.

    Args:
        ctx: CodebaseContext dict from analyze_codebase node.

    Returns:
        Formatted markdown string, or empty string if context is empty.
    """
    parts: list[str] = []

    project_desc = ctx.get("project_description", "")
    if project_desc:
        parts.append(f"## Codebase Analysis\n\n{project_desc}")

    conventions = ctx.get("conventions", [])
    if conventions:
        conv_lines = "\n".join(f"- {c}" for c in conventions)
        parts.append(f"### Coding Conventions\n\n{conv_lines}")

    # #1816: detected code patterns (scan_patterns output, wired in per
    # #401's original acceptance — "existing code patterns are injected").
    code_patterns = ctx.get("code_patterns", {})
    if code_patterns:
        labels = {
            "naming_convention": "Naming convention",
            "state_pattern": "State management",
            "node_pattern": "Node/function style",
            "test_pattern": "Test framework",
            "import_style": "Import style",
        }
        pattern_lines = "\n".join(
            f"- {labels.get(k, k)}: {v}" for k, v in code_patterns.items()
        )
        parts.append(f"### Detected Code Patterns\n\n{pattern_lines}")

    frameworks = ctx.get("frameworks", [])
    if frameworks:
        fw_lines = "\n".join(f"- {f}" for f in frameworks)
        parts.append(f"### Frameworks & Libraries\n\n{fw_lines}")

    module_structure = ctx.get("module_structure", "")
    if module_structure:
        parts.append(f"### Module Structure\n\n```\n{module_structure}\n```")

    key_excerpts = ctx.get("key_file_excerpts", {})
    if key_excerpts:
        excerpt_parts = []
        for path, content in key_excerpts.items():
            excerpt_parts.append(f"**{path}**:\n```\n{content}\n```")
        parts.append("### Key File Excerpts\n\n" + "\n\n".join(excerpt_parts))

    related_code = ctx.get("related_code", {})
    if related_code:
        related_parts = []
        for path, content in related_code.items():
            related_parts.append(f"**{path}**:\n```\n{content}\n```")
        parts.append("### Related Code\n\n" + "\n\n".join(related_parts))

    dep_summary = ctx.get("dependency_summary", "")
    if dep_summary:
        parts.append(f"### Dependencies\n\n{dep_summary}")

    if not parts:
        return ""

    return "\n\n".join(parts)


def _truncate_prompt(prompt: str) -> str:
    """Truncate an oversized prompt by dropping lowest-priority sections.

    Issue #508: Mirrors the pattern from generate_spec.py. Splits on ## headings,
    drops sections by priority (context/codebase first, then repo structure),
    and hard-truncates as a last resort.

    Args:
        prompt: Oversized prompt string.

    Returns:
        Truncated prompt within MAX_TOTAL_PROMPT_CHARS.
    """
    if len(prompt) <= MAX_TOTAL_PROMPT_CHARS:
        return prompt

    # Split into sections by ## headings
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in prompt.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines)))
            current_heading = line
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, "\n".join(current_lines)))

    # Drop sections by priority (lowest value = drop first)
    drop_order = [
        "Codebase Analysis",
        "Related Code",
        "Key File Excerpts",
        "Dependencies",
        "Coding Conventions",
        "Frameworks",
        "Module Structure",
        "TARGET REPOSITORY STRUCTURE",
        "ACTUAL REPOSITORY STRUCTURE",
        "Context",
    ]

    dropped: list[str] = []
    for keyword in drop_order:
        if len("\n\n".join(s[1] for s in sections)) <= MAX_TOTAL_PROMPT_CHARS:
            break
        sections_new = []
        for heading, body in sections:
            if keyword.lower() in heading.lower():
                dropped.append(heading or keyword)
            else:
                sections_new.append((heading, body))
        sections = sections_new

    result = "\n\n".join(s[1] for s in sections)

    if dropped:
        logger.warning("[N1] Dropped sections to fit cap: %s", dropped)
        print(f"    [WARN] Dropped {len(dropped)} section(s): {', '.join(dropped)}")

    # Hard truncate as last resort
    if len(result) > MAX_TOTAL_PROMPT_CHARS:
        result = result[:MAX_TOTAL_PROMPT_CHARS]
        logger.warning("[N1] Hard-truncated prompt to %d chars", MAX_TOTAL_PROMPT_CHARS)

    return result


def validate_draft_structure(content: str) -> str | None:
    """Check for unresolved open questions in draft.

    Issue #235: Mechanical validation gate to catch structural issues
    before Gemini review.

    Issue #245: Only checks the 'Open Questions' section, ignoring Definition
    of Done and other sections that legitimately have unchecked checkboxes.

    Issue #248: This function is kept for backward compatibility but is NO LONGER
    called in the main generate_draft flow. Open questions now proceed to review
    where Gemini can answer them.

    Args:
        content: Draft content to validate.

    Returns:
        Error message if validation fails, None if passes.
    """
    if not content:
        return None

    # Extract only the Open Questions section
    # Pattern: from "### Open Questions" or "## Open Questions"
    # until the next "##" header or end of document
    pattern = r"(?:^##?#?\s*Open Questions\s*\n)(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        # No Open Questions section found - that's fine
        return None

    open_questions_section = match.group(1)

    # Count unchecked boxes only in this section
    unchecked = re.findall(r"^- \[ \]", open_questions_section, re.MULTILINE)
    if unchecked:
        return f"BLOCKED: {len(unchecked)} unresolved open questions - resolve before review"

    return None