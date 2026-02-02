# Issue #52: Audit viewer filters (--issue, --verdict, --date)

## User Story

**As an** Orchestrator debugging a specific issue,
**I want** to filter audit logs by issue ID, verdict, or date range,
**So that** I can quickly find relevant governance decisions without scanning the entire log.

## Context

This is a future enhancement identified during review of #50 (Governance Node & Audit Logger).

## Problem Statement

As the audit log grows, finding specific entries becomes tedious. The initial viewer shows all entries, but targeted debugging requires filtering.

## Proposed Solution

Add filter flags to `tools/view_audit.py`:
```bash
# Filter by issue
python tools/view_audit.py --issue 48

# Filter by verdict
python tools/view_audit.py --verdict BLOCK

# Filter by date range
python tools/view_audit.py --since 2026-01-22
python tools/view_audit.py --since 2026-01-22 --until 2026-01-23

# Combine filters
python tools/view_audit.py --issue 48 --verdict BLOCK --live
```

## Acceptance Criteria

- [ ] `--issue N` filters by issue_id
- [ ] `--verdict APPROVED|BLOCK` filters by verdict
- [ ] `--since DATE` filters entries on or after date
- [ ] `--until DATE` filters entries on or before date
- [ ] Filters work with `--live` mode
- [ ] Filters can be combined

## Related Issues

- #50 - Implement Governance Node & Audit Logger (parent)