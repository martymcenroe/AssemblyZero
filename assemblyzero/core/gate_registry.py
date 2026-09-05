"""The gate registry: every site that can end a run, named and classified (#2719).

The factory is killed by its own immune system. Counted over boostgauge's 180
run logs on 2026-09-02: 135 ended at a failure banner, and 59 of those were a
gate refusing the drafter's own output (`factory_report.py`, cause-of-death
section). Each gate was added after one death to prevent one bad outcome, and
nothing retired one, because nothing recorded why any of them existed. The
operator's framing: 189 places to say no, fitted to 180 runs. Overtraining.

This module is the map of the maze. It has two halves that keep each other
honest:

**The walker** (`scan_halt_sites`) re-derives the set of halt sites from the
workflow source on every run, by a closed, authored pattern set (§28a: syntax
goes to a parser). A halt site is one of:

* ``raise ImplementationError(...)``
* ``return {..., "error_message": <non-empty>, ...}`` from a node
* ``StageResult(..., error_message=<non-empty>)`` in the orchestrator
* ``refusals.append(...)`` and ``conservation_event=<non-empty>`` in
  revision pinning, which refuse a revision rather than end a run

Each site's identity is ``path::qualname::kind::index`` -- no line number, so
an unrelated edit above the site does not churn it (the fail-open audit's
scheme, #2475).

**The registry** (`GATE_REGISTRY`) is the authored table: one row per gate,
naming the sites it covers, the stage it runs in, what it judges, what it does
today, the issue that created it, and the run that justified it. The CI test
asserts the two halves agree in both directions: every walked site names a
row (no unregistered gate), and every row's sites exist (no phantom gate).

``judges`` is the column the routing policy (#2723) reads:

* ``model_output`` -- the drafter's own draft, code, or tests
* ``upstream_artifact`` -- an earlier stage's approved artifact (the LLD, the
  spec, the test plan): this stage cannot revise it
* ``issue_body`` -- the operator's issue text
* ``budget`` -- a spending limit: money, wall clock, rounds, iterations
* ``infrastructure`` -- the environment: files, git, gh, credentials, a
  transport that did not answer
* ``operator`` -- a human gate waiting on a person

``action`` is what the gate DOES today, not what it should do. Under the
routing policy a gate that judges model output may only ``revise``; today
nearly all of them ``halt``, and the ratchet (#2720) is what stops that count
rising while it is being brought down.

Python, not YAML: the walker, the ratchet, and the routing policy all import
this table (operator ruling, 2026-09-02).
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

JUDGES_MODEL_OUTPUT = "model_output"
JUDGES_UPSTREAM = "upstream_artifact"
JUDGES_ISSUE_BODY = "issue_body"
JUDGES_BUDGET = "budget"
JUDGES_INFRASTRUCTURE = "infrastructure"
JUDGES_OPERATOR = "operator"
#: The orchestrator relaying a halt a sub-workflow already decided. Not a
#: gate of its own; listed so the walker's site is named and not double
#: counted as a second death.
JUDGES_RELAY = "relay"
JUDGES: tuple[str, ...] = (
    JUDGES_MODEL_OUTPUT,
    JUDGES_UPSTREAM,
    JUDGES_ISSUE_BODY,
    JUDGES_BUDGET,
    JUDGES_INFRASTRUCTURE,
    JUDGES_OPERATOR,
    JUDGES_RELAY,
)

ACTION_HALT = "halt"
ACTION_REVISE = "revise"
ACTION_ADVISE = "advise"
ACTIONS: tuple[str, ...] = (ACTION_HALT, ACTION_REVISE, ACTION_ADVISE)

STAGES: tuple[str, ...] = ("lld", "spec", "impl", "pr", "orchestrator")

#: The four kinds of halt site the walker recognises. Closed and authored; a
#: new kind is added here deliberately, never discovered.
KIND_RAISE = "raise"
KIND_RETURN = "return"
KIND_STAGE_RESULT = "stage_result"
KIND_REFUSAL = "refusal"
KIND_CONSERVATION = "conservation"
KINDS: tuple[str, ...] = (
    KIND_RAISE, KIND_RETURN, KIND_STAGE_RESULT, KIND_REFUSAL, KIND_CONSERVATION,
)

#: The exception classes a node raises to end a run. ``ValueError`` and
#: ``RuntimeError`` are bugs, not gates, and are deliberately not here.
HALT_EXCEPTIONS: tuple[str, ...] = ("ImplementationError",)

#: The orchestrator reports a stage failure by constructing a `StageResult`,
#: nearly always through its `_make_stage_result` helper. Both are the same
#: site shape.
STAGE_RESULT_CALLS: tuple[str, ...] = ("StageResult", "_make_stage_result")

#: Where the walker looks. The package's workflow tree, orchestrator included.
WALK_SUBDIR = Path("assemblyzero") / "workflows"

#: Appended to a message by `halted()` so the terminal record and the report
#: can join a death to its gate without parsing prose (#2721).
_TAG_RE = re.compile(r"\[gate:([a-z0-9_.]+)\]\s*$")


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    """One row: a named reason a run can end, and the code that does it."""

    key: str
    stage: str
    judges: str
    action: str
    #: The static head of the message the gate emits, as the run log shows it.
    emits: str
    #: Walker site keys this row covers. Empty only for a gate whose halt is
    #: decided outside the walked tree (a router edge, a core budget); such a
    #: row names where in `decided_in`.
    sites: tuple[str, ...] = ()
    decided_in: str = ""
    created_by: str = ""
    justified_by: str = ""
    notes: str = ""


def _s(prefix: str, *indexes: int) -> tuple[str, ...]:
    """``_s("a.py::f::return", 0, 2)`` -> the two site keys, spelled once."""
    return tuple(f"{prefix}::{i}" for i in indexes)


_IS = "assemblyzero/workflows/implementation_spec"
_RQ = "assemblyzero/workflows/requirements"
_TS = "assemblyzero/workflows/testing"
_OR = "assemblyzero/workflows/orchestrator"

#: Authored 2026-09-03 from the walker's 160 sites. `created_by` and
#: `justified_by` are filled where the code itself names the issue or the run;
#: the rest is git archaeology for a later pass and is left empty rather than
#: guessed. `action` is what the gate does TODAY.
GATE_REGISTRY: tuple[Gate, ...] = (
    # ---- lld: the requirements workflow ----------------------------------
    Gate(
        "lld.input_precondition", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "No issue number specified",
        _s(f"{_RQ}/nodes/load_input.py::_load_brief::return", 0, 1, 2)
        + _s(f"{_RQ}/nodes/load_input.py::_load_issue::return", 0, 1)
        + _s(f"{_RQ}/nodes/validate_test_plan.py::validate_test_plan_node::return", 1),
        notes="the brief or issue the run was pointed at is missing or unreadable",
    ),
    Gate(
        "lld.arc_unreadable", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "LLD analysis cannot read the arc",
        _s(f"{_RQ}/nodes/analyze_codebase.py::analyze_codebase::return", 0),
        created_by="#2684",
    ),
    Gate(
        "lld.requirements_unverified", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "the consistency gate did not run",
        _s(f"{_RQ}/nodes/analyze_requirements.py::_halt_unverified::return", 0),
        created_by="#2474", notes="the gate could not reach its model; fail closed",
    ),
    Gate(
        "lld.requirements_conflict", "lld", JUDGES_ISSUE_BODY, ACTION_HALT,
        "REQUIREMENTS CONFLICT",
        _s(f"{_RQ}/nodes/analyze_requirements.py::analyze_requirements::return", 0),
        decided_in=f"{_RQ}/nodes/analyze_requirements.py::_format_conflict_message",
        created_by="#1899",
        notes="29 of 135 banner kills on boostgauge; the fix is an issue-body ruling",
    ),
    Gate(
        "lld.drafter_failed", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Drafter failed",
        _s(f"{_RQ}/nodes/generate_draft.py::generate_draft::return", 0, 3),
    ),
    Gate(
        "lld.preflight", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "[PREFLIGHT] Gemini unavailable",
        _s(f"{_RQ}/nodes/generate_draft.py::generate_draft::return", 1),
    ),
    Gate(
        "lld.invalid_model_config", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Invalid drafter",
        _s(f"{_RQ}/nodes/generate_draft.py::generate_draft::return", 2)
        + _s(f"{_RQ}/nodes/review.py::review::return", 1),
    ),
    Gate(
        "lld.budget.cost", "lld", JUDGES_BUDGET, ACTION_HALT,
        "[BUDGET]",
        _s(f"{_RQ}/nodes/generate_draft.py::generate_draft::return", 4)
        + _s(f"{_RQ}/nodes/review.py::review::return", 3),
    ),
    Gate(
        "lld.step_budget", "lld", JUDGES_BUDGET, ACTION_HALT,
        "budget",
        _s(f"{_RQ}/step_budget.py::invoke_with_budget::return", 0),
        decided_in=f"{_RQ}/step_budget.py::describe_budget_exhaustion",
    ),
    Gate(
        "lld.best_of_n_unusable", "lld", JUDGES_BUDGET, ACTION_HALT,
        "BEST-OF-N: all",
        _s(f"{_RQ}/nodes/generate_draft.py::_generate_best_of_n::return", 0),
        created_by="#2573", justified_by="#2723",
        notes=(
            "budget since #2774 (operator ruling 2026-09-04 on #2723): N "
            "drafts were bought and all N were spent. An (N+1)th draft is the "
            "request that just failed N times, at N drafts per retry"
        ),
    ),
    Gate(
        "lld.edit_script_rejected", "lld", JUDGES_BUDGET, ACTION_HALT,
        "SEARCH/REPLACE",
        _s(f"{_RQ}/nodes/generate_draft.py::generate_draft::return", 5, 6, 7, 8),
        justified_by="#2723",
        notes=(
            "a revision that was not a usable edit script, or that changed "
            "nothing; budget since #2763 (operator ruling 2026-09-04 on "
            "#2723) -- the draft loop re-prompts and the cap is what stops it"
        ),
    ),
    Gate(
        "lld.reviewer_failed", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Reviewer response rejected",
        _s(f"{_RQ}/nodes/review.py::review::return", 0, 2),
    ),
    Gate(
        "lld.mechanical_validation", "lld", JUDGES_BUDGET, ACTION_HALT,
        "MECHANICAL VALIDATION FAILED",
        _s(f"{_RQ}/nodes/validate_mechanical.py::_validate_lld_mechanical_inner::return",
           0, 1, 2, 3, 4),
        justified_by="#2723",
        notes=(
            "15 of 135 banner kills on boostgauge; budget since #2759 "
            "(operator ruling 2026-09-04 on #2723) -- the graph carries "
            "N1_5_validate_mechanical -> N1_generate_draft and the halt is "
            "that loop running out"
        ),
    ),
    Gate(
        "lld.test_plan_validation", "lld", JUDGES_BUDGET, ACTION_HALT,
        "Test plan validation failed after",
        _s(f"{_RQ}/nodes/validate_test_plan.py::validate_test_plan_node::return", 0),
        justified_by="#2723",
        notes=(
            "budget since #2764 (operator ruling 2026-09-04 on #2723) -- the "
            "message's own 'failed after N revision(s)' is the count of "
            "revisions the cap allowed and the drafter spent"
        ),
    ),
    Gate(
        "lld.finalize.issue_creation", "lld", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Failed to create issue",
        _s(f"{_RQ}/nodes/finalize.py::_finalize_issue::return", 0, 1, 2, 3),
    ),
    # ---- spec: the implementation-spec workflow -------------------------
    Gate(
        "spec.input_precondition", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "No issue number provided",
        _s(f"{_IS}/nodes/load_lld.py::load_lld::return", 0, 1, 2)
        + _s(f"{_IS}/nodes/analyze_codebase.py::analyze_codebase::return", 0)
        + _s(f"{_IS}/nodes/human_gate.py::human_gate::return", 0),
    ),
    Gate(
        "spec.lld_not_usable", "spec", JUDGES_UPSTREAM, ACTION_HALT,
        "GUARD: LLD content too short",
        _s(f"{_IS}/nodes/load_lld.py::load_lld::return", 3, 4),
        notes="the LLD is too short or not approved; this stage cannot revise it",
    ),
    Gate(
        "spec.manifest_uncompilable", "spec", JUDGES_UPSTREAM, ACTION_HALT,
        "ASSERTION MANIFEST UNCOMPILABLE",
        _s(f"{_IS}/nodes/compile_manifest.py::compile_assertion_manifest::return", 0),
        created_by="#2533",
    ),
    Gate(
        "spec.manifest_gate", "spec", JUDGES_UPSTREAM, ACTION_HALT,
        "ASSERTION MANIFEST GATE",
        _s(f"{_IS}/nodes/compile_manifest.py::manifest_gate::return", 0),
        created_by="#2533",
    ),
    Gate(
        "spec.finalize.draft_guard", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "GUARD: Cannot finalize empty spec draft",
        _s(f"{_IS}/nodes/finalize_spec.py::finalize_spec::return", 0, 1),
        justified_by="#2723",
        notes=(
            "infrastructure since #2772 (operator ruling 2026-09-04 on "
            "#2723): a guard against an impossible state, not a gate on the "
            "drafter. By this node the draft has passed completeness "
            "validation and earned an APPROVED verdict, so an empty draft "
            "means something upstream lied -- and an empty draft has no span "
            "for a revision to cite. Sibling of spec.finalize.precondition "
            "in the same node, which was already infrastructure"
        ),
    ),
    Gate(
        "spec.finalize.precondition", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "GUARD: Cannot finalize spec with verdict",
        _s(f"{_IS}/nodes/finalize_spec.py::finalize_spec::return", 2, 3, 4, 5),
    ),
    Gate(
        "spec.drafter_failed", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Drafter failed",
        _s(f"{_IS}/nodes/generate_spec.py::generate_spec::return", 0, 4),
    ),
    Gate(
        "spec.preflight", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "[PREFLIGHT] Gemini unavailable",
        _s(f"{_IS}/nodes/generate_spec.py::generate_spec::return", 1),
    ),
    Gate(
        "spec.invalid_model_config", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Invalid drafter",
        _s(f"{_IS}/nodes/generate_spec.py::generate_spec::return", 2)
        + _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 2),
    ),
    Gate(
        "spec.edit_script_rejected", "spec", JUDGES_BUDGET, ACTION_HALT,
        "[EDIT-SCRIPT] spec revision rejected",
        _s(f"{_IS}/nodes/generate_spec.py::generate_spec::return", 3),
        decided_in=f"{_IS}/nodes/generate_spec.py::_spec_edit_halt",
        justified_by="#2723",
        notes=(
            "the revision's edit blocks did not apply, or pinning refused "
            "every one; budget since #2762 (operator ruling 2026-09-04 on "
            "#2723) -- build_edit_script_prompt re-prompts with the apply "
            "failure before the retry is spent"
        ),
    ),
    Gate(
        "spec.budget.cost", "spec", JUDGES_BUDGET, ACTION_HALT,
        "[BUDGET]",
        _s(f"{_IS}/nodes/generate_spec.py::generate_spec::return", 5)
        + _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 3),
    ),
    Gate(
        "spec.review_ceiling", "spec", JUDGES_BUDGET, ACTION_HALT,
        "Spec review stopped",
        _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 0),
        created_by="#2383",
        notes="the grant's hard ceiling reached inside the node",
    ),
    Gate(
        "spec.review_cap", "spec", JUDGES_BUDGET, ACTION_HALT,
        "Iteration cap:",
        decided_in="assemblyzero/core/halt_node.py::describe_iteration_cap",
        notes=(
            "decided by route_after_review in implementation_spec/graph.py; the "
            "message is synthesized by the halt node from state. 7 of 135 banner "
            "kills on boostgauge; run 11 (run-issue4-183941) is the exhibit"
        ),
    ),
    Gate(
        "spec.review.empty_draft", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "GUARD: Spec draft is empty",
        _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 1),
        justified_by="#2723",
        notes=(
            "infrastructure since #2773 (operator ruling 2026-09-04 on "
            "#2723): a guard against an impossible state. An empty draft has "
            "no span for a revision to cite, and asking the drafter to revise "
            "nothing is regeneration, which #2569 removed from the revision "
            "path. Also saves the paid reviewer call on a draft with no "
            "content"
        ),
    ),
    Gate(
        "spec.reviewer_failed", "spec", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Spec review LLM call failed",
        _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 4),
    ),
    Gate(
        "spec.reviewer_verdict_unreadable", "spec", JUDGES_INFRASTRUCTURE,
        ACTION_HALT,
        "Spec review response yielded no extractable verdict",
        _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 5),
        justified_by="#2723",
        notes=(
            "the reviewer's output, not the drafter's; infrastructure since "
            "#2769 (operator ruling 2026-09-04 on #2723) -- the reviewer did "
            "not answer in the shape it was asked to, which is a transport or "
            "parse failure and not a judgement about the spec"
        ),
    ),
    Gate(
        "spec.review_blocked", "spec", JUDGES_ISSUE_BODY, ACTION_HALT,
        "Spec review BLOCKED",
        _s(f"{_IS}/nodes/review_spec.py::review_spec::return", 6),
        decided_in=f"{_IS}/nodes/review_spec.py::review_spec",
        justified_by="#2723",
        notes=(
            "a BLOCKED verdict; carries the requirements-conflict escalation "
            "too, which is why the report files this row's 5 kills under "
            "spec.requirements_conflict and this key shows 0. issue_body "
            "since #2770 (operator ruling 2026-09-04 on #2723) -- a BLOCKED "
            "verdict is a requirements conflict for the operator to rule on, "
            "and no amount of redrafting fixes a contradiction in the issue"
        ),
    ),
    Gate(
        "spec.requirements_conflict", "spec", JUDGES_ISSUE_BODY, ACTION_HALT,
        "REQUIREMENTS CONFLICT",
        decided_in=f"{_IS}/nodes/review_spec.py::review_spec",
        created_by="#1900",
        notes="the reviewer's escalation marker inside a BLOCKED verdict (spec.review_blocked)",
    ),
    Gate(
        "spec.completeness_cap", "spec", JUDGES_BUDGET, ACTION_HALT,
        "Iteration cap:",
        _s(f"{_IS}/nodes/validate_completeness.py::validate_completeness::return", 0),
        notes="12 of 135 banner kills on boostgauge",
    ),
    Gate(
        "spec.pinning_refusal", "spec", JUDGES_MODEL_OUTPUT, ACTION_REVISE,
        "pinning refusal",
        _s(f"{_IS}/revision_pinning.py::enforce_pinning::refusal", 0),
        created_by="#2532",
        notes="restores the locked span and continues; 145 refusals across 180 runs",
    ),
    Gate(
        "spec.conservation_gate", "spec", JUDGES_MODEL_OUTPUT, ACTION_REVISE,
        "the walked merge",
        _s(f"{_IS}/revision_pinning.py::_conservation_override::conservation", 0, 1, 2),
        created_by="#2559",
        notes="emits the revision unenforced or the previous draft; never halts",
    ),
    # ---- impl: the testing workflow --------------------------------------
    Gate(
        "impl.input_precondition", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "No issue number provided",
        _s(f"{_TS}/nodes/load_lld.py::load_lld::return", 0, 2)
        + _s(f"{_TS}/nodes/load_lld.py::_load_from_issue::return", 0, 1, 2, 3),
    ),
    Gate(
        "infra.missing_spec", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "no implementation spec found",
        _s(f"{_TS}/nodes/load_lld.py::load_lld::return", 1),
    ),
    Gate(
        "impl.lld_not_usable", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "GUARD: LLD content too short",
        _s(f"{_TS}/nodes/load_lld.py::load_lld::return", 3),
    ),
    Gate(
        "impl.no_files_to_implement", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "Implementation failed: No files to implement",
        _s(f"{_TS}/nodes/implementation/orchestrator.py::implement_code::return", 0),
    ),
    Gate(
        "impl.path_guard", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "file path(s) in LLD do not match",
        _s(f"{_TS}/nodes/implementation/orchestrator.py::implement_code::return", 1),
        created_by="#445",
    ),
    Gate(
        "impl.api_error", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "API error after",
        _s(f"{_TS}/nodes/implementation/orchestrator.py::generate_file_with_retry::raise", 0, 1),
        created_by="#2423",
    ),
    Gate(
        "impl.file_generation_failed", "impl", JUDGES_BUDGET, ACTION_HALT,
        "FATAL: Failed to implement",
        _s(f"{_TS}/nodes/implementation/orchestrator.py::generate_file_with_retry::raise",
           2, 3, 4, 5),
        decided_in=f"{_TS}/nodes/implementation/claude_client.py::ImplementationError",
        justified_by="#2723",
        notes=(
            "a summary instead of code, no code block, or validation failed, "
            "N times; budget since #2760 (operator ruling 2026-09-04 on "
            "#2723) -- generate_file_with_retry re-prompts with the "
            "validation error up to MAX_FILE_RETRIES and raises only after"
        ),
    ),
    Gate(
        "impl.modify_target_missing", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "File marked as 'Modify' but does not exist",
        _s(f"{_TS}/nodes/implementation/orchestrator.py::implement_code::raise", 0),
    ),
    Gate(
        "impl.context_too_large", "impl", JUDGES_BUDGET, ACTION_HALT,
        "Context too large",
        _s(f"{_TS}/nodes/implementation/orchestrator.py::implement_code::raise", 1),
    ),
    Gate(
        "impl.path_enforcement", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "is not in the LLD's Section 2.1 list",
        decided_in="assemblyzero/hooks/file_write_validator.py::path_advisory",
        created_by="#188",
        justified_by="#2736",
        notes=(
            "advisory since #2736 (operator ruling 2026-09-04): the LLD's file "
            "list is a plan, not a contract. It refused four of issue #4's "
            "seventeen shipped files on boostgauge main, three of them tests"
        ),
    ),
    Gate(
        "impl.write_failed", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Failed to write file",
        # Index 2, not 3: #2736 retired the path-enforcement raise above this
        # one in the same function, and a site index is positional (#2738).
        _s(f"{_TS}/nodes/implementation/orchestrator.py::implement_code::raise", 2),
    ),
    Gate(
        "impl.scenario_ratio_guard", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "GUARD: Mechanical pre-checks failed",
        _s(f"{_TS}/nodes/review_test_plan.py::review_test_plan::return", 0),
        notes="judges the LLD's test plan; see #2675 for moving it into the spec stage",
    ),
    Gate(
        "impl.invalid_model_config", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Invalid reviewer",
        _s(f"{_TS}/nodes/review_test_plan.py::review_test_plan::return", 1)
        + _s(f"{_TS}/nodes/revise_test_plan.py::revise_test_plan::return", 1),
    ),
    Gate(
        "impl.reviewer_failed", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Reviewer failed after up to",
        _s(f"{_TS}/nodes/review_test_plan.py::review_test_plan::return", 2, 3),
    ),
    Gate(
        "impl.reviewer_verdict_unreadable", "impl", JUDGES_INFRASTRUCTURE,
        ACTION_HALT,
        "Test-plan reviewer response rejected",
        _s(f"{_TS}/nodes/review_test_plan.py::review_test_plan::return", 4),
        justified_by="#2723",
        notes=(
            "the reviewer's output, not the drafter's; infrastructure since "
            "#2768 (operator ruling 2026-09-04 on #2723) -- there is nobody "
            "to ask for a revision, because the drafter did not write the "
            "verdict that could not be read"
        ),
    ),
    Gate(
        "impl.test_plan_no_requirements", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "Test plan revision blocked: no requirements",
        _s(f"{_TS}/nodes/revise_test_plan.py::revise_test_plan::return", 0),
    ),
    Gate(
        "impl.revisor_failed", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Test plan revision LLM call failed",
        _s(f"{_TS}/nodes/revise_test_plan.py::revise_test_plan::return", 2),
    ),
    Gate(
        "impl.test_plan_revision_incomplete", "impl", JUDGES_BUDGET, ACTION_HALT,
        "Test plan revision budget spent",
        _s(f"{_TS}/nodes/revise_test_plan.py::revise_test_plan::return", 3),
        justified_by="#2775",
        notes=(
            "budget since #2775 (ruling 1 of #2723). It judged model output "
            "only because it fired on the FIRST short revision: the return "
            "recorded a reason, and since #2793 a recorded reason routes to "
            "HALT, so route_after_review never reached its revise branch and "
            "MAX_REVISION_CYCLES was unreachable from this site -- the "
            "cap was dead code. The site now records no reason under the cap "
            "and the N1 <-> N1.5 loop runs; what is left here is the "
            "allowance running out, which is a budget"
        ),
    ),
    Gate(
        "impl.no_test_files", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "No test",
        _s(f"{_TS}/nodes/scaffold_tests.py::scaffold_tests::return", 0)
        + _s(f"{_TS}/nodes/verify_phases.py::verify_red_phase::return", 0, 1)
        + _s(f"{_TS}/nodes/verify_phases.py::_verify_red_non_pytest::return", 0),
        notes=(
            "no scenarios, no test files, or the named file is not on disk. "
            "Lost a fifth site in #2753 when the unreachable run_tests node "
            "was retired; the four here are live"
        ),
    ),
    # #2753: `impl.test_file_validation` and `impl.test_execution_failed`
    # stood here until 2026-09-04. Every site either row named lived in
    # `testing/nodes/run_tests.py`, a node no graph ever declared. `git log`
    # gives one commit for that file, 52992973 (#381, the multi-framework
    # runner), which added `run_tests` and `check_coverage` as nodes and
    # wired neither; `git log -S run_tests -- testing/graph.py` is empty, so
    # it was never wired rather than unwired later. The runner abstraction
    # those nodes were meant to sit on shipped and is live -- called directly
    # from `verify_red_phase` and `verify_green_phase`.
    #
    # Retired with the node. A row whose `action` column describes code that
    # cannot execute is a promise about nothing, and these two were counted
    # as protection for six months.
    #
    # The structural check the first row was NAMED for is alive at N2.5,
    # `validate_tests_mechanical.validate_test_structure`. Its live
    # consequence is `impl.scaffold_suite_invalid`, which is what the
    # answer-key audit labels those verdicts as of this change.
    Gate(
        "impl.completeness_gate_zero_requirements", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "Completeness gate: cannot certify",
        _s(f"{_TS}/nodes/completeness_gate.py::completeness_gate::return", 0),
        created_by="#2552",
    ),
    Gate(
        "impl.coverage_unreadable", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "COVERAGE MEASUREMENT FAILED",
        _s(f"{_TS}/nodes/augment_tests.py::augment_tests_for_coverage::return", 0)
        + _s(f"{_TS}/nodes/verify_phases.py::verify_green_phase::return", 1),
        decided_in=f"{_TS}/coverage_report.py",
        notes="a harness defect, never a test gap; see #2690's mapping",
    ),
    Gate(
        "impl.e2e_safety_limit", "impl", JUDGES_BUDGET, ACTION_HALT,
        "GUARD: E2E safety limit exceeded",
        _s(f"{_TS}/nodes/e2e_validation.py::e2e_validation::return", 0),
    ),
    Gate(
        "impl.e2e_error", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "E2E validation error",
        _s(f"{_TS}/nodes/e2e_validation.py::e2e_validation::return", 1),
    ),
    Gate(
        "impl.stagnation.e2e", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "E2E stagnant",
        decided_in=f"{_TS}/nodes/e2e_validation.py::e2e_validation (advisory)",
        created_by="#2723",
        notes="advises via advised(); the e2e cap and circuit breaker end this loop",
    ),
    Gate(
        "impl.e2e_cap", "impl", JUDGES_BUDGET, ACTION_HALT,
        "E2E failed after",
        _s(f"{_TS}/nodes/e2e_validation.py::e2e_validation::return", 3),
    ),
    Gate(
        "impl.circuit_breaker", "impl", JUDGES_BUDGET, ACTION_HALT,
        "[CIRCUIT]",
        _s(f"{_TS}/nodes/e2e_validation.py::e2e_validation::return", 2)
        + _s(f"{_TS}/nodes/verify_phases.py::verify_green_phase::return", 5, 7)
        + _s(f"{_TS}/nodes/verify_phases.py::_verify_green_non_pytest::return", 2, 4),
        decided_in=f"{_TS}/circuit_breaker.py::check_circuit_breaker",
    ),
    Gate(
        "impl.green_phase_stopped", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Green phase stopped",
        _s(f"{_TS}/nodes/verify_phases.py::verify_green_phase::return", 0),
        notes="pytest exit 2 or 3: interrupted or an internal error",
    ),
    Gate(
        "impl.red_phase_stopped", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Red phase stopped",
        _s(f"{_TS}/nodes/verify_phases.py::verify_red_phase::return", 2),
    ),
    Gate(
        "impl.red.import_errors", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "Red phase detected",
        decided_in=f"{_TS}/nodes/verify_phases.py::verify_red_phase",
        created_by="#842", justified_by="#2766",
        notes=(
            "advisory since #2766. It never fired in the 180-run window, and "
            "it could have: with no parseable Section 2.1 the expected set is "
            "empty and EVERY red-phase import error is 'unexpected', which is "
            "the phase's normal state. Two reasons it advises. Its inference "
            "is #2736's overturned one -- 'unexpected' means 'not in the LLD "
            "file plan', and the plan is a plan, not a contract, which is why "
            "impl.path_enforcement already advises. And its own halt was "
            "unintended: the return set next_node='N4_implement_code' beside "
            "error_message, route_after_red reads the error first, so the "
            "route was dead. Falling through reaches N4 anyway, because the "
            "import errors satisfy the red phase"
        ),
    ),
    # #2761 (operator ruling 2026-09-04): one row named two different things,
    # and the report could not say which of its kills was which. Split, and
    # the code's own message decides each half's owner.
    #
    # This split is the authorised rise: `halt_rows_per_stage['impl']` goes
    # 34 -> 35. No new place can stop a run -- halt SITES are unchanged,
    # both returns already existed -- and the model-output count is unchanged
    # too, because one half leaves the category as the other keeps it.
    Gate(
        "impl.red.preexisting_implementation", "impl", JUDGES_INFRASTRUCTURE,
        ACTION_HALT,
        # Found in the site's own static head, not by the `decided_in`
        # file-wide fallback: the old row's emits was the bare token, which
        # lives in validate_tests_mechanical.py and so matched a file rather
        # than a return. That is the weakness #2776 is about.
        "tests passed unexpectedly, and neither a red-entry marker",
        # Index 3 since #2766, which was 4 until the import-errors return
        # above it stopped recording a reason and left the walker's count.
        #
        # The non-pytest site joined in #2796, and `emits` above is carried
        # by the PYTEST site's own head rather than by the file-wide
        # `decided_in` fallback. That matters: the non-pytest message says
        # something deliberately different, because that path does not
        # perform the marker-and-prior-writes check this text describes. It
        # is registered here for what it concludes -- the worktree's state,
        # deterministic on an unchanged tree -- not for how it got there.
        _s(f"{_TS}/nodes/verify_phases.py::verify_red_phase::return", 3)
        + _s(f"{_TS}/nodes/verify_phases.py::_verify_red_non_pytest::return", 2),
        decided_in=f"{_TS}/nodes/verify_phases.py::verify_red_phase",
        created_by="#2337", justified_by="#2761",
        notes=(
            "infrastructure by the #2761 ruling, and the message says why: "
            "'neither a red-entry marker nor this run's own prior writes "
            "explain them -- the implementation existed before this stage "
            "entered'. That is the state of the worktree the stage was "
            "handed, not something the drafter wrote. Deterministic on an "
            "unchanged tree, which is why it carries the token and is not "
            "retried. Both recorded kills are here: run-issue331 on the "
            "pre-#2337 message, run-issue379 on this one"
        ),
    ),
    Gate(
        "impl.deterministic_failure", "impl", JUDGES_MODEL_OUTPUT, ACTION_HALT,
        # This one still needs the `decided_in` fallback, and it is worth
        # saying why: the return is `f"{DETERMINISTIC_FAILURE}: {message}"`,
        # so its static head is literally "{}: {}" and carries no text at
        # all. `decided_in` now names the function that composes the message
        # rather than the module that defines the token, which is the honest
        # pointer and the narrowest the check can currently be given.
        "Test(s) failing for a reason no implementation can fix",
        _s(f"{_TS}/nodes/verify_phases.py::verify_green_phase::return", 4),
        decided_in=f"{_TS}/nodes/verify_phases.py::verify_green_phase",
        justified_by="#2761",
        notes=(
            "model_output by the #2761 ruling, and the message says that too "
            "-- 'The TEST is the wrong side here, fix or remove it'. N4c "
            "generated the test; a platform error is how the defect shows, "
            "not whose it is. Zero kills in the 180-run window. Keeps the "
            "key because the answer-key audit's stub count reports under it, "
            "and a hollow test and an unsatisfiable one are one family: a "
            "test no implementation can make pass"
        ),
    ),
    Gate(
        "impl.scaffold_suite_invalid", "impl", JUDGES_UPSTREAM, ACTION_HALT,
        "the generated test suite cannot be",
        decided_in=f"{_TS}/nodes/validate_tests_mechanical.py",
        notes=(
            "the spec's own test functions were stubs or used phantom fixtures; "
            "decided by route_after_validate in testing/graph.py. Run 8 "
            "(run-issue4-163140) is the exhibit; #2706 and #2707 moved the check "
            "into the spec stage where it is revisable"
        ),
    ),
    # #2796: `impl.red_phase_failed` stood here until 2026-09-04. It ended
    # with one site, the non-pytest unexpected-pass return, after #2767 turned
    # the two 'no tests collected' returns into a bounded reroute. That site
    # now carries the DETERMINISTIC_FAILURE token and is registered under
    # `impl.red.preexisting_implementation` above, beside the pytest return
    # that reaches the same conclusion -- so the row has no site left and is
    # retired rather than kept as a name for nothing.
    #
    # The retirement is a fall the ratchet should read carefully. No gate
    # softened: the site still halts, and it halts for the same reason. What
    # changed is which row owns it and what the run log says about it, and
    # the model-output count drops because the owning row judges the state of
    # the worktree the stage was handed -- infrastructure -- rather than
    # anything the drafter wrote.
    #
    # What this does NOT do is teach that path to tell a resumable case from
    # a fatal one; the port that would is filed as its own issue, blocked on
    # a framework-to-source-extension table this repo does not have.
    Gate(
        "impl.green.collection_broken", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "collected 0 tests",
        _s(f"{_TS}/nodes/verify_phases.py::verify_green_phase::return", 2),
        created_by="#2546", justified_by="#2723",
        notes=(
            "infrastructure since #2765 (operator ruling 2026-09-04 on "
            "#2723): pytest collecting nothing is a broken suite -- an import "
            "error, a syntax error, a file pytest cannot see -- not a failing "
            "one. Worth keeping either way: a suite that collects zero tests "
            "trivially passes and would otherwise read as green"
        ),
    ),
    Gate(
        "impl.green.iteration_cap", "impl", JUDGES_BUDGET, ACTION_HALT,
        "Green phase failed after",
        _s(f"{_TS}/nodes/verify_phases.py::verify_green_phase::return", 3, 6)
        + _s(f"{_TS}/nodes/verify_phases.py::_verify_green_non_pytest::return", 1, 3),
    ),
    Gate(
        "impl.stagnation.test_count", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "Test count stagnant",
        decided_in=(
            f"{_TS}/nodes/verify_phases.py::verify_green_phase and "
            f"::_verify_green_non_pytest (advisory)"
        ),
        created_by="#2723",
        notes=(
            "11 of 135 banner kills on boostgauge before it became advisory; "
            "the iteration cap and circuit breaker end this loop"
        ),
    ),
    Gate(
        "impl.stagnation.test_identity", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "Test identity stagnant",
        decided_in=f"{_TS}/nodes/verify_phases.py::verify_green_phase (advisory)",
        created_by="#2723",
        notes="the frozen-tests symmetry break below it still routes to N4",
    ),
    Gate(
        "impl.stagnation.coverage", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "Coverage stagnant",
        decided_in=(
            f"{_TS}/nodes/verify_phases.py::verify_green_phase and "
            f"::_verify_green_non_pytest (advisory)"
        ),
        created_by="#2711",
        justified_by="run-issue4-172600",
        notes=(
            "11 of 135 banner kills on boostgauge. Killed run 9, the furthest run "
            "in the record (green, 3 passed, 72%), with four iterations unspent. "
            "Advisory since #2723"
        ),
    ),
    Gate(
        "impl.stagnation.full_suite", "impl", JUDGES_MODEL_OUTPUT, ACTION_ADVISE,
        "Full suite regression stagnant",
        decided_in=f"{_TS}/nodes/verify_phases.py::verify_green_phase (advisory)",
        created_by="#2723",
        notes="the route below it already sends the named regressions back to N4",
    ),
    Gate(
        "impl.runner_unavailable", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Runner unavailable",
        _s(f"{_TS}/nodes/verify_phases.py::_verify_red_non_pytest::return", 1)
        + _s(f"{_TS}/nodes/verify_phases.py::_verify_green_non_pytest::return", 0),
    ),
    Gate(
        "impl.branch_exists", "impl", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "already exists and carries",
        decided_in=f"{_OR}/stages.py::run_impl_stage",
        notes="raised as RuntimeError inside the impl stage; wrapped as 'Implementation stage error'",
    ),
    # ---- pr ----------------------------------------------------------------
    # #2787: `pr.commit_message_guard` stood here until 2026-09-04, and it was
    # the ONLY row in this stage -- the `pr: 1` the ratchet carried was this
    # row and nothing else. Both its sites lived in
    # `testing/nodes/validate_commit_message.py`, a function no run enters.
    #
    # Measured, not inferred. All four graphs were built and their nodes
    # enumerated -- testing (16), requirements (12), implementation_spec (11),
    # orchestrator (4) -- and none declares a commit-message node. Nothing in
    # `tools/` calls it. The only caller in the package was the answer-key
    # audit, calling it directly to score itself, which is where its
    # "ran 6, refused 0" came from.
    #
    # The repair #2787 proposed -- compute the trailer instead of halting over
    # its absence -- turned out to be the live behaviour already:
    # `orchestrator/stages.py:1814` builds `Closes #{issue_number}` into the
    # PR title and body itself. So the gate could not be repaired into
    # usefulness either: on the only path that exists the trailer is an
    # f-string, not model output, and cannot be missing.
    #
    # Retired on #2753's reasoning, which retired two rows with the unwired
    # `run_tests.py`: a row whose `action` column describes code that cannot
    # execute is a promise about nothing. This one was counted as the pr
    # stage's protection since #190.
    #
    # `test_gate_registry.py`'s reachability probe did not catch it because it
    # asks whether a module is IMPORTABLE from a built graph, not whether a
    # node calls it -- the gap #2791 is about, and this is its second exhibit.
    # ---- orchestrator ------------------------------------------------------
    Gate(
        "orchestrator.mock_outward_effects", "orchestrator", JUDGES_INFRASTRUCTURE,
        ACTION_HALT, "mock mode:",
        _s(f"{_OR}/graph.py::_run_stage_node::stage_result", 0),
        notes="a mock roll stops before any stage with outward effects",
    ),
    Gate(
        "orchestrator.human_gate", "orchestrator", JUDGES_OPERATOR, ACTION_HALT,
        "Human gate enabled",
        _s(f"{_OR}/graph.py::_run_stage_node::stage_result", 1),
    ),
    Gate(
        "orchestrator.subworkflow_halted", "orchestrator", JUDGES_RELAY, ACTION_HALT,
        "workflow halted before finalizing",
        _s(f"{_OR}/stages.py::_make_stage_result::stage_result", 0)
        + _s(f"{_OR}/stages.py::run_lld_stage::stage_result", 1)
        + _s(f"{_OR}/stages.py::run_spec_stage::stage_result", 0)
        + _s(f"{_OR}/stages.py::run_impl_stage::stage_result", 1)
        + _s(f"{_OR}/stages.py::run_cleanup_stage::stage_result", 0),
        created_by="#2677",
        notes="relays a halt a sub-workflow already decided; not a second death",
    ),
    Gate(
        "orchestrator.lld_review_verdict", "orchestrator", JUDGES_OPERATOR, ACTION_HALT,
        "LLD review verdict",
        _s(f"{_OR}/stages.py::run_lld_stage::stage_result", 0),
    ),
    Gate(
        "infra.lld_stage_exception", "orchestrator", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "LLD stage error",
        _s(f"{_OR}/stages.py::run_lld_stage::stage_result", 2),
    ),
    Gate(
        "orchestrator.spec_stage_exception", "orchestrator", JUDGES_INFRASTRUCTURE,
        ACTION_HALT, "Spec stage error",
        _s(f"{_OR}/stages.py::run_spec_stage::stage_result", 1),
    ),
    Gate(
        "orchestrator.impl_stage_exception", "orchestrator", JUDGES_INFRASTRUCTURE,
        ACTION_HALT, "Implementation stage error",
        _s(f"{_OR}/stages.py::run_impl_stage::stage_result", 3),
    ),
    Gate(
        "orchestrator.pr_stage_exception", "orchestrator", JUDGES_INFRASTRUCTURE,
        ACTION_HALT, "PR stage error",
        _s(f"{_OR}/stages.py::run_pr_stage::stage_result", 2),
    ),
    Gate(
        "orchestrator.triage_failed", "orchestrator", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Triage stage: cannot synthesize brief",
        _s(f"{_OR}/stages.py::run_triage_stage::stage_result", 0),
    ),
    Gate(
        "orchestrator.visual.declaration_unreadable", "orchestrator",
        JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "visual-gate declaration unreadable",
        _s(f"{_OR}/stages.py::run_visual_stage::stage_result", 0),
    ),
    Gate(
        "orchestrator.visual.no_deliverable", "orchestrator", JUDGES_INFRASTRUCTURE,
        ACTION_ADVISE, "no visual deliverable declared",
        _s(f"{_OR}/stages.py::run_visual_stage::stage_result", 1),
        notes="a skip with a message, not a halt",
    ),
    Gate(
        "orchestrator.visual_gate_halted", "orchestrator", JUDGES_OPERATOR, ACTION_HALT,
        "visual gate halted",
        _s(f"{_OR}/stages.py::run_visual_stage::stage_result", 2),
        notes="the operator's picture ruling",
    ),
    Gate(
        "impl.worktree_env_provisioning", "orchestrator", JUDGES_INFRASTRUCTURE,
        ACTION_HALT, "Worktree environment provisioning failed",
        _s(f"{_OR}/stages.py::run_impl_stage::stage_result", 0),
    ),
    Gate(
        "infra.worktree", "orchestrator", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "Git worktree error",
        _s(f"{_OR}/stages.py::run_impl_stage::stage_result", 2),
    ),
    Gate(
        "orchestrator.pr.no_worktree", "orchestrator", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "No worktree path available for PR creation",
        _s(f"{_OR}/stages.py::run_pr_stage::stage_result", 0),
    ),
    Gate(
        "infra.pr_creation", "orchestrator", JUDGES_INFRASTRUCTURE, ACTION_HALT,
        "PR creation error",
        _s(f"{_OR}/stages.py::run_pr_stage::stage_result", 1),
    ),
    Gate(
        "budget.ceiling_timeout", "orchestrator", JUDGES_BUDGET, ACTION_HALT,
        "ceiling_timeout",
        decided_in="assemblyzero/core/retry_gate.py",
        created_by="#2423",
        notes="the wall-clock ceiling on one model call; 1 of 180 logs carries it",
    ),
)


# ---------------------------------------------------------------------------
# The walker
# ---------------------------------------------------------------------------


@dataclass
class HaltSite:
    """One place the workflow code can end a run, as the walker found it."""

    path: str
    qualname: str
    kind: str
    index: int
    line: int
    head: str

    @property
    def key(self) -> str:
        return f"{self.path}::{self.qualname}::{self.kind}::{self.index}"


@dataclass
class WalkCoverage:
    """What the walker examined. Counted, never estimated."""

    files_scanned: int = 0
    files_unparseable: list[str] = field(default_factory=list)
    functions_scanned: int = 0


def _static_head(node: ast.AST | None, resolve) -> str:
    """The literal prefix of a message expression, or ``<...>`` when none.

    Reads constants, f-strings (dynamic parts become ``{}``), the left side of
    a concatenation, a name (through `resolve`), and the first literal
    argument of a call. Anything else is reported as its node type so the
    inventory says what it could not read rather than guessing.
    """
    if node is None:
        return "<none>"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
        return "".join(parts)
    if isinstance(node, ast.BinOp):
        return _static_head(node.left, resolve)
    if isinstance(node, ast.Name):
        return resolve(node.id, node.lineno)
    if isinstance(node, ast.Call):
        for arg in node.args:
            head = _static_head(arg, resolve)
            if not head.startswith("<"):
                return head
        for keyword in node.keywords:
            if keyword.arg in ("reason", "message", "msg"):
                return _static_head(keyword.value, resolve)
        return f"<call {ast.unparse(node.func)[:40]}>"
    if isinstance(node, ast.IfExp):
        return _static_head(node.body, resolve)
    if isinstance(node, ast.Subscript):
        return _static_head(node.value, resolve)
    return f"<{type(node).__name__}>"


def _make_resolver(func: ast.AST):
    """Resolve a name at a line to the head of its nearest prior assignment."""
    assigns: dict[str, list[ast.Assign]] = defaultdict(list)
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            assigns[node.targets[0].id].append(node)

    def resolve(name: str, lineno: int, depth: int = 0) -> str:
        if depth > 4:
            return f"<var {name}>"
        before = [a for a in assigns.get(name, []) if a.lineno < lineno]
        if not before:
            return f"<var {name}>"
        nearest = max(before, key=lambda a: a.lineno)

        def inner(name_: str, line: int) -> str:
            return resolve(name_, line, depth + 1)

        head = _static_head(nearest.value, inner)
        if head == "" and len(before) > 1:
            # An initializer (`message = ""`); the real text is the one before.
            others = [a for a in before if a is not nearest]
            head = _static_head(max(others, key=lambda a: a.lineno).value, inner)
        return head

    return resolve


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_empty_string(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == ""


def _sites_in_function(func: ast.AST, rel: str) -> list[tuple[str, int, str]]:
    """(kind, line, head) for every halt site in one function body."""
    resolve = _make_resolver(func)
    found: list[tuple[str, int, str]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            if _call_name(node.exc) in HALT_EXCEPTIONS:
                head = "<none>"
                for keyword in node.exc.keywords:
                    if keyword.arg == "reason":
                        head = _static_head(keyword.value, resolve)
                found.append((KIND_RAISE, node.lineno, head))
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "error_message"
                    and not _is_empty_string(value)
                ):
                    found.append(
                        (KIND_RETURN, node.lineno, _static_head(value, resolve))
                    )
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in STAGE_RESULT_CALLS:
                for keyword in node.keywords:
                    if keyword.arg == "error_message" and not _is_empty_string(
                        keyword.value
                    ):
                        found.append(
                            (
                                KIND_STAGE_RESULT,
                                node.lineno,
                                _static_head(keyword.value, resolve),
                            )
                        )
            if (
                name == "append"
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "refusals"
            ):
                found.append((KIND_REFUSAL, node.lineno, "pinning refusal"))
            for keyword in node.keywords:
                if keyword.arg == "conservation_event" and not _is_empty_string(
                    keyword.value
                ):
                    found.append(
                        (
                            KIND_CONSERVATION,
                            node.lineno,
                            _static_head(keyword.value, resolve),
                        )
                    )
    return found


def scan_halt_sites(
    root: Path, subdir: Path = WALK_SUBDIR
) -> tuple[list[HaltSite], WalkCoverage]:
    """Every halt site under ``root/subdir``, keyed, in path order."""
    coverage = WalkCoverage()
    sites: list[HaltSite] = []
    base = root / subdir
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        try:
            # utf-8-sig: two files in this tree carry a BOM (see the fail-open
            # audit, which found the same).
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (SyntaxError, ValueError, OSError):
            # fail-open: a file that will not parse is recorded in
            # coverage.files_unparseable, which the report prints and the
            # test asserts empty, so the shortfall is carried in the data
            # rather than hidden; the sweep continues so one bad file does
            # not blank the other hundred and eighty-three.
            coverage.files_unparseable.append(rel)
            continue
        coverage.files_scanned += 1
        per_function: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                coverage.functions_scanned += 1
                for kind, line, head in _sites_in_function(node, rel):
                    per_function[(node.name, kind)].append((line, head))
        for (qualname, kind), found in sorted(per_function.items()):
            for index, (line, head) in enumerate(sorted(found)):
                sites.append(HaltSite(rel, qualname, kind, index, line, head))
    return sites, coverage


# ---------------------------------------------------------------------------
# Registry queries
# ---------------------------------------------------------------------------


def registry_by_key(registry: tuple[Gate, ...] = ()) -> dict[str, Gate]:
    return {gate.key: gate for gate in (registry or GATE_REGISTRY)}


def site_to_gate(registry: tuple[Gate, ...] = ()) -> dict[str, str]:
    """site key -> gate key, over the whole registry."""
    mapping: dict[str, str] = {}
    for gate in (registry or GATE_REGISTRY):
        for site in gate.sites:
            mapping[site] = gate.key
    return mapping


def unregistered(
    sites: list[HaltSite], registry: tuple[Gate, ...] = ()
) -> list[HaltSite]:
    """Walked sites no row names. The gate the ratchet exists to catch."""
    known = site_to_gate(registry)
    return [site for site in sites if site.key not in known]


#: Site kinds whose head the WALKER synthesises rather than reads out of the
#: code. `refusal` sites get the literal string "pinning refusal"; it appears
#: in no source file and never will, so a text rule cannot be asked about them.
_SYNTHETIC_HEAD_KINDS: frozenset[str] = frozenset({KIND_REFUSAL, KIND_CONSERVATION})


#: Single-site rows whose site head the WALKER reads wrongly, not rows that
#: are wrong (#2776). Each entry is a defect in `_static_head`, not in the
#: registry, and #2814 is where they get fixed; every one should disappear.
EMITS_HEAD_EXEMPTIONS: dict[str, str] = {
    "impl.deterministic_failure": (
        "the return is f\"{DETERMINISTIC_FAILURE}: {message}\", so the static "
        "head is literally '{}: {}' and carries no text to compare"
    ),
    "spec.review_blocked": (
        "the return interpolates three values and no literal words survive; "
        "head is '{}\\n  exit: {}\\n  {}'"
    ),
    "spec.edit_script_rejected": (
        "the return is _spec_edit_halt(halt_reason), and _static_head takes a "
        "call's first literal ARGUMENT rather than following into the callee, "
        "so it reads the reason ('every edit touched locked content...') "
        "instead of the wrapper's '[EDIT-SCRIPT] spec revision rejected' "
        "prefix. The row is right and the head is wrong"
    ),
}


def mismatched_emits(
    sites: list[HaltSite], registry: tuple[Gate, ...] = ()
) -> list[tuple[str, str, str]]:
    """(gate key, emits, head) where a row's message is not its site's (#2776).

    The two-way check proves every site is named and every name exists.
    Neither notices a row naming the WRONG return: retire a gate, add a return
    at the end, and the surviving row owns a return it has nothing to do with,
    with no phantom to give it away. Only comparing the row's message to THAT
    SITE's head catches it.

    Measured before it was written, because the obvious wider forms do not
    work. Over the whole named set, `emits`-in-head fails 42 of 128 readable
    sites -- a row covering five returns can only name one of their messages.
    A source-text rule (is `emits` written in the function the site is in, or
    in what `decided_in` names) reads 0 of 81 and is therefore worthless HERE:
    both the right and the wrong return live in the same function, so it
    passes the very case this exists to catch. A check that cannot fail on
    its own scenario is the defect, not the guard.

    So: single-site rows only, where `emits` and the head are answerable
    one-to-one. That is 51 of the 81 rows with sites. The other 30 are
    multi-site rows, whose `emits` names one of several messages by design,
    and two rows whose only site has an unreadable head.
    """
    found: list[tuple[str, str, str]] = []
    by_key = {s.key: s for s in sites}
    for gate in (registry or GATE_REGISTRY):
        if len(gate.sites) != 1 or gate.key in EMITS_HEAD_EXEMPTIONS:
            continue
        site = by_key.get(gate.sites[0])
        if site is None or site.kind in _SYNTHETIC_HEAD_KINDS:
            continue
        if site.head.startswith("<"):
            continue
        if gate.emits not in site.head:
            found.append((gate.key, gate.emits, site.head))
    return sorted(found)


def phantoms(
    sites: list[HaltSite], registry: tuple[Gate, ...] = ()
) -> list[tuple[str, str]]:
    """(gate key, site key) for registry sites the walker did not find."""
    walked = {site.key for site in sites}
    return [
        (gate.key, site)
        for gate in (registry or GATE_REGISTRY)
        for site in gate.sites
        if site not in walked
    ]


@dataclass(frozen=True)
class Renumbering:
    """A registry site that moved because a sibling above it was removed.

    Not a new gate and not a missing one: the same return, at a new index,
    because `index` is positional within a function (#2738).
    """

    gate_key: str
    named: str
    found: str
    head: str

    def describe(self) -> str:
        return (
            f"{self.gate_key} names {self.named}, and the return that prints "
            f"{self.head[:60]!r} is now at {self.found} -- a sibling return "
            f"was removed above it. Remap the row to the new index."
        )


def _site_parts(key: str) -> tuple[str, str, str]:
    """(path, qualname, kind) of a site key, dropping its positional index."""
    path, qualname, kind, _index = key.rsplit("::", 3)
    return path, qualname, kind


def renumberings(
    sites: list[HaltSite], registry: tuple[Gate, ...] = ()
) -> tuple[list[Renumbering], list[HaltSite], list[tuple[str, str]]]:
    """Tell a renumbered site apart from a new one and a deleted one (#2738).

    Returns (renumbered, still_unregistered, still_phantom).

    A site key is ``path::qualname::kind::index`` and the index is the
    position of the return among its siblings, so retiring one halt site
    shifts every later site of the same kind in the same function. The
    two-way check then reports the NEIGHBOURS as unregistered and phantom
    and says nothing about the gate that actually moved -- in #2723 it named
    four gates that had not been touched, which is the wrong first hypothesis
    to hand a reader in the middle of a gate change.

    A phantom and an unregistered site are the same return when they share a
    path, a qualname, a kind AND the static message head the walker already
    computes. Anything unmatched stays in its original list, so a genuinely
    new gate is still reported as a new gate: this narrows the report, it does
    not weaken the check.

    Pairing is one-to-one and taken in index order, which matters when several
    siblings share a head: two returns printing the same text shift by the
    same amount and in the same order, so the Nth phantom is the Nth found.
    """
    fresh = unregistered(sites, registry)
    ghosts = phantoms(sites, registry)

    #: Unregistered sites, grouped by everything except their index.
    available: dict[tuple[str, str, str, str], list[HaltSite]] = defaultdict(list)
    for site in fresh:
        available[(site.path, site.qualname, site.kind, site.head)].append(site)
    for group in available.values():
        group.sort(key=lambda s: s.index)

    matched_sites: set[str] = set()
    matched_ghosts: set[tuple[str, str]] = set()
    found: list[Renumbering] = []

    for gate_key, named in sorted(ghosts, key=lambda g: g[1]):
        try:
            path, qualname, kind = _site_parts(named)
        except ValueError:
            # fail-open: a row naming something that is not a site key at all
            # is a real defect, and it is REPORTED rather than raised -- this
            # entry stays in the returned phantom list, where the audit prints
            # it and the CI gate fails on it. Raising here would replace a
            # named finding with a traceback and would stop the other rows
            # being examined at all.
            continue
        # The head the registry row expects is not stored on the row -- only
        # `emits` is, and that is prose for humans. So the head comes from the
        # candidates themselves, and a group is claimable only if exactly one
        # head is on offer for this (path, qualname, kind), or one of them
        # matches the row's `emits`.
        heads = [
            key for key in available
            if key[:3] == (path, qualname, kind) and available[key]
        ]
        if not heads:
            continue
        chosen = heads[0]
        if len(heads) > 1:
            row = registry_by_key(registry).get(gate_key)
            emits = (row.emits if row else "") or ""
            preferred = [key for key in heads if emits and emits in key[3]]
            if len(preferred) != 1:
                # Ambiguous: several returns in this function moved and their
                # message heads do not tell them apart. Reported as phantom and
                # unregistered, unchanged, because a guessed remap is worse
                # than an honest "work these out by hand".
                continue
            chosen = preferred[0]
        site = available[chosen].pop(0)
        matched_sites.add(site.key)
        matched_ghosts.add((gate_key, named))
        found.append(Renumbering(gate_key, named, site.key, site.head))

    return (
        sorted(found, key=lambda r: r.named),
        [site for site in fresh if site.key not in matched_sites],
        [ghost for ghost in ghosts if ghost not in matched_ghosts],
    )


def halt_counts() -> dict[str, int]:
    """Rows whose action is `halt`, per stage. The ratchet's quantity (#2720)."""
    counts: dict[str, int] = defaultdict(int)
    for gate in GATE_REGISTRY:
        if gate.action == ACTION_HALT:
            counts[gate.stage] += 1
    return dict(sorted(counts.items()))


def halted(key: str, message: str) -> str:
    """Tag a halt message with its gate key.

    For new sites. A legacy site is covered by its walker key in the registry;
    a site written after this module exists calls `halted()` so the terminal
    record (#2721) reads the key instead of matching prose.
    """
    if key not in registry_by_key():
        raise KeyError(f"{key!r} is not a registered gate")
    return f"{message.rstrip()} [gate:{key}]"


def gate_key_of(message: str) -> str:
    """The key `halted()` tagged onto a message, or ""."""
    match = _TAG_RE.search(message or "")
    return match.group(1) if match else ""


#: What an advisory says about the run's fate when the caller does not say.
#: True of every guard inside a bounded loop, which is what #2723 softened.
ADVISORY_CONTINUES_DEFAULT = "Continuing; the budget decides."


def advised(key: str, message: str, *, continues: str = "") -> str:
    """What an `advise` gate prints instead of ending the run (#2723).

    An advisory says the same sentence a halt used to say and does not route.
    It carries the gate key for the same reason `halted()` does -- so the log
    line can be counted against the registry rather than matched as prose --
    and it says plainly that the run continues, because the identical sentence
    was a terminal message for as long as these guards have existed and a
    reader will remember it that way.

    ``continues`` is that plain statement. It defaults to the stagnation
    guards' sentence, which is true of a guard inside a bounded loop: the run
    goes on and a budget above it decides when to stop. A gate outside such a
    loop must say something else rather than inherit a sentence that is not
    true of it -- `impl.path_enforcement` (#2736) writes the file and no budget
    is involved, so an inherited "the budget decides" would be prose nobody
    could act on.

    Refuses a key whose row still halts. An advisory printed by a gate that
    then ends the run anyway would be the worst of both: a log that says the
    run continued and a run that did not.
    """
    row = registry_by_key().get(key)
    if row is None:
        raise KeyError(f"{key!r} is not a registered gate")
    if row.action == ACTION_HALT:
        raise ValueError(
            f"{key!r} is a halt row; advised() is for a gate that does not end "
            f"the run. Change the row's action first, and lower the ratchet "
            f"baseline in the same PR (#2720)."
        )
    tail = (continues or ADVISORY_CONTINUES_DEFAULT).strip()
    return f"{message.rstrip()} {tail} [gate:{key}]"
