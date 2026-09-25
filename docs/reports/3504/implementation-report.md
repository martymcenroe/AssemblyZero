# Implementation Report — Nested claude -p calls load no user hooks (#3504)

Backfilled 2026-09-25 after the merge, from PR #3543 (merge `a9c34f51`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## The evidence

One nested call was run exactly as `ClaudeCLIProvider` runs it (`ClaudeCLIProvider("haiku").invoke`, prompt "Reply with the single word OK.", from an empty directory inside a git repository), and the hooks' own records were read. As the provider ran it: the call succeeded in 4.5 s; SessionStart's `session-baseline.sh` wrote `{repo}/data/.session-baseline/{session_id}.txt`; the SessionEnd transcript archiver scanned 17,725 files and copied 29,773,442 bytes. With `disableAllHooks`: the call succeeded in 3.0 s and neither hook acted. PreToolUse and PostToolUse can never fire, because a nested call passes `--tools ""`.

## What changed

- Every command `ClaudeCLIProvider` builds, in `invoke` and `_probe_alive`, carries `--settings '{"disableAllHooks": true}'`, defined once as `NESTED_SETTINGS_ARGS`. `--setting-sources user` is unchanged, so authentication behaves as before; only the hooks are switched off. The large-system-prompt path keeps the flag.
- ADR 0232 records the evidence, the decision and the consequences; ADR 0208's CLI section points to it. It was Proposed here and Accepted with #3517.

## Files

`assemblyzero/core/llm_provider.py`, `docs/adrs/0208-llm-invocation-strategy.md`, `docs/adrs/0232-nested-claude-calls-load-no-user-hooks.md`, `tests/integration/test_nested_hooks_live.py`, `tests/unit/test_nested_claude_env.py`.
