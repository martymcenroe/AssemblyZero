# Test report: #4186

## New tests

| Test | Tests in the files |
|---|---|
| Test 1, the summary that decides `[SUCCESS]` | `tests/unit/test_new_repo_ubuntu_run.py::TestFailedSteps`: `test_a_missing_hook_list_is_a_failed_step`, `test_a_missing_hook_list_is_named_in_run_order`, `test_no_missing_hook_list_changes_nothing` |
| Test 1, the hook stage in a run | `tests/unit/test_new_repo_post_create_hooks.py::TestHookListStage`: `test_a_missing_list_fails_the_run_and_runs_no_hook`; `test_an_empty_list_runs_no_hook_and_is_not_a_failure`, for an empty file and a comments-only file; `test_the_run_reads_the_list_it_names` |

The stage tests drive `main()` through the GitHub path with every GitHub boundary replaced, the home a tmp directory, `DEFAULT_POST_CREATE_HOOKS` patched to a tmp path and the hook runner a mock, so no listed hook runs. The missing-list run exits 1, prints the `FAILED` line, never calls the runner, prints no `[SUCCESS]`, names the list in `[FAILED]` and alerts once. The empty-list runs print "None listed", call the runner with no hooks, and end in `[SUCCESS]` with no alert.

The tests were written first. Before the change, the three `failed_steps` tests failed on the unknown keyword, the missing-list run exited 0, and the other stage runs read the list from the reader's import-time default rather than the patched path.

## Existing tests changed

- `tests/unit/test_cerberus_after_auto_review.py`, `_run_main`: it drives the GitHub path and patched only the reader. It now also points `DEFAULT_POST_CREATE_HOOKS` at an empty file under its tmp home; without that it fails wherever the real list is absent, as on CI. No assertion changed.
- `tests/unit/test_new_repo_post_create_hooks.py`: `test_missing_file_means_no_hooks` is renamed `test_missing_file_reads_as_an_empty_list`, with the same assertion. The reader still returns `[]`; the run reports the missing file.

## Not covered here

- Test 2, the operator's own `new-repo` run from Ubuntu, is recorded on #4186 by the coordinator.
- No test runs a real hook through `main()`.

## Targeted runs, 2026-11-14

Every `tests/unit/test_new_repo*.py` file with `test_no_spelled_projects_root.py` and `test_cerberus_after_auto_review.py`: `4 failed, 281 passed, 1 warning in 325.01s (0:05:25)`. After a comment-only edit, `test_new_repo_post_create_hooks.py` alone: `13 passed, 1 warning in 20.90s`.

The four failures are `tests/unit/test_new_repo_ubuntu_run.py::TestResolveProjectPath`: `test_real_config_gives_an_absolute_path_beside_this_checkout`, `test_asks_for_the_spelling_of_this_os`, `test_refuses_a_relative_root` and `test_refuses_a_windows_root_resolved_against_the_cwd`. They fail the same way on the primary at 94cc7239, in code this change does not touch: each resolves against this machine's real `~/.assemblyzero/config.json`, which was changed at 9:07 PM Central on 2026-11-14, after #4768's unit tier passed them.

## Unit tier, 2026-11-14

`poetry run pytest tests/unit/ -q --tb=short -v`, run directly rather than through test-gate (#4758):

`10 failed, 15210 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1245.96s (0:20:45)`

Six failures are `tests/unit/test_pat_session_named_prompt.py::TestRealGpg`, four `test_the_right_passphrase_decrypts_with_no_box_from_gpg` cases, `test_a_wrong_passphrase_fails_cleanly` and `test_the_passphrase_is_never_in_argv_env_output_or_errors`: the failures #4766 tracks, in a file this change does not touch. The other four are the `TestResolveProjectPath` tests above, which fail on the primary too. No other test failed.
