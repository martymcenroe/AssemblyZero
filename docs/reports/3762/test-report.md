# Test report: #3762, #3763

## New tests

- `tests/unit/test_stale_design_keeps_the_base.py` (2): an unsettled committed `LLD-002.md` keeps the base, logs the keeping line and never calls `establish_new_attempt`; an unsettled non-design committed file still establishes a new attempt.
- `tests/unit/test_impl_worktree_base.py::test_the_base_is_fetched_into_the_remote_tracking_ref`: the fetch is `fetch origin <base>`, with no local-ref refspec.
- `tests/unit/test_impl_worktree_base.py::test_a_failed_fetch_fails_the_stage_rather_than_build_stale`: a refused fetch issues no worktree add and fails the stage with `could not fetch origin/<base>`.

## Moved to the new contract

- `test_speedrun_roll.py::test_base_holding_this_issues_work_triggers_a_fresh_attempt` → `test_base_holding_this_issues_unsettled_lld_is_kept_for_a_redraw` (#3762).
- Six assertions that pinned the bare base name as the worktree commit-ish now expect `origin/<base>` (#3763): `test_impl_worktree_base.py` lines 83 and 97, `test_impl_resume_from_preserved_attempt.py` lines 289, 298, 305, `test_impl_resume_prefers_best_measured.py` line 322.

## Runs, 2026-10-07, Ubuntu (WSL)

- With the #3762 change stashed: the design case failed and the non-design case passed. With it, the roll suites (`test_stale_design_keeps_the_base`, `test_fresh_recheck_keeps_settled`, `test_speedrun_roll`, `test_resume_versus_residue`, `test_stage_finality_launcher`): 55 passed.
- The worktree and resume suites with `test_orchestrator_stages.py`: 109 passed; `test_impl_worktree_base.py` with the two new tests: 11 passed.
- `tools/audit_halt_sites.py --check`: PASS. Fail-open baseline regenerated.
- Full `tests/unit`, run after run 58 ended (no roll live): 10957 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 57s.
- `ruff check`: `speedrun_roll.py` 37/37, `stages.py` 20/20, `test_speedrun_roll.py` 1/1 against `main`; the new test file clean.
