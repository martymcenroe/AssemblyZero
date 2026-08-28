# Test Report — The IO-Example Complaint Addresses Its Target (#2590)

## Issue Reference
[#2590](https://github.com/martymcenroe/AssemblyZero/issues/2590)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_completeness_pinning_deadlock.py` | **21 passed** (6 new) |
| `tests/unit/test_completeness_message_addressability.py` | **19 passed** (1 test moved) |
| combined | 40 passed in 0.5s |
| `tests/unit` (full) | see below |
| `ruff` on both touched test files | clean |

## The Fixtures Were Proved To Fail Without The Fix

The essential check: the production line was temporarily reverted and the new tests re-run.

**4 of 6 went red**, including the end-to-end deadlock test:

- `test_the_parameterised_function_is_addressed`
- `test_both_drafts_draw_the_same_token`
- `test_the_span_carries_no_call_parens`
- `test_the_demanded_example_survives_pinning_in_the_same_round`

**2 stayed green, correctly.** `test_the_zero_arg_function_stays_addressed` pins the case that already worked — it is the "must not regress" direction and green in both states is the right answer. `test_an_unnamed_sibling_function_is_still_locked` drives enforcement with explicit tokens rather than the message, so it is a scoping guard independent of the reword.

Without that distribution the suite would be compatible with a tautology.

## What Is Pinned

**The issue's table, both directions (4 tests).** Parameterised and zero-arg drafts each drive the **real** check and the **real** `named_tokens`; no message text is hand-written, so a reword that drops the address fails the suite. `test_both_drafts_draw_the_same_token` asserts both cases yield the identical token — if a future change makes addressability depend on the parameter list again, that is the assertion that says so. `test_the_span_carries_no_call_parens` is the specific regression guard.

**The class-3 end-to-end property (1 test).** Real complaint → real `named_tokens` → real `enforce_pinning`, with the drafter's fix in the **replacement** shape that enforcement actually refused. Asserts zero refusals, zero regressions, and that the example text survives in the merged output.

**The inverse (1 test).** Inside a fence, where `_blocks` splits per `def`: naming one function frees its block, and a sibling function meddled with in the same round is still reverted with a refusal recorded. This is what stops the fix from being an over-unlock.

**The sweep's own pin, flipped.** `test_functions_have_io_examples_loses_the_address_on_parameters` moved out of `TestUnaddressableToday` and into `TestAddressableToday` as `..._addresses_a_parameterised_function`, **with `FUNCTION_WITH_PARAMS` unchanged** — only the expected verdict moved, which is what the issue's acceptance asked for.

## Seam Choice

`test_completeness_pinning_deadlock.py` rather than `test_pinning_conservation.py`: this defect is the deadlock class (a demanded change being refused), not the conservation class (content lost through a merge). The file already replays #2555's deadlock end to end against real producers, and the new section follows its conventions — module-level fixtures, a `_io_complaint()` helper that asserts the fixture still trips the check, and no hand-written message strings.

## Regression Risk

One f-string in one check. The message is consumed by `named_tokens` (now matches, previously did not), by the halt text, and by prompt-failure telemetry, where it changes the recorded fingerprint for this check — a deliberate consequence of a reworded message, and the same thing that happens on any message change under #2074's fingerprint contract. The full unit suite confirms nothing else moved.
