# Implementation Report: implementation_spec N6 finalize reaches HALT (#3887, #3891)

A #3581 sweep batch covering the 11 violations recorded in the spec graph's routing (#3887) and the finalize node (#3891).

## What changed

### `workflows/implementation_spec/graph.py` (#3887, 2 sites)

- **N6 finalize.** It reached END by an unconditional edge, so every error it returned ended the run with no HALT record and no alert. These were an empty or short draft, a non-APPROVED verdict, a bad issue number, and a failed or missing write. A new `route_after_finalize` sends a non-empty `error_message` to HALT, and anything else to END.
- **`route_after_human_gate`.** It sent an empty or unknown `next_node` to END, as if the human had chosen manual handling. It now returns END only for the gate's explicit `END`, the manual exit, and HALT for anything it never sets.
- **`atlas.py`.** The N4 and N6 successor descriptions follow the routing.

### `workflows/implementation_spec/nodes/finalize_spec.py` (#3891, 9 sites)

- **The guards.** Empty draft, short draft, verdict and issue number were violations only because N6 could not reach HALT. With the router they now halt and alert.
- **A missing `repo_root`.** It used to write the spec under the process's working directory, through `Path(".")`. It now halts.
- **A missing or absent `audit_dir`.** The lineage save and the move to `done/` used to be skipped without a word. They now halt, and run unconditionally once the guard has passed.
- **The durable hand-off copy (#2311).** When it could not be written, the node printed a warning and passed, which left a relaunch unable to find the spec. It now halts. `spec_path` therefore always names the hand-off copy; the `or spec_path` fallback was dead and is removed.
- **`output_dir.mkdir`.** It moved inside the write's error handling, so a failure to create the directory is reported like a failed write.

### Registry and baselines

- **`gate_registry.py`, `spec.finalize.precondition`.** The row now names returns 2–8. My two guards shifted the earlier write and not-created returns from 4 and 5 to 6 and 7. The new hand-off failure is return 8, the same kind of failure as a write failing. No new halt row; the ratchet is unchanged. `gate_registry_baseline.json` `measured_against` now records 149 halt sites.
- **Loud-failure baseline:** 326 to 325, the N6 unrouted error. `BASELINE_CEILING` is 325.
- **Fail-open baseline:** regenerated; findings 547 to 546, nothing added.
- **Ledger 0908:** the 11 sites are marked "FIXED in #3581 spec finalize batch (#3887)".

## Behaviour this changes for a real run

The orchestrator's spec stage already failed on a non-empty `error_message` (`stages.py`), so a pipeline outcome is unchanged. What changes is that the HALT record and the alert now exist. A spec run with no audit directory now halts at N6 instead of finalizing without lineage; the orchestrator creates the directory before the run (`stages.py`).
