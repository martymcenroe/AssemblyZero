# Test report: #4728

Run in Ubuntu (WSL) in the worktree, with the worktree's own poetry environment. Nothing in these tests decrypts anything: the classic-PAT session is a stand-in that yields a dummy string, because the decrypt belongs to the operator, never to a test or an agent.

## T1 (R2, R6): which secrets the program deletes

`tests/tools/test_fleet_remove_cerberus_secrets.py`, on a fake GitHub that keeps each repository's Actions and Dependabot secrets and answers as GitHub does (200 or 404 for one secret, 204 for a deletion, `/user/repos` a page at a time).

- `test_t1_both_secrets_in_both_scopes_mean_exactly_four_deletions`: a repository holding both secrets in both scopes, plus an unrelated secret in each scope, gets exactly the four `DELETE`s; its unrelated secrets survive; a second repository holding only an unrelated secret gets none; and no call names an unrelated secret at all.
- `test_t1_one_secret_in_one_scope_is_one_deletion`.
- `test_the_delete_refuses_any_other_secret_or_scope_before_any_call`: `delete()` with another name, or another scope, raises before any call is made.

## T2 (R4, R5): a stop, and the rerun

- `test_t2_a_rerun_after_a_stop_skips_the_clean_repositories`: three repositories; the deletion of the second's `dependabot/REVIEWER_APP_ID` is refused with 403. The run exits 1, names `delete in beta` and `beta dependabot/REVIEWER_APP_ID: DELETE answered HTTP 403`, reports `cleaned 1, already clean 0, not finished 2 of 3`, and never reaches the third. With the refusal lifted, the rerun prints the first as `clean`, deletes nothing from it, deletes the second's remaining two and the third's four, and exits 0.
- The other stops: `test_a_read_back_that_still_finds_the_secret_stops_the_run`, `test_a_read_neither_200_nor_404_stops_even_the_dry_run` (an unreadable repository is never read as clean, and the run goes no further), `test_an_archived_repository_that_refuses_is_named_with_what_to_do`, `test_a_failed_decrypt_stops_before_any_call`, `test_a_failed_token_check_stops_before_the_listing`.

## R2, R3: the dry run, the listing and the printing

- `test_the_dry_run_deletes_nothing_and_names_the_holders`, and `test_after_an_apply_the_dry_run_lists_no_holder`, which is T3's check on the fake.
- `test_it_prints_before_and_after_the_decryption`: the stand-in session prints a marker when it opens; the text before it holds the step-1 line about the passphrase box, and the text after it starts with `decrypted`, then every later step.
- `test_the_listing_pages_and_puts_archived_repositories_last`, `test_the_repo_flag_limits_the_run_and_an_unknown_name_stops_it`, `test_the_session_reason_names_no_repository`.
- Standard 0017 and ADR-0216: `test_every_flag_the_docstring_names_is_recognized`, `test_the_pat_never_reaches_argv_or_the_environment` (by `ast`: no `os`, no `subprocess`, no `environ`).

## T3 (R1, R2)

Needs the operator's `--apply` and then his dry run, whose last line must read `Done (dry run): no repository of the N holds either secret.`

## T4 (R7): nothing can deploy the secrets again

`tests/unit/test_cerberus_secret_deploy_retired.py`:

- `test_t4_the_deploy_tool_and_its_tests_are_gone`.
- `test_t4_no_tool_test_or_package_module_imports_it`, by `ast` over every `.py` file under `tools/`, `tests/` and `assemblyzero/` that names the tool; `test_the_import_check_sees_both_import_forms` proves the parse catches both forms.
- `test_t4_new_repo_refuses_the_pem_flags`, for `--cerberus-pem` and `--cerberus-pem-gpg`: exit 2, `unrecognized arguments`.
- `test_t4_new_repo_keeps_no_cerberus_deploy_step`: no `_deploy_cerberus`, `deploy_to_repo`, `verify_secrets` or `cerberus_pem_session` on the module, and no `cerberus_status` in `failed_steps()`.
- `test_nothing_live_names_the_retired_tool`, with `docs/audits/`, `docs/reports/` and dated history rows left as written; `test_the_search_finds_what_it_is_looking_for` proves the search can find a hit.

The two searches use `git grep`. Walking the trees file by file took 378 s for one test on this Windows-mounted checkout; `git grep` takes about 7 s.

## Each new test fails when its change is reverted

On unchanged `origin/main`, read with `git cat-file -e` and `git grep -c`: the tool and its test file exist, `tools/new_repo.py` holds two `from deploy_cerberus_secrets import` lines, four lines with `"--cerberus-pem` and thirteen with `cerberus_status`. So every T4 assertion fails there. The T1 and T2 tests import a module that does not exist on `main`.

## Changed to the new contract

- `tests/unit/test_new_repo.py`: T290 checks the parsed arguments carry no PEM attribute; T292 checks `--cerberus-pem` is refused with exit 2, with and without `--no-github`; `TestCerberusPostDeployAdvice` checks the scaffolder prints no post-deploy advice and no `cerberus_status`.
- `tests/unit/test_new_repo_guidance.py`: the keep-the-key-active rule is now checked in runbook 0939, where a rotation meets the Revoke button, since the scaffolder deploys no key.
- `tests/unit/test_new_repo_ubuntu_run.py`: `failed_steps()` has no `cerberus_status`, and passing one is a `TypeError`.
- `tests/unit/test_cerberus_after_auto_review.py`: the sandbox run guards `_pat_session.cerberus_pem_session` instead of names `new_repo` no longer has, and the PEM flags are refused with exit 2.
- `tests/unit/test_fleet_ids.py`: the retired tool leaves the list of programs that read the App ID.

## Lint and the loud-failure baseline

Ruff passes on both new files and the new test file. On `tools/new_repo.py` it reports 20 findings against 23 on `main`, every one already there. `tools/audit_loud_failure.py --check`: PASS, 115 sites, all in the baseline.

## Full suite

`pytest -q` on this branch, off `origin/main` at f06e4075: 15063 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 46 min 36 s (another worktree's full suite ran at the same time). No failure comes from this branch. The 18 are the ones that fail the same way on unchanged `main`: 16 in `tests/test_auto_reviewer_wait_loop.py` (see #4528), `test_full_pipeline_success` (see #4529, #3737) and `test_adr_references_resolve` (see #3730).
