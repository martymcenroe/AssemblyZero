"""The graph atlas for the implementation-spec workflow (#2157).

Same contract as the requirements atlas: position narration, tutorial and
quiz modes read from here, and the drift guard in
``tests/unit/test_graph_atlas.py`` pins this file to the actual compiled
``StateGraph`` so it cannot rot when the graph is rewired.

``ordinal`` is the position on the forward path; ``HALT`` has none.
"""

from __future__ import annotations

TOTAL_STEPS = 7

ATLAS: dict[str, dict] = {
    "N0_load_lld": {
        "title": "load LLD",
        "ordinal": 1,
        "goal": "Load the approved LLD this spec will be built from.",
        "teach": (
            "The spec stage never re-litigates the LLD: it consumes the "
            "approved document as ground truth. A missing or unreadable LLD "
            "halts here, before anything is spent."
        ),
        "successors": {
            "N1_analyze_codebase": "the LLD loaded",
            "HALT": "the LLD could not be loaded",
        },
    },
    "N1_analyze_codebase": {
        "title": "analyze codebase",
        "ordinal": 2,
        "goal": "Read the target repo so the spec references real code.",
        "teach": (
            "Same grounding rule as the LLD stage: the generator is handed "
            "the actual tree, so file paths and interfaces in the spec are "
            "facts rather than guesses."
        ),
        "successors": {
            "N2_generate_spec": "analysis complete",
            "HALT": "analysis failed",
        },
    },
    "N2_generate_spec": {
        "title": "generate spec",
        "ordinal": 3,
        "goal": "The drafter model writes the implementation spec.",
        "teach": (
            "Failed validations and revision verdicts loop back here for a "
            "fresh generation. A drafter failure halts outright: an "
            "unconditional forward edge here once let an error ride through "
            "a vacuous validation pass and severed the error chain."
        ),
        "successors": {
            "N3_validate_completeness": "a draft was generated",
            "HALT": "the drafter itself failed",
        },
    },
    "N3_validate_completeness": {
        "title": "completeness validation",
        "ordinal": 4,
        "goal": "Check the spec covers everything the LLD requires.",
        "teach": (
            "The mechanical gate of this stage: an incomplete spec loops "
            "back for regeneration up to the iteration cap. Only a complete "
            "spec earns a review."
        ),
        "successors": {
            "N4_human_gate": "passed, with the human gate on",
            "N5_review_spec": "passed, with the human gate off",
            "N2_generate_spec": "incomplete; regenerate",
            "HALT": "still incomplete at the iteration cap",
        },
    },
    "N4_human_gate": {
        "title": "human gate",
        "ordinal": 5,
        "goal": "An optional human checkpoint before review.",
        "teach": (
            "Autonomous rolls run with this gate off. When it is on, a "
            "human forwards the spec, sends it back for revision, or takes "
            "it over manually."
        ),
        "successors": {
            "N5_review_spec": "the human approved",
            "N2_generate_spec": "the human asked for a revision",
            "HALT": "an error at the gate",
            "END": "the human took over manually",
        },
    },
    "N5_review_spec": {
        "title": "adversarial review",
        "ordinal": 6,
        "goal": "A second model judges the spec against the LLD.",
        "teach": (
            "Approval finalizes; a revise verdict loops back to the "
            "generator while iterations remain. The same blocking verdict "
            "twice in a row is stagnation and halts the run instead of "
            "circling forever."
        ),
        "successors": {
            "N6_finalize_spec": "approved",
            "N2_generate_spec": "revise; regenerate",
            "HALT": "error, blocked, stagnation, or the cap",
        },
    },
    "N6_finalize_spec": {
        "title": "finalize",
        "ordinal": 7,
        "goal": "Save the approved spec where implementation will read it.",
        "teach": (
            "The saved spec is the hand-off artifact: the implementation "
            "stage builds from this file, not from this run's transcript."
        ),
        "successors": {
            "END": "always",
        },
    },
    "HALT": {
        "title": "halt",
        "ordinal": None,
        "goal": "Record why the run stopped, then end it cleanly.",
        "teach": (
            "HALT is the run stating its reason for stopping in a form the "
            "launcher and telemetry can read; it is an exit, never a step."
        ),
        "successors": {
            "END": "always",
        },
    },
}
