# Test Report: each node's calls recorded under its own seat (#3577)

## New tests

`tests/unit/test_seat_attribution.py`, with a run record open and every seat on one spec (`mock:review`, the shape of `gemini.toml`, offline):

| Test | What it pins |
|---|---|
| `test_the_requirements_drafter_is_recorded_as_its_seat` | N1, driven end to end, records `requirements.draft` |
| `test_the_requirements_analysis_is_recorded_as_its_seat` | N0c, driven end to end, records `requirements.analyze` |
| `test_the_spec_drafter_resolves_its_own_seat_last` | spec N2 resolves `spec.review`, then `spec.draft`, then builds (on the source: the node needs an LLD on disk to reach its call) |
| `test_test_augmentation_is_recorded_as_its_seat` | a call made with `seat="impl.augment_tests"` records it, and N4c passes that seat to both of its calls |

## The tests fail without the fix

With the four node files stashed by name:

```
FAILED tests/unit/test_seat_attribution.py::test_the_requirements_drafter_is_recorded_as_its_seat
FAILED tests/unit/test_seat_attribution.py::test_the_requirements_analysis_is_recorded_as_its_seat
FAILED tests/unit/test_seat_attribution.py::test_the_spec_drafter_resolves_its_own_seat_last
3 failed, 1 passed
```

The fourth test passed at that point because it called `call_claude_for_file` directly. It now also asserts, on N4c's source, that both of N4c's calls pass the seat.

## Runs

With the fix, the new tests and their neighbours (escalation, gate timeout, N4c, requirements nodes, gate registry, halt-site renumbering, emits pairing, fail-open audit, model record): 315 passed.

Full unit tier: `2 failed, 10785 passed, 21 skipped, 7 deselected, 5 xfailed` in 698.78s. The two failures are #3468's pair, red on `main`.
