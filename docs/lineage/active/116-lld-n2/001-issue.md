# Issue #116: Add GitHub Actions CI workflow for automated testing

## Context

Currently there is no CI workflow - tests only run manually via `poetry run pytest`.

## Scope

- Add `.github/workflows/ci.yml` for automated testing
- Run on push to main and PRs
- Run `poetry run pytest` with coverage reporting
- Cache poetry dependencies for speed
- Consider matrix testing for Python versions (3.10, 3.11, 3.12)

## Acceptance Criteria

1. Tests run automatically on every PR
2. Tests run on push to main
3. Coverage report generated
4. Badge in README showing CI status

## Notes

- Tests use fixtures and mocks, should not require API keys
- Some tests may need `LANGSMITH_TRACING=false` to avoid tracing errors