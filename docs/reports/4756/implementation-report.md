# Implementation report: #4756

## The defect

Four files in `tests/integration/` carried no tier marker: `test_cascade_hook_integration.py`, `test_janitor_workflow.py`, `test_lld_parsing_chain.py` and `test_orchestrator_graph.py`. CI runs `tests/unit/` whole and runs `tests/` three more times with `-m integration`, `-m e2e` and `-m adversarial`, so no CI step and no local tier collected them.

Collecting `tests/` outside `tests/unit/` with `-m "not (integration or e2e or adversarial)"` at HEAD found 608 tests in 22 files:

| Where | Files | Disposition |
|---|---|---|
| `tests/tools/` | 15 | moved to `tests/unit/tools/` under #4278 |
| the four files above | 4 | moved to `tests/unit/` |
| `tests/test_universal_claude_md.py` | 1 | marked `integration` |
| `tests/canary/test_box_canary.py` | 1 | left as it is, on purpose |
| `tests/benchmark/test_cascade_detector_latency.py` | 1 | left as it is, on purpose |

## The move (R1)

`git mv` of the four files into `tests/unit/`. `pyproject.toml` defines `integration` as tests that call real external services, and these call none, so a marker would have mislabelled them. No file of the same name existed in `tests/unit/`.

`test_orchestrator_graph.py:215` reaches the repository root with `.parent.parent.parent`. The file sits at the same depth in `tests/unit/` as in `tests/integration/`, so the line needed no change. The other three find their inputs relative to the working directory.

`tests/unit/test_orchestrator_stage_runners.py` said the file "carries no such marker". It now says the file carried none and has since moved into the unit tier.

## `tests/test_universal_claude_md.py`, which the plan did not list

The investigation's table summed to 602 of the 608 tests. The other 6 are this file's. It reads the operator's universal `CLAUDE.md`, outside the repository, and `test_issue_references_exist` asks GitHub through `gh`, so it fits the `integration` definition, and it skips wherever that `CLAUDE.md` is absent, as in CI. Its module `pytestmark` is now `[pytest.mark.integration, pytest.mark.skipif(...)]`. Unmarked, it ran in no tier, although its docstring says it runs locally to catch drift. The local integration tier now runs it: 6 passed on Ubuntu before the change, in 103 seconds.

This kept the named list at the two files the plan named.

## The guard (R2)

`tests/unit/test_every_test_file_runs_in_a_tier.py`, shared with #4278.

It walks `tests/` as pytest does: `python_files`, `norecursedirs`, `python_classes` and `python_functions` from `pyproject.toml`, or pytest's defaults, read from pytest 9.0.3's source; `--ignore` and `--ignore-glob` in `addopts`; and the literal `collect_ignore` and `collect_ignore_glob` of every conftest. `__pycache__` and virtual environments are skipped, as pytest skips them. A conftest that defines `pytest_ignore_collect`, or changes either ignore list at run time, stops the check with `UnreadableCollection`, because it cannot be read statically. Today no conftest does either.

Each test file is parsed with `ast`; no regular expression reads code. A file passes when:

- it is under `tests/unit/`;
- every test function and test class in it carries `integration`, `e2e` or `adversarial`, through a module `pytestmark`, a class decorator, a class `pytestmark`, or the function's own decorator; or
- it is in `NAMED_EXCEPTIONS` with its reason.

`NAMED_EXCEPTIONS` holds exactly two files:

- `tests/canary/test_box_canary.py`: the launch health check's own micro suite, named by `assemblyzero/speedrun/box_health.py`.
- `tests/benchmark/test_cascade_detector_latency.py`: a wall-clock budget marked `benchmark`, deselected on purpose (#4190).

A failure names each file and the tests in it that no marker reaches, and says the three ways out.

Run against a copy of HEAD's `tests/` tree, extracted with `git archive`, the check names 20 files: the four above, `tests/test_universal_claude_md.py`, and the 15 files of `tests/tools/`. On the changed tree it names none.

## Tests

In `tests/unit/test_every_test_file_runs_in_a_tier.py`:

- `test_every_test_file_runs_in_a_tier`: the check on the repository.
- `test_every_named_exception_still_exists`
- `test_every_named_exception_has_a_reason`
- `test_an_unmarked_file_outside_the_unit_tier_fails_and_is_named`: a `tmp_path` tree with an unmarked `tests/integration/test_x.py` fails, and the message names that file and its test, and not the unmarked file under `tests/unit/`.
- `test_a_tier_marker_in_any_position_passes`, six cases: a module `pytestmark`, a `pytestmark` list beside a `skipif`, a class decorator, a class `pytestmark`, a decorator on every function, and a module with no tests.
- `test_a_test_no_tier_marker_reaches_is_named`, three cases: one of two functions unmarked, a module marked only `benchmark`, one of two methods unmarked.
- `test_a_named_exception_passes`
- `test_files_pytest_does_not_collect_are_skipped`: a fixture data file, a hidden folder, `build/`, and a folder in a conftest's `collect_ignore`.
- `test_a_conftest_this_check_cannot_read_stops_it`

## The run

On Ubuntu, 2026-11-14, through `tools/test-gate.py`, so the unit tier's conftest applies:

- the four moved files: `38 passed`;
- `tests/unit/tools/`: `559 passed`;
- `tests/unit/test_every_test_file_runs_in_a_tier.py`: `16 passed`.

No moved test needed a change beyond its path.

## Ruff

`ruff check` on each changed or moved file, compared with its text at HEAD under the new name: the same findings, none added. The new test file is clean.
