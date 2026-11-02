# Test report: #4554

## Unit

`tests/unit/test_pinning_plural_section_references.py`, 76 tests, on the fixture `test_pinning_section_references.py` already holds (subsections 5.1, 5.2, 6.1 to 6.3, 7.1 and 10.1).

- T1 (R1, AC1): `TestATwoItemPluralNamesBothSections::test_edits_under_both_pass_and_one_under_a_sibling_is_refused`. "Update Sections 5.1 and 6.2" passes the edits under `### 5.1` and `### 6.2` and refuses the one under `### 5.2`. Also `test_it_names_what_the_two_singulars_name` (the plural's lines equal the union of the two singular references' lines), `test_the_real_verdicts_sentence_names_both`, `test_whole_sections_name_their_subsections`, `test_an_item_no_heading_carries_names_nothing`, `test_no_item_any_heading_carries_names_nothing` and `test_the_doubled_sign_reads_the_same`.
- T2 (R2, AC2): `TestACommaListNamesEachSection::test_three_items_name_three_subsections`, with `test_edits_under_all_three_pass` and `test_four_items`.
- T3 (R3, AC3): `TestAnotherPluralShapeNamesNothing::test_a_range_or_a_choice_names_nothing` for "Sections 5.1 through 5.3" and "Sections 5.1 or 5.2", and `test_an_edit_under_its_first_item_stays_refused` for both.
- The closed grammar: `TestThePluralGrammar` pins the four vocabulary constants and the unchanged singular ones, and enumerates 17 accepted shapes, 26 refused shapes, 3 shapes that name less than they seem to, the canonical tokens, and 7 whole-token cases for `section_token_numbers`.
- Conservation: `TestAPluralNamesNoTest` (dropping a test under a section a plural names is refused entire, and a backticked plural cannot reach a test whose block mentions it).
- Other readers: `TestTheOtherReadersAgree` (#4551's answers leave a plural out, quoted whole or not; a block that only mentions a plural stays locked; the addressability classifier reads both headings).

Run against `main` at `98962a54` with a replay script: T1's revision comes back with 3 refusals and neither the 5.1 nor the 6.2 edit kept, T2's text yields no reference, and a backticked plural in a completeness message counts as answered by a line that repeats it.

Adjusted: `test_pinning_section_references.py::TestTheReferenceGrammar::test_rejected_forms` listed "Sections 3.6 and 5.7 agree" as a refused plural. It now lists "Sections 3.6 cover it", a one-item plural, which the plural grammar still refuses.

## Real calls

None.

## Full suite

`tests/unit/`: 14,329 passed, 66 skipped, 7 deselected, 7 xfailed.
