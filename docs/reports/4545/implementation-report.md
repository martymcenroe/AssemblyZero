# Implementation report: #4545

An implementation-spec run's reviewer asked for the tautological tests "test_req_060 through test_req_130" to be removed. The drafter's edit removed them. The conservation gate (#2559) counted a test as named only by its exact identifier: the two endpoints matched, the six tests between them did not, and conservation refused the revision entire. The re-prompt said "every edit touched locked content and was refused by pinning (0 refusal(s))", so the drafter sent the same revision twice more and the run halted `edit_script_rejected`.

## What changed

- `assemblyzero/workflows/implementation_spec/revision_pinning.py`: a closed grammar for ranges of numbered tests. An endpoint is a numbered test name (`test_req_060`, `test_req_060_slug`, `test_t060`, `test_060`: a prefix, the first digit run, then nothing or `_` and more) or a T-style id (`T060`, standing for `test_t060_...`). The joiners are enumerated in `RANGE_WORD_JOINERS` (`through`, `to`, spaces both sides) and `RANGE_DASH_JOINERS` (hyphen, en dash, spaces optional). Both endpoints share a prefix and run low to high, or the text is not a range. `named_test_ranges` reads them; `range_named_tests` returns every test name in the draft that a range covers. `PinningResult` gains `conservation_lost`, the tests a conservation event names.
- `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py`: `_pinning_names` takes the draft and adds the range-named tests to the round's tokens, before the drafter is called and in pinning. The ever-named union reads ranges from prior verdicts and complaints the same way. `_apply_pinning` keeps its signature over a new `_pin_revision` that returns the whole result. When pinning returns the draft unchanged, `_pinning_refusal` gives the reason by gate: conservation names itself, the tests and every edit block it refused; locked content keeps its wording and its count of restored regions; a result with neither says so.

## What did not change

A test outside every named range, an unnumbered test, and a test of another prefix stay unnamed, and conservation still refuses their removal. A T-style range does not reach a `test_req_` test through a mapping table. The conservation event text, its registry head ("the revision removed"), and the halt's `[EDIT-SCRIPT] spec revision rejected` head are unchanged.
