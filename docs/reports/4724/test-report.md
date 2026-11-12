# Test report: #4724

Run in Ubuntu (WSL) in the worktree, with the worktree's own poetry environment. The branch also carries #4723; the full-suite run below covers both.

## New tests

- T1 (R2), governance T08: `tests/tools/test_governance_suite_no_caller.py::test_a_repository_without_workflows_or_cerberus_secrets_passes_the_infrastructure_tests`. The suite's local infrastructure tests run against a repository holding no secret and no workflow file. They all pass, are T07 alone, and never list the repository's secrets. `test_the_retired_checks_are_gone_from_the_suite` checks that T08's and T09's functions are gone.
- T1 (R2), readiness audit: `tests/unit/test_fleet_readiness.py`.
  - `test_audit_one_repo_without_the_cerberus_secrets_is_ready`: strict protection and no secret in either scope is READY, and the absence is still reported.
  - `test_audit_one_secrets_lookup_error_changes_no_verdict`: a 403 on the secrets leaves the column blank and the verdict READY.
  - `test_audit_one_accumulates_multiple_failures` now counts one failure, branch protection.
- T2 (R2), `new_repo.py` in a sandbox: `tests/unit/test_cerberus_after_auto_review.py::test_a_github_repository_is_created_without_any_cerberus_pem`.
  - It runs `main()` through the whole GitHub path with no PEM flag, while an encrypted PEM sits at the old default path. The classic-PAT session, `requests` and the configure and verify helpers are replaced.
  - The run prints `[SUCCESS]` and exits 0.
  - The Cerberus PEM decrypt, the secret deploy and the secret check are each replaced by a stub that fails the test if reached, so no real key is ever touched.
- T2, the gate itself, in `tests/unit/test_new_repo.py::TestCerberusPemOptional`:
  - `test_T290_missing_pem_without_no_github_proceeds_to_creation`: `main()` hands off to creation with no PEM.
  - `test_T292b_no_default_gpg_fallback_when_neither_flag_passed`: a PEM at `~/.secrets/cerberus-pem.gpg` is not picked up.
  - In `test_cerberus_after_auto_review.py`, `test_the_scaffolder_has_no_default_pem_and_no_pem_gate` checks the constant and both messages are gone, and `test_the_pem_flags_stay_refused_with_no_github` checks the optional flags still refuse `--no-github`.
- T3 (R3) has no subject, because no per-repository secret has a reader. The finding is held instead, in `test_cerberus_after_auto_review.py`:
  - `test_only_the_retired_auto_review_files_read_the_per_repo_secrets` fails if any workflow other than `auto-reviewer.yml` and `auto-reviewer-caller.yml` reads either secret. Its message names the three checks to restore.
  - `test_the_retired_reusable_workflow_still_reads_them_only_in_a_job_that_never_runs` fails if the job loses its `if: false`.
  - `test_no_workflow_the_scaffolder_writes_reads_the_secrets`, with PyPI on and off.
  - `test_the_worker_approves_with_its_own_secrets_not_the_per_repo_ones`.
- Changed to the new contract: `TestCerberusPostDeployAdvice::test_anchor_comment_naming_issue_present` looks for `if cerberus_status == "OK":`, since the branch before it is gone.

## Each new test fails when its change is reverted

The tool and runbook changes were stashed by name, and the retired audit was written back from `HEAD`. Then the new and changed tests were run: 11 failed, 14 passed. The 11:

- the two governance tests;
- the three readiness tests above;
- T290 and T292b;
- in the new file: the sandbox run (the old fallback reached the PEM-decrypt stub), the no-gate check, and #4723's two retirement tests.

The 14 that pass on the old code have no change of their own to revert: the four tests that hold the no-reader finding (five items, one parametrized), the `--no-github` refusal, the six unchanged readiness tests, and T291 and T292. The restored audit was checked identical to `HEAD` and removed, and the stash was applied. Every stashed path was checked identical to it, and the stash was dropped.

## Targeted

The new file, the three changed test files, `test_new_repo_no_auto_review_caller.py`, `test_new_repo_guidance.py`, `test_new_repo_safety.py`, `test_loud_failure_check.py` and `test_deploy_cerberus_secrets.py`: 217 passed. Ruff finds nothing in the new test file and adds no finding to any changed file.

## Full suite

`pytest -q` on this branch, off `origin/main` at 823f30ee: 15056 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 19 min 5 s. No failure comes from this branch. The 18 are the ones that fail the same way on unchanged `main`: 16 in `tests/test_auto_reviewer_wait_loop.py` (see #4528), `test_full_pipeline_success` (see #4529, #3737) and `test_adr_references_resolve` (see #3730).

After the full run, two blocks of print text in `tools/new_repo.py` were reworded. The new test file and every `new_repo` test file were run again on the final tree: 244 passed.
