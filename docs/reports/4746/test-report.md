# Test report: #4746

## Changed tests

- `tests/unit/test_dependabot_outcomes.py`:
  - Test 1 (R1, R2): `test_main_counts_the_reviews_posted_whatever_the_outcome`. Through `main()` and the real `process_pr`, one PR approved and merged, one approved and deferred on `blocked`, one approved and errored on a failed squash merge, and one deferred with a COMMENTED review. The Summary reads `3 APPROVED + 1 COMMENTED = 4 total`; one count recorded before `main()` shows the reset.
  - `test_a_review_github_refuses_is_not_counted` and `test_review_tally_is_exact_under_concurrent_records` (eight threads).
  - `test_main_counts_no_commented_review_for_a_two_strike_deferral` now runs the real `process_pr` for the tested PR.
  - `_pipeline` takes `real_reviews`, `unmergeable`, `merge_fails` and `final_state`; `_main_harness` runs the real `process_pr` when given no fake.
- `tests/unit/test_dependabot_review.py::TestProcessRepoWithBudget::test_result_dict_always_carries_limit_skipped_key` no longer expects the removed `UNREVIEWED_DEFERRED` key.

## Full suite, 2026-11-13

Every tier finished after the last code edit, at 4:00 PM Central. Each exited 0.

- Unit tier, 4:27 PM Central: `= 14546 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1148.40s (0:19:08) =`
- Integration tier, 4:10 PM Central: `=== 65 passed, 7 skipped, 15246 deselected, 34 warnings in 135.05s (0:02:15) ===`
- E2E tier, 4:10 PM Central: `======== 19 passed, 15299 deselected, 34 warnings in 159.39s (0:02:39) =========`
- Adversarial tier, 4:09 PM Central: `======== 1 skipped, 15317 deselected, 34 warnings in 106.36s (0:01:46) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 4:08 PM Central: `559 passed, 1 warning in 19.68s`
- `ruff check`: `tools/dependabot_review.py` reports 16 findings, the same as at 6815f7be. `tests/unit/test_dependabot_outcomes.py` is clean, and `tests/unit/test_dependabot_review.py` reports 4, the same as at 6815f7be.

No nightly was run.
