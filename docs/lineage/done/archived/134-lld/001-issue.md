# Issue #134: fix: E2E validation step fails with 'no tests collected' (return code 5)

## Problem

The TDD workflow E2E validation step (N6) consistently fails with pytest return code 5, which means "no tests were collected".

## Evidence

From issue #78 workflow run:
```
[N6] Running E2E validation...
    Running E2E tests on 1 file(s)
    Return code: 5
    E2E tests failed - iteration 2
```

This repeats for iterations 3, 4, etc.

## Context

- Green phase passes: 16 tests, 100% coverage
- All unit/integration tests work
- Only E2E step fails

## Likely Causes

1. **Marker mismatch**: E2E tests may need `@pytest.mark.e2e` marker, but test file doesn't have it
2. **Test discovery**: Pytest filters may not be matching E2E tests
3. **Sandbox requirement**: E2E tests may require `--sandbox-repo` argument that wasn't provided

## Current Workaround

Use `--skip-e2e` flag to bypass E2E validation:
```bash
poetry run python tools/run_implement_from_lld.py --issue 78 --auto --skip-e2e
```

## Files to Investigate

- `agentos/workflows/testing/nodes/e2e_validation.py` - E2E validation node
- `agentos/workflows/testing/nodes/scaffold_tests.py` - Test scaffolding (may need E2E markers)

## Acceptance Criteria

- [ ] E2E tests are properly marked with `@pytest.mark.e2e`
- [ ] Test scaffolding includes appropriate markers for detected test types
- [ ] E2E validation correctly filters for E2E tests only
- [ ] Workflow completes successfully with E2E when sandbox is configured