---
repo: martymcenroe/AgentOS
issue: 289
url: https://github.com/martymcenroe/AgentOS/issues/289
fetched: 2026-02-05T02:30:35.814871Z
---

# Issue #289: feat: Add path security validation to TDD workflow

## Summary

Add path security validation from the original Issue #87 spec to prevent directory traversal and secret file exposure.

## Background

Issue #87 specified security controls for context files. These were not implemented in the current TDD workflow.

## Requirements

### Path Validation
1. All `--context` paths must resolve within project root
2. Reject paths containing `../` traversal sequences
3. Reject absolute paths outside project root
4. Resolve and validate symbolic links
5. Log rejected paths to audit trail

### Secret File Rejection
1. Reject files matching patterns (case-insensitive):
   - `*.env`, `.env*`
   - `*credentials*`
   - `*secret*`
   - `*.pem`, `*.key`
2. Clear error message on rejection

### File Size Limits
1. Reject individual files larger than 100KB
2. Clear error message with actual vs limit size

## Implementation

Create `agentos/workflows/testing/path_validator.py`:
- `validate_context_path(path, project_root) -> (bool, error)`
- `is_secret_file(path) -> bool`
- `check_file_size(path, limit=100*1024) -> (bool, error)`

## Acceptance Criteria

- [ ] `../` traversal rejected with clear error
- [ ] Absolute paths outside project rejected
- [ ] Symlinks resolved and validated
- [ ] Secret file patterns rejected
- [ ] Files >100KB rejected with size in error
- [ ] All rejections logged to audit

## Parent Issue

Extracted from #87 (Implementation Workflow)