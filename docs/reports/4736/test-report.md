# Test report: #4736

## Changed tests

- `tests/unit/test_dependabot_fake_root_guard.py` (new):
  - Test 1 (R1, AC1): a PR head that lacks `tests/fake_root_guard.py` while `main` has it is not tested unchanged, and the log says why. `test_head_without_guard_is_deferred_untested_and_rebased`, `test_head_without_guard_on_current_branch_is_not_recreated` and `test_guard_check_error_is_errored_and_runs_nothing`.
  - Test 2 (R1, AC1): a PR head that carries the guard runs as before. `test_head_with_guard_runs_install_and_pytest`.
  - `fake_root_guard_gap` against real git repositories: `test_gap_names_the_guard_when_head_predates_it`, `test_gap_is_empty_when_head_carries_the_guard` and `test_gap_reports_an_error_outside_a_repository`.
- `tests/unit/test_dependabot_review.py` (two places) and `tests/tools/test_dependabot_review.py` (four places): the existing flow tests stub `fake_root_guard_gap` to report a head that carries the guard, so they still reach the suite run they test.
- Test 3 and AC2, the listing of `C:\tmp` and the other fake roots before and after the next nightly, is carried by a follow-up issue, filed before the PR.

## Runs, 2026-11-13

Every run below finished after the last code edit, at 2:19 PM Central.

- Targeted run, 2:20 PM Central: 273 passed in 35 s.
- Unit tier, 2:42 PM Central: 14510 passed, 66 skipped, 7 deselected, 7 xfailed in 22m 7s.
- Integration tier, 2:44 PM Central: 65 passed, 7 skipped in 1m 31s.
- E2E tier, 2:46 PM Central: 19 passed in 2m 11s.
- Adversarial tier, 2:49 PM Central: 1 skipped in 45 s. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 2:49 PM Central: 559 passed in 13 s.
- No #4735 failures.
- `ruff check`: `tools/dependabot_review.py` reports 16 findings, the same as `main`. The new test files are clean.

No nightly was run.
