# Implementation report: #4694

A real implementation run on a TypeScript target (a Vitest web suite beside a Python suite), every call on `gemini-3.8-flash-high`, stopped at 28 of 29 Vitest tests. The one failure's frame named only the test file, so #2851 left the planned source file unchanged (`[EDIT-SCRIPT] no failure attributed to web/shared/engine.ts; left unchanged this iteration`). The model on the test file answered NO-EDIT and named the source file and the function where the fix belonged. Nothing routed the failure there, and N4 changed no file until the cap.

## What changed

- New module `assemblyzero/workflows/testing/nodes/implementation/decline_routing.py`:
  - `exercised_sources(test_paths, planned, repo_root)`: the planned, non-test files the given test files import, through `resolve_import_targets`, plus a `src/`-layout lookup for Python tests that import their package by name (`from pkg import module` also tries `pkg/module.py`). A test file that cannot be read or parsed raises, as `resolve_import_targets` does (#3779).
  - `files_named(reason, planned)`: the planned files a NO-EDIT reason names, by full path or by a tail ending at a separator, and the file names in it that match no planned file. The tokenizer accepts only a closed list of file extensions, so `e.g.` and `next.last_shown_price_usd_per_mwh` are not files.
  - `is_test_path(path)`: `is_test_file` for a repo-relative plan path. `is_test_file` judges the absolute paths N4 writes, and `tests/unit/test_x.py` without a leading slash fails its `/tests/` test.
  - `declines_outside_plan_text` and `decline_note`, the halt's and the routed prompt's wording.
- R1, `implement_code`: when every attributed path is a test file, the planned sources those tests import join `attributed_paths`, so #2851's skip does not apply to them that iteration, and a line says so.
- R2, `implement_code`: a NO-EDIT from either edit path (`try_edit_script_fix`, `edit_large_file`) is read by `files_named`. A named planned file the loop has not reached gets the failure this iteration, its context led by the decline's reason. One the loop has already passed goes to the returned `declined_routes`, and the next iteration offers it first, with the reason. Each file's prompts and edit calls now receive `file_error_context`, which is the iteration's corpus unless a route leads it.
- R3: a NO-EDIT naming an unplanned file is printed at once, carried in `_nothing_changed`'s stall text, returned as `declines_outside_plan`, and reported by `verify_phases._with_the_stall` in the cap's halt when the last pass changed something.
- R4: a planned file that no failure and no failing test's import names is still left unchanged.
- `TestingWorkflowState` gains `declined_routes` and `declines_outside_plan`.

## What did not change

When the failures attribute to no file, every file still receives the whole corpus; a route only leads its file's context and moves it first. #2866's rule for a failed patch on a test file, and the freeze rule (#2064), are untouched. #4692, the halt-at-once when only the spec can fix a failure, is a separate change and stays filed.

## Noticed, not changed

The #2866 test-file checks in `implement_code` test `filepath.split("/")[0] in ("tests", "test")`, which misses a TypeScript target's `web/tests/*.test.ts`. A failed patch on such a test file would fall back to regenerating it.
