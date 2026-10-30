# Test Report: the core/ package under standard 0034 (#3581 step 5)

Each fixed site has a test that fails before its fix and passes after, measured by stashing the module's source by named path in the worktree. Filled in module by module.

## llm_provider.py and provider_storm.py

**New: `tests/unit/test_llm_provider_loud_failure.py` (40).** Each test is named for its ledger line. One per site, plus a clean-stream test and a real-answer test that pin what is kept.

**Before the fix, measured** with `llm_provider.py` and `provider_storm.py` stashed: 38 failed, 2 passed. The two are `test_a_real_answer_still_succeeds` and `test_1729_the_rate_limit_is_read_from_error_type`, which pin kept behaviour.

**Changed tests, each asserting the new behaviour in place of the retired one:**
- `test_llm_provider.py::test_cost_calculation_unknown_model`: an unpriced model raises; it returned 0.0.
- `test_llm_provider.py`: the two raw-stdout fallback tests now expect `""`.
- `test_llm_idle_timeout.py::test_the_idle_threshold_is_overridable_too`: a bad or non-positive value raises.
- `test_provider_storm.py::test_non_timeout_errors_do_not_trip_the_storm_counter`: a source-text check, now anchored on the timeout branch (`if outcome.timed_out:`). Its old anchor was the storm probe's `except subprocess.TimeoutExpired`, and the slice reached the real branch only while no `return call_result` sat between them.

**Neighbouring suites:** 266 passed across `test_llm_provider.py`, `test_llm_idle_timeout.py`, `test_one_claude_cli_transport.py`, `test_provider_storm.py`, `test_llm_instrumentation.py`, `test_prompt_caching.py`, `test_nested_claude_env.py`, `test_model_record.py`, `test_seat_attribution.py` and the new file.

## gemini_client.py

**New: `tests/unit/test_gemini_client_loud_failure.py` (12)**, each named for its ledger line, plus `test_a_good_answer_is_quiet`.

**Before the fix, measured** with `gemini_client.py` stashed: 11 failed, 1 passed (`test_a_good_answer_is_quiet`, which pins kept behaviour).

**Changed test:** `test_llm_instrumentation.py::test_missing_usage_metadata` now expects the raise. It is joined by `test_a_named_model_with_no_usage_has_no_counts`, which keeps the absent-counts case.

**Changed later (found by the batch after it, 2026-10-30):** `test_stage_watchdog.py::TestProgrammingErrorsAreNotRetried` still asserted the retired shape, a "Programming error" failed call and a raised `RuntimeError` being retried, and its 3 tests failed on this branch. They now assert the new one: `test_type_error_propagates_without_retry_or_sleep` and `test_attribute_error_also_propagates_at_once` (one attempt, no sleep), and `test_a_transport_failure_still_retries`, where `_invoke_via_cli` returns a failed result, the only way a transport failure arrives now.

**Neighbouring suites:** 266 passed across the agy transport, sandbox, call-bound, client, headline, scorecard, call-guard, instrumentation, preflight, scout and structured-output tests.

## verdict_schema.py

**New: `tests/unit/test_verdict_schema_loud_failure.py` (7):** the four fixed sites, a verdict that still parses with its reason, and two `test_716_*` that pin the won't-do (rendered feedback is still compared by its lines).

**Before the fix, measured** with `verdict_schema.py` stashed: the 4 site tests failed and the 3 that pin kept behaviour passed.

**Changed tests**, each asserting the raise in place of "nothing found": `test_finalize_structured_output.py::test_empty_content`, `test_structured_stagnation.py::test_empty_feedback_cannot_be_compared` (renamed from `test_empty_feedback_not_stagnant`), `test_verdict_schema.py::test_empty_text`.

**Neighbouring suites:** 801 passed across every test that imports the module, before the three changes above (the 3 failures were those three tests).

## seats.py

**New: `tests/unit/test_seats_loud_failure.py` (8)**, one per site plus `test_a_readable_lift_time_is_quiet` and the off-Linux case. `tests/conftest.py` replaces `other_side_claude_home` in every test, so the file captures the real function at import.

**Before the fix, measured** with `seats.py` stashed: 7 failed, 1 passed (`test_a_readable_lift_time_is_quiet`). Measured twice; the second time after the lock handlers moved from a printed line to `alert_operator`.

**Neighbouring suites:** 344 passed across the seats, spend-lock, profile, attribution and agy-seat tests.

## resume_contract.py

**New: `tests/unit/test_resume_contract_loud_failure.py` (14)**, one or two per site, plus four that pin kept behaviour: an absent file is still absent, no contract is still a silent pass, an intact world is quiet and consumes the contract, and the contract is written as JSON.

**Before the fix, measured** with `resume_contract.py` stashed: 10 failed, 4 passed (the four that pin kept behaviour).

**Neighbouring suites:** 94 passed across the halt node, halt evidence, home-state guard, implementation and LLD runner tests that write or check contracts.

## interface_surface.py

**New: `tests/unit/test_interface_surface_loud_failure.py` (13)**, one per site plus `test_a_readable_repo_still_gives_its_whole_surface`.

**Before the fix, measured** with `interface_surface.py` stashed: 12 failed, 1 passed (the kept whole-surface case).

**Changed tests:** `test_interface_surface.py::test_syntax_error_raises` (was `test_syntax_error_falls_back_to_head`) and `test_missing_repo_raises` (was `test_missing_repo_yields_empty_map`).

**Neighbouring suites:** 232 passed across `test_interface_surface.py` and `test_implementation_spec_workflow.py` before those two changes, which were the 2 failures.

## validation/test_plan_validator.py

**New: `tests/unit/test_test_plan_validator_loud_failure.py` (7)**: the five sites, plus `test_another_table_in_section_10_is_not_read_as_scenarios` and `test_a_clean_plan_has_no_parse_errors_and_passes`, which pin that only scenario tables are read.

**Before the fix, measured** with the validator stashed: 5 failed, 2 passed (the two that pin kept behaviour).

**Neighbouring suites:** 540 passed, 1 skipped, across every test that imports the validator, the integration parsing chain included.

## settlement.py

**New: `tests/unit/test_settlement_loud_failure.py` (9)**: the five sites, plus three that pin kept behaviour (an absent input is quiet and unsettles, a binding doc inside the repo keeps its relative key, a readable artifact settles with its hash).

**Before the fix, measured** with `settlement.py` stashed: 6 failed, 3 passed (the three that pin kept behaviour).

**Neighbouring suites:** 216 passed across every test that imports the module, plus the two audits' own tests.

## capacity.py

**New: `tests/unit/test_capacity_loud_failure.py` (12)**: nine for the seven sites (two each for 75 and 89), plus three that pin kept behaviour (a missing state file is no record and quiet, a record with a null reset time binds for the cooldown, an unchecked provider is not listed as exhausted).

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 9 failed, 3 passed (the three that pin kept behaviour). Each failure was the missing raise, or Gemini reported as available.

**Changed test:** `test_capacity_gate.py::test_corrupt_state_file_raises` (was `test_corrupt_state_file_does_not_block_work`).

**Neighbouring suites:** 428 passed and 1 failed across `test_capacity_gate.py`, `test_capacity_loud_failure.py`, `test_capacity_fidelity.py`, `test_capacity_stage_retry.py`, the Claude CLI provider tests (`test_llm_provider.py`, `test_llm_provider_loud_failure.py`, `test_529_hardening.py`, `test_one_claude_cli_transport.py`, `test_llm_idle_timeout.py`, `test_llm_provider_json_schema.py`, `test_nested_claude_env.py`, `test_model_call_guard.py`, `test_claude_spend_lock_refusal.py`), the orchestrator entry tests (`test_alert_channel_at_start.py`, `test_stage_verdict_is_explicit.py`) and the two audits' own tests. The one failure was the fail-open baseline going stale by the three fixed handlers; after `--write-baseline` the audits' tests pass.

## preflight.py

**New: `tests/unit/test_preflight_loud_failure.py` (10)**: eight for the five sites (two each for 64, 94 and 102, one for the tag), plus `test_a_known_alias_a_full_id_and_no_gemini_spec_are_answers` and `test_a_passing_probe_is_quiet`, which pin kept behaviour. The file overrides `tests/unit/conftest.py`'s `_bypass_gemini_preflight`, so the real check runs against a fake client.

**Before the fix, measured** with HEAD's `preflight.py` put back in place for the run: 8 failed, 2 passed (the two that pin kept behaviour).

**Changed test:** `test_preflight_transport.py::test_a_spec_without_a_known_name_raises` (was `test_a_spec_without_a_known_name_still_gets_a_gemini_model`).

**Neighbouring suites:** 1434 passed, 1 skipped and 1 failed across every unit and integration test file that names the preflight, `generate_draft` or `generate_spec`, plus the two audits' own tests. The failure was `test_no_fixed_site_left_in_the_baseline`, before `--write-baseline`; after it the audits' tests pass.

## retry.py

**New: `tests/unit/test_retry_loud_failure.py` (4)**: one per site, plus `test_a_retry_that_recovers_writes_no_error_line`, which pins that a recovered retry is not a failure.

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 3 failed, 1 passed (the one that pins kept behaviour).

**Changed tests:** none; no existing test read the stdout lines.

**Neighbouring suites:** 91 passed across `test_retry.py`, the new file and the two audits' own tests.

## retry_gate.py

**New: `tests/unit/test_retry_gate_loud_failure.py` (8)**: two for the site (with and without fail-fast), plus two that pin kept behaviour: every class `classify_failure` returns is accepted (parametrized over five messages) and a transient failure keeps the caller's budget.

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 2 failed, 6 passed (the kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 876 passed, 5 skipped and 1 failed across every unit and integration test file that names `retry_gate`, `should_retry`, `utils/retry.py` or either orchestrator, plus the two audits' own tests. The failure, `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`, is not this change: it fails the same way with HEAD's `retry_gate.py` in place. Its `mock_all_stages` fixture has no runner for the `visual` stage that 8b3cb594 (#2518) added to `STAGE_ORDER`, so the graph loops until LangGraph's recursion limit.

## errors.py

**New: `tests/unit/test_errors_loud_failure.py` (3)**: the site, through `classify_anthropic_error` with a real `anthropic.RateLimitError`, plus two that pin kept behaviour (a numeric header is read and quiet; no header is no hint and quiet).

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 1 failed, 2 passed (the two that pin kept behaviour).

**Changed tests:** none.

**Neighbouring suites:** 359 passed across every test file that imports `assemblyzero.core.errors`, `test_llm_provider.py` (the Anthropic provider) and the two audits' own tests.

## stage_watchdog.py

**New: `tests/unit/test_stage_watchdog_loud_failure.py` (5)**: two for the site (a stall alerts once; an undelivered alert is raised when the stage ends), plus three that pin kept behaviour (SLOW, no nominal and an operator wait do not alert). The SLOW test backdates the watchdog's start, so the ratio does not depend on timing.

**Before the fix, measured** with HEAD's `stage_watchdog.py` put back in place for the run: 2 failed, 3 passed (the three that pin kept behaviour).

**Changed tests:** none.

**Neighbouring suites:** 164 passed and 3 failed across every test file that imports the module and the two audits' own tests. The 3 failures are not this change: `test_stage_watchdog.py::TestProgrammingErrorsAreNotRetried` fails the same way with HEAD's `stage_watchdog.py` in place. Those tests drive `GeminiClient.invoke` and assert its behaviour before faa39781 (#3777), which made a fault in the call raise instead of returning "Programming error"; they were not among that commit's changed tests.

## state_persistence.py

**New: `tests/unit/test_state_persistence_loud_failure.py` (5)**: two for 77 (a corrupt snapshot and an unreadable one), `test_an_absent_snapshot_is_none`, which pins kept behaviour, and two `test_42_*` that pin the won't-do (a value JSON cannot hold is written as text, and the docstring carries the reason).

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 3 failed, 2 passed. The failures were the two for 77 and the docstring pin; the passes were the absent snapshot and the kept `str()`.

**Changed test:** `test_state_persistence.py::test_load_corrupt_json_raises` (was `test_load_corrupt_json_returns_none`).

**Neighbouring suites:** 411 passed and 1 failed across every unit and integration test file that names the module, HALT or the resume contract, plus the two audits' own tests. The failure was the fail-open baseline going stale by the fixed handler; after `--write-baseline` the audits' tests pass.

## run_record.py

**New: `tests/unit/test_run_record_loud_failure.py` (28)**: twenty-six for the twenty-four sites (two each for 103 and 134), plus two that pin kept behaviour (a tee that outlives its record writes to the console quietly, and a clean run alerts no one). The failures are injected at the edges the module already uses: a run log opened as a file whose write, flush or close fails, an events log whose open is refused, a console that raises `BrokenPipeError`, and git commands that exit 128 or cannot run.

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 26 failed, 2 passed (the two that pin kept behaviour). Each failure was the missing alert, the missing raise, or the tag still in place.

**Changed test:** `test_run_record.py::test_outside_a_git_repo_it_raises` (was `test_never_raises_outside_a_git_repo`).

**Neighbouring suites:** 639 passed across every test file that imports the module (`test_run_record.py`, the new file, `test_model_record.py`, `test_decision_table_survives.py`, `test_impl_dry_run_is_dry.py`, `test_lld_dry_run_is_dry.py`, `test_lld_writes_only_worktree.py`), every test file that drives `tools/run_requirements_workflow.py` or `tools/run_implement_from_lld.py` (twenty-three more), and the two audits' own tests. Run before `--write-baseline`, the same set less the tool tests had one failure, `test_no_fixed_site_left_in_the_baseline`, which the new baseline cleared.

## model_record.py

**New: `tests/unit/test_model_record_loud_failure.py` (11)**: eight for the four sites (three for 70, three for 123), plus three that pin kept behaviour (an empty spec has no id and is quiet, a `mock:` or `scripted:` spec resolves to its model, and no open record is no write).

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 8 failed, 3 passed (the three that pin kept behaviour).

**Changed tests:** none.

**Neighbouring suites:** 243 passed and 1 failed across every test file that imports `model_record` or `call_recording` (`test_model_record.py`, the new file, `test_seat_attribution.py`, `test_call_recording_isolation.py`, `test_call_recording_roll.py`, `test_impl_lands_through_driver.py`, `test_impl_standalone_end_state.py`, `test_lld_mock_completes.py`, `test_lld_mock_is_offline.py`, `test_lld_writes_only_worktree.py`, `test_llm_provider_loud_failure.py`), the run record's two test files and the two audits' own tests. The one failure was `test_no_fixed_site_left_in_the_baseline`, before `--write-baseline`; after it the audits' tests pass (77).

## call_recording.py

**New: `tests/unit/test_call_recording_loud_failure.py` (15)**: eleven for the ten sites (two for 187), plus four that pin kept behaviour (a clean recording reads back whole and in order, a partial last line is counted and not read and is quiet, an absent recording is empty and quiet, and a faithful replay is quiet).

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 11 failed, 4 passed (the four that pin kept behaviour).

**Changed tests:** none. Every existing test that builds a `ReplayProvider` gives its calls a `success` field, and none writes a recording by hand.

**Neighbouring suites:** 298 passed and 1 failed across every test file that imports `call_recording` or `model_record` (`test_call_recording_isolation.py`, `test_call_recording_roll.py`, `test_model_record.py`, `test_seat_attribution.py`, `test_impl_lands_through_driver.py`, `test_impl_standalone_end_state.py`, `test_lld_mock_completes.py`, `test_lld_mock_is_offline.py`, `test_lld_writes_only_worktree.py`, `test_llm_provider_loud_failure.py`, both new files), every test file that imports the replay (`test_replay_run.py`, `test_github_writes_inert.py`, `test_alert_channel_at_start.py`) and the two audits' own tests. The one failure was `test_no_fixed_site_left_in_the_baseline`, before `--write-baseline`; after it the audits' tests pass (77).

## audit.py

**New: `tests/unit/test_audit_loud_failure.py` (11)**: nine for the five sites (two for 238, three for 267, two for 270), plus two that pin kept behaviour (an empty log is no entries and quiet, and a clean log reads whole).

**Before the fix, measured** by writing the tests first and running them against the unchanged module: 8 failed, 2 passed (the two that pin kept behaviour). The ninth site test, a shard the consolidator removes between the listing and the read, was added after the fix, when the first version still read such a shard as empty; measured with HEAD's `audit.py` put back in place for the run: 9 failed, 2 passed.

**Changed test:** `tests/integration/test_audit_sharding.py::TestTailSkipsLocked::test_a_shard_that_is_not_json_raises` (was `test_graceful_degradation_on_unreadable`, which asserted the partial result).

**Neighbouring suites:** 122 passed and 6 xfailed across `test_audit.py`, the new file, `test_consolidate_logs_large_file.py`, `test_cov_target_resolution.py` and the two audits' own tests, plus 22 passed in `tests/integration/test_audit_sharding.py` (run with `-m integration`). Run before `--write-baseline`, the same unit set had one failure, `test_the_baseline_is_not_stale`: the fail-open baseline still listed the four removed handlers.

## #4161: the checkout's telemetry logs

**New: `tests/unit/test_checkout_telemetry_isolation.py` (5).** Three T2 tests send one writer's record at the checkout itself and find the checkout's log unchanged and the record under `tmp_path`; one checks that a record sent to a test's own directory stays there; T1 checks that the session guard watches exactly the paths the unredirected writers use.

**Before the fix, measured** with the autouse fixture absent: the three T2 tests failed, the other two passed, and the new session guard failed the run naming all three files. Those writes, and the worktree's older byproducts from 2026-10-09, were recorded on #4161 and deleted.

**Neighbouring suites:** 130 passed across the new file and every test of the three writers, the factory report and the call-recording isolation.

## #4163: the call recorder between tests

**New: `tests/unit/test_call_recording_isolation.py` (3).** The first test arms the recorder; the second finds it disarmed; the third checks the artifact is gone and `/audit/` is ignored.

**Before the fix, measured** with the conftest change stashed: `test_2_the_next_test_finds_it_disarmed` failed, which is the leak shown.
