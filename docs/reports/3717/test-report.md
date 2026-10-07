# Test report: #3717, #3740, #3741

## New: `tests/unit/test_orchestrator_lands_through_driver.py` (11)

- `test_the_pr_stage_lands_through_the_driver`: `merge_driver.land` stubbed; it receives `issue=2`, `base=<attempt branch>`, the worktree's real branch, a title and a body file both carrying `Closes #2`; no `gh pr create`, no `gh pr merge` and no `git push` reach `run_command`; state carries `impl_pr_url` and `impl_squash_sha`.
- `test_a_driver_refusal_fails_the_pr_stage_once`: a `MergeDriverError` is a failed stage, `transient` False, the driver's output in the message.
- `test_orchestrate_refuses_without_the_driver`: `tools/orchestrate.py` run as a subprocess with `AZ_MERGE_DRIVER` removed from its environment exits 2 and names the variable.
- `test_finalize_says_the_lld_did_not_land`: `commit_and_pr` raising prints `[LLD] NOT LANDED:` with the reason and still sets `commit_error`.
- `test_the_lld_stage_fails_when_the_lld_did_not_land`: an APPROVED sub-result carrying `commit_error` is a failed lld stage, `transient` False, `not landed` and the reason in the message.
- `test_a_driver_landed_lld_resumes`, `test_an_lld_that_never_left_the_machine_is_declined_aloud`, `test_lld_landed_on_base_reads_the_attempt_branch` (a real bare remote: the LLD file on `origin/<base>` is found for its issue and not for another), and `test_each_decline_names_its_check` (no state, another base, a failed lld stage).

## Moved onto the driver contract

- `tests/unit/test_cleanup_stage.py`: the three `_merge_pr` tests are deleted with the function. Cleanup with a landed LLD deletes the copies; without one keeps them; `test_cleanup_merges_nothing` asserts no `gh` command and the `git merge-base --is-ancestor <sha> origin/<base>` check; an unconfirmed squash fails the stage (#2011); a state with no squash is not confirmed.
- `tests/unit/test_cleanup_impl_pr_recovery.py`: #2019's recovery and fault, with `_squash_on_base` in place of `_merge_pr`.
- `tests/unit/test_orchestrator_stages.py::TestRunPrStage` (4): the same four intents, Closes in title and body, the real worktree branch, the base from state or detected from the target, the adversarial summary in the body, read from the driver stub's arguments and body file instead of a `gh pr create` argv. Each test uses its own `tmp_path` as the target, so no body file lands in a real checkout.

## Registries

- `assemblyzero/core/gate_registry.py`: the two stages' rows follow their sites' new positions; new halt rows `orchestrator.lld_not_landed` (#3740) and `orchestrator.pr_landing_refused` (#3717). `tools/audit_halt_sites.py --check`: PASS, 145 halt sites, every one registered. Ratchet baseline regenerated (`tests/fixtures/gate_registry_baseline.json`).
- `tests/fixtures/fail_open_baseline.json`: regenerated; the new handler is ruled on in the code, the existing two renumber.

## Runs, 2026-10-07, Ubuntu (WSL)

- The new file with the two cleanup files and the five resume suites (`test_resume_after_failure`, `test_resume_artifact_lookup`, `test_resume_versus_residue`, `test_resume_after_ceiling_halt`, `test_resume_from_pr_stage`), `test_no_retries` and `test_fail_open_audit`: 171 passed.
- The registry tests (`test_emits_pairing`, `test_gate_registry`, `test_halt_site_renumbering`, `test_non_pytest_red_is_deterministic`, `test_routing_policy`, `test_section_ten_carries_tests`): 119 passed.
- `tests/unit/test_orchestrator_stages.py`: 55 passed.
- Full `tests/unit`: 10886 passed, 66 skipped, 7 deselected, 6 xfailed in 10m 18s. (The first full run, before the registry rows and `TestRunPrStage` moved, had 12 failures, all in those two groups.)
- `ruff check`: every edited file carries the same findings as on `main`; the new test file has none.
