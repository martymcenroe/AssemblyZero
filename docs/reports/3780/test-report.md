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
