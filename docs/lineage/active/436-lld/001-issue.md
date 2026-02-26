---
repo: martymcenroe/AssemblyZero
issue: 436
url: https://github.com/martymcenroe/AssemblyZero/issues/436
fetched: 2026-02-26T07:17:49.967934Z
---

# Issue #436: test(integration): Add automated E2E test for issue workflow (mock mode)

## Gap

Mock infrastructure exists but no automated test harness invokes the full issue workflow graph end-to-end.

## Scope

- Create automated E2E test using `--mock --auto` flags
- Verify the full graph execution path
- Add to CI pipeline
- Source: `docs/reports/active/testing-audit-2026-01-27.md`

## Labels

test-gap, backlog