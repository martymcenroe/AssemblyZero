---
repo: martymcenroe/AgentOS
issue: 256
url: https://github.com/martymcenroe/AgentOS/issues/256
fetched: 2026-02-04T02:12:45.763317Z
---

# Issue #256: feat: Safe file write gate - require approval before overwriting files

## Problem

The TDD implementation workflow can silently **replace** entire files, deleting critical code. In PR #165, `state.py` (270 lines) was replaced with a 56-line version, losing functionality.

**Root cause:** The workflow writes files without checking if they already exist and have significant content.

## Proposed Solution

Add a LangGraph workflow node in `agentos/workflows/testing/nodes/` that:

1. Before writing any file, checks if it already exists
2. If file exists with >100 lines, shows diff and requires approval
3. Classifies changes as MODIFY, REPLACE, or NEW
4. Cannot be bypassed in `--auto` mode for destructive changes

## Implementation Paths

| File | Change |
|------|--------|
| `agentos/workflows/testing/nodes/safe_file_write.py` | Add - new gate node |
| `agentos/workflows/testing/graph.py` | Modify - insert gate before file writes |
| `agentos/workflows/testing/state.py` | Modify - add approval state fields |

## Merge Strategies

When overwriting detected:
1. **Append** - Add new code to end of file
2. **Insert** - Add at specific location  
3. **Extend** - Add new methods to existing class
4. **Replace** - Full replacement (requires explicit approval)

## Acceptance Criteria

- [ ] Detects existing files before write
- [ ] Files with >100 lines require approval if >50% changed
- [ ] Shows what will be DELETED if replacing
- [ ] Cannot silently replace in --auto mode
- [ ] Works with TDD implementation workflow

## Related

- Replaces #173 (closed - had wrong project paths)
- Original bug: PR #165