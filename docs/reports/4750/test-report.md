# Test report: #4750

## Changed tests

- `tests/unit/test_dependabot_public_only.py` (new), driving `main()` with the real `process_repo` and `process_pr` and `run` stubbed at the `gh` boundary:
  - Test 1 (R1, R5): `test_private_repo_gets_no_review_comment_merge_or_test`, over the worker pool, the sequential loop and the pre-pass with `--limit`; `test_repo_mode_skips_a_private_repo` for `--repo`.
  - Test 2 (R2): `test_unreadable_visibility_skips_the_repo_and_says_why`, for a fleet listing without the field and for `--repo`.
  - Test 3 (R4): `test_switch_on_processes_the_private_repo`, for the flag and for the constant; `test_the_switch_defaults_off`.
  - Test 4 (R1): `test_prepass_skips_a_private_repos_pr`.
  - Test 5 (R3): `test_summary_lists_skipped_private_repos_apart`, with a `PRIVATE` and an `INTERNAL` repository.
  - `test_fleet_listing_visibility_needs_no_second_call`: no `gh repo view` in a fleet run, and each run starts from an empty record.
- `tests/unit/test_dependabot_outcomes.py`: `_main_harness` stubs `repo_is_public` as public, so the existing `main()` tests assert what they did before.

## Full suite, 2026-11-13

Every tier finished after the last code edit, at 4:00 PM Central. Each exited 0.

- Unit tier, 4:27 PM Central: `= 14546 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1148.40s (0:19:08) =`
- Integration tier, 4:10 PM Central: `=== 65 passed, 7 skipped, 15246 deselected, 34 warnings in 135.05s (0:02:15) ===`
- E2E tier, 4:10 PM Central: `======== 19 passed, 15299 deselected, 34 warnings in 159.39s (0:02:39) =========`
- Adversarial tier, 4:09 PM Central: `======== 1 skipped, 15317 deselected, 34 warnings in 106.36s (0:01:46) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 4:08 PM Central: `559 passed, 1 warning in 19.68s`
- `ruff check`: `tools/dependabot_review.py` reports 16 findings, the same as at 6815f7be. `tests/unit/test_dependabot_public_only.py` is clean.

No nightly was run.
