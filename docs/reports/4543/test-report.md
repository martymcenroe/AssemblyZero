# Test report: #4543

## Unit

`tests/unit/test_agy_output_limit.py`, 19 test functions (23 cases with parameters). The fixtures follow agy's record of conversation `986f610b` (step types, token counts and agy's `ERROR_MESSAGE` text) and the envelope's usage from the model-call ledger; the answer text is invented.

- T2: `test_t2_the_cut_envelope_is_named_as_cut_at_the_output_limit` (the failure opens with the cut, names 65,531 tokens and the record) and `test_t2_invoke_classifies_the_cut_and_never_returns_the_answer` (`OUTPUT_LIMIT` on every attempt and on the result, retried to the attempt limit, no answer returned, never UNKNOWN).
- `test_t2_the_answer_is_never_in_the_failure`: the answer's text is absent; its length is given.
- `test_a_retry_that_answers_is_used`: a cut attempt followed by an answer returns the answer.
- `test_an_error_with_no_cut_in_the_record_is_not_called_a_cut`, `test_an_unreadable_record_is_said_and_not_guessed`, `test_a_broken_record_is_said_and_not_guessed`: an `ERROR` that agy's record does not explain stays `agy status 'ERROR'` and says what the record showed or why it could not be read.
- `test_agys_stderr_is_kept_in_the_failure`.
- `test_ids_paths_and_counts_in_a_status_failure_are_not_read_as_words`, `test_an_answer_naming_a_quota_is_not_a_quota_failure`, `test_the_first_hundred_characters_carry_no_number` (65,529 and 65,503 tokens): no id, path, count or answer text is read as a rate limit or a capacity outage.
- `test_agys_own_stderr_still_classifies_a_status_failure`, `test_a_field_agy_adds_to_its_envelope_still_classifies_a_status_failure`: agy's own words still classify.
- `test_the_record_path_is_agys_brain_under_the_home`, `test_a_conversation_id_that_is_not_a_uuid_makes_no_path` (4 cases), `test_an_envelope_naming_no_conversation_reads_nothing`, `test_a_wsl_agys_record_is_read_through_wsl`, `test_a_wsl_cat_that_fails_is_said`, `test_cuts_are_counted_per_notice`.

`tests/unit/test_agy_agent_warning_scope.py`: its `_agy_once` stand-in now makes the record read raise, so the test never reads this machine's agy home. Its 7 tests pass unchanged otherwise. `tests/unit/test_fail_open_audit.py` passes with the baseline unchanged.

## agy's real records

The failure text was run over agy's records of the three calls (no model call): each reads as cut, at 65,531, 65,532 and 65,532 output tokens.

## Real calls

One, bounded at 480 s, `gemini-3.8-flash-high`: it was ended in its first turn with no envelope (conversation `e86c5406`). T3 was not run: R3 does not apply, as the issue records.

## Full suite

`tests/unit/`: 13,967 passed, 66 skipped, 7 xfailed.
