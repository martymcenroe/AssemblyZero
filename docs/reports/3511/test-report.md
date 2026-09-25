# Test Report — The implementation branch is not pushed at worktree creation (#3511)

Backfilled 2026-09-25 after the merge, from PR #3532 (merge `c06062ec`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_impl_no_push_before_work.py`. Each test uses a throwaway repo with a bare origin and compares the origin's refs (name and SHA) before and after:

- `test_create_worktree_pushes_nothing`: the worktree and branch exist locally, the origin is unchanged, and the branch has no upstream.
- `test_a_run_that_halts_at_n0_leaves_the_origin_unchanged`: a real (non-mock) run with no LLD halts at N0 (`[N0]` appears in the output and `[N1]` does not); the worktree was cut, and the origin is unchanged.
- `test_a_full_mock_run_leaves_the_origin_unchanged`: `--mock` runs every node, including local checkpoint commits, and the origin is unchanged.

## Results the PR reported

Against the old code, all three fail. With the change, they pass, alongside `test_impl_dry_run_is_dry.py` and `test_implement_from_lld_cli.py`: 60 passed.

The tests redirect `state_persistence.STATE_DIR` and `resume_contract.STATE_DIR` to the test's temporary directory. The first draft did not, and its N0 halt wrote `testing-42.json` into the real `~/.assemblyzero/workflow_state/`; that wider leak is #3531.

## Not verified for this backfill

- Nothing was re-run.
