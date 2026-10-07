# Test report: #3754, #3755, #3756

## New and changed tests

- `tests/unit/test_spec_calls_existing_code.py` (10): the boostgauge #2 call `Telltale(duration=60.0)` fails and names `duration` and `window`; `Telltale(window=...)`, `Telltale(60.0)` and `Telltale(None, decay_rate=...)` pass; a function with a wrong keyword fails; a keyword-only parameter is accepted; `**kwargs` and a class without its own `__init__` are not judged; a callee the plan Modifies is not judged; an aliased import is followed; an unparseable fence is left to its own check; `from boostgauge.renderer import Renderer` fails `import_targets_exist` and a real submodule passes it.
- `tests/unit/test_spec_settlement_names_its_gate.py` (6): the spec stage carries `gate:spec-completeness`, other stages and stage-less calls do not; adding a check changes it; a spec settled without it no longer verifies; one settled with it does; an LLD settlement is unaffected.
- `tests/unit/test_implementation_spec_workflow.py`: `test_resolves_parent_module_src_layout`, which encoded the parent forgiveness, replaced by `test_a_name_inside_a_module_is_not_a_module` and `test_a_missing_submodule_of_a_real_package_does_not_resolve`.
- `tests/unit/test_check_classification.py`: the count moves from 16 to 17 and names `call_signatures_match`.
- `tests/unit/test_completeness_message_addressability.py`: `check_call_signatures_match` declared uncovered beside `check_import_targets_exist` (both need a real repo tree), in both lists.

## Runs, 2026-10-07, Ubuntu (WSL)

- The import-resolver suites (`test_import_checker_base`, `test_import_checker_env`, `test_import_resolves_empty_segments`, `test_implementation_spec_workflow`, `test_completeness_message_addressability`, `test_interface_surface`): 278 passed after the change.
- Every settlement suite (`test_arc_doc_sync`, `test_no_retries`, `test_stage_finality`, `test_stage_finality_launcher`, `test_stage_finality_skip`, `test_staleness_is_content`) with the new settlement file: 125 passed.
- `tools/audit_halt_sites.py --check`: PASS. Fail-open baseline regenerated (totals only); the two new handlers are ruled on in the code.
- Full `tests/unit`, with all three changes: 10948 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 0s.
- `ruff check`: `settlement.py` 4/4, `speedrun_roll.py` 37/37, `stages.py` 20/20 against `main`; `validate_completeness.py` 6/6; the two new test files and `check_classification.py` have none.
