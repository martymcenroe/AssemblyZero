# Test report: #4271

## Changed tests

- `tests/unit/test_spec_import_map_reads_the_base_4271.py` (new, 10 tests):
  - T1: `TestTheNodeMapsABaseOnlyTarget::test_t1_a_base_only_modify_target_appears_in_the_import_map`.
  - R2: `TestTheHelper::test_r2_a_target_found_nowhere_raises_naming_it`, for Modify and for Delete, and `TestTheHelper::test_r2_without_a_base_a_missing_target_raises_naming_it`.
  - The base read: `TestTheHelper::test_a_base_only_target_is_read_from_the_base`, `test_a_base_only_target_with_a_bom_is_read`, `test_the_checkout_copy_wins_over_the_base` and `test_a_base_only_target_that_does_not_parse_raises_naming_the_base`.
  - Unchanged behaviour: `TestTheHelper::test_an_add_not_yet_written_still_has_no_imports` and `test_a_node_halt_on_a_missing_target_still_routes_to_halt`.

## Implementation runs, 2026-11-14

- The new file before the fix: `9 failed, 1 passed`. After it: `10 passed`.
- `test_analyze_codebase.py`, `test_analyze_codebase_loud_failure.py`, `test_spec_analyze_codebase_loud_failure.py`, `test_implementation_spec_workflow.py`, `test_spec_graph_loud_failure.py` and the seventeen files that name `gate_registry`, other than `test_loud_failure_check.py`: `6 failed, 711 passed`. The six were the two #4273 halt sites no `GATE_REGISTRY` row named yet. With those registered: `717 passed`.

## Full suite, 2026-11-14

Every tier ran in the worktree after the last edit, at 3:30 AM Central. Each exited 0.

- Unit tier, 3:59 AM Central: `= 14562 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1119.35s (0:18:39) =`
- Integration tier, 3:42 AM Central: `=== 65 passed, 7 skipped, 15262 deselected, 34 warnings in 76.48s (0:01:16) ====`
- E2E tier, 3:42 AM Central: `========= 19 passed, 15315 deselected, 34 warnings in 80.49s (0:01:20) =========`
- Adversarial tier, 3:42 AM Central: `========= 1 skipped, 15333 deselected, 34 warnings in 63.97s (0:01:03) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 3:41 AM Central: `559 passed, 1 warning in 15.81s`

No nightly was run.
