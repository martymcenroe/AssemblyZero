# Implementation Report: one run tests a Python suite and a Vitest suite (#4236, #4237, #3001, #3087, #3085)

The target is a repository with a pytest suite at its root and a Vitest suite in `web/`. Before this change the implementation workflow kept one test framework per run, sent a `.test.ts` path to Jest at the root, where nothing is installed, and never ran a Vitest suite in full. The rule is ADR 0236 and standard 0034: a failure is loud, stops what depends on it, and alerts the operator. Every new failure path below returns an `error_message` that the testing graph routes to `HALT`, and `HALT` alerts (#3724).

## #4236: every framework is written, and every phase runs every framework

`load_lld.py` resolved every framework and kept the first at three sites (`:1069`, `:1320`, `:1440` before this change). `framework_configs` was read in `verify_phases.py` (`:1677`, `:3271`) and written nowhere.

- All three load sites (`load_lld`, `_load_from_issue`, `_mock_load_lld`) now call `_framework_configs`, which resolves and places every framework, and write `framework_configs` (each entry checkpoint-safe, strings not enums) beside `framework_config`, which stays the first entry. A resolution failure, including an unreadable `package.json` that used to raise out of the node, returns an `error_message` marked `DETERMINISTIC FAILURE` and routes to `HALT`.
- `verify_red_phase` and `verify_green_phase` build one leg per framework (`_framework_legs`). With one framework, that framework runs every test file exactly as before. With more than one, each test file belongs to exactly one framework: the one whose file type it is, in the deepest directory that holds it, told apart by `.spec.` or `.test.` when two share a directory. A test file no framework owns, or that two own, halts the phase.
- Each leg runs on its own test files in its own directory, and sees only the implementation files of its own language and directory, so pytest's best-iteration snapshot and restore (#2050) never touch the TypeScript files. Files a leg registers (#2897) are joined back into the run's lists.
- Before any suite runs in a multi-framework phase, `_preflight_legs` starts every JavaScript runner and calls its new `require_dependencies`. A missing `npx`, or no `node_modules/.bin/vitest` (or `jest`, `playwright`) in the framework's directory or any directory above it up to the root, halts the phase naming the framework, its directory and every directory searched. A Yarn Plug'n'Play `.pnp.cjs` counts as installed. The single-framework red and green phases make the same check before they run.
- A framework that no test file of this run belongs to has nothing to verify in the red or green phase. That is printed and logged as `red_phase_framework_without_tests` or `green_phase_framework_without_tests`, and in the green phase its whole suite still runs at the full-suite gate once every targeted framework is green.
- The green result's `full_suite_validated` is true only when every framework's gate passed. An earlier framework's clean gate does not carry over when a later framework fails.

## #4237: a TypeScript test path resolves to the runner its own directory has

`framework_detector.py:105` mapped `.test.ts` to Jest, file patterns outranked the `vitest` keyword, `resolve_framework` (`:311-332`) let the LLD outrank the project, and `_configs_with_directories` (`load_lld.py:55`) placed a framework the project lacked at the root.

- `named_js_test_paths` finds every `.test.ts`, `.test.js`, `.spec.ts` and `.spec.js` path the LLD names, by splitting on markdown delimiters. A glob such as `*.test.ts` names no file and is not a path.
- `runner_for_test_path` reads the directory that holds the path, then each directory above it to the root. The first directory that declares a runner decides by its strongest evidence: config files, then the `package.json` `test` script, then a `vitest` or `jest` dependency. Two runners at the same strength that the file's name cannot choose between halt with both named. No runner in any of those directories halts with every directory searched.
- `place_frameworks` places each framework: a `test_dirs` declaration in `.unleashed.json`, then the directory the LLD's own path gave, then detection. pytest runs at the root by construction. Any other framework the project has nowhere raises `FrameworkResolutionError` naming it and every directory searched; it is never run from the root. `resolve_framework_dirs` is `resolve_framework` with this placement.
- An explicit `Test framework:` line keeps the highest priority, and an explicit JavaScript declaration covers every JavaScript path, so no runner is inferred beside it.
- A keyword is the weakest signal. With a project to read, a keyword such as `jest` adds no JavaScript runner when a declaration or a test path already named one, so prose like "Jest-compatible" beside a Vitest path does not halt the run.
- `detect_framework_from_lld` called without a project still reads `.test.ts` as Jest, as it did; production always passes the repository root.

## #3001: a pytest dev dependency is not a pytest suite

The issue's premise is partly superseded. Since #3707, `detect_framework_from_project` returns every framework it finds instead of `None` on ambiguity, so a config file is no longer discarded by a tie. The loose clause was still there (`framework_detector.py:285`): any `pyproject.toml` containing the word `pytest` made the root a pytest project. pytest was found before the subdirectories, so on a target with Vitest in `web/` it came first and was the one framework the run kept.

- `_has_pytest_suite` replaces the clause. pytest is detected from a declaration (`[tool.pytest` in `pyproject.toml`, `pytest.ini`, `[tool:pytest]` in `setup.cfg`, `[pytest]` in `tox.ini`, a root `conftest.py`) or from Python test files (`test_*.py`, `*_test.py`, `conftest.py`) at the root or in `tests/` or `test/` to two levels, skipping `node_modules` and the other skipped directories. A dependency line alone is not evidence.
- Test files count as evidence, not only the configuration marker the issue proposed, because a Python suite with no `[tool.pytest` section is common; dropping the clause alone would have dropped its suite without a word on a target with Vitest in `web/`.

## #3087: the full-suite gate runs for every framework

The gate existed only in the pytest green phase (`verify_phases.py:3074`). `_verify_green_non_pytest` returned success at `:3772` and `:3783` without it and never wrote `full_suite_validated`.

- `_full_suite_gate` is now the one gate. It runs `run_pytest([])` for pytest, and for Jest, Vitest and Playwright the runner with no test paths, which runs the project's whole suite (each runner adds paths only when given some). The droppings removal (#2048), visual-sample preservation (#2443), collection-cause lead (#2914), stagnation advisory and repair grace (#2920) apply to every framework.
- A regression routes to N4 with `full_suite_validated: False`. A whole suite that cannot start, or that collects nothing, halts. This applies to pytest too, where a whole suite collecting nothing used to read "0 tests passed, no regressions" and validate.
- Both non-pytest success returns now carry `full_suite_validated: True` and `full_suite_regressions: []`, measured values.

## #3085: a non-pytest suite that collects nothing is a collection failure

`_verify_green_non_pytest` had no zero-collected guard: 0 passed, 0 failed and 0 errors fell through `:3631` to the coverage branch at `:3692` and went to the implementer as undertested.

- `_zero_collected_route` is #2546's guard moved out of the pytest branch unchanged, and both green branches call it. The first zero is a named repair task; the second halts naming the collection error. The pytest branch's messages are word for word what they were.

## Compliance with standard 0034

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| N0 cannot resolve or place a framework (`_framework_resolution_failed`) | ERROR line printed | `error_message` names the path or framework and the directories searched | returns to `HALT` | through `HALT` |
| A test file no framework owns, two own, or a framework that cannot start (`_halt_legs_cannot_run`) | ERROR line printed | names the file or the framework, its directory and the cause | the phase runs no suite; `HALT` | through `HALT` |
| A single-framework runner unavailable or not installed | ERROR line printed | names the framework and cause | `HALT` | through `HALT` |
| The full suite cannot start or collects nothing (`_halt_full_suite_gate`) | ERROR line printed | names the framework, its directory, the exit code and the collection error | `full_suite_validated: False`; `HALT` | through `HALT` |
| Zero collected, second time | printed | collection error in `error_message` | `HALT` | through `HALT` |

## The gate registry

Every halt site must name a row in `assemblyzero/core/gate_registry.py`. The moved zero-collected halt is now `impl.green.collection_broken`'s site, the sites after it in `_verify_green_pytest_single` were renumbered, and the multi-framework phases' "No test files" guards joined `impl.no_test_files`. Three halt rows are new: `impl.framework_unresolved`, `impl.framework_cannot_run` and `impl.full_suite_cannot_run`, all `infrastructure`. Each names the operator's ADR 0236 ruling in `created_by`, as the earlier ADR 0236 rows do, and the ratchet baseline's impl halt rows rise from 37 to 40 in the same change. The parent session should confirm that citing that ruling is acceptable for this rise.

## New defects found, not changed here

- `assemblyzero/workflows/testing/nodes/scaffold_tests.py:1207-1214`: `determine_test_file_path` writes a Jest, Vitest or Playwright scaffold to `<root>/tests/`, ignoring the framework's `working_directory`. On a target whose Vitest suite is in `web/`, the scaffold lands where Vitest does not look. In a multi-framework run the new ownership check halts on it; in a single-framework run Vitest is handed a path outside its directory.
- `assemblyzero/workflows/testing/nodes/scaffold_tests.py:1322-1332`: the scaffolder writes tests for `framework_config`, the first framework, only. A second framework's new tests are not scaffolded.
- `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1166-1171`: N4 registers only `.py` files under `tests/` named `test_*` as test files, so TypeScript tests it writes never join `test_files`. They run only when that framework's whole suite runs at the gate.
- `assemblyzero/workflows/testing/runners/jest_runner.py:74`: Vitest runs without `--coverage`, and its JSON reporter carries no `coverageMap`, so every Vitest run measures 0% coverage and a green Vitest run can never meet the coverage target. The non-pytest coverage branch also routes a shortfall to `N4_implement_code`, where the pytest branch routes it to `N4c_augment_tests` (#2327).

## A consequence to know before a real run

Any target with a JavaScript test suite within two levels of its root is now a multi-framework target, and the run needs that suite's packages installed. This repository is one: `sentinel/package.json` runs `vitest run`, so an AssemblyZero run whose LLD names no JavaScript runner resolves to pytest and Vitest in `sentinel/`, and halts at N3 unless `sentinel/node_modules/.bin/vitest` exists in the worktree. Before this change that suite was detected and silently dropped.
