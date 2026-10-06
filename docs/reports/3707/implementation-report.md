# Implementation Report: a JavaScript project in a subdirectory is detected and run there (#3707)

## What was wrong

`detect_framework_from_project` looked for `jest.config.*`, `vitest.config.*` and `package.json` at the repository root only, so a target with `pyproject.toml` at the root and its web app under `web/` was seen as pytest only and its Vitest suite never ran. The non-pytest runners were built by `get_runner(framework, repo_root)` with the registry's bare config, so even a framework the LLD named started at the root, where there is no `package.json`, with test paths that are relative to the root.

## Changes made

1. `framework_detector.detect_framework_dirs(project_root)`: the frameworks the project has and where each lives, relative to the root. JavaScript frameworks are looked for at the root and up to `MAX_DETECT_DEPTH` (2) levels below it, skipping `SKIPPED_DIRS` (`node_modules`, `data`, `dist`, `build`, `coverage`, `__pycache__`, `.git`, `.venv`, `venv`) and hidden directories; pytest at the root. A `test_dirs` declaration in the target's `.unleashed.json` (`{"vitest": "web"}`) wins over detection, and a declaration naming no framework raises. `detect_framework_from_project` returns that map's keys, in the root-only detector's order for a root-only project.
2. `load_lld._configs_with_directories`: N0 sets `working_directory` on each framework config from the detected map (None for the root); the run record's `Frameworks:` line names each framework with its directory.
3. `runner_registry.get_runner(framework, project_root, working_directory=None)` carries the directory onto the runner's config; `verify_phases` passes the state config's `working_directory` at both non-pytest call sites.
4. `BaseTestRunner.project_dir` (root joined with `working_directory`) and `_paths_for_runner` (a test path inside `project_dir`, given relative to the root or absolute, is made relative to it). `JestRunner` reads `package.json` and `tsconfig.json` from `project_dir`; `JestRunner` and `PlaywrightRunner` pass their test paths through `_paths_for_runner`. The subprocess already ran in `working_directory` (`BaseTestRunner._run_subprocess`).

## Not changed

The pytest path (`_verify_red_pytest_single`, `_verify_green_pytest_single`) still runs at the root; a `pyproject.toml` below the root is not looked for.
