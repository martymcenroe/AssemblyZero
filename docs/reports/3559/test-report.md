# Test Report — Reports backfilled for the eighteen PRs of 2026-09-24 (#3559)

## What was run

From the main checkout's venv, against this worktree:

```
tests/unit/test_reports_backfilled_2026_09_24.py
19 passed, 1 warning in 2.22s

poetry run ruff check tests/unit/test_reports_backfilled_2026_09_24.py
All checks passed!
```

The test is parametrised over the eighteen `(issue, PR)` pairs of the #3559
table and, for each, asserts `implementation-report.md` and `test-report.md`
exist under `docs/reports/{issue}/`, carry `Backfilled 2026-09-25`, and name
`PR #<n>`. A second test pins the table at eighteen distinct issues.

## On the tree before the backfill

The same test against `main` at `344b8108` fails all eighteen parametrised
cases, since none of the directories existed; that is the count the #3559
table was built from (`ls docs/reports/` on that commit).

## What each backfilled test report contains

The tests the PR added or changed, by name, as the PR body listed them; the
counts the PR reported at the time, verbatim; and a "Not verified for this
backfill" section stating that nothing was re-run. Where a PR body reported
no counts (#3515, #3514, #3507, #3508), the report says so and points at the
PR's CI run at its merge commit.

## Not verified

- Nothing from the eighteen PRs was re-run for the backfill. The reports are
  transcriptions of the record, and say so.
