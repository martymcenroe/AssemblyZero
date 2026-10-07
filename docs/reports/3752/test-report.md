# Test report: #3752

## Added to `tests/unit/test_test_plan_validator.py::TestHumanDelegationDetection`

- `test_the_message_names_the_words_and_both_remedies`: boostgauge #2's T100 ("Absent needle (post-reset) visual check (REQ-3)", Auto) gives one violation whose message contains `"visual check"`, `reword` and `Manual`, and no backslash.
- `test_the_same_scenario_typed_manual_is_not_flagged`.
- `test_every_phrase_is_still_flagged` (8): each phrase of `HUMAN_DELEGATION_PATTERNS` in a Unit-typed description is flagged once, and the message quotes that phrase.

## Runs, 2026-10-07, Ubuntu (WSL)

- The validator file: 36 passed. With the validator change stashed (named path): 9 failed (the message test and the eight phrase tests, which assert the quoted phrase), 27 passed (including the unchanged Manual exemption).
- Full `tests/unit`: 10929 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 8s. (Run before the final test-only edit that made the T100 fixture a method; the validator file was rerun after it: 36 passed.)
- `ruff check`: the validator module and its test file carry the same counts as on `main` (3 and 3).
