---
repo: martymcenroe/AgentOS
issue: 170
url: https://github.com/martymcenroe/AgentOS/issues/170
fetched: 2026-02-05T01:46:30.474689Z
---

# Issue #170: feat: Add pre-commit check for type/class renames that miss usages

## Problem

PR #165 renamed `RequirementsWorkflowState` to `WorkflowState` but created alias `RequirementsState` instead of `RequirementsWorkflowState`. This broke all imports.

**Root cause:** No automated check to verify all usages of a renamed type are updated.

## Proposed Solution

Add a LangGraph workflow node or pre-commit hook that:

1. Detects when a class/type definition is removed or renamed
2. Greps the codebase for all usages of the old name
3. Fails if any usages remain after the change

### Implementation Approach

```python
def check_type_renames(state: WorkflowState) -> dict:
    """Pre-commit check for orphaned type references."""
    # Get list of removed/renamed types from git diff
    # Grep codebase for each old name
    # Fail if found in source files (not docs/lineage)
    pass
```

## Acceptance Criteria

- [ ] Workflow node detects removed type definitions
- [ ] Workflow node greps for old names in source files
- [ ] Workflow fails with clear error listing orphaned usages
- [ ] Excludes docs/lineage from check (historical references ok)

## Related

- Issue #168: Bug caused by missing this check
- PR #165: The breaking change