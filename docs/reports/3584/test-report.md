# Test Report: the deferred-scope audit runs on Gemini through agy and stops loudly (#3584)

## Tests added

All in `tests/unit/test_audit_deferred_scope.py`.

**`TestGeminiOnly`:**
- `test_T1_a_claude_profile_is_refused_before_any_call`: under `AZ_MODEL_PROFILE=claude`, `require_gemini_seat` raises `AuditFailed` naming the `claude:` spec, and no provider is built. (T1)
- `test_the_default_profile_resolves_to_gemini`.

**`TestLoudStop`:**
- `test_T2_a_failure_on_the_second_candidate_stops_with_no_report[raise]` and `[fail]`: a provider that raises, or returns an unsuccessful result, on the second of three candidates makes `main()` return 1, writes neither report, and alerts once with that candidate's issue number, the spec and the phase. (T2)
- `test_unparseable_answer_stops`.
- `test_a_refused_profile_alerts_and_writes_nothing`.
- `test_T3_a_complete_run_names_the_resolved_model`: the report names `` `gemini:3.1-pro` (gemini-3.1-pro-high, through agy) `` and carries neither `claude --print` nor "Claude Opus". (T3)
- `test_a_limited_run_says_so`.

**`TestCache`:**
- `test_a_cached_error_is_dropped_and_reclassified`.
- `test_a_corrupt_cache_stops_the_audit`.
- `test_a_failed_state_index_fetch_stops_the_audit`.

## Tests changed

`TestCategoryFor::test_error` becomes `test_there_is_no_error_category`, because the field and the category are gone.

## Runs, 2026-10-07

- `tests/unit/test_audit_deferred_scope.py`: 58 passed.
- With `tests/unit/test_loud_failure_check.py` at ceiling 333: 76 passed.
- `git grep "claude --print" tools/audit_deferred_scope.py`: nothing (acceptance criterion).
- Full `tests/unit` tier on `fddc1e25`, with the machine quiet: 10986 passed, 66 skipped, 7 deselected, 6 xfailed in 12m 20s. Lineage archival ran inside the worktree after the last test run and had nothing to stage.
- `tools/audit_loud_failure.py --check`: PASS at 333 after `--write-baseline` shrank it. `tools/audit_fail_open.py --check --strict`: PASS. `tools/audit_halt_sites.py --check`: PASS.
- `ruff check` on the two changed files: no finding beyond those on `main`.
