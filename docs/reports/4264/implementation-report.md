# Implementation report: #4264

## The premise, checked on main first

`assemblyzero/speedrun/requirements_status.py` kept an append-only ledger, `data/speedrun/telemetry/requirements-unverified.jsonl`, of runs that proceeded without a requirements verdict (#2290). Two banners read it: `main` in `tools/orchestrate.py`, after the stage table, and `_requirements_unverified_lines` in `tools/speedrun_roll.py`, which `_render_verdict` printed last on every branch.

On main at `ae4ed1dd`, `git grep` finds no caller of `record_unverified` in `assemblyzero/` or `tools/`. Its one caller was `_record_unverified` in the N0c node, and #3585 removed it: the comment that replaced it in `assemblyzero/workflows/requirements/nodes/analyze_requirements.py` says that path now halts. `test_an_all_unarticulated_verdict_files_nothing_and_halts_unverified` in `tests/unit/test_n0c_unarticulated_conflict.py` shows the all-unarticulated verdict halting with `REQUIREMENTS_UNVERIFIED_MARKER` in its message. So nothing wrote the ledger, and the banners could never print.

## What changed (R1, R2)

- `tools/orchestrate.py`: the banner and its read are gone, with the `orchestration_started_at` stamp that only scoped the read. A comment names #4264 in their place.
- `tools/speedrun_roll.py`: `_requirements_unverified_lines` is gone, and `_render_verdict` no longer computes or prints its lines. `_render_verdict` keeps its `since` argument, which `_blocking_questions` still reads.
- `assemblyzero/speedrun/requirements_status.py`: deleted. After the two reads went, nothing under `assemblyzero/` or `tools/` named it.

## Tests removed, and why

`tests/unit/test_requirements_status_loud_failure.py` is deleted. Its seven tests exercised only the deleted module's writer and reader.

In `tests/unit/test_n0c_unarticulated_conflict.py`, the `node` fixture no longer patches `record_unverified`, since the module it patched is gone. Two tests asserted only that the patched writer was not called, and went with it: `test_an_all_unarticulated_verdict_writes_no_proceeded_record` and `test_a_clean_verdict_is_not_recorded_as_unverified`. Two others lose that one assertion and keep the rest: `test_a_mixed_verdict_halts_on_the_real_one_and_files_only_that` and `test_a_well_formed_verdict_is_unchanged`.

In `tests/unit/test_requirements_gate_timeout.py`:

- Removed, because each exercised only the ledger or the banner: `test_a_verdict_records_nothing`, `test_the_standalone_precheck_does_not_write_roll_records`, `test_a_record_that_cannot_be_written_alerts_and_raises`, `test_since_filters_older_records`, the class `TestTheBanner` (`test_no_records_says_nothing`, `test_the_banner_names_the_state_and_the_issue`), `test_a_successful_roll_still_reports_unverified_requirements`, and `test_an_unreadable_ledger_never_costs_the_verdict`, whose patch target was the deleted reader.
- Kept, with the ledger assertion dropped and the name changed to what remains: `test_an_exhausted_retry_halts`, `test_an_unparseable_response_halts`, `test_the_last_fail_open_path_now_halts`. Each still asserts the run halted.
- `TestTheVerdictBlockCarriesIt` is now `TestTheVerdictBlock`. `test_a_clean_roll_says_nothing_extra` is unchanged. `test_a_failed_roll_carries_it_too` is now `test_a_failed_roll_reads_as_failed`: it writes no record, keeps its `ROLL FAILED` assertion, and asserts the banner is absent.

In `tests/unit/test_speedrun_roll_kill.py`, three tests in `TestKilledVerdictRendering` patched `_requirements_unverified_lines` to silence the banner. The patch is gone; their assertions are unchanged.

## T1

`tests/unit/test_requirements_status_retired.py` (new) parses every `.py` file under `assemblyzero/` and `tools/` with `ast` and fails on any `Name`, `Attribute`, `import` or `from ... import` name, or string constant that is `requirements_status` or has it as a dotted or slashed component. Its other tests show the module file is gone, that the check finds each of eight planted forms, and that it passes the live `requirements_unverified` state key and the `REQUIREMENTS UNVERIFIED:` halt marker.

## The loud-failure baseline

The two removed banners each held an `except Exception` that `tests/unit/test_loud_failure_check.py` tracks. Once the deletion is staged, `test_no_fixed_site_left_in_the_baseline` will report both entries as fixed. They leave `tests/fixtures/loud_failure_baseline.json`, its `count` drops from 115 to 113, and `BASELINE_CEILING` drops by two:

- `tools/orchestrate.py::main::swallowed_handler::1`
- `tools/speedrun_roll.py::_requirements_unverified_lines::swallowed_handler::1`

## The run

On Ubuntu, 2026-11-14, with the two deletions staged and both entries out of the baseline (`count` 113, `BASELINE_CEILING` 113):

- `tests/unit/test_loud_failure_check.py`: `18 passed`. It reported no other fixed site and no new one.
- The same file with `test_failopen_tags_3767.py` and `test_fail_open_audit.py`: `88 passed`.
- The orchestrator and launcher tests, every `tests/**/test_*.py` that loads `tools/orchestrate.py` or `tools/speedrun_roll.py`: `1042 passed, 20 skipped, 1 warning in 717.94s (0:11:57)`.

## Left alone

`docs/audits/0908-loud-failure-sweep-ledger.md` still has rows for the deleted module and its deleted test file. It is a dated record of the sweep, so it stays as written.
