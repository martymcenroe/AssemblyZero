# Test Report — The LLD dry run deletes and shifts nothing before it exits (#3507)

Backfilled 2026-09-25 after the merge, from PR #3525 (merge `cdd8ab7f`) and its body (#3559). None of it was re-run for this backfill.

## Tests the PR added

`tests/unit/test_lld_dry_run_is_dry.py` reads the filesystem after `main()` on a throwaway repo with a bare origin: the LLD and lineage are byte-identical after `--dry-run --yes`, no `42-lld-n1` appears, no worktree or branch is cut, and no run record is written. #3294 recorded that the old test checked only the flag; these check the tree.

## Results the PR reported

The PR body states no counts. Its CI run at `cdd8ab7f` is the record. The later #3510 PR notes that this file's wording assertion was updated there.

## Not verified for this backfill

- Nothing was re-run.
