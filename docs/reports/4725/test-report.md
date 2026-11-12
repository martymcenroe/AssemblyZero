# Test report: #4725

Run in Ubuntu (WSL) in the worktree, with the worktree's own poetry environment.

## New tests

`tests/tools/test_land_workflow_plan.py`, class `TestIssueRepo`, 13 tests on the fake GitHub the file already uses. A recorder wraps the fake's Contents-API PUT and DELETE to keep each commit message, and `DIRECTIVE` is the fleet's pre-flight pattern for every closing keyword GitHub honours.

| Test | Covers |
|---|---|
| `test_a_target_naming_its_issue_repo_validates` (T1) | a target with `issue_repo` validates, beside one without it |
| `test_a_bad_issue_repo_is_refused_by_name` (T1, 5 cases) | empty, an integer, `null` and `ho me` are "not a repository name"; `o/home` is "a name, not owner/name" |
| `test_the_reference_names_the_home_only_when_one_is_given` | `closes_ref()` gives `#7` without the key and `o/home#7` with it |
| `test_a_delete_closes_the_issue_in_its_home_with_one_directive` (T2, T4) | one pull request, titled `ci: remove auto-reviewer.yml (Closes o/home#7)`; its body starts `Closes o/home#7` and holds that one directive and no other; the title holds only it; the branch is still `ci/staged-workflow-7`; the removal commit's message carries the same reference; the file is gone from `main` |
| `test_the_long_title_fallback_keeps_the_home_reference` (T3) | `ci: update 8 workflows (Closes o/home#7)` and `ci: remove 8 workflows (Closes o/home#7)` |
| `test_a_replaced_workflow_commit_closes_the_issue_in_its_home` (T4) | a replace target: the title, the one body directive and the commit message all carry `o/home#7` |
| `test_a_target_without_issue_repo_still_closes_its_own_issue` (T6) | without the key, the title, the body's one directive and the commit message carry `#7`, as before |
| `test_the_single_repository_lander_still_closes_its_own_issue` (T6) | `_closes()` gives `#7` for a config without `closes`, and the reference when one is set |
| `test_the_dry_run_names_the_home` (T5) | the dry run prints `o/alpha  PR closes o/home#7  branch ci/staged-workflow-7` and `o/beta  PR closes #9  branch ci/staged-workflow-9`, and asks for no credential |

## Each new test fails when its change is reverted

`tools/land_workflow_plan.py` and `tools/land_staged_workflow.py` were stashed by name, so both went back to `origin/main` while the new tests stayed: 11 failed, 54 passed. The two new tests that passed have no change of their own to revert:

- `test_a_target_naming_its_issue_repo_validates`: the old validator ignores unknown keys.
- `test_a_target_without_issue_repo_still_closes_its_own_issue` pins the unchanged behaviour.

The stash was then applied, both files were checked identical to it, and it was dropped.

## Targeted

`tests/tools/test_land_workflow_plan.py` and `tests/tools/test_land_staged_workflow.py`: 101 passed. `tools/audit_loud_failure.py --check` passes at 115 sites, all in the baseline. Ruff adds no finding: its one report on `tools/land_staged_workflow.py`, an unused `noqa` at line 95, is on `origin/main` as well.

## Full suite

`pytest -q` on this branch, at `origin/main` dbf64ebd: 15063 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 18 min 39 s. No failure comes from this branch. The 18 are the ones that fail the same way on unchanged `main`, each tracked:

- 16 in `tests/test_auto_reviewer_wait_loop.py` (see #4528);
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (see #4529, #3737);
- `tests/test_universal_claude_md.py::test_adr_references_resolve` (see #3730).
