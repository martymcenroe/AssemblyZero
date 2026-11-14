# Test report: #4273

## Changed tests

- `tests/unit/test_spec_finalize_record_failures_4273.py` (new, 6 tests):
  - T1: `TestTheAuditSave::test_t1_an_unwritable_audit_directory_halts_through_the_graph`.
  - The audit save: `TestTheAuditSave::test_a_directory_on_the_audit_file_name_halts` and `test_a_failed_save_leaves_the_lineage_in_active`.
  - The lineage move: `TestTheLineageMove::test_a_move_that_cannot_make_its_destination_halts` and `test_a_lineage_outside_active_halts`.
  - Unchanged behaviour: `test_a_clean_finalize_still_reaches_end`.
- The two new halt sites, `finalize_spec::return::9` and `finalize_spec::return::10`, join the `spec.finalize.precondition` row in `assemblyzero/core/gate_registry.py`. `test_gate_registry.py`, `test_halt_site_renumbering.py`, `test_non_pytest_red_is_deterministic.py`, `test_routing_policy.py` and `test_section_ten_carries_tests.py` hold the registry. No test file in that set changed.

## Implementation runs, 2026-11-14

- The new file before the fix: `5 failed, 1 passed`, with `PermissionError ... 001-final-spec.md` raised out of N6.
- The new file with `test_spec_finalize_halts.py`, `test_finalize_spec_loud_failure.py`, `test_spec_handoff_survives_janitor.py` and `test_finalize_repair_routing.py`: `64 passed`.
- With the two sites registered, the five gate-registry files above and `test_gate_registry_loud_failure.py`: `117 passed`.

## Full suite, 2026-11-14

Every tier ran in the worktree after the last edit, at 3:30 AM Central. Each exited 0.

- Unit tier, 3:59 AM Central: `= 14562 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1119.35s (0:18:39) =`
- Integration tier, 3:42 AM Central: `=== 65 passed, 7 skipped, 15262 deselected, 34 warnings in 76.48s (0:01:16) ====`
- E2E tier, 3:42 AM Central: `========= 19 passed, 15315 deselected, 34 warnings in 80.49s (0:01:20) =========`
- Adversarial tier, 3:42 AM Central: `========= 1 skipped, 15333 deselected, 34 warnings in 63.97s (0:01:03) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 3:41 AM Central: `559 passed, 1 warning in 15.81s`

No nightly was run.
