# 0841 - Open Issues Currency Audit

**Status:** STUB - Implementation pending
**Category:** Documentation Health
**Frequency:** Weekly
**Auto-Fix:** No (requires human judgment)

---

## Purpose

Detect stale, abandoned, or secretly-completed issues. GitHub issues drift from reality faster than any other artifact.

---

## Checks

### 1. Stale Issue Detection

| Check | Threshold | Action |
|-------|-----------|--------|
| No activity in 7+ days | Warning | Ping assignee |
| No activity in 14+ days | Alert | Triage: close or update |
| No activity in 30+ days | Critical | Force close with "stale" label |

**Suggested implementation:**
```bash
gh issue list --state open --json number,title,updatedAt --jq '.[] | select(.updatedAt < (now - 7*24*60*60 | todate))'
```

### 2. Ghost Completion Detection

Issues marked "open" but actually done. Signs:
- PR merged that references issue but issue not closed
- All checklist items ticked but issue open
- "Done" or "complete" in recent comments but issue open

**Suggested implementation:**
- Cross-reference merged PRs with `Closes #N` against open issues
- Parse issue body for `- [x]` checkboxes, flag if all checked

### 3. Orphan Issue Detection

Issues with no assignee, no labels, or no milestone after 48 hours.

### 4. Blocker Chain Analysis

Find issues blocked by other issues that are themselves blocked. Circular dependencies or deep chains indicate planning problems.

**Suggested implementation:**
- Parse "blocked by #N" patterns
- Build dependency graph
- Alert on chains > 3 deep or cycles

---

## Suggestions for Future Implementation

1. **Issue Velocity Tracking**: Compare issues opened vs closed per week. Declining velocity = backlog debt accumulating.

2. **Label Hygiene**: Flag issues with conflicting labels (e.g., both `bug` and `enhancement`).

3. **Estimate Drift**: If issues have time estimates, compare actual resolution time. Systematic underestimation indicates planning problems.

4. **Cross-Repo Awareness**: For multi-repo projects, detect issues that reference files/code in other repos.

5. **AI-Assisted Triage**: Feed stale issues to Haiku with context, get suggested actions (close, needs-info, blocked-by-X).

---

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| - | - | STUB - Not yet implemented | - |

---

## Related

- [0842 - Reports Completeness](0842-audit-reports-completeness.md)
- [0838 - Broken References](0838-audit-broken-references.md)
