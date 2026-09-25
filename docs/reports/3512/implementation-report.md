# Implementation Report — --mock cuts no LLD worktree and fetches nothing in N0b (#3512)

Backfilled 2026-09-25 after the merge, from PR #3535 (merge `d3048cad`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

N0b (`analyze_codebase.py`) cut the `{issue}-lld` worktree and branch whenever `base_branch` was set, and for `--type lld` it always is. `setup_lld_worktree` runs `git fetch origin <base>` first. N5 already honoured `--mock` (#2288), but N0b never read the flag. So a mock run needed a network and left `data/worktrees/{issue}-lld` and the `{issue}-lld` branch in the target repo.

## What changed

Under `config_mock_mode`, N0b does not call `setup_lld_worktree`: no fetch, no worktree, no branch. It prints what it skipped, and the analysis reads the checkout. That is not the leak #2684 guards against, because the mock drafter reads nothing it is given. Real runs are unchanged.

A mock run still wrote the LLD, `lld-status.json` and lineage into the checkout after this change; that was #3510.

## Files

`assemblyzero/workflows/requirements/nodes/analyze_codebase.py`, `tests/unit/test_lld_mock_is_offline.py`.
