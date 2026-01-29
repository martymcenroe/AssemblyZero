# Implementation Report: Issue #95 - Add --select and LLD Status Tracking

**Issue:** #95
**Date:** 2026-01-29
**Worktree:** AgentOS-86 (extending existing #86 implementation)

## Summary

Added `--select` flag to `run_lld_workflow.py` that presents open GitHub issues for selection, filtering out issues that already have Gemini-approved LLDs. Implemented LLD status tracking in a cache file and embedded review evidence directly in LLD files.

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/lld/audit.py` | Modified | Added LLD detection and tracking functions |
| `agentos/workflows/lld/nodes.py` | Modified | Embed review evidence in finalize node |
| `tools/run_lld_workflow.py` | Modified | Added --select and --audit flags |
| `tests/test_lld_workflow.py` | Modified | Fixed path assertion for docs/lld/ |
| `docs/lld/lld-status.json` | Added | Initial empty cache file |

## Design Decisions

### 1. Detection Pattern Priority
Chose 4 detection patterns in priority order:
1. `**Final Status:** APPROVED` - most explicit marker
2. Review Summary table entries - structured data
3. `### Gemini Review #N` headings - common pattern
4. Status field with date - legacy support

This ensures both new and existing LLDs are correctly detected.

### 2. Cache-First with Fallback
The `check_lld_status()` function checks cache first, then falls back to file scan. This optimizes for the common case while ensuring correctness even with stale cache.

### 3. docs/lld/ Path Convention
Changed from `docs/LLDs/active/` to `docs/lld/active/` to match the existing directory structure (already `docs/lld/done/` existed). Updated test assertion to match.

### 4. Review Evidence Embedding
The `embed_review_evidence()` function modifies LLD content in-place to add:
- Status field update with approval date
- Review Summary table (created if not present)
- Final Status marker at document end

This makes the review status discoverable by both humans and automated tools.

## Known Limitations

1. **Path separator in JSON**: Windows paths in lld-status.json use backslashes. This is fine for Windows-only use but may cause issues if shared across platforms.

2. **No versioning of review evidence**: If an LLD is re-reviewed, the old review evidence may be partially overwritten. The Review Summary table accumulates entries, but the Status field and Final Status marker are replaced.

3. **Pre-existing failing test**: `test_draft_revision_mode` in `test_issue_workflow.py` fails - this is pre-existing and unrelated to #95 changes.

## Code References

- LLD detection: `agentos/workflows/lld/audit.py:286-350`
- Review embedding: `agentos/workflows/lld/audit.py:558-621`
- Interactive selector: `tools/run_lld_workflow.py:53-145`
- Finalize with embedding: `agentos/workflows/lld/nodes.py:395-462`
