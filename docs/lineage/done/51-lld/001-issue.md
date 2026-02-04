# Issue #51: Audit log rotation and archiving

## User Story

**As an** Orchestrator running long-lived agent sessions,
**I want** automatic rotation and archiving of `governance_history.jsonl`,
**So that** log files don't grow unbounded and historical data is preserved in an organized archive.

## Context

This is a future enhancement identified during review of #50 (Governance Node & Audit Logger).

## Problem Statement

The `logs/governance_history.jsonl` file will grow indefinitely as governance decisions accumulate. Without rotation:
1. File reads become slow
2. Disk space is consumed
3. Historical analysis becomes unwieldy

## Proposed Solution

Implement log rotation with archiving:
- Rotate when file exceeds size threshold (e.g., 10MB) or age (e.g., daily)
- Archive to `logs/archive/governance_history_YYYY-MM-DD.jsonl.gz`
- Compress archived files
- Update `view_audit.py` to search across archives when needed

## Acceptance Criteria

- [ ] Logs rotate automatically based on configurable threshold
- [ ] Archived files are compressed
- [ ] Archive naming follows consistent pattern
- [ ] Viewer can optionally search archives

## Related Issues

- #50 - Implement Governance Node & Audit Logger (parent)