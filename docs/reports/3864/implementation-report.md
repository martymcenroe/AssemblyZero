# Implementation Report: the requirements graph sends every error to HALT (#3864)

A #3581 sweep batch covering the seven violations recorded in `assemblyzero/workflows/requirements/graph.py`.

## What changed

| Site | Before | Now |
|---|---|---|
| `graph.py:578`, N0b → N0c | An unconditional edge; an N0b error (the arc worktree could not be cut) ran N0c's model calls before anything halted | `route_after_analyze_codebase` sends an error to HALT |
| `:308`, `route_after_ponder` | Unconditional | A Ponder error routes to HALT. N1 clears `error_message` on success, so a BLOCKED validation's message from the previous round never reaches it |
| `:235`, `route_after_validate_mechanical` | Never read `error_message`; a non-BLOCKED error went on to N1b as a pass | After the BLOCKED branch, which carries its own message into the retry, any error routes to HALT |
| `:334`, `route_from_human_gate_draft` | An unknown or empty decision ended the run as a manual exit | END only for the gate's explicit `END`; anything else halts |
| `route_from_human_gate_verdict` | The same pattern (not separately recorded) | The same fix |
| `:380`, the open-questions cap | Handed unanswered questions to the verdict gate, which in auto mode finalizes | Halts, emitting `workflow.halt_and_plan` like the mechanical cap |
| `:414`, the review cap | Finalized a still-BLOCKED draft | Halts, emitting `workflow.halt_and_plan` |
| `:505`, `route_after_finalize` | A finalize error ended at END | Halts. The #2233 repair route is unchanged |

The edge maps gain HALT for Ponder, N2, N4 and N5, and N0b gets a conditional edge. The requirements atlas names every new successor, as its test requires.

## Baselines and ledger

- **Loud-failure baseline:** 325 to 324, N0b's unrouted error. `BASELINE_CEILING` is 324.
- **Fail-open baseline:** regenerated; the denominator rose with the new routers, and no finding was added.
- **Ledger 0908:** the seven sites are marked "FIXED in #3581 requirements graph batch (#3864)".
- **Not marked:** `finalize.py`'s sites (#3867) whose only stated defect was "routed to END, not HALT" now reach HALT. They are not marked fixed here, because several also lack details in their messages. #3867 is told which ones to re-judge.

## Behaviour this changes for a real run

- A requirements run whose review reaches its cap still BLOCKED now halts and alerts. It used to save the BLOCKED LLD, skip the commit, and report the workflow complete.
- The same holds for unanswered open questions at the cap.
- An auto-mode run therefore stops at the point the draft failed, with the reason in the HALT record.
