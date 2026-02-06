---
description: Mine reports for testing gaps and automation opportunities
argument-hint: "[--full] [--file path/to/report.md]"
---

# Test Gap Mining Skill

**Model hint:** Use **Sonnet** - requires pattern recognition across reports and code correlation.

**Purpose:** Analyze implementation reports, test reports, and code to identify testing gaps and automation opportunities.

**Per AssemblyZero:adrs/test-first-philosophy:** Continuous test improvement requires systematic mining of existing documentation for test debt.

---

## Help

Usage: `/test-gaps [--full] [--file path/to/report.md]`

| Argument | Description |
|----------|-------------|
| (none) | Quick scan - recent reports only |
| `--full` | Comprehensive scan - all reports |
| `--file` | Analyze specific report file |

---

## Execution

### Step 1: Pre-Filter Reports (COST OPTIMIZATION)

**Before reading full reports, use Grep to identify which reports have test gaps.**

Run these Grep patterns across report directories:
```
Grep pattern: "manual testing|tested manually"
Grep pattern: "not tested|untested|skipped"
Grep pattern: "deferred|future work"
Grep pattern: "edge case.*not covered"
Grep pattern: "happy path only"
Grep pattern: "hard to test|difficult to mock"
Grep pattern: "TODO|FIXME"
```

This produces a list of files that contain gap indicators. Only proceed with files that have matches.

**Why:** Report files can be large. Pre-filtering with Grep (fast, no token cost) eliminates reports with no gaps before expensive file reads.

**If no reports have gap indicators:** Report "No test gaps found in reports" and exit early.

### Step 2: Gather Matched Reports

**Quick scan (default):**
```
Read matched docs/reports/*/test-report.md (last 5 issues with matches)
Read matched docs/reports/*/implementation-report.md (last 5 issues with matches)
```

**Full scan (--full):**
```
Read ALL matched docs/reports/*/test-report.md
Read ALL matched docs/reports/*/implementation-report.md
Read docs/9000-lessons-learned.md (if exists)
```

**Single file (--file):**
```
Read the specified file only (no pre-filter)
```

### Step 3: Pattern Matching

Scan each report for these gap indicators:

| Pattern | Category | Priority |
|---------|----------|----------|
| "manual testing" / "tested manually" | Automation opportunity | HIGH |
| "not tested" / "untested" / "skipped" | Known gap | CRITICAL |
| "deferred" / "future work" | Planned debt | MEDIUM |
| "edge case" + "not covered" | Missing coverage | HIGH |
| "happy path only" | Missing negative tests | HIGH |
| "works on my machine" | Environment-specific gap | MEDIUM |
| "hard to test" / "difficult to mock" | Architecture issue | LOW |
| "TODO" / "FIXME" in test code | Incomplete test | HIGH |

### Step 4: Cross-Reference Code

For each gap found:
1. Identify the affected code file
2. Check if unit tests exist for that file
3. Check current test coverage (if available)
4. Estimate complexity to add tests

### Step 5: Generate Report

Output a prioritized list:

```markdown
# Test Gap Analysis

**Scan type:** [Quick/Full/Single file]
**Reports analyzed:** [count]
**Date:** [YYYY-MM-DD]

---

## Critical Gaps (No tests exist)

| File | Gap Description | Source | Effort |
|------|-----------------|--------|--------|
| `path/to/file.js` | [description] | Report #XXX | [Low/Med/High] |

## Automation Opportunities (Manual → Automated)

| File | Current Testing | Automation Benefit | Source |
|------|-----------------|-------------------|--------|
| `path/to/file.js` | Manual login flow | Reduce regression time | Report #XXX |

## Edge Cases Missing

| File | Edge Case | Why Not Tested | Priority |
|------|-----------|----------------|----------|
| `path/to/file.js` | Empty allowlist | "Deferred" | HIGH |

## Architecture Issues (Hard to test)

| File | Issue | Suggested Refactor |
|------|-------|-------------------|
| `path/to/file.js` | Tight coupling to DOM | Extract pure functions |

---

## Recommended Actions

1. **[CRITICAL]** [First priority action]
2. **[HIGH]** [Second priority action]
3. ...

## Issues to Create

- [ ] `test(unit): Add tests for [file]` - [brief description]
- [ ] `refactor: Extract [function] for testability`
```

---

## Example Output

```markdown
# Test Gap Analysis

**Scan type:** Quick
**Reports analyzed:** 5
**Date:** 2026-01-09

---

## Critical Gaps (No tests exist)

| File | Gap Description | Source | Effort |
|------|-----------------|--------|--------|
| `src/popup.js` | 484 lines, 0 unit tests | Report #207 | High |
| `src/auth.js` | OAuth flow untested | Report #116 | Medium |

## Automation Opportunities (Manual → Automated)

| File | Current Testing | Automation Benefit | Source |
|------|-----------------|-------------------|--------|
| `src/popup.js` | Manual allowlist testing | 10 min → 5 sec | Report #194 |

## Recommended Actions

1. **[CRITICAL]** Add unit tests for popup.js (Issue #207 in progress)
2. **[HIGH]** Add integration tests for OAuth flow
3. **[MEDIUM]** Create E2E test for age gate flow

## Issues to Create

- [ ] `test(unit): Add tests for auth.js OAuth flow`
- [ ] `test(e2e): Add age gate verification test`
```

---

## Notes

- This skill is READ-ONLY - it analyzes but does not modify files
- Creates issues only when user confirms
- Helps maintain test-first philosophy compliance
- Run periodically (weekly recommended) to prevent test debt accumulation
