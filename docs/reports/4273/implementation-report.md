# Implementation report: #4273

## The defect

`finalize_spec` in `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py` saves the final spec to the audit trail with `save_audit_file`, then moves the lineage from `active/` to `done/` with `move_lineage_to_done`. Neither call had a handler, so a failure in either raised out of N6, for example `PermissionError ... 001-final-spec.md`, instead of returning an `error_message` that `route_after_finalize` sends to HALT, which alerts.

## The fix

- The audit save catches `OSError` and returns `spec_path: ""` with an `error_message` naming the issue, the target path, and the cause, and saying the lineage stays in `active/`.
- The lineage move catches `(OSError, LineageSourceError)` and returns `spec_path: ""` with an `error_message` naming the lineage directory, the repository root, and the cause. `LineageSourceError` is now imported from `assemblyzero.workflows.requirements.audit`.

## The gate registry

The two new returns are halt sites, `finalize_spec::return::9` and `finalize_spec::return::10`. No `GATE_REGISTRY` row named them, so `test_gate_registry.py`, `test_halt_site_renumbering.py`, `test_non_pytest_red_is_deterministic.py`, `test_routing_policy.py` and `test_section_ten_carries_tests.py` failed, six tests in all. Both are added to the `spec.finalize.precondition` row in `assemblyzero/core/gate_registry.py`, whose notes now say #4273 added them. The returns before them keep their numbers. The row count did not change, so `tests/fixtures/gate_registry_baseline.json` did not either.

## Tests

In `tests/unit/test_spec_finalize_record_failures_4273.py` (new):

- `TestTheAuditSave::test_t1_an_unwritable_audit_directory_halts_through_the_graph` (T1)
- `TestTheAuditSave::test_a_directory_on_the_audit_file_name_halts`
- `TestTheAuditSave::test_a_failed_save_leaves_the_lineage_in_active`
- `TestTheLineageMove::test_a_move_that_cannot_make_its_destination_halts`
- `TestTheLineageMove::test_a_lineage_outside_active_halts`
- `test_a_clean_finalize_still_reaches_end`

Before the fix: `5 failed, 1 passed`, with `PermissionError ... 001-final-spec.md` raised out of N6.

## The run

On Ubuntu, 2026-11-14:

- The new file with `test_spec_finalize_halts.py`, `test_finalize_spec_loud_failure.py`, `test_spec_handoff_survives_janitor.py` and `test_finalize_repair_routing.py`: `64 passed`.
- With the two sites registered, the five gate-registry files above and `test_gate_registry_loud_failure.py`: `117 passed`.

`ruff check` on `finalize_spec.py` reports the same three findings as at HEAD (`I001`, `UP017` twice), and on `gate_registry.py` the same one finding as at HEAD; none added. The new test file is clean.
