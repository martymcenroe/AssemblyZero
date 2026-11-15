# Test report: #4786

No test reads a real key file, runs gpg or calls GitHub. The `main()` runs use a placeholder classic-PAT file and pr-sentinel key file in a temporary home. Prompts are counted by replacing `_pat_session._ask_passphrase`, which every decrypt goes through, and gpg is replaced by a stand-in that succeeds.

All in `tests/unit/test_new_repo_post_create_hooks.py`, class `TestPassphraseList` unless noted.

| Issue test | Test |
|---|---|
| All three files present and a hook registered: the list names three | `test_three_secrets_are_listed_counted_and_asked`, through `main()` with the real PAT session, hook runner and pr-sentinel check: the block, captured before the first prompt, lists three and says 3; the prompts are the classic PAT, the hook's secret and the pr-sentinel credential, in that order |
| pr-sentinel file missing and a hook that fails to import: both named with reasons | `test_a_missing_key_and_an_unloadable_hook_are_named_with_reasons`, through `main()`: says 2, names the hook with `ModuleNotFoundError` and the key file with `tools/store_pr_sentinel_app_key.py`; exit 1 |
| AC1: the count printed equals the prompts made | Both tests above assert the printed count equals the counted prompts (3 and 2) |
| A hook without `PASSPHRASES` is listed as declaring none | `test_a_hook_without_passphrases_is_listed_as_declaring_none`; also `TestHookListStage::test_the_run_reads_the_list_it_names` through `main()` |
| A malformed `PASSPHRASES` is a load error naming the hook | `test_a_malformed_passphrases_is_a_load_error_naming_the_hook`, for a string, an empty name and an integer: the block names the hook and the error, and its `post_create` never runs |
| A hook module executes once per run | `test_a_hook_module_executes_once_when_loaded_then_run`; the two `main()` tests also check the hook's execution marker holds one line |
| The classic PAT's file missing | `test_a_missing_classic_pat_file_means_nothing_is_asked`: count 0, the PAT named, the rest not reached |

`TestHookListStage::test_the_run_reads_the_list_it_names` now writes a real hook and asserts the stage receives the loaded hook. `_run_main` patches `new_repo.DEFAULT_PAT_PATH` and `DEFAULT_PR_SENTINEL_APP_GPG` to temporary files on every run, can run the real PAT session, and can run the real hook runner.

The code change was written before these tests, so they were not seen to fail first.

## Targeted run

`test_new_repo.py`, `test_new_repo_post_create_hooks.py`, `test_new_repo_ubuntu_run.py`, `test_cerberus_after_auto_review.py`, `test_new_repo_safety.py`, `test_new_repo_guidance.py`, `test_loud_failure_check.py`, `test_gh_actions_secret.py`, `test_store_pr_sentinel_app_key.py`: `295 passed, 1 warning in 167.07s`.

`test_cerberus_after_auto_review.py`'s helper now points the classic PAT and pr-sentinel paths at its tmp home, so the passphrase list never looks at the machine's own files: `10 passed`.

## Unit tier, 2026-11-15

Run on Ubuntu with pytest directly: `15422 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1705.79s (0:28:25)`. No test failed. The branch was then replayed onto main after #4785 landed; the replayed tree differs from the tested one only in `docs/reports/4785/test-report.md`.

## Ruff

Before the two fixes below, ruff found two new findings on changed lines: an implicit string join inside a list in `passphrase_plan`, and an unused unpacked name in a test. Both were fixed. The other findings were there before this change: 20 in `tools/new_repo.py`, 1 in `tools/_pat_session.py`, 2 in the test file.
