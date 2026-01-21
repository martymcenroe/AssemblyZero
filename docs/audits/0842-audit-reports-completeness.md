# 0842 - Reports Completeness Audit

**Status:** STUB - Implementation pending
**Category:** Documentation Health
**Frequency:** Weekly
**Auto-Fix:** Yes (can generate missing report skeletons)

---

## Purpose

Ensure every closed issue has proper implementation and test reports. Reports are the institutional memory that survives context compaction.

---

## Checks

### 1. Missing Reports for Closed Issues

| Artifact | Required For | Location |
|----------|--------------|----------|
| Implementation Report | All closed issues with code changes | `docs/reports/{issue-id}/implementation-report.md` |
| Test Report | All closed issues with code changes | `docs/reports/{issue-id}/test-report.md` |
| LLD | Features and non-trivial bugs | `docs/reports/{issue-id}/lld-*.md` |

**Suggested implementation:**
```bash
# Get closed issues
gh issue list --state closed --json number,closedAt --jq '.[].number'

# Check for report directory
for issue in $issues; do
  if [ ! -d "docs/reports/$issue" ]; then
    echo "MISSING: docs/reports/$issue/"
  fi
done
```

### 2. Report Quality Gates

Even if report exists, check it's not a skeleton:
- Implementation report has > 50 words
- Implementation report lists at least one file changed
- Test report includes actual test output (not just "tests passed")
- Test report has coverage metrics if available

### 3. Report Staleness

Reports that reference files that no longer exist, or code that has substantially changed since the report was written.

**Suggested implementation:**
- Extract file paths from reports
- Check if files still exist
- Compare file modification date to report date

### 4. Retroactive Report Detection

Issues closed BEFORE the report gate was implemented (2026-01-17) should be flagged differently - these are historical exceptions, not violations.

---

## Auto-Fix Capability

When missing reports detected:

1. **Generate skeleton** with:
   - Issue number and link
   - Closed date
   - List of commits between issue open and close dates
   - Placeholder sections

2. **Do NOT auto-fill** content that requires human judgment

---

## Suggestions for Future Implementation

1. **Report Templates by Issue Type**: Different templates for bugs vs features vs refactors.

2. **Commit-to-Report Linking**: Automatically extract "what changed" from git log.

3. **Report Freshness Score**: Decay score over time if the code referenced has changed significantly.

4. **Cross-Reference Validation**: Verify that files mentioned in reports still exist and line numbers are still valid.

5. **Gemini Review Integration**: Submit reports to Gemini for completeness scoring.

---

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| - | - | STUB - Not yet implemented | - |

---

## Related

- [0841 - Open Issues](0841-audit-open-issues.md)
- [0103 - Implementation Report Template](../templates/0103-implementation-report-template.md)
- [0108 - Test Report Template](../templates/0108-test-report-template.md)
