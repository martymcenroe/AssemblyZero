# Test Report — The Gemini preflight runs only when Gemini is configured, and checks agy (#3506)

Backfilled 2026-09-25 after the merge, from PR #3540 (merge `2963678b`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_preflight_transport.py`. It overrides the conftest fixture so that `check_gemini_available` raises if it is ever called.

- `test_n1_with_claude_specs_and_no_credential_file_drafts`: the acceptance test. With no credential file and Claude on every node, N1 reaches the drafter.
- `test_a_claude_only_run_needs_no_preflight`, `test_a_gemini_reviewer_gets_the_transport_check`, `test_the_probe_runs_once_per_process`.
- `test_no_agy_is_a_transport_failure`, `test_a_failed_probe_is_a_transport_failure`, `test_an_empty_answer_is_a_failure`, `test_a_raising_probe_is_a_transport_failure`.

## Results the PR reported

All 8 fail on the old code. The full local unit tier first showed 3 gate-registry failures because the message head had changed; the head was restored. The registry, preflight and spec suites: 120 passed; the remaining failures were the known #3468 pair.

## What the tests missed

The tests handed the check a fake client and the conftest stubbed the real one, so nothing built the real `GeminiClient`, and the probe's use of the Claude default model (#3541) was found an hour later by an unrelated experiment. The lesson is recorded in the 2026-09-24 handoff: when code constructs a real collaborator, at least one test must run that real constructor.

## Not verified for this backfill

- Nothing was re-run.
