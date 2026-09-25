# Test Report — -f joins PROHIBITED_FLAGS, the short form of --force (#3515)

Backfilled 2026-09-25 after the merge, from PR #3522 (merge `eeb5c5ec`) and its body (#3559). None of it was re-run for this backfill.

## Tests the PR added

`tests/unit/test_shell_security.py` pins the four forms: `git push -f`, `git branch -f`, `git checkout -f` and `git worktree remove -f` are refused.

## Results the PR reported

The PR body states no counts. The PR's CI run at `eeb5c5ec` is the record.

## Not verified for this backfill

- Nothing was re-run.
