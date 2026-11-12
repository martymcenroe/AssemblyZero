# Test Report: five stale or state-dependent tests (#4528, #4529, #3737, #4733, #3730)

All runs were on 2026-11-12, under Ubuntu, from the worktree, using the primary checkout's poetry environment.

## Targeted

- `tests/unit/test_orchestrator_stage_runners.py`, `tests/integration/test_orchestrator_graph.py`, `tests/unit/test_orchestrator_stages.py`, `tests/unit/test_capacity_stage_retry.py`, `tests/unit/test_rehearsal_pair.py` and `tests/unit/test_retry_mode.py`: 131 passed. `test_full_pipeline_success` is among them.
- `tests/unit/test_universal_claude_md_checkers.py` and `tests/test_universal_claude_md.py`: 12 passed, 1 failed. The failure is `test_adr_references_resolve` on ADR-0003 alone, as expected. `test_file_path_references_resolve` passes with `~/.claude/claude-spend.lock` absent (#4733 T1).
- `pytest --collect-only -m integration tests/integration/test_orchestrator_graph.py`: `no tests collected (9 deselected)`, which is why CI never ran the orchestrator test (#3737).

## Full suite

`pytest -q -p no:cacheprovider` with the repository's default markers: 15,077 passed, 5 failed, 66 skipped, 93 deselected, 7 xfailed, in 34 min 42 s. The baseline on `main` (`51e98150`) was 19 failures.

- `tests/test_universal_claude_md.py::test_adr_references_resolve`: ADR-0003, which the law gives no path. It passes once the operator deploys the law.
- Four tests that come from the environment, not from this change: `tests/unit/test_green_collection_failure_on_planned_module.py::TestContinueOnCollectionErrors::test_run_pytest_passes_the_flag_when_asked`, and in `tests/unit/test_green_loop_contract.py::TestCoverageScopeIsTheWholeFeature`, `test_one_cov_flag_per_target_in_order`, `test_a_single_string_is_a_one_entry_list` and `test_no_targets_means_no_cov_flags`. Each one calls the real `poetry env info --path` for the working directory. The worktree has no poetry environment of its own, so they raise `TargetEnvironmentError: poetry names no environment for .../AssemblyZero-4528`. On `main`, in the primary checkout, which has an environment, the same selection gives 6 passed. This change touches none of the code they exercise.

## ruff

`ruff check` on the five changed or added Python files reports 8 findings. The same 8 appear on `main` in the three files that existed before; the two new files report none.
