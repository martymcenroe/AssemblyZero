# Implementation Report: Issue 3676 (TypeScript Safety)

## Changes
- Modified `assemblyzero/workflows/testing/runners/jest_runner.py`'s `run_tests()` method.
- When `TestFramework.VITEST` is detected, the runner now inspects the project root before running vitest.
- If `package.json` contains a `typecheck` script, it executes `npm run typecheck`.
- If no script is found but `tsconfig.json` exists, it executes `npx tsc --noEmit`.
- If the typecheck process exits with a non-zero code, it short-circuits and returns a `TestRunResult` using the fallback parser, injecting the typecheck failure directly into `raw_output`. This ensures that TypeScript compilation failures correctly block the pipeline.
- Created `tests/unit/test_vitest_typecheck.py` to assert the behavior explicitly.
