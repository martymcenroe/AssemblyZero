# Test report: #4719, #4720, #4721

Run in Ubuntu (WSL) in the worktree, with the worktree's own poetry environment.

## New tests

- `tests/unit/test_new_repo_no_auto_review_caller.py` (#4719, T2): `create_github_workflows()` writes no caller with PyPI on or off; a full `--no-github` scaffold in `tmp_path` carries no `auto-reviewer.yml`, creates no `.github/workflows/` with PyPI off and does not `git add` it; a `--pypi` scaffold carries exactly `release.yml` and does add it; `new_repo` keeps no caller template and no caller check; the two retired tools are absent and no file under `tools/` or `tests/` names them.
- `tests/tools/test_governance_suite_no_caller.py` (#4720, T4): the governance suite's local infrastructure tests on a repository with no workflow file all pass, and none asks for a workflow file.
- `tests/unit/test_fleet_readiness.py` (#4720, T4): a repository without the caller is READY; an error reading the caller changes no verdict; the multiple-failure case now counts two failures, not three.
- `tests/tools/test_audit_cerberus_health.py::TestRepositoryWithoutTheCaller` (#4720, T4): a repository without the caller exits 0, is never read for runs, and is reported as the retired caller, not as a failure.
- `tests/tools/test_land_workflow_plan.py`, the T5 section (#4721), on a fake GitHub that copies `main` to a new branch, honours a Contents-API DELETE only for the blob the branch holds, and carries removals to `main` on merge:
  - the exact delete-only plan shape validates from a JSON file without `source`; a plan with any replace entry still needs it; a delete entry carrying `staged` or `expect`, an unknown `action`, a bad blob or a path outside `.github/workflows/` is refused by name;
  - an absent file gives `already` with no write;
  - a moved blob stops with no write;
  - a delete writes branch, remove, PR, merge, delete-branch, opens one PR titled `ci: remove auto-reviewer.yml (Closes #7)`, waits for no run and leaves `main` without the file;
  - a read-back that still finds the file stops the run at `verify`;
  - a mixed target lands in one PR and waits only for the replaced workflow;
  - a branch already lacking the file takes no second DELETE;
  - a rerun after a stop skips the landed target;
  - `--max-targets 2` lands exactly two of four, and a rerun lands the other two;
  - targets already done do not count toward the cap;
  - `--max-targets 0` is refused;
  - `--apply` prints the count and contributions before the session opens;
  - the dry run prints the `delete ... base ...` lines and the count, and asks for no credential.
- Changed to the new contract: `tests/unit/test_new_repo_no_test_workflow.py`, `tests/unit/test_new_repo_pypi.py`, `tests/unit/test_new_repo.py` (the caller-check class removed), `tests/unit/test_new_repo_guidance.py` (the caller-template class removed), `tests/unit/test_loud_failure_check.py` (ceiling 115).
- Removed with their tools: `tests/unit/test_deploy_auto_reviewer_workflow.py`, `tests/unit/test_upgrade_auto_reviewer_caller.py`.

## Each new test fails when its change is reverted

The five implementation files were stashed by name, so the code went back to `origin/main` while the new tests stayed. A placeholder `tools/deploy_auto_reviewer_workflow.py` stood for the restored tool. The new and changed tests were then run: 31 failed, 56 passed. Every new test failed except two, and neither has a change of its own to revert:

- `TestRepositoryWithoutTheCaller::test_exits_zero` pins behaviour the Cerberus audit already had.
- `TestDeletePlan::test_a_plan_with_any_replace_entry_still_needs_source` guards the new condition from the other side, and the old code required `source` always.

The changed tests in `test_new_repo_pypi.py` also pass on the old code, because they now assert only the `release.yml` behaviour both versions share; the caller assertions moved to the new T2 file. The stash was then applied, the five files were checked identical to it, and it was dropped.

## Targeted

The changed areas (`test_land_workflow_plan.py`, `test_land_staged_workflow.py`, the new T2 and T4 files, `test_audit_cerberus_health.py`, `test_fleet_readiness.py`, `test_new_repo_guidance.py`, `test_new_repo_no_test_workflow.py`, `test_new_repo_pypi.py`, `test_new_repo.py`) all pass. `tools/audit_loud_failure.py --check` passes at 115 sites. Ruff adds no finding to any changed file.

## Full suite

Recorded in the following commit, after `origin/main` is merged into the branch.
