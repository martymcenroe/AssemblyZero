---
repo: martymcenroe/AssemblyZero
issue: 434
url: https://github.com/martymcenroe/AssemblyZero/issues/434
fetched: 2026-02-26T01:02:05.124768Z
---

# Issue #434: test(unit): Add tests for claude-usage-scraper.py regex parsing

## Gap

`claude-usage-scraper.py` has zero automated tests. The regex and ANSI parsing logic is complex and error-prone.

## Scope

- Extract regex/ANSI parsing into testable functions
- Add unit tests with fixture inputs covering edge cases
- Source: `docs/reports/done/3-test-report.md`

## Labels

test-gap, backlog