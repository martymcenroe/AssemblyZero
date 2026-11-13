# Implementation report: #4750

## The ruling

On 2026-11-13 the operator ruled that dependabot work stays off until December wherever it costs GitHub Actions minutes, and that public repositories may go ahead. On a private repository every approval and merge, and every `@dependabot rebase` or `@dependabot recreate`, runs workflows that spend those minutes. The nightly treated every repository alike.

## R1, R5: one point every path passes through

`tools/dependabot_review.py`:

- `main()` empties the visibility record at the start of each run (`:2768`), builds `repos` as before, and then calls `select_public_repos` (`:2790`) before anything acts on a repository. The zero-review pre-pass (`:2834`), the worker pool, the sequential loop and `--repo` mode all take their repositories from the list it returns, so a skipped repository gets no review, comment, `@dependabot` command, merge or test run, and the pre-pass never reads its PRs.
- `select_public_repos` (`:2326`) keeps a repository only when `repo_is_public` says so, and prints one `[SKIP]` line per skipped repository with the reason.

## R2: visibility is read in every run

- `list_fleet_repos` now asks `gh repo list` for `visibility` as well (`:2263`) and records each repository's answer in `_REPO_VISIBILITY` (`:2271`, declared at `:286`), so a fleet run makes no second call.
- `repo_is_public` (`:2293`) uses that record, and otherwise asks `gh repo view <repo> --json visibility --jq .visibility` with a 60-second timeout (`VISIBILITY_TIMEOUT_S`, `:281`). A failed call, an empty answer or an `OSError` returns `(False, reason)`, and the reason says the repository was treated as private. Only `PUBLIC` is public; `PRIVATE` and `INTERNAL` are skipped.

## R3: the Summary lists the skipped repositories

The skipped repositories are kept in their own list, `skipped_private`, not in `RESULT_KEYS`, whose lists hold PRs. The Summary prints `Skipped (private, #4750): [...]` after the outcome lists when the list is not empty (`:2997`). The `FLEET-COMPLETE` line is unchanged.

## R4: the switch

`INCLUDE_PRIVATE_REPOS = False` (`:280`), with a comment citing #4750 and the ruling. `--include-private` (`:2725`) turns it on for a single run; either one keeps every repository and reads no visibility.

## Tests

`tests/unit/test_dependabot_public_only.py`, driving `main()` with the real `process_repo` and `process_pr`, `run` stubbed at the `gh` boundary, and every action helper recorded with the repository it names:

- Test 1, `test_private_repo_gets_no_review_comment_merge_or_test` (`:194`), over the worker pool, the sequential loop and the pre-pass with `--limit`: the public repository is approved and merged; the private one is never listed, tested, reviewed, commented on or merged, and no `gh` command names it beyond the listing. `test_repo_mode_skips_a_private_repo` (`:217`) covers `--repo`.
- Test 2, `test_unreadable_visibility_skips_the_repo_and_says_why` (`:236`), for a fleet listing without the field and for `--repo`: `gh repo view` fails, the repository is skipped, and the line carries the error and "treated as private".
- Test 3, `test_switch_on_processes_the_private_repo` (`:259`), for the flag and for the constant. `test_the_switch_defaults_off` (`:281`).
- Test 4, `test_prepass_skips_a_private_repos_pr` (`:289`).
- Test 5, `test_summary_lists_skipped_private_repos_apart` (`:310`), with a `PRIVATE` and an `INTERNAL` repository.
- `test_fleet_listing_visibility_needs_no_second_call` (`:329`): no `gh repo view` in a fleet run, and each run starts from an empty record.

`tests/unit/test_dependabot_outcomes.py:295`: `_main_harness` stubs `repo_is_public` as public, so the existing `main()` tests assert what they did before.

## Runbook

`docs/runbooks/0911-dependabot-pr-audit.md`: a section on the skip, the switch and the flag; the Summary's new line; a History row.
