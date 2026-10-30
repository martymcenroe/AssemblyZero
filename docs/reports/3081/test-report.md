# Test Report: a Python suite and a Vitest suite are scaffolded, written, run and measured (#4244, #4243, #3081, #4245, #3065, #3067, #4246, #3089)

In progress. Each issue's section is written when its commit lands.

## #4244: `tests/unit/test_scaffold_every_framework.py` (5)

- T1: a target with pytest at the root and Vitest in `web/` gets two scaffolds, `tests/test_issue_7.py` and a `.test.ts` importing from `vitest` (on `4ac9c81a`: one file, `assert 0 == 1`); `generated_tests` is the Python scaffold the pytest validator reads (passed there too: it was the only scaffold).
- T2: a pytest-only target writes the one scaffold as before (kept behaviour, passed there).
- T3: a TypeScript template that raises for the second framework, and a Vitest runner with no `npx`, each halt N2 naming `vitest (web)` and the cause, print an ERROR line on stderr, and route to HALT (on `4ac9c81a`: `assert 'vitest (web)' in ''`, nothing scaffolded for Vitest).
- Against the unchanged source: 3 failed, 2 passed. On the fix: 5 passed.

## #4243: `tests/unit/test_ts_scaffold_in_its_directory.py` (6)

- T1: in a two-framework run the Vitest scaffold is `web/tests/issue_7.test.ts`, and `verify_phases._framework_legs` gives it to the Vitest leg and `tests/test_issue_7.py` to pytest; a single-framework Vitest config with `working_directory: web` gets `web/tests/`; a JavaScript framework at the root and pytest keep the root's `tests/` (two kept behaviours).
- T2: a scaffold for Vitest in `web/` in a run whose frameworks are pytest at the root and Vitest in `app/` raises `ScaffoldPathError` naming `issue_7.test.ts`, `pytest` and `vitest (app)`; a `working_directory` of `../elsewhere` raises naming "outside the repository".
- Against the unchanged source: 4 failed (`assert [] == [...web/tests/issue_7.test.ts]`, the root's `tests/` path, and `ImportError: cannot import name 'ScaffoldPathError'` twice), 2 passed. On the fix: 6 passed.
