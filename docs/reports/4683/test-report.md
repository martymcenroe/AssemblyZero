# Test report: #4683

## Unit

`tests/unit/test_n4_large_file_edit_script.py`, 16 tests. The orchestrator tests drive `implement_code` on a tmp tree with the model call stubbed and `came_from_base` standing in for git, as `test_edit_script_reaches_the_mid_arc_fix.py` does. The large file is 804 lines and over 30,000 characters; the spec's Section 6 gives it a diff and gives a second file instructions that must not reach its prompt.

- T1 (R1, R6): `TestTheThreshold`, 5 tests: the threshold is `CODE_GEN_PROMPT_CAP // 2`, large at 30,000 characters and not at 29,999, never for an Add, and the fixtures fall on the sides they should.
- T2 (R2): `TestTheDraftPrompt`, 4 tests: the subsection is this file's only, a `## ` line inside a diff fence ends nothing, a path the spec does not name has none, and the draft prompt carries the spec and not "Some tests fail".
- T3 (R1, R3): `TestALargeFileOnItsFirstDraft::test_is_patched_in_place_with_no_whole_file_call`: one edit-script call, the draft prompt, the file patched in place, no whole-file call and no `[PRUNE]` line.
- Retry: `test_a_missed_anchor_is_retried_with_its_reason`: the second prompt carries the first attempt's failure, and the second patch is written.
- T5 (R3): `test_a_patch_that_deletes_most_of_it_meets_the_size_gate`: a patch that removes 600 of 804 lines is refused by the size gate, the retry is told "Mechanical Size Gate", and the file keeps its lines.
- T4 (R4): `TestWhenNoEditScriptHolds`, 2 tests: after `MAX_FILE_RETRIES` attempts N4 raises `ImplementationError` naming the file, "too large to rewrite" and both attempts, the file is unchanged, and the whole-file path is never taken.
- T6 (R5): `TestALargeTestFileInAFix::test_is_left_byte_identical`: a large test file whose fix patch never applies is byte-identical after the iteration, with an alert naming #2866.
- T7 (R6): `TestASmallFileIsUnchanged::test_takes_the_whole_file_path`.

Run with `main`'s `orchestrator.py` at `141a64b0` written over the branch's (the two helper modules kept, so the file imports), then the branch's restored and checked by hash: 6 failed, 10 passed. The 6 are T3, the retry, T5, both T4 tests and T6: every test of the routing. The 10 that pass hold the helpers and the small-file path, which did not change. With the change: 16 passed.

Neighbours, with the change: every N4 test file (`test_implement_code_*`, `test_implementation_edit_script_fix.py`, `test_edit_script_*`, `test_failed_patch_on_a_test_file_leaves_it.py`, `test_failure_attribution_*`, `test_green_phase_real_run_defects.py`, `test_n4_*`, `test_orchestrator_loud_failure.py`, `test_spec_edit_script.py`), `test_gate_registry.py`, `test_gate_registry_loud_failure.py`, `test_emits_pairing.py`, `test_loud_failure_check.py` and the unrequested-changes tests: 465 passed.

## Real calls

None.

## Full suite

14,910 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed. The same 18 fail on `main` at `9527cadc` with no change applied: 16 in `tests/test_auto_reviewer_wait_loop.py`, `tests/test_universal_claude_md.py::test_adr_references_resolve`, and `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`.

## Lint

`ruff check` on the five changed files reports only what `main` already reports in them: `orchestrator.py` I001, SIM102, RUF059 and BLE001; `edit_script_fix.py` SIM103, SIM102 and ISC004 (the fix prompt's); `gate_registry.py` SIM102. The new test file is clean.
