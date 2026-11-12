# Test report: #4712, #4713

Run in Ubuntu (WSL) in the worktree, with the primary checkout's poetry environment.

## New tests

- `tests/tools/test_land_workflow_plan.py` (#4713), against a fake GitHub: plan validation, each fault refused by name, a duplicate target, a reason naming the source, no repository baked into the tool; the pull request's title and body; the verdict for each conclusion; one target landed end to end as one branch, one pull request, then merge and delete; a moved base blob stopping before any write; a target already landed skipped without a write; a conclusion the plan does not expect stopping with the pull request left open; a carriage return refused; one session covering every target; the first failure stopping the run with its counts; the private-name and default-branch preflight; the dry run asking for no credential; `--only`. They cannot pass before the change: the module did not exist.
- `tests/unit/test_new_repo_no_test_workflow.py` (#4712): the scaffolder writes exactly `auto-reviewer.yml` and `release.yml`, with and without PyPI; no job in them runs a command from a closed, written-out list of test and lint commands; the check catches each listed command, passes a job set `if: false`, and ignores a command inside a longer word.

## Targeted

`tests/tools/test_land_workflow_plan.py`, `tests/tools/test_land_staged_workflow.py`, `tests/unit/test_new_repo_no_test_workflow.py` and `tests/unit/test_new_repo_pypi.py`: 125 passed.

## Full suite

`pytest -q` on this branch: 15052 passed, 22 failed, 66 skipped, 93 deselected, 7 xfailed, in 32 min 20 s. No failure comes from this branch:

- 18 fail the same way on unchanged `main` at 60ee3fd3 (`18 failed, 45 passed` for those files run alone), each tracked: 16 in `tests/test_auto_reviewer_wait_loop.py` (see #4528), `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (see #4529, #3737), and `tests/test_universal_claude_md.py::test_adr_references_resolve` (see #3730).
- 4 in `tests/unit/test_green_collection_failure_on_planned_module.py` and `tests/unit/test_green_loop_contract.py` fail only in a worktree: each asks poetry for the environment of the checkout it runs in, and `poetry env info --path` exits 1 in a worktree that has none of its own. Run alone on `main` in the primary checkout, they pass.
