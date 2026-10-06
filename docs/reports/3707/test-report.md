# Test Report: a JavaScript project in a subdirectory is detected and run there (#3707)

## Before the change

`detect_framework_from_project` on a target with `pyproject.toml` at the root, `web/package.json` (`"test": "vitest run"`) and `web/vitest.config.ts`: `['pytest']` (measured 2026-10-06).

## Tests added

`tests/unit/test_js_project_in_subdirectory.py`:

- `test_the_web_subdirectory_is_seen_with_its_directory`: the fixture above yields `{pytest: ".", vitest: "web"}` and `[pytest, vitest]`.
- `test_node_modules_and_data_are_never_descended_into`: decoy `package.json` files under `node_modules/` and `data/` are not seen.
- `test_the_root_keeps_its_old_order`: a root-only project is detected as before (config files, then package.json, then pytest).
- `test_two_levels_down_is_found_and_three_is_not`.
- `test_a_declaration_in_unleashed_json_wins`; `test_a_declaration_naming_no_framework_is_refused`.
- `test_n0_puts_each_directory_on_its_config`: detected in `web/`, at the root, and named-but-absent (root).
- `test_the_registry_puts_the_directory_on_the_config`; `test_the_subprocess_runs_in_the_project_directory` (the runner's `cwd` ends in `web`); `test_test_paths_are_made_relative_to_the_project_directory`; `test_get_runner_carries_the_directory_into_the_vitest_runner` (skipped where `npx` is absent).

## Runs

- The new file with `test_framework_detector.py`, `test_framework_injected_receivers.py`, `test_framework_integration.py`, `test_load_lld.py`, `test_load_lld_v2.py`, `test_jest_runner.py`, `test_runner_registry.py` and `test_testing_workflow.py`: see the closing comment on #3707.
- Full unit tier in the worktree: on the closing comment.
