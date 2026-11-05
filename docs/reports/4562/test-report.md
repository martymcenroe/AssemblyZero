# Test report: #4562

## Unit

`tests/unit/test_merge_instructions.py`, 10 passed. Three are new:

- T1 (R1): `test_no_review_section_counts_the_checks` finds pr-sentinel's two check names, the `totalCount` query and the job count in the section's command blocks, and both outcomes of the count.
- T1 (R2): `test_no_review_section_needs_the_log_only_when_the_checks_are_present` requires every line of the section that says only the operator can read the Worker's log to be the line for a PR whose pr-sentinel checks are present.
- T2 (R3): `test_runbook_tree_splits_the_no_review_branch` finds both outcomes in the decision tree.

The file's existing `test_no_command_block_lands_by_hand` passes over the new commands. `ruff check` on the file is clean.

## Full suite

`tests/`, against the worktree: 14,887 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 23 min 18 s.

All 18 failures also fail on `main` at `e5aeca4e` without this change. Each is already tracked:

- 16 in `tests/test_auto_reviewer_wait_loop.py`: the workflow step they read is gone (#4528).
- `tests/test_universal_claude_md.py::test_adr_references_resolve`: ADR-0003 and ADR-0010 are another repository's ADRs (#3730).
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`: `GraphRecursionError` (#4529, #3737).

None of these files reads runbook 0935.

## Commands run with the agent token (T3)

Run once each on 2026-11-04 against a merged PR in a private repository whose head ran two workflows of one job each. The head-commit read returned the commit; the `totalCount` query returned `4`; the run list returned Tests (`success`) and Auto Review (`skipped`); each run's job count was `1`. That is 4 contexts against 2 jobs, so pr-sentinel's two checks were present. Listing that commit's check runs with the same token returned a 403.
