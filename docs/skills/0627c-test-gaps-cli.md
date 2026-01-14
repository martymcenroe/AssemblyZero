# /test-gaps - CLI Usage (Manual Steps)

**File:** `docs/skills/0627c-test-gaps-cli.md`
**Prompt Guide:** [0627p-test-gaps-prompt.md](0627p-test-gaps-prompt.md)
**Version:** 2026-01-14

---

## Overview

The `/test-gaps` skill mines reports for testing gaps. For manual analysis, search for gap indicators.

---

## Manual Analysis

### Search for Gap Indicators

```bash
# Find "manual testing" mentions
grep -r "manual testing\|tested manually" PROJECT/docs/

# Find untested mentions
grep -r "not tested\|untested\|skipped" PROJECT/docs/

# Find deferred items
grep -r "deferred\|future work" PROJECT/docs/

# Find edge case gaps
grep -r "edge case.*not covered\|happy path only" PROJECT/docs/

# Find TODOs in tests
grep -r "TODO\|FIXME" PROJECT/tests/
```

### Gap Categories

| Pattern | Category | Priority |
|---------|----------|----------|
| "manual testing" | Automation opportunity | HIGH |
| "not tested" | Known gap | CRITICAL |
| "deferred" | Planned debt | MEDIUM |
| "edge case not covered" | Missing coverage | HIGH |
| "happy path only" | Missing negative tests | HIGH |
| "works on my machine" | Environment-specific | MEDIUM |
| "hard to test" | Architecture issue | LOW |

---

## Report Locations

```bash
# Implementation reports
ls PROJECT/docs/reports/*/implementation-report.md

# Test reports
ls PROJECT/docs/reports/*/test-report.md

# Session logs (may contain test notes)
ls PROJECT/docs/session-logs/
```

---

## When to Use Manual vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Quick search for one pattern | **CLI** |
| Comprehensive gap analysis | **Skill** |
| Generate action plan | **Skill** |
| Create issues from gaps | **Skill** |
| Saving tokens | **CLI** |

---

## Related Files

- Test reports: `PROJECT/docs/reports/*/test-report.md`
- Skill definition: `~/.claude/commands/test-gaps.md`
