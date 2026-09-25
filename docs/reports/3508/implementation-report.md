# Implementation Report — The implement dry run exits before the worktree is cut and the branch pushed (#3508)

Backfilled 2026-09-25 after the merge, from PR #3526 (merge `0f4d7ac2`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502, stage 3.

## What was wrong

The dry-run exit in `run_implement_from_lld.py` sat after worktree creation, which creates the sibling directory, cuts `{issue}-implementation`, and (at the time) pushed it to origin; the tool then printed "no files modified".

## What changed

The dry-run block sits before the worktree section, reports the plan (the worktree path and branch it would cut and from what base, or "none" under `--no-worktree`; the LLD, database, mode flags), and returns. It also skips `check_and_consume`, which deletes a verified resume contract on the way through; a dry run must leave the halt's record for the real resume.

## Files

`tests/unit/test_impl_dry_run_is_dry.py`, `tools/run_implement_from_lld.py`.
