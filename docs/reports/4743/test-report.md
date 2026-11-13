# Test report: #4743

## Changed tests

- `tests/unit/test_dependabot_network_guard.py` (new), over `tests/network_command_guard.py` (new):
  - Test 1: `test_guard_refuses_a_real_gh_start`, `test_guard_refuses_git_fetch_from_an_https_url` and `test_guard_refuses_git_against_a_remote_configured_with_a_network_url`.
  - Local git still runs: `test_guard_allows_local_git_against_a_tmp_path_repository`, `test_network_reason_passes_what_stays_local`.
  - `test_a_swallowed_refusal_still_fails_the_test` and `test_network_reason_names_each_network_form`.
  - AC1: `test_every_test_file_that_loads_the_tool_runs_under_the_guard`.
- `tests/conftest.py`: the `no_network_commands` fixture. The seven files that load the tool opt in with `pytestmark = pytest.mark.usefixtures("no_network_commands")`, one line each.
- Test 2 (R2): `test_deferred_install_fail_path_calls_cleanup_worktree` and `test_deferred_test_fail_path_calls_cleanup_worktree` in `tests/unit/test_dependabot_review.py` stub `_pr_changed_files`, and `TestProcessPrDeferralStaleBranchPriority._stub_pipeline` in `tests/tools/test_dependabot_review.py` stubs `_pr_changed_files` and `review_comment_on_pr`. No assertion changed.

## Implementation runs, 2026-11-13

- Seven files with the guard on, before the stubs: `5 failed, 290 passed, 1 warning, 5 errors in 23.17s`.
- The same, with the two named tests stubbed: `3 failed, 292 passed, 1 warning, 3 errors in 43.44s`. The three were the `TestProcessPrDeferralStaleBranchPriority` tests.
- `tests/unit/test_dependabot_network_guard.py` alone: `20 passed, 1 warning in 8.79s`.
- The seven files, the new test file and five others that name the tool, twice: `387 passed, 1 skipped, 1 warning in 123.32s (0:02:03)` and `387 passed, 1 skipped, 1 warning in 124.63s (0:02:04)`.

## Full suite, 2026-11-13

Every tier finished after the last code edit, at 4:00 PM Central. Each exited 0.

- Unit tier, 4:27 PM Central: `= 14546 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1148.40s (0:19:08) =`
- Integration tier, 4:10 PM Central: `=== 65 passed, 7 skipped, 15246 deselected, 34 warnings in 135.05s (0:02:15) ===`
- E2E tier, 4:10 PM Central: `======== 19 passed, 15299 deselected, 34 warnings in 159.39s (0:02:39) =========`
- Adversarial tier, 4:09 PM Central: `======== 1 skipped, 15317 deselected, 34 warnings in 106.36s (0:01:46) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 4:08 PM Central: `559 passed, 1 warning in 19.68s`
- `ruff check`: the three new files are clean. No changed file gains a finding against 6815f7be; `tests/tools/test_dependabot_review.py` drops from 4 to 3.

No nightly was run.
