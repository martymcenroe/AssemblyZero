# Test report: #4699

## Unit

`tests/tools/test_land_staged_workflow.py`, 13 new tests beside the 23 it had. GitHub is a fake `requests` set on the module, the clock and sleep are fakes passed to `wait_for_workflow`, and the token is a dummy string: nothing is decrypted.

- T1 (R1): `TestWaitForWorkflow::test_t1_a_run_in_progress_at_every_poll_is_reported_as_still_running`: in progress at every poll until Ctrl-C at the sixtieth sleep, past the old forty-poll budget; returns `WaitResult("in_progress", <run URL>)`. `test_t1_the_report_says_still_running_with_the_url_and_never_not_started`: `report_wait` prints STILL RUNNING and the URL, not "did not START", and refuses the merge. `test_a_run_still_in_progress_never_merges_even_with_merge_on_red`.
- T2 (R2): `test_t2_a_run_that_completes_after_the_old_budget_is_waited_for`: seen queued, then 60 polls in progress, then green; 62 polls, conclusion `success`. `test_t2_a_red_conclusion_after_the_old_budget_is_returned_too`.
- The bounds: `test_no_run_is_returned_only_when_no_run_ever_appeared` (exactly 40 polls, and the report says did not START), `test_a_run_that_appears_late_in_the_budget_is_then_waited_for`, `test_ctrl_c_before_any_run_appears_is_not_reported_as_a_run`, `test_the_running_wait_backs_off_to_its_cap` (15, 22.5, 33.75, 50.625, then 60), `test_the_ceiling_ends_the_wait_as_still_running_with_the_url` (the clamped sleeps sum to exactly six hours).
- T3 (R3): `TestPutWorkflowOnARerun::test_t3_a_branch_already_holding_the_staged_text_gets_no_put`, with `test_a_branch_holding_other_text_is_updated_in_place` and `test_a_branch_without_the_file_gets_it`.

With the change: 36 passed.

## Real calls

None. The tool's credentialed path is the operator's to run.

## Full suite

Run from the worktree with the main checkout's environment and the worktree first on `PYTHONPATH`: 14,946 passed, 22 failed, 66 skipped, 93 deselected, 7 xfailed, in 18m 43s.

- 18 are the set the #4694 report records failing on `main`: 16 in `tests/test_auto_reviewer_wait_loop.py`, `tests/test_universal_claude_md.py::test_adr_references_resolve`, and `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`. None of the three files names the lander.
- 4 failed because the run's working directory was the worktree, which has no poetry environment of its own: `test_green_collection_failure_on_planned_module.py::TestContinueOnCollectionErrors::test_run_pytest_passes_the_flag_when_asked` and three in `test_green_loop_contract.py::TestCoverageScopeIsTheWholeFeature` each stop on `poetry env info --path` exiting 1 for the worktree. Rerun with the main checkout as the working directory, both files: 40 passed.
