# Implementation Report — The provider clears CLAUDECODE for nested claude -p itself (#3505)

Backfilled 2026-09-25 after the merge, from PR #3521 (merge `2f9ac7fa`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502, stage 2.

## What was wrong

`ClaudeCLIProvider` built the nested `claude -p` environment at two sites as `os.environ.copy()` plus `PYTHONWARNINGS`, and left `CLAUDECODE` to whatever the parent session had. Launched from inside a Claude Code session without the `CLAUDECODE=` prefix, every nested call failed, and the failure read as a model error.

## What changed

Both sites call one helper, `_nested_claude_env()`, which sets `CLAUDECODE` to the empty string (not unset, which the harness treats differently), the way `speedrun_roll.py` already does for its own child. `CLAUDE.md`'s gotcha row and the three babysit-protocol commands stop prescribing the prefix.

## Files

`CLAUDE.md`, `assemblyzero/core/llm_provider.py`, `docs/babysit-protocol.md`, `tests/fixtures/fail_open_baseline.json`, `tests/unit/test_nested_claude_env.py`.
