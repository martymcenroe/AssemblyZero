# Implementation report: #4708, #4709

One branch for two issues of one concern: unit tests that leave files outside pytest's own temporary folder, found by the write trace for #4706 on 2026-11-11.

## #4708: the telemetry buffer and the hourglass

`tests/home_state_guard.redirect`, the body of the autouse fixture `home_state_stays_out_of_home`, now points four more bindings under each test's `tmp_path / "home-state"`:

- `assemblyzero.telemetry.emitter._BUFFER_DIR`, read at call time by `_write_to_buffer` and `flush`, to `telemetry-buffer/`;
- `assemblyzero.workflows.death.hourglass.HISTORY_PATH`, which `hourglass` imports by name and the rest node appends to, to `hourglass/history.json`;
- `age_meter.AGE_METER_STATE_PATH`, and the default argument of `load_age_meter_state` and `save_age_meter_state`, to `hourglass/age_meter.json`. The default was bound when the functions were defined, so the fixture replaces each function's `__defaults__`; setting the module attribute alone would move nothing.

`assemblyzero.workflows.death.constants` is left alone. It is the design record, and `test_path_constants_absolute.py` asserts that its paths are absolute and under `~/.claude`. `real_bindings()` now also records the buffer, history and age-meter paths as the modules define them.

The session guard snapshots the two traced paths beside the two #3531 ones. `GUARDED_PATHS` stays the #3531 pair, which `test_the_guarded_paths_are_the_two_the_issue_names` pins; `TRACED_PATHS` holds the #4708 pair, and `snapshot()` now defaults to `WATCHED_PATHS`, the union, which is what `conftest.py` takes at session start and finish.

### A third writer the trace missed

With the buffer watched, the first full run failed the session guard: `added: ~/.assemblyzero/telemetry-buffer/2026-11-12.jsonl`, two `tool.start` events for `run_requirements_workflow` and `run_implement_from_lld` at 6:35:55 and 6:36:00 PM Central. `tests/unit/test_profile_bench.py::_help` runs each tool's `--help` in a child process with the real home. The tools wrap `main()` in `track_tool`, whose `tool.start` is emitted before argparse exits, and a child process never sees the autouse redirect. The child now runs with `ASSEMBLYZERO_TELEMETRY=0`; the test asserts only on the help text. The two events stay in the operator's buffer: the file is outside the Projects tree, where an agent deletes nothing.

## #4709: the triage brief in the system temp

`tests/unit/test_orchestrator_stages.py` has a module-wide autouse fixture, `temp_files_stay_under_tmp_path`, that sets `tempfile.tempdir` to `tmp_path / "system-temp"` for each test. `_fetch_issue_body_to_temp_brief` writes the brief with `tempfile.mkstemp`, so the four tests the issue names now leave it under their own `tmp_path`, which pytest prunes. Module-wide, so a new test in the file that reaches the writer is covered without asking for it. No production code changes.

## Assertions

No existing assertion changed. The only edits to existing tests are the fixture added to `test_orchestrator_stages.py`, the environment of `test_profile_bench.py::_help`, and an import order fix in the block the fixture touched.

## Lint

`ruff check` on the five changed files reports only findings that `origin/main` already has on lines this change does not touch (`RUF059`, `I001` in function-level imports, `PLR0402`, `PLW1510` on the existing subprocess test, `RUF100`). The import-order finding on the top-level block of `test_orchestrator_stages.py`, which this change edits, is fixed.
