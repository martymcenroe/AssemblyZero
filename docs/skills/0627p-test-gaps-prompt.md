# /test-gaps - Prompt Usage

**File:** `docs/skills/0627p-test-gaps-prompt.md`
**CLI Guide:** [0627c-test-gaps-cli.md](0627c-test-gaps-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/test-gaps                    # Quick scan - recent reports
/test-gaps --full             # Comprehensive - all reports
/test-gaps --file report.md   # Analyze specific file
/test-gaps --help             # Show help
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| Comprehensive gap analysis | **Skill** |
| Quick pattern search | **CLI** |
| Generate action plan | **Skill** |
| Create GitHub issues | **Skill** |
| Saving tokens | **CLI** |

---

## What It Does

1. Searches implementation/test reports
2. Identifies test gaps and manual testing
3. Categorizes by priority
4. Generates action plan
5. Optionally creates GitHub issues

---

## Arguments

| Argument | Description |
|----------|-------------|
| (none) | Quick scan - recent reports |
| `--full` | Comprehensive - all reports |
| `--file path` | Analyze specific file |
| `--help` | Show help |

---

## Gap Indicators

| Pattern | Category | Priority |
|---------|----------|----------|
| "manual testing" | Automation opportunity | HIGH |
| "not tested" / "untested" | Known gap | CRITICAL |
| "deferred" / "future work" | Planned debt | MEDIUM |
| "edge case not covered" | Missing coverage | HIGH |
| "happy path only" | Missing negative tests | HIGH |
| "works on my machine" | Environment-specific | MEDIUM |
| "hard to test" | Architecture issue | LOW |
| TODO/FIXME in tests | Incomplete test | HIGH |

---

## Example Session

```
User: /test-gaps --full

Claude: Scanning all reports for test gaps...

# Test Gap Analysis

**Scan type:** Full
**Reports analyzed:** 12
**Date:** 2026-01-14

## Critical Gaps (No tests exist)

| File | Gap | Source | Effort |
|------|-----|--------|--------|
| `auth.py` | No test for token expiry | Report #123 | Medium |
| `api.py` | Error handling untested | Report #125 | Low |

## Automation Opportunities

| File | Current | Benefit | Source |
|------|---------|---------|--------|
| `login.py` | Manual login flow | Reduce regression | Report #123 |

## Recommended Actions

1. **[CRITICAL]** Add token expiry tests to auth.py
2. **[HIGH]** Add error handling tests to api.py
3. **[HIGH]** Automate login flow testing

## Issues to Create

- [ ] `test(unit): Add token expiry tests for auth.py`
- [ ] `test(unit): Add error handling tests for api.py`
- [ ] `test(e2e): Automate login flow`

Create these issues? (y/n)
```

---

## Output Format

```markdown
# Test Gap Analysis

**Scan type:** [Quick/Full/Single file]
**Reports analyzed:** [count]
**Date:** [YYYY-MM-DD]

## Critical Gaps (No tests exist)
| File | Gap | Source | Effort |

## Automation Opportunities
| File | Current | Benefit | Source |

## Recommended Actions
1. [Priority] Action

## Issues to Create
- [ ] Issue title
```

---

## Notes

- Read-only skill - analyzes but doesn't modify
- Creates issues only with user confirmation
- Run periodically (weekly recommended)

---

## Source of Truth

**Skill definition:** `~/.claude/commands/test-gaps.md`
