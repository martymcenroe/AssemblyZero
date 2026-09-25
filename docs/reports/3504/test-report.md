# Test Report — Nested claude -p calls load no user hooks (#3504)

Backfilled 2026-09-25 after the merge, from PR #3543 (merge `a9c34f51`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

- `tests/unit/test_nested_claude_env.py::TestNestedCallsLoadNoUserHooks`: the flag is in the `invoke` command, the large-prompt command and the liveness-probe command.
- `tests/integration/test_nested_hooks_live.py` (opt-in, `AZ_LIVE_NESTED_PROBE=1`): one real nested call from a throwaway repository, asserting that no SessionStart baseline file appears for its session id.

## Results the PR reported

The three unit tests fail without the flag. The live test was run both ways: on the old code it failed (`session-baseline.sh wrote .../data/.session-baseline/f4891ffc-....txt`), and with the flag it passed. Full local unit tier: 10,619 passed, 2 failed, the known #3468 pair.

## Not verified for this backfill

- Nothing was re-run.
