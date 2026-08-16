"""The graph atlas for the requirements workflow (#2157).

Machine-readable answers to the operator's three questions about a live
run: where are we in the graph, what is this node FOR, and what comes
next. Position narration (#2158), tutorial mode (#2160), and quiz mode
(#2161) all read from here, and NOTHING else may hardcode the graph.

The drift guard in ``tests/unit/test_graph_atlas.py`` compares this atlas
against the actual compiled ``StateGraph``: every node here exists there,
every node there exists here, and every successor here is a real edge.
Rewire the graph without touching this file and the suite fails naming
the gap.

``ordinal`` is the position on the LLD workflow's FORWARD path (loops and
halts do not consume ordinals; the issue workflow skips some nodes, which
is documented rather than modeled). ``HALT`` has no ordinal: it is where
runs end, never a step on the way.
"""

from __future__ import annotations

TOTAL_STEPS = 11

ATLAS: dict[str, dict] = {
    "N0_load_input": {
        "title": "load input",
        "ordinal": 1,
        "goal": "Load the issue (or brief) the document will be built from.",
        "teach": (
            "Everything downstream builds from this text, which is why an "
            "ambiguous issue is caught two nodes later rather than at the "
            "end. LLD runs go on to read the codebase; issue-drafting runs "
            "skip straight to the drafter."
        ),
        "successors": {
            "N0b_analyze_codebase": "LLD run",
            "N1_generate_draft": "issue-drafting run",
            "HALT": "the input could not be loaded",
        },
    },
    "N0b_analyze_codebase": {
        "title": "analyze codebase",
        "ordinal": 2,
        "goal": "Read the target repo so the draft cites real files, not guesses.",
        "teach": (
            "The drafter is only as grounded as the context it is handed. "
            "This node walks the actual code so the LLD names modules that "
            "exist and follows conventions already in the tree."
        ),
        "successors": {
            "N0c_analyze_requirements": "always",
        },
    },
    "N0c_analyze_requirements": {
        "title": "requirements consistency gate",
        "ordinal": 3,
        "goal": (
            "Check the issue's requirements agree with each other before any "
            "tokens are spent drafting."
        ),
        "teach": (
            "No spec can satisfy two contradictory sentences, so a conflict "
            "halts the run and files a question for the operator instead of "
            "drafting the wrong reading. A halt here is the system working: "
            "the cheapest possible failure, before generation. The gate also "
            "halts when it could not RUN — an unreachable governance model "
            "stops the run rather than letting it draft against requirements "
            "nobody checked (#2474)."
        ),
        "successors": {
            "N1_generate_draft": "the requirements are consistent",
            "HALT": (
                "a requirements conflict needs an operator ruling, or the "
                "gate reached no verdict and the run must not draft unchecked"
            ),
        },
    },
    "N1_generate_draft": {
        "title": "generate draft",
        "ordinal": 4,
        "goal": "The drafter model writes the document.",
        "teach": (
            "Draw quality varies enormously between attempts on identical "
            "input, which is why failed validations loop back here for a "
            "fresh draft rather than patching a bad one. LLD runs go to the "
            "auto-fix pass next; issue-drafting runs go to review."
        ),
        "successors": {
            "N_ponder_stibbons": "LLD run",
            "N2_human_gate_draft": "issue-drafting run with the draft gate on",
            "N3_review": "issue-drafting run with the draft gate off",
            "HALT": "the drafter itself failed",
        },
    },
    "N_ponder_stibbons": {
        "title": "auto-fix pass",
        "ordinal": 5,
        "goal": "Repair mechanical slips in the draft before validation sees them.",
        "teach": (
            "Cheap deterministic fixes (formatting, known slip patterns) "
            "applied before validation, so the validator judges the best "
            "version of the draft and loop-backs are spent on real defects."
        ),
        "successors": {
            "N1_5_validate_mechanical": "always",
        },
    },
    "N1_5_validate_mechanical": {
        "title": "mechanical validation",
        "ordinal": 6,
        "goal": (
            "Check the document's structure: required sections present, "
            "paths real, tables well-formed."
        ),
        "teach": (
            "This is the gate that catches a drafter dropping mandatory "
            "sections (the campaign's most common mechanical failure). It "
            "blocks and redrafts up to the iteration cap; a document that "
            "cannot pass structure is never shown to a reviewer."
        ),
        "successors": {
            "N1b_validate_test_plan": "the structure passed",
            "N1_generate_draft": "the structure failed; redraft",
            "HALT": "still failing at the iteration cap",
        },
    },
    "N1b_validate_test_plan": {
        "title": "test-plan validation",
        "ordinal": 7,
        "goal": (
            "Check the draft's test plan actually discriminates: coverage, "
            "no vague assertions, nothing delegated to a human."
        ),
        "teach": (
            "A plan whose tests would pass either way proves nothing. This "
            "gate reads the plan the way a skeptic would, and sends the "
            "draft back if the tests could not tell a correct build from a "
            "wrong one."
        ),
        "successors": {
            "N2_human_gate_draft": "passed, with the draft gate on",
            "N3_review": "passed, with the draft gate off",
            "N1_generate_draft": "the plan failed; redraft",
            "HALT": "an error, or still failing at the cap",
        },
    },
    "N2_human_gate_draft": {
        "title": "human gate: draft",
        "ordinal": 8,
        "goal": "An optional human checkpoint on the draft before review.",
        "teach": (
            "Autonomous rolls run with this gate off. When it is on, a "
            "human reads the draft and sends it forward, back for revision, "
            "or takes it over manually."
        ),
        "successors": {
            "N3_review": "the human sent it to review",
            "N1_generate_draft": "the human asked for a revision",
            "END": "the human took over manually",
        },
    },
    "N3_review": {
        "title": "adversarial review",
        "ordinal": 9,
        "goal": (
            "A second model judges the draft against the issue with an "
            "adversarial brief."
        ),
        "teach": (
            "The reviewer never sees the drafter's reasoning, so agreement "
            "means two independent readings converged. Open questions can "
            "loop the draft back for revision; the same blocking verdict "
            "twice in a row is stagnation and halts the run rather than "
            "circling."
        ),
        "successors": {
            "N4_human_gate_verdict": "the verdict gate is on, or a question needs a human",
            "N5_finalize": "approved with the verdict gate off",
            "N1_generate_draft": "blocked or unanswered questions; revise",
            "N3_review": "follow-up review round",
            "HALT": "error, stagnation, or the iteration cap",
        },
    },
    "N4_human_gate_verdict": {
        "title": "human gate: verdict",
        "ordinal": 10,
        "goal": "An optional human checkpoint on the review verdict.",
        "teach": (
            "The escalation point: when the reviewer marks a question as "
            "needing a human, the run stops here even in otherwise "
            "ungated mode."
        ),
        "successors": {
            "N5_finalize": "the human approved",
            "N1_generate_draft": "the human asked for a revision",
            "END": "the human took over manually",
        },
    },
    "N5_finalize": {
        "title": "finalize",
        "ordinal": 11,
        "goal": "Save the approved document where the next stage will read it.",
        "teach": (
            "An approved LLD lands in the target repo's docs tree; a "
            "drafted issue is filed on GitHub. The artifact, not this run's "
            "transcript, is what the next stage consumes. This stage carries "
            "a validation gate of its own, and failing it sends the document "
            "back for a surgical revision rather than discarding the attempt "
            "and drafting it again."
        ),
        "successors": {
            "N1_generate_draft": "finalize's own validation blocked the document",
            "END": "the artifact is saved, or the repair budget is spent",
        },
    },
    "HALT": {
        "title": "halt",
        "ordinal": None,
        "goal": "Record why the run stopped, then end it cleanly.",
        "teach": (
            "HALT is not a crash: it is the run stating its reason for "
            "stopping (conflict, cap, stagnation, error) in a form the "
            "launcher and the telemetry can read."
        ),
        "successors": {
            "END": "always",
        },
    },
}
