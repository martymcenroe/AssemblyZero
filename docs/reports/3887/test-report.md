# Test Report: implementation_spec N6 finalize reaches HALT (#3887, #3891)

## Tests added: `tests/unit/test_spec_finalize_halts.py`

- `test_the_graph_routes_n6_through_a_router`: N6's successors in the compiled graph are exactly `HALT` and `__end__`. On main, N6 had only `__end__`.
- `test_each_guard_routes_to_halt`, parametrized: an empty draft, a non-APPROVED verdict and a bad issue number each return an `error_message` that `route_after_finalize` sends to HALT.
- `test_a_missing_repo_root_halts`, `test_a_missing_audit_dir_halts` and `test_an_unwritable_handoff_copy_halts`: the three new halts.
- `test_a_clean_finalize_ends_normally`: the control.

## Tests changed

- `test_implementation_spec_workflow.py`:
  - `test_routes_to_end_on_empty_next_node` is now `test_routes_to_halt_on_empty_next_node`;
  - `test_routes_to_end_on_the_manual_exit` is added;
  - the two `TestFinalizeSpec` tests that write a spec supply a lineage directory through `_lineage`.
- `test_check_classification.py`: an empty human-gate decision now asserts HALT, and the explicit `END` still asserts END.
- `test_spec_handoff_survives_janitor.py`: `_state` supplies the run-scoped lineage directory the orchestrator creates.
- `test_loud_failure_check.py`: `BASELINE_CEILING` 326 to 325.

## Runs, 2026-10-07

- **All four tiers:**
  - integration: 64 passed, 7 skipped;
  - e2e: 19 passed;
  - adversarial: 1 skipped;
  - unit: 11,017 passed and 1 failed.
- **The one unit failure** was `test_cascade_detector.py::TestDetectionLatency::test_typical_input_latency`. It is a wall-clock latency test, and it failed while two delegated readers ran beside the tier. Run alone straight afterwards, its file passed 53 of 53. This batch does not touch cascade detection. The defect is #3731's, noted there for this second test.
- `tools/audit_halt_sites.py --check`: PASS, 149 halt sites, every one registered.
- `tools/audit_loud_failure.py --check`: PASS at 325. `tools/audit_fail_open.py --check --strict`: PASS.
- `lint_vs_main.py`: no new `ruff` finding in the 8 changed files.
