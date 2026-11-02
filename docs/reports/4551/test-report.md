# Test report: #4551

## Unit

`tests/unit/test_completeness_typescript_criteria.py`, 19 tests. The fixtures have the real run's shape (Python tests for rows 010 to 050, Vitest tests for rows 060 to 130, a planned `.test.ts` diff) in an invented domain.

- T1 (R1): `TestVitestTestsCoverTheirCriteria::test_rows_060_to_130_in_section_ten_pass` and `test_rows_060_to_130_in_a_planned_test_file_pass`. Both fixtures, written out and checked on `main` at `de22f4eb`, fail with the eight runtime criteria missing. Also: `test_main_reported_every_runtime_row_missing`, `test_a_describe_title_names_the_criterion_of_the_tests_it_holds`, `test_tsx_fences_are_read_with_the_tsx_grammar`.
- T2 (R1): `TestAnUntestedCriterionStillFails::test_row_110_with_no_test_in_either_language_fails`, with `test_a_todo_or_skipped_test_covers_nothing`, `test_a_test_the_diff_removes_covers_nothing`, `test_a_current_state_excerpt_is_not_a_test_the_spec_carries`, `test_a_longer_tag_does_not_cover_a_shorter_one`, `test_a_planned_file_that_is_not_a_test_file_is_not_read`.
- T3 (R2): `TestTheRecurrenceHaltNamesItsGate::test_refusals_name_the_completeness_check_and_classify` (the class and the recovery plan), `test_a_conservation_override_names_the_conservation_gate`, `test_with_no_reversion_the_halt_keeps_its_old_reading`.
- T4 (R3): `TestAnAnswerToANamedComplaintSurvivesPinning::test_the_answering_line_survives_through_the_real_call_site`, with `test_the_placeholder_is_locked_by_naming_alone`, `test_without_the_answer_vocabulary_the_line_was_refused` (the old behaviour), `test_a_line_that_answers_nothing_is_still_refused`, `test_the_vocabulary_reads_the_complaints_keys_and_tokens`.

## Real draft

All N3 completeness checks run, with no model call, on the halted run's last spec draft and its saved state: all pass, `criteria_have_tests` at 13/13 across 28 tests, 16 TypeScript. On `main` the same draft fails `criteria_have_tests` with eight criteria missing.

## Real calls

None.

## Full suite

`tests/unit/`: 14,189 passed, 66 skipped, 7 deselected, 7 xfailed.
