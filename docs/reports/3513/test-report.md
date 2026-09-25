# Test Report — find_existing_worktree matches {Repo}-{issue} on {issue}-implementation exactly (#3513)

Backfilled 2026-09-25 after the merge, from PR #3530 (merge `90c87c3c`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added or rewrote

In `tests/unit/test_implement_from_lld_cli.py::TestWorktreeHandling`, all against a throwaway repo with real `git worktree add`:

- `test_find_existing_worktree` (rewritten; it previously mocked `subprocess.run`): `Repo-420` and `Repo-42` both exist. Issue 42 finds only `Repo-42`, issue 4 finds neither, and issue 420 finds `Repo-420`.
- `test_the_right_name_on_the_wrong_branch_is_not_a_match`: `Repo-42` on `42-lld`.
- `test_a_suffixed_directory_is_not_a_match`: `Repo-42-lld` on `42-implementation`.
- `test_create_worktree_refuses_the_right_path_on_the_wrong_branch`

## Results the PR reported

Against the old code, all four fail. With the change, the file passes: 53 passed.

## Not verified for this backfill

- Nothing was re-run.
