---
repo: martymcenroe/AgentOS
issue: 173
url: https://github.com/martymcenroe/AgentOS/issues/173
fetched: 2026-02-04T00:54:10.275171Z
---

# Issue #173: feat: TDD workflow should merge into existing files, not overwrite

## Problem

The TDD implementation workflow completely **replaced** `state.py` (270 lines) with a new version (56 lines), deleting critical code. The workflow generated new code without merging with existing content.

**Root cause:** TDD workflow writes files without checking if they already exist and have content.

## Proposed Solution

Add a LangGraph workflow node that:

1. Before writing any file, checks if it already exists
2. If file exists and has content, requires MERGE not REPLACE
3. Shows diff between existing content and proposed content
4. Requires human approval for any file replacement

### Implementation Approach

```python
def safe_file_write(state: WorkflowState) -> dict:
    """Check for existing content before overwriting."""
    for file_path, new_content in proposed_writes:
        if file_path.exists():
            existing = file_path.read_text()
            if len(existing) > 100:  # Non-trivial file
                # WARNING: About to replace 270 lines with 56 lines
                # Show: what will be DELETED
                # Require: explicit approval or merge strategy
        pass
```

### Merge Strategies

1. **Append** - Add new code to end of file
2. **Insert** - Add new code at specific location
3. **Extend** - Add new fields/methods to existing class
4. **Replace** - Full replacement (requires explicit approval)

## Acceptance Criteria

- [ ] TDD workflow detects existing files before write
- [ ] Files with >100 lines require merge approval
- [ ] Shows what will be DELETED if replacing
- [ ] Cannot silently replace files in --auto mode

## Related

- Issue #168: Bug caused by silent file replacement
- PR #165: The breaking change