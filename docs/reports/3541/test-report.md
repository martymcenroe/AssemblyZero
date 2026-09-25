# Test Report — The transport preflight probes with a Gemini model, not the Claude default (#3541)

Backfilled 2026-09-25 after the merge, from PR #3542 (merge `a39e29b2`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New class `TestTheProbeUsesAGeminiModel` in `tests/unit/test_preflight_transport.py`:

- `test_the_real_client_is_built_without_raising`: the real `GeminiClient` constructor runs, with only `invoke` and `_find_agy_cli` stubbed. This is the test #3506's suite lacked.
- `test_the_runs_gemini_spec_picks_the_probe_model`: `gemini:3.1-pro` gives `gemini-3.1-pro-high`.
- `test_a_spec_without_a_known_name_still_gets_a_gemini_model`

## Results the PR reported

All 3 fail on `2963678b`. With the fix: the preflight files 19 passed; the gate registry, spec, requirements-node and provider suites 301 passed. `audit_fail_open --check` passed.

## Not verified for this backfill

- Nothing was re-run.
