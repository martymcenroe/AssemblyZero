# Test Report — The provider clears CLAUDECODE for nested claude -p itself (#3505)

Backfilled 2026-09-25 after the merge, from PR #3521 (merge `2f9ac7fa`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

`tests/unit/test_nested_claude_env.py`: the helper clears an inherited `CLAUDECODE=1`, sets the empty string when the parent had nothing, inherits everything else, and `invoke()` hands that env to `Popen`.

## Results the PR reported

Run with the provider and roll suites: 153 passed.

## Not verified for this backfill

- Nothing was re-run.
- The PR body does not state an old-code run for these tests.
