# Implementation Report — The LLD dry run deletes and shifts nothing before it exits (#3507)

Backfilled 2026-09-25 after the merge, from PR #3525 (merge `cdd8ab7f`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502, stage 3.

## What was wrong

`check_and_shift_existing_lld` ran in `main()` before `run_single_workflow`'s dry-run exit, so `--dry-run --yes` on an issue that already had an LLD deleted the LLD, shifted its lineage a generation, and then printed DRY RUN.

## What changed

The call is skipped on a dry run, and the dry-run plan says what a real run would do first: which LLD it would delete, which lineage it would shift (and that it would ask for YES without `--yes`), and which worktree and branch N0b would cut.

## Files

`tests/unit/test_lld_dry_run_is_dry.py`, `tools/run_requirements_workflow.py`.
