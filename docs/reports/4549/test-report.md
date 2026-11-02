# Test report: #4549

## Unit

`tests/unit/test_conservation_reads_ranges.py`, 202 tests (62 from #4545, reworked and extended here).

- T1 (R1): `TestARangeInBackticksNamesEveryTestInIt::test_t1_a_backticked_range_lets_the_requested_removal_through` (the verdict item in the resumed run's shape, "Functions `test_req_060` through `test_req_130` ...") and `test_t1_a_backticked_en_dash_range_lets_it_through`. Both fail on `main`, where conservation names 070 through 120.
- T2 (R1): `TestTheRangeGrammar::test_each_accepted_form_is_a_range` runs five endpoint forms by six joiners by five wrappings (bare, each in backticks, first in backticks, last in backticks, whole range in one span): 150 cases. On `main` the 90 cases with a backticked endpoint fail and the 60 bare and whole-span cases pass, so nothing accepted before is lost. `test_the_backticked_en_dash_range_written_out` checks `` `test_req_060`–`test_req_130` `` written out.
- T3 (R2): `test_forms_outside_the_grammar_are_not_ranges` runs the twelve forms refused before, bare and with each endpoint in backticks: 24 cases, all refused, as on `main`. `test_backticks_that_do_not_wrap_an_endpoint_are_not_ranges`: an unpaired closing backtick, an unpaired opening one, double backticks, and a word joiner with no space after a backtick.
- T4 (R3): `test_t4_a_test_outside_a_backticked_range_is_still_refused`: removing `test_req_050_...` with the backticked range is refused, and the conservation event names 050 alone.

## Real calls

None. Every drafter is a mock. The `main` comparison ran the pure tests only.

## Full suite

`tests/unit/`: 14,170 passed, 66 skipped, 7 deselected, 7 xfailed.
