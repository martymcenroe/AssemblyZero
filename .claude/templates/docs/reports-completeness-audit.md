# Reports Completeness Audit

## Purpose

Verify all closed issues have required reports (implementation-report.md, test-report.md). Catches process violations where issues were closed without documentation.

## Trigger

- Weekly (as part of session closeout)
- Before any major milestone
- After discovering a missing report

## Procedure

### Step 1: List Recently Closed Issues

```bash
# Get issues closed in last 30 days
gh issue list --repo {{GITHUB_REPO}} --state closed --limit 100 --json number,title,closedAt \
  --jq '.[] | select(.closedAt > (now - 2592000 | todate)) | "\(.number): \(.title)"'
```

### Step 2: Check for Reports

```bash
# For each closed issue, check if reports exist
for issue in $(gh issue list --repo {{GITHUB_REPO}} --state closed --limit 50 --json number -q '.[].number'); do
  if [ ! -f "docs/reports/done/${issue}-implementation-report.md" ]; then
    echo "MISSING: #$issue - No implementation report"
  elif [ ! -f "docs/reports/done/${issue}-test-report.md" ]; then
    echo "MISSING: #$issue - No test report"
  else
    echo "OK: #$issue"
  fi
done
```

### Step 3: Check Exceptions

**Before flagging any issue, verify it's not exempt:**

```bash
# For each closed issue, check exception criteria:
gh issue view {ID} --repo {{GITHUB_REPO}} --json labels,title,body

# Check for exemptions:
# 1. Labels contain "chore" or "documentation" → EXEMPT
# 2. Title starts with "chore:" or "docs:" → EXEMPT
# 3. Implementation plan exists → EXEMPT
# 4. No code changes (docs-only PR) → EXEMPT
```

## Exceptions

| Issue Type | Reports Required? | Notes |
|------------|-------------------|-------|
| Feature implementation | Yes | Both reports required |
| Bug fix | Yes | Both reports required |
| Implementation plan (process/config) | No | Plan is self-contained |
| Documentation only | No | No code = no test report |
| Chore (deps, formatting) | No | Minor changes exempt |
| Superseded/Deprecated | No | Closed without implementation |

## Output Format

```markdown
## Reports Completeness Audit - {DATE}

### Summary
- Issues checked: {N}
- Complete: {N}
- Missing reports: {N}
- Exempt: {N}

### Missing Reports
| Issue | Title | Missing |
|-------|-------|---------|
| #121 | Feature X | Both |

### Actions Taken
- Created docs/reports/active/121-implementation-report.md
- Created docs/reports/active/121-test-report.md
```

---

*Template from: AssemblyZero/.claude/templates/docs/reports-completeness-audit.md*
