---
repo: martymcenroe/AssemblyZero
issue: 381
url: https://github.com/martymcenroe/AssemblyZero/issues/381
fetched: 2026-02-25T08:29:31.810735Z
---

# Issue #381: TDD workflow: support Playwright/TypeScript test suites (not just pytest)

## Problem

The TDD implementation workflow (`run_implement_from_lld.py`, runbook 0909) assumes all tests are Python/pytest. When generating a Playwright test suite (TypeScript `.spec.ts` files), the workflow:

1. **N2 scaffold** generates a `tests/test_issue_N.py` file even when the LLD specifies TypeScript Playwright tests
2. **N2.5 validation** fails with "No import statements found" because it looks for Python imports in a file that should be TypeScript
3. **N5 verify_green** runs `pytest` which can't execute `.spec.ts` files
4. **N5 coverage** skips all implementation files as "test paths" since they're all under `tests/` — resulting in 0% coverage and infinite iteration loops

### Observed Behavior (Hermes issue #56)

```
[N2] Scaffolding tests...
    Test file: tests/test_issue_56.py    ← wrong, should be .spec.ts files
    Generated 38 tests
[N2.5] Validating generated tests (mechanical)...
    Validation FAILED: No import statements found
    [ESCALATE] Max attempts reached, escalating to Claude
[N4] Implementing code file-by-file (iteration 0)...
    14/14 files written                  ← all .spec.ts files, correct
[N5] Verifying green phase...
    Results: 0 passed, 0 failed
    Coverage: 0.0%                       ← pytest found nothing to run
    [ITERATE] Coverage 0.0% < target 95% ← loops forever
```

## Expected Behavior

The workflow should detect the test framework from the LLD and adapt:

| LLD specifies | Test runner | File pattern | Coverage tool |
|---------------|-------------|-------------|---------------|
| Python tests | `pytest` | `test_*.py` | `pytest-cov` |
| Playwright e2e | `npx playwright test` | `*.spec.ts` | Playwright's built-in coverage or skip |
| Jest/Vitest | `npx jest` / `npx vitest` | `*.test.ts` | `--coverage` flag |

## Proposed Fix

### N0 (LoadLLD)
- Parse LLD for test framework indicators (Playwright, Jest, pytest, etc.)
- Set `test_runner` and `test_file_pattern` in workflow state

### N2 (ScaffoldTests)
- Use `test_file_pattern` to generate appropriate file types
- For Playwright: scaffold `.spec.ts` files with `import { test, expect } from '@playwright/test'`

### N2.5 (ValidateTests)
- Framework-aware validation (TypeScript imports vs Python imports)

### N5 (VerifyGreen)
- Run the appropriate test runner based on `test_runner` state
- For Playwright: `npx playwright test` with `--reporter=json`
- Parse results from the runner's native format
- Coverage: either use framework-specific coverage or accept a lower/no coverage target for e2e tests

### Coverage Target
- E2E tests inherently can't measure code coverage the same way unit tests do
- Consider a separate metric for e2e: "scenarios passing / scenarios defined"
- Or allow LLDs to set `coverage_type: scenario` instead of `coverage_type: line`

## Context
- Discovered while running `run_implement_from_lld.py --issue 56` for Hermes (Playwright dashboard test suite)
- The workflow successfully generated all 14 TypeScript files but couldn't verify them
- Files are in worktree `Hermes-56` and look correct — just need the right test runner