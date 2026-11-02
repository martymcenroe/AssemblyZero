# Test report: #4545

## Unit

`tests/unit/test_conservation_reads_ranges.py`, 62 tests. The fixture is the real run's shape made generic: a spec whose Section 10.1 fence holds `test_req_010` through `test_req_130`, and a verdict asking for "test_req_060 through test_req_130" to be removed.

- T1 (R1): `test_t1_removing_the_whole_requested_range_passes_conservation` and `test_t1_removing_the_six_inside_the_endpoints_passes_conservation`, through `_apply_pinning`; `test_the_drafter_node_lands_the_requested_removal_first_time`, through `generate_spec` with an edit-script drafter. Both T1 tests fail against `main`'s pinning code: on the whole range conservation fires and names 070 through 120, and on the inner six the previous draft comes back.
- Still refused: `test_a_test_outside_the_range_is_still_refused` (050 removed with the range; conservation names 050 alone), `test_a_test_the_verdict_never_mentions_is_still_refused` (an unnumbered test inside the removed span), `test_a_t_style_range_does_not_reach_another_prefix`, and the control `test_naming_only_the_endpoints_still_refuses_the_six_between`. `test_a_t_style_range_names_its_own_tests` covers `T060 to T130` against `test_t` tests.
- T2 (R2): `test_t2_the_reprompt_names_conservation_and_the_removed_test` reads the failure section of the second and third prompts; `test_t2_the_halt_names_conservation_and_the_removed_test` reads the halt. Neither says "locked content".
- T3 (R3): `test_t3_the_count_is_the_number_of_refused_edits`: two edit blocks, and the halt says "all 2 edit block(s)". `TestTheReasonForEachGate` covers each branch of `_pinning_refusal` and that `conservation_lost` carries the named tests.
- The grammar: `TestTheRangeGrammar` runs every accepted endpoint form against every joiner (40 cases), pins the joiner lists, and checks twelve forms that are not ranges.

The pinning suites from earlier issues pass unchanged: `test_pinning_conservation.py`, `test_revision_pinning.py`, `test_generate_spec_pinning.py`, `test_spec_edit_script.py`, `test_gate_registry.py`, `test_interaction_matrix.py`, `test_golden_disasters.py` and the rest of the pinning set.

## Real calls

None. Every drafter is a mock.

## Full suite

`tests/unit/`: 14,007 passed, 66 skipped, 7 deselected, 7 xfailed.
