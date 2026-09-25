# Implementation Report — -f joins PROHIBITED_FLAGS, the short form of --force (#3515)

Backfilled 2026-09-25 after the merge, from PR #3522 (merge `eeb5c5ec`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502, stage 2.

## What was wrong

`PROHIBITED_FLAGS` in `assemblyzero/utils/shell.py` refused `--admin`, `--force`, `-D` and `--hard`. `-f` is `--force` spelled short, and `git push -f`, `git branch -f`, `git checkout -f` and `git worktree remove -f` all passed the gate.

## What changed

`-f` is on the list. One correction to the issue as filed: `checkpoints.py` runs its `git notes add -f` through its own `_run` helper, not through `run_command`, so it was never behind this gate and needs no change. No caller in `assemblyzero/` passes `-f` to `run_command`.

The baseline fixture moved because the fail-open gate's denominator counted functions at the time (the lock #3523 later removed).

## Files

`assemblyzero/utils/shell.py`, `tests/unit/test_shell_security.py`.
