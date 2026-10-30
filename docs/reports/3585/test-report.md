# Test Report: run-path modules outside the workflow packages under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, measured by running the new test file against the unchanged module first. Filled in module by module.

## speedrun/requirements_status.py

**New: `tests/unit/test_requirements_status_loud_failure.py` (7).** Each site test is named for its ledger line, plus tests that pin the kept behaviour: a written record reads back, an absent ledger is `[]`, blank lines are not corruption.

**Before the fix, measured** against the unchanged module: 4 failed, 3 passed. The three are the kept-behaviour tests.

**Changed test:** `test_requirements_gate_timeout.py::test_recording_never_raises` is now `test_a_record_that_cannot_be_written_alerts_and_raises`.

**Neighbouring suites:** 67 passed across `test_requirements_gate_timeout.py` and `test_n0c_unarticulated_conflict.py`.

## utils/ast_sentinel.py

**New: `tests/unit/test_ast_sentinel_loud_failure.py` (6).** Four site tests, plus an undefined name that is still a finding and a clean file that is ok.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** `test_ast_sentinel.py::test_analyze_file_io_error` and `::test_syntax_error` expect `SentinelCannotRun`; they read an `<io>` and a `<syntax>` finding.

**Neighbouring suites:** 24 passed across `test_ast_sentinel.py` and the new file; `test_validate_mechanical.py` 79 passed; `test_mechanical_gates.py` 18 passed.

## utils/lld_verification.py

**New: `tests/unit/test_lld_verification_loud_failure.py` (3).** The site test (a path outside the current directory with no project root is refused), plus a path inside the current directory and an explicit root, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 1 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 23 passed across `test_issue_177.py` and the new file.

## utils/lld_path_enforcer.py

**New: `tests/unit/test_lld_path_enforcer_loud_failure.py` (3).** It pins the kept behaviour: a spec with no Section 2.1 yields no paths and no alert, an LLD with Section 2.1 yields its paths, and the docstring says why the absence is quiet.

**Before the change, measured** against the unchanged module: 1 failed (the docstring test), 2 passed (the behaviour, which is kept).

**Changed tests:** none.

**Neighbouring suites:** 57 passed across `test_lld_path_enforcer.py`, `test_file_write_validator.py`, `test_freeze_tests_symmetry_break.py`, `test_path_advisory.py` and the new file.

## utils/codebase_reader.py

**New: `tests/unit/test_codebase_reader_loud_failure.py` (11).** Eight site tests, plus three that pin the quiet answers: a missing file, a binary or sensitive file, and a repo with no config file. The site tests match the exception by name, so against the old module they fail on "did not raise".

**Before the fix, measured** against the unchanged module: 8 failed ("did not raise CodebaseReadError"), 3 passed (the kept-behaviour tests).

**Changed tests, each asserting the raise in place of the empty result:** in `test_codebase_reader.py`, `test_corrupted_pyproject`, `test_corrupted_package_json`, `test_symlink_outside_repo_returns_empty`, `test_symlink_outside_repo_in_batch`, `test_non_utf8_file_returns_empty` (now `test_non_utf8_file_raises`), `test_oserror_on_exists_returns_empty` (now `..._raises`), `test_file_outside_repo_root_returns_empty` (now `..._raises`), `test_oserror_on_read_text_returns_empty` (now `..._raises`), `test_oserror_on_resolve_returns_empty` (now `..._raises`); in `test_analyze_codebase.py`, `TestSymlinkOutsideRepoBlocked::test_symlink_outside_repo_returns_empty`.

**Neighbouring suites:** 184 passed across `test_codebase_reader.py`, `test_analyze_codebase.py` and the new file; 80 passed across `test_issue_2684.py`, `test_requirements_graph_halts.py`, `test_cache_semi_static.py`, `test_base_api_surface.py`, `test_base_symbols_in_api_check.py`, `test_interface_surface.py` and `test_symbol_gather_reports_unreadable.py`.

## speedrun/convergence.py

**New: `tests/unit/test_convergence_loud_failure.py` (13).** Site tests for 90 (three event kinds, and a root the store path cannot be built from), 91, 185, 186 and 195 (two shapes), the `802` consumer test, and three kept-behaviour tests: a clean store, an absent store and a written record. The store-path test came with the follow-up commit; it failed against the first version (the path was built outside the alerted region) and passes after.

**Before the fix, measured** by putting HEAD's `convergence.py` and `factory_report.py` back: 11 failed, 1 passed (`test_a_written_record_returns_true`). Two of the eleven, `test_a_clean_store_reads_with_no_alert` and `test_a_missing_store_is_a_quiet_empty_answer`, fail only on the return shape: the old reader returned `(records, count)`.

**Changed tests:** `test_convergence_record.py::test_a_corrupt_line_is_counted_rather_than_dropped` is now `test_a_corrupt_line_stops_the_read`. The return shape changed every other read in `test_convergence_record.py` (12 lines), `test_testing_atlas.py` (2), `test_mock_roll.py` (1) and `test_call_recording_roll.py` (1); each dropped an `unreadable == 0` assertion that the raise now carries.

**Neighbouring suites (convergence):** 195 passed across the new file, `test_convergence_record.py`, `test_testing_atlas.py`, `test_factory_report.py`, `test_call_recording_roll.py`, `test_mock_roll.py`, `test_checkout_telemetry_isolation.py`, `test_profile_bench.py`, `test_model_record.py`, `test_narration.py`, `test_narration_gates_off.py` and `test_halt_node.py`.

## workflows/narration.py

**New: `tests/unit/test_narration_loud_failure.py` (9).** Site tests for 55 (kept), 64, 114 (two shapes), 160 (two) and 181, plus a healthy node and a state with no `repo_root`, which pin kept behaviour.

**Before the fix, measured** against the unchanged module (with the convergence fix already in): 6 failed, 3 passed (the three kept-behaviour tests).

**Changed tests, each asserting the new behaviour in place of the retired one:**
- `test_narration.py::test_an_unknown_node_warns_once_then_stays_silent` is now `test_an_unknown_node_fails_the_graph_build`;
- `test_narration.py::test_a_broken_atlas_entry_never_costs_the_node` is now `test_a_broken_atlas_entry_stops_the_node`;
- `test_narration_gates_off.py::TestNarrationStillNeverCostsARun::test_a_node_still_runs_when_narration_explodes` is now `TestNarrationFailureIsLoud::test_a_node_does_not_run_when_narration_explodes`;
- `test_convergence_record.py::test_a_node_still_runs_when_the_record_cannot_be_written` is now `test_a_node_does_not_run_when_the_record_cannot_be_written`;
- `test_node_modules_supply_nodes.py::test_narrated_names_the_wrapped_module` wrapped a node with an empty atlas; it now gives the node an entry.

**Neighbouring suites (narration):** 131 passed across the new file, `test_narration.py`, `test_narration_gates_off.py`, `test_node_modules_supply_nodes.py`, `test_convergence_record.py`, `test_testing_atlas.py`, `test_graph_atlas.py`, `test_tutorial_mode.py`, `test_quiz_mode.py` and `test_halt_legibility.py`; 249 passed across `test_implementation_spec_workflow.py`, `test_requirements_graph_halts.py` and `test_finalize_repair_routing.py`, which build the graphs.

## speedrun/prompt_telemetry.py

**New: `tests/unit/test_prompt_telemetry_loud_failure.py` (7).** Site tests for 130, 152, 180 and 188 (two shapes), plus an absent store and a written failure, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 5 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** in `test_prompt_telemetry.py`, `test_empty_details_are_not_recorded` is now `test_empty_details_are_recorded_under_their_own_fingerprint`, `test_a_malformed_line_does_not_break_the_report` is now `test_a_malformed_line_stops_the_report`, and `test_a_write_failure_is_logged_and_swallowed` is now `test_a_write_failure_alerts_and_raises`.

**Neighbouring suites:** 180 passed across `test_prompt_telemetry.py`, `test_checkout_telemetry_isolation.py`, `test_check_requirements.py`, `test_factory_report.py`, `test_n0c_unarticulated_conflict.py`, `test_requirements_gate_reproduces.py` and `test_spec_convergence_telemetry.py` before the three changes (the three were the only failures); 66 passed across the new file, `test_prompt_telemetry.py`, `test_spec_convergence_telemetry.py` and `test_checkout_telemetry_isolation.py` after.

## workflows/telemetry/hallucination_log.py

**New: `tests/unit/test_hallucination_log_loud_failure.py` (6).** Site tests for 105, 114 and 123, both sinks failing, and two kept-behaviour tests: a sink given as None, and both sinks written.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the kept-behaviour tests).

**Changed tests:** in `test_hallucination_telemetry.py`, `test_missing_audit_dir_skips_that_sink_without_error` is now `test_missing_audit_dir_alerts_and_raises_after_the_other_sink`, and `test_sink_failure_is_swallowed` is now `test_sink_failure_alerts_and_raises`.

**Neighbouring suites:** 235 passed across the new file, `test_hallucination_telemetry.py`, `test_checkout_telemetry_isolation.py` and `test_implementation_spec_workflow.py`.

## visual_gate/config.py

**New: `tests/unit/test_visual_gate_config_loud_failure.py` (6).** Site tests for 77 (absent and empty) and 79, plus an explicit zero floor, a full declaration and no declaration, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 3 failed, 3 passed (the kept-behaviour tests).

**Changed tests:** none; every existing declaration already carries both keys.

**Neighbouring suites:** 127 passed across the new file, `test_contract_fidelity.py`, `test_gate_opens_browser.py`, `test_visual_gate_decompose.py`, `test_visual_gate_loop.py`, `test_visual_gate_guardrails.py`, `test_visual_gate_stage.py` and `test_visual_gate_live_resume.py`; `test_assertion_manifest.py` 29 passed.

## utils/retry.py

**New: `tests/unit/test_utils_retry_loud_failure.py` (5).** Two site tests (a failure not worth retrying, and retries exhausted), plus a quiet success and the failed result still returned, not raised (two cases), which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 2 failed, 3 passed (the kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 85 passed across the new file, `test_utils_retry.py`, `test_retry_gate_wiring.py` and `test_retry_gate.py`; 23 passed across `test_gemini_retry_boundary.py`, `test_json_verdict_review_test_plan.py` and `test_review_test_plan_structured_output.py`.

## utils/process.py

**New: `tests/unit/test_process_loud_failure.py` (6).** Site tests for 33 (a failing `taskkill`) and 41 (a `taskkill` timeout, an OS refusal), plus three that pin the quiet answers: `taskkill` exit 0, `taskkill` exit 128 ("not found"), and `ProcessLookupError`.

**Before the fix, measured** against the unchanged module: 3 failed, 3 passed (the kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 97 passed across the new file, `test_gemini_call_bounds.py`, `test_gemini_client.py`, `test_gemini_client_loud_failure.py`, `test_llm_idle_timeout.py` and `test_one_claude_cli_transport.py`.

## utils/workflow_timeout.py

**New: `tests/unit/test_workflow_timeout_loud_failure.py` (3).** Two site tests (the alert precedes the exit; the exit happens when the alert cannot be delivered), plus a disabled timeout that arms nothing. `os._exit` is replaced for the test.

**Before the fix, measured** against the unchanged module: 2 failed, 1 passed (the kept-behaviour test).

**Changed tests:** none.

**Neighbouring suites:** 15 passed across the new file and `test_workflow_timeout.py`.

## telemetry/cost.py

**New: `tests/unit/test_telemetry_cost_loud_failure.py` (6).** Site tests for 73 (two unpriced models, a sum that meets one, the instrumented record carrying None), plus a priced model and a priced model with no tokens, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the kept-behaviour tests).

**Changed tests:** in `test_cost_estimator.py`, `TestUnknownModel`'s four tests (0.0 and a WARNING) are three that expect None: `test_unknown_model_has_no_estimate`, `test_gemini_model_has_no_estimate`, `test_gpt_model_has_no_estimate`. The warning test is gone with the warning.

**Neighbouring suites:** 50 passed across the new file, `test_cost_estimator.py` and `test_llm_instrumentation.py`.

## utils/speedrun.py

**New: `tests/unit/test_utils_speedrun_loud_failure.py` (5).** Site tests for 144, 320 and 335, plus an absent run log and a written attempt, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 3 failed, 2 passed (the kept-behaviour tests).

**Changed test:** `test_speedrun.py::test_run_logger_skips_malformed_lines` is now `test_run_logger_refuses_malformed_lines`.

**Neighbouring suites:** 35 passed across the new file, `test_speedrun.py` and `test_model_record.py`.

## telemetry/store.py

**New: `tests/unit/test_telemetry_store_loud_failure.py` (7).** Site tests for 71, 88, 114 and 127, plus a disabled store, a day with no file, and written records read back and queried, which pin kept behaviour.

**Before the fix, measured** by putting HEAD's `store.py` back: 4 failed, 3 passed (the kept-behaviour tests).

**Changed test:** `test_llm_instrumentation.py::TestWriteFailure::test_oserror_does_not_propagate` is now `test_oserror_alerts_and_propagates`; the file's now-unused `import logging` is removed.

**Neighbouring suites:** 31 passed across the new file, `test_llm_instrumentation.py` and `test_telemetry_cost_loud_failure.py`.

## telemetry/emitter.py

**New: `tests/unit/test_telemetry_emitter_loud_failure.py` (10).** Site tests for 68, 84, 151, 156, 192, 200 and 203; tests for 54 and 171 that pin the two kept answers; and a healthy emit and flush.

**Before the fix, measured** by putting HEAD's `emitter.py` back: 7 failed, 3 passed (the two won't-do pins and the healthy path).

**Changed tests:** in `test_telemetry_emitter.py`, `TestWriteToBuffer::test_never_raises` is now `test_a_buffer_write_failure_alerts_and_raises`, and `TestEmit::test_never_raises_on_any_error` is now `test_an_event_that_cannot_be_built_alerts_and_raises`; the now-unused `Path` import is removed.

**Neighbouring suites:** 120 passed across the new file, `test_telemetry_emitter.py`, `test_factory_report.py`, `test_red_phase_import_is_named.py`, `test_spec_test_missing_imports.py` and `test_requirements_graph_halts.py`.

## telemetry/actor.py

**New: `tests/unit/test_telemetry_actor_loud_failure.py` (5).** Site tests for 34 (a failing `gh`; the token never requested) and 48 (`gh` missing, `gh` timing out), plus a logged-in `gh` that names the user quietly.

**Before the fix, measured** against the unchanged module: 4 failed, 1 passed (the kept-behaviour test).

**Changed tests:** none; `test_telemetry_actor.py::test_fallback_on_error` still holds ("unknown" on `FileNotFoundError`).

**Neighbouring suites:** 45 passed across the new file, `test_telemetry_actor.py`, `test_telemetry_emitter.py` and `test_telemetry_emitter_loud_failure.py`.

## speedrun/restore.py

**New: `tests/unit/test_restore_loud_failure.py` (7).** Site tests for 46, 83, 140 (two) and 150 against a real temporary git repository, plus the quiet "not restorable" (no ref, no path) and a file restored from `HEAD`, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 5 failed, 2 passed (the kept-behaviour tests).

**Changed tests:** `test_restore_from_graveyard.py::test_a_path_outside_the_repo_declines` is now `test_a_path_outside_the_repo_is_refused`, and `test_resume_after_failure.py::test_restore_artifact_outside_repo_refuses` expects the `ValueError`; both returned False.

**Neighbouring suites:** 136 passed across the new file, `test_input_rebuild_from_refs.py`, `test_restore_from_graveyard.py`, `test_restore_prefers_durable_and_base.py`, `test_resume_after_ceiling_halt.py`, `test_resume_from_pr_stage.py`, `test_spec_handoff_survives_janitor.py`, `test_speedrun_roll_kill.py`, `test_resume_after_failure.py` and `test_leavings_janitor.py`.
