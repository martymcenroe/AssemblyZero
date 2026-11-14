# Implementation report: #4271

## The defect

`_extract_import_dependencies` in `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` skipped any planned file missing from the checkout, with `if not full_path.exists() ... : continue`. A Modify or Delete target that exists only on the base branch, which `_load_planned_file` already reads from the base (#2033), therefore reached the drafter with no import map, and nothing said so.

## The fix

`_extract_import_dependencies` takes `base_ref_name: str = ""`, and `_analyze` passes the base it already resolved. For each planned `.py` file there are now four cases:

- In the checkout: read as before, with `utf-8-sig` (#2507).
- An Add missing from the checkout: skipped. A file not yet written has no imports.
- A Modify or Delete target the base ships: read with `read_from_base`, with a leading BOM removed, and named `<path> on <base>` in any parse error.
- Anything else: raises `CodebaseReadError`, naming the change type, the path, and where it looked (the checkout, and the base when there is one). The node's existing handler turns that into a halt.

## Tests

In `tests/unit/test_spec_import_map_reads_the_base_4271.py` (new):

- `TestTheNodeMapsABaseOnlyTarget::test_t1_a_base_only_modify_target_appears_in_the_import_map` (T1)
- `TestTheHelper::test_a_base_only_target_is_read_from_the_base`
- `TestTheHelper::test_a_base_only_target_with_a_bom_is_read`
- `TestTheHelper::test_the_checkout_copy_wins_over_the_base`
- `TestTheHelper::test_r2_a_target_found_nowhere_raises_naming_it`, for Modify and for Delete (R2)
- `TestTheHelper::test_r2_without_a_base_a_missing_target_raises_naming_it` (R2)
- `TestTheHelper::test_a_base_only_target_that_does_not_parse_raises_naming_the_base`
- `TestTheHelper::test_an_add_not_yet_written_still_has_no_imports`
- `TestTheHelper::test_a_node_halt_on_a_missing_target_still_routes_to_halt`

Before the fix: `9 failed, 1 passed`. T1 failed because `telltale.py` was missing from the import map, and R2 failed with `DID NOT RAISE CodebaseReadError`.

## The run

On Ubuntu, 2026-11-14, after the fix:

- The new file: `10 passed`.
- `test_analyze_codebase.py`, `test_analyze_codebase_loud_failure.py`, `test_spec_analyze_codebase_loud_failure.py`, `test_implementation_spec_workflow.py`, `test_spec_graph_loud_failure.py` and the seventeen files that name `gate_registry`, other than `test_loud_failure_check.py`: `6 failed, 711 passed`. All six were the two #4273 halt sites in `finalize_spec.py` that no `GATE_REGISTRY` row named; see the #4273 report. With those registered, the six files that had failed: `117 passed`, and the whole set again: `717 passed`.

`ruff check` on `analyze_codebase.py` reports the same five findings as at HEAD (`F841`, `I001` twice, `ISC004`, `RUF100`), none added. The new test file is clean.
