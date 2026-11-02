# Test report: #4552

## Unit

`tests/unit/test_pinning_section_references.py`, 64 tests. The fixture has the real run's shape (edge-case lines under `### 5.1`, a "No changes required" line under a numbered change instruction, a fenced function under `### 6.3`) in an invented domain.

- T1 (R1, AC1): `TestASubsectionReferenceNamesItsHeading::test_the_revision_the_verdict_asked_for_passes`, and the same revision through `_apply_pinning` in `test_it_passes_through_the_real_call_site`: no refusal, no regression event. Also `test_the_other_change_instruction_the_run_refused_passes`, `test_the_heading_text_after_the_number_does_not_matter`, `test_the_subsection_holds_its_fenced_functions`, `test_a_sibling_the_verdict_never_names_stays_locked`, `test_a_sibling_edit_is_still_refused`, `test_a_block_that_only_mentions_the_section_stays_locked`, `test_section_one_does_not_reach_section_ten`, `test_a_completeness_failure_names_its_subsection_too`.
- Run against `main` at `035b31b7`, 13 of the 16 tests in the T1, T2 and T3 classes fail. The three that pass there are `test_a_sibling_the_verdict_never_names_stays_locked` and T3's `test_an_unrelated_edit_stays_refused` and `test_it_never_widens_to_the_whole_draft`, which pin behaviour `main` already had.
- T2 (R2, AC2): `TestASectionReferenceNamesItsSubsections::test_section_six_names_its_subsections_and_not_seven`, with `test_an_edit_under_six_passes_and_one_under_seven_is_refused` and `test_the_section_ends_at_a_heading_without_a_number`.
- T3 (R3, AC3): `TestAnUnmatchedReferenceNamesNothing::test_an_unrelated_edit_stays_refused`, with `test_it_never_widens_to_the_whole_draft` and `test_a_mention_in_the_text_does_not_stand_in_for_a_heading`.
- The closed grammar: `TestTheReferenceGrammar` enumerates 12 accepted forms, 12 rejected forms, the vocabulary constants, the canonical token, whole-token parsing, 10 heading numbers, and a heading inside a fence.
- Conservation: `TestASectionReferenceNamesNoTest` (dropping a test under a named section is refused entire; naming the test still lets it go).
- Other readers: `TestTheOtherReadersAgree` (the #4551 answers vocabulary and the addressability classifier).

Adjusted: `test_error_path_message_is_addressable.py::test_the_bare_message_was_the_defect` uses the error-path check's new header, and `test_review_feedback_carries_items.py::test_the_old_text_left_the_three_lines_locked` reads its rationale without the LLD's "Section 10.1", which now names the draft's 10.1.

## Real round

`named_line_flags` on the halted run's previous draft with the verdict that asked for the edits: the refused lines read LOCKED on `main` and NAMED here.

## Real calls

None.

## Full suite

`tests/unit/`: 14,253 passed, 66 skipped, 7 deselected, 7 xfailed.
