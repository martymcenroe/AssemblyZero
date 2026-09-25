# Test Report — --mock cuts no LLD worktree and fetches nothing in N0b (#3512)

Backfilled 2026-09-25 after the merge, from PR #3535 (merge `d3048cad`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_lld_mock_is_offline.py`. It runs the real `tools/run_requirements_workflow.py` `main()` with `--type lld --mock` against a throwaway repo that has no remote at all:

- `test_a_mock_run_completes_with_no_remote`: exit 0.
- `test_a_mock_run_cuts_no_worktree_and_no_branch`: `git worktree list --porcelain` and `git branch --list --all` are identical before and after, and there is no `data/worktrees/`.
- `test_a_mock_run_sends_no_fetch_and_no_push`: every git command sent through `git_operations.run_command` is recorded, and none is a `fetch` or a `push`.

## Results the PR reported

Against the old code, the second and third fail. The first passes on both: with no remote, the old fetch failed silently and the cut fell back to local `main`, which is the silent network dependency the change removes. This run needed #3533 (PR #3534) to reach finalize. Neighbouring suites (fifteen files): 674 passed. `tools/audit_fail_open.py --check` passed with no baseline change.

## Not verified for this backfill

- Nothing was re-run.
