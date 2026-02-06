# Open Issues Currency Audit

## Purpose

Identify open issues that are:
- **Actually complete** - Code exists, just never closed
- **Deprecated/Superseded** - Obsoleted by architectural changes
- **Stale** - No activity, unclear if still relevant
- **Misaligned** - Description doesn't match current architecture/terminology

## Trigger

- Bi-weekly
- Before sprint planning
- After major architectural changes

## Procedure

### Step 1: Generate Issue List

```bash
# Export open issues to review
gh issue list --repo {{GITHUB_REPO}} --state open --limit 100 --json number,title,labels,updatedAt,body \
  > temp-open-issues.json

# Quick summary
gh issue list --repo {{GITHUB_REPO}} --state open --json number,title,labels \
  --jq '.[] | "#\(.number): \(.title) [\(.labels | map(.name) | join(", "))]"'
```

### Step 2: Check for Completed Issues

For each issue, verify the code doesn't already exist:

```bash
# Example: Issue #45 (Feature X)
# Check if the feature exists
ls src/feature_x.py  # If exists, issue may be complete
grep -r "feature_x" src/  # If function exists, verify
```

**Red Flags:**
- LLD exists AND implementation code exists → Likely complete
- Tests exist and pass → Likely complete
- Reports exist in `docs/reports/done/{ID}-*-report.md` → Definitely complete

### Step 3: Check for Deprecated Issues

Look for issues that reference:
- Old architecture patterns
- Old terminology (verify against glossary)
- Superseded approaches
- Closed dependency issues

### Step 4: Check for Stale Issues

```bash
# Issues not updated in 30+ days
gh issue list --repo {{GITHUB_REPO}} --state open --json number,title,updatedAt \
  --jq '.[] | select(.updatedAt < (now - 2592000 | todate)) | "#\(.number): \(.title) (last: \(.updatedAt))"'
```

### Step 5: Remediation Actions

| Finding | Action |
|---------|--------|
| Complete (code exists) | Close with comment, create reports if missing |
| Deprecated | Close with "Superseded by #{NEW}" comment |
| Stale but valid | Add comment requesting status, add `needs-triage` label |
| Misaligned terminology | Update issue description via `gh issue edit` |
| Misaligned architecture | Update or close depending on relevance |

## Output Format

```markdown
## Open Issues Currency Audit - {DATE}

### Summary
- Issues reviewed: {N}
- Actually complete: {N}
- Deprecated: {N}
- Stale: {N}
- Misaligned: {N}
- Current (no action): {N}

### Actions Taken

#### Closed (Complete)
| Issue | Reason |
|-------|--------|
| #45 | Code exists in src/feature.py |

#### Closed (Deprecated)
| Issue | Superseded By |
|-------|---------------|
| #119 | #121 |

#### Updated (Terminology)
| Issue | Changes |
|-------|---------|
| #126 | Updated description |

#### Flagged (Stale)
| Issue | Last Updated | Action |
|-------|--------------|--------|
| #84 | 30+ days | Added needs-triage label |
```

---

*Template from: AssemblyZero/.claude/templates/docs/open-issues-audit.md*
