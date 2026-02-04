---
repo: martymcenroe/AgentOS
issue: 171
url: https://github.com/martymcenroe/AgentOS/issues/171
fetched: 2026-02-04T01:50:02.039125Z
---

# Issue #171: feat: Add mandatory diff review gate before commit in TDD workflow

## Problem

PR #165 committed auto-generated code without reviewing the diff. The TDD workflow replaced a 270-line `state.py` with a 56-line version, deleting critical enums and fields.

**Root cause:** No mandatory diff review gate before committing.

## Proposed Solution

Add a LangGraph workflow node that:

1. Shows the full `git diff --stat` before commit
2. For files with significant changes (>50% lines changed), shows the actual diff
3. Requires explicit human approval before proceeding
4. Flags files that were REPLACED vs MODIFIED

### Implementation Approach

```python
def diff_review_gate(state: WorkflowState) -> dict:
    """Mandatory diff review before commit."""
    diff_stat = run_git_diff_stat()
    
    for file in files_with_major_changes:
        # Flag: "WARNING: 80% of state.py was replaced"
        # Show before/after line counts
        # Require explicit approval
    pass
```

## Acceptance Criteria

- [ ] Workflow shows diff stats before any commit
- [ ] Files with >50% change ratio are flagged with WARNING
- [ ] Human must explicitly approve (not auto-skip)
- [ ] Diff review cannot be bypassed even in --auto mode

## Related

- Issue #168: Bug caused by missing this gate
- PR #165: The breaking change