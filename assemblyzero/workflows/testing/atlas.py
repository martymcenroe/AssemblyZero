"""The graph atlas for the testing (implementation) workflow (#2157, #2733).

Same contract as the requirements and implementation-spec atlases: position
narration reads from here, the convergence record (#2721) takes its node
ordinal from here, and the drift guard in ``tests/unit/test_graph_atlas.py``
pins this file to the actual compiled ``StateGraph`` so it cannot rot when the
graph is rewired.

This is the stage where runs get furthest and where they most often die --
45 of the 135 failures counted over boostgauge's 180 runs, including
``run-issue4-172600``, the furthest run in the whole record, which stopped at
N5 with three tests passing at 72% coverage. Until this file existed, the
report had to grep node markers out of a prose log to say where in the
implementation stage a run had reached, which is exactly what #2721 set out
to stop doing.

``ordinal`` is the position on the forward path. A node that exists only to
loop back consumes no ordinal, so a run that dies inside one reports the
forward node it came from as its furthest position, which is the truth about
how far it got. ``HALT`` has none either, for the reason the other atlases
give: it is an exit, never a step.
"""

from __future__ import annotations

#: The forward path: N0, N1, N2, N2.5, N3, N4, N4b, N5, N6, N7, N7.5, N8, N9.
#: `N1_5_revise_test_plan` and `N4c_augment_tests` are loops and are excluded,
#: as is `HALT`.
TOTAL_STEPS = 13

ATLAS: dict[str, dict] = {
    "N0_load_lld": {
        "title": "load LLD and spec",
        "ordinal": 1,
        "goal": "Load the approved LLD and implementation spec to build from.",
        "teach": (
            "The implementation stage consumes two upstream documents as "
            "ground truth and revises neither. A missing spec or an LLD too "
            "short to be usable stops the run here, before anything is spent."
        ),
        "successors": {
            "N1_review_test_plan": "the LLD and spec loaded",
            "HALT": "neither document could be loaded",
        },
    },
    "N1_review_test_plan": {
        "title": "review test plan",
        "ordinal": 2,
        "goal": "Judge the LLD's test plan before any test is written.",
        "teach": (
            "Mechanical pre-checks run first and cost nothing; a reviewer "
            "model follows. A BLOCKED verdict earns one revision rather than "
            "a stop, which is what N1.5 is for."
        ),
        "successors": {
            "N2_scaffold_tests": "the plan is usable",
            "N1_5_revise_test_plan": "blocked; revise the plan once",
            "HALT": "the reviewer failed and left a reason",
            "END": "blocked under a strict policy, or out of revisions",
        },
    },
    "N1_5_revise_test_plan": {
        "title": "revise test plan",
        "ordinal": None,
        "goal": "Rewrite the test plan against the reviewer's objection.",
        "teach": (
            "A loop, not a step: a revised plan goes back for re-review "
            "rather than forward, so no plan reaches the scaffolder without "
            "having been judged in the state it is in. What ends the loop is "
            "the revision budget, and when it is spent the run stops here "
            "rather than sending the same short plan round again."
        ),
        "successors": {
            "N1_review_test_plan": "the plan was revised; judge it again",
            "HALT": (
                "the revision left a reason: the budget is spent, or the "
                "revision could not be attempted at all"
            ),
        },
    },
    "N2_scaffold_tests": {
        "title": "scaffold tests",
        "ordinal": 3,
        "goal": "Write the test suite from the plan, before any code exists.",
        "teach": (
            "The tests are written first and are the specification the code "
            "must satisfy. Where the spec ships executable Section 10 test "
            "functions, those are what the scaffold is built from."
        ),
        "successors": {
            "N2_5_validate_tests": "tests were generated",
            "HALT": "scaffolding failed",
            "END": "this was a scaffold-only run, which is a finish",
        },
    },
    "N2_5_validate_tests": {
        "title": "validate tests",
        "ordinal": 4,
        "goal": "Check the generated suite is executable and really asserts.",
        "teach": (
            "Mechanical, no model call: imports, test functions, assertions "
            "(#2752 reads one level into a helper), stub counting and "
            "scenario coverage. A failure regenerates rather than stopping, "
            "until the scaffold attempt budget is spent."
        ),
        "successors": {
            "N3_verify_red": "the suite is usable",
            "N2_scaffold_tests": "unusable; regenerate while attempts remain",
            # Declared in the router's mapping and never returned: #2331
            # removed the escalate-to-implementation route, because a suite
            # the validator had just called unusable was entering the coder
            # having skipped the red phase. The edge is in the compiled graph
            # and is named here so the drift guard stays honest about it.
            "N4_implement_code": "never taken; the edge #2331 stopped using",
            "HALT": "still unusable when the attempt budget is spent",
            "END": "the node returned no reason to record",
        },
    },
    "N3_verify_red": {
        "title": "verify red phase",
        "ordinal": 5,
        "goal": "Prove the tests fail before the code that satisfies them.",
        "teach": (
            "A test that passes against an empty implementation is testing "
            "nothing. This phase is what makes the suite's later green a "
            "result rather than a coincidence."
        ),
        "successors": {
            "N4_implement_code": "the tests fail, as they must",
            "N5_verify_green": "the work is already done (#2337)",
            "N2_scaffold_tests": "the suite is broken; scaffold again",
            "HALT": "the tests pass without code, or the runner is unusable",
            "END": "the node returned no reason to record",
        },
    },
    "N4_implement_code": {
        "title": "implement code",
        "ordinal": 6,
        "goal": "Write the code, one file at a time, until the tests can pass.",
        "teach": (
            "The stage's spender. A fix asks for edits rather than a rewrite "
            "(#2407), and a file the LLD's plan did not name is written with "
            "an advisory rather than refused (#2736)."
        ),
        "successors": {
            "N4b_completeness_gate": "the files were written",
            "HALT": "the implementer could not produce usable code",
        },
    },
    "N4b_completeness_gate": {
        "title": "completeness gate",
        "ordinal": 7,
        "goal": "Check every requirement has code before the tests are run.",
        "teach": (
            "Cheaper than discovering the gap in the green loop: an "
            "unimplemented requirement goes back to the coder while "
            "iterations remain."
        ),
        "successors": {
            "N5_verify_green": "every requirement has code",
            "N4_implement_code": "something is missing; implement it",
            "HALT": "the gate itself failed and left a reason",
            "END": "still incomplete at the iteration cap; the orchestrator "
                   "reads the BLOCK verdict (#1779)",
        },
    },
    "N4c_augment_tests": {
        "title": "augment tests for coverage",
        "ordinal": None,
        "goal": "Add tests for code the suite does not reach.",
        "teach": (
            "A loop, not a step, and deliberately one-way: it always returns "
            "to verification and never routes to implementation, so a "
            "coverage shortfall cannot turn into an edit of the code (#2327)."
        ),
        "successors": {
            "N5_verify_green": "always",
        },
    },
    "N5_verify_green": {
        "title": "verify green phase",
        "ordinal": 8,
        "goal": "Run the suite against the code and drive it to passing.",
        "teach": (
            "The iterate loop, and where the furthest recorded run stopped. "
            "Only a budget or a broken environment ends it: the stagnation "
            "guards advise and the iteration cap and circuit breaker decide "
            "(#2723)."
        ),
        "successors": {
            "N6_e2e_validation": "green, and end-to-end validation applies",
            "N7_finalize": "green, with nothing left to validate",
            "N4_implement_code": "still failing; implement again",
            "N4c_augment_tests": "green but under-covered; add tests (#2327)",
            "N2_scaffold_tests": "the suite itself is the problem",
            "HALT": "the iteration cap, the circuit breaker, or a dead runner",
            "END": "the node returned no reason to record",
        },
    },
    "N6_e2e_validation": {
        "title": "end-to-end validation",
        "ordinal": 9,
        "goal": "Exercise the feature as a user would, not as a unit test does.",
        "teach": (
            "Unit tests can all pass on a feature that does not work. This "
            "loop is bounded by its own cap and the circuit breaker; its "
            "stagnation guard advises rather than ending the run."
        ),
        "successors": {
            "N7_finalize": "validated, or not applicable",
            "N4_implement_code": "the feature does not work; implement again",
            "HALT": "the circuit breaker, or an e2e error with a reason",
            "END": "the e2e iteration cap, which records no reason",
        },
    },
    "N7_finalize": {
        "title": "finalize",
        "ordinal": 10,
        "goal": "Write the test and implementation reports and commit them.",
        "teach": (
            "The artifacts a human reads afterwards are produced here and "
            "committed into the implementation worktree, so they travel to "
            "the target's main branch with the pull request rather than "
            "being left untracked (#1626)."
        ),
        "successors": {
            "N7_5_adversarial": "finalized",
            "HALT": "finalizing failed",
            "END": "documentation is being skipped, which is a finish",
        },
    },
    "N7_5_adversarial": {
        "title": "adversarial review",
        "ordinal": 11,
        "goal": "Attack the finished work looking for what the tests missed.",
        "teach": (
            "Non-blocking by design: its findings are recorded and the run "
            "continues, because a late adversarial opinion is evidence for a "
            "human rather than a gate on the machine."
        ),
        "successors": {
            "N8_document": "always, whatever it found",
            "END": "the adversarial step itself errored",
        },
    },
    "N8_document": {
        "title": "document",
        "ordinal": 12,
        "goal": "Generate the wiki page, runbook and README the work needs.",
        "teach": (
            "Committed into the implementation worktree for the same reason "
            "the reports are (#1631), so documentation lands with the code "
            "instead of being written and lost."
        ),
        "successors": {
            "N9_cleanup": "documented",
            "END": "documentation failed or was skipped",
        },
    },
    "N9_cleanup": {
        "title": "cleanup",
        "ordinal": 13,
        "goal": "Leave the target repository as the run found it.",
        "teach": (
            "The last forward step. What it removes is scaffolding the run "
            "created, never the operator's own working state."
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
            "Reachable since #2756, from all ten routers that can carry an "
            "`error_message`. Before that it was declared and stranded: every "
            "stop routed straight to END and the orchestrator relayed the "
            "message, so implementation-stage halts never passed through the "
            "node that writes the halt bundle -- the artifact carrying the "
            "gate key, the outstanding work and the resume line. An exit, "
            "never a step, so it takes no ordinal."
        ),
        "successors": {
            "END": "always -- the reason is recorded, the run is over",
        },
    },
}
