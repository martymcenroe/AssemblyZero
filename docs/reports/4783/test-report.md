# Test report: #4783

## New tests

`tests/unit/test_gh_actions_secret.py`, 25 tests. No network: a fake GitHub stands behind the HTTP call `tools/_gh_retry.py` makes, so `set_secret` runs through the real retry helper, and the helper's sleeps are made instant. Each repository and scope gets a real PyNaCl key pair, so the sealed value is opened, not only inspected. The PAT and the secret value are fakes.

| Test of #4783 | Tests |
|---|---|
| Public key fetched for each scope; PUT carries the right `key_id` and a sealed value that opens to the original; True on 201 and 204 | `TestSetSecret::test_a_2xx_put_of_the_sealed_value_returns_true`, for `actions` and `dependabot` with 201 and with 204; `test_each_scope_seals_with_its_own_key`, where the Dependabot value does not open with the Actions key; `test_the_sealed_value_never_carries_the_plaintext`; `test_both_calls_carry_the_pat_as_a_bearer_token`; `test_the_scope_defaults_to_actions`; `test_owner_defaults_to_the_fleet_user_and_can_be_named` |
| False on a 4xx PUT | `test_a_4xx_put_returns_false` for 400, 403, 404 and 422; `test_a_put_that_never_connects_returns_false` |
| False on a failed key fetch | `test_a_failed_key_fetch_returns_false_and_puts_nothing` for 301, 403 and 404; `test_a_key_fetch_that_never_connects_returns_false_and_puts_nothing`, after the helper's retries |
| The hook's call shape | `test_the_signature_is_the_one_the_hook_calls`: `repo, name, value, pat, scope="actions"`, with anything after them keyword-only; `test_the_scopes_are_actions_and_dependabot` |
| The contract test (R3, AC1, AC2) | `TestHookImportContract`: `test_the_contract_names_both_modules`; `test_every_named_module_is_in_tools_and_has_its_names`, which imports each module from `tools/` and checks each name is callable; `test_a_hook_importing_the_whole_contract_runs`, a hook file outside `tools/` that imports the whole contract, run by `run_post_create_hooks`; `test_the_runner_documents_the_contract` |

## Not covered here

- AC3 is the operator's live run on Ubuntu, after the hook's own import changes in its repository. It is recorded on #4771.
- No test calls GitHub.

## Targeted runs, 2026-11-15

`tests/unit/test_gh_actions_secret.py` alone: `25 passed, 1 warning in 10.07s`.

With `tests/unit/test_cerberus_secret_deploy_retired.py` and every `tests/unit/test_new_repo*.py`: `303 passed, 1 warning in 140.59s (0:02:20)`.

## Unit tier, 2026-11-15

Run on Ubuntu with pytest directly: `6 failed, 15365 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1031.74s (0:17:11)`.

The six failures are all `tests/unit/test_pat_session_named_prompt.py::TestRealGpg`, which fail on Ubuntu because gpg-agent cannot start in their GNUPGHOME (#4766). They fail the same way on main at ed77a367. No other test failed.
