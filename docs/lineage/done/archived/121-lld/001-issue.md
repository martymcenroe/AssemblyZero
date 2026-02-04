# Issue #121: fix: inconsistent LLD drafts directory path (uppercase vs lowercase)

## Problem

There's path inconsistency for LLD drafts directories:

| Location | Path | Case |
|----------|------|------|
| `agentos/core/config.py:66` | `docs/llds/drafts` | lowercase |
| `agentos/workflows/lld/nodes.py:957` | `docs/LLDs/drafts` | **UPPERCASE** (hardcoded) |
| `agentos/workflows/lld/audit.py:43` | `docs/lld/active` | lowercase |

The hardcoded path in `nodes.py` creates a stray `docs/LLDs/` directory that's confusing and inconsistent with the rest of the codebase.

## Root Cause

Line 957 in `agentos/workflows/lld/nodes.py`:
```python
drafts_dir = repo_root / "docs" / "LLDs" / "drafts"
```

Should use the constant from `config.py` instead of hardcoding.

## Proposed Fix

**Option A:** Use the existing constant
```python
from agentos.core.config import LLD_DRAFTS_DIR
drafts_dir = repo_root / LLD_DRAFTS_DIR
```

**Option B:** Eliminate drafts directory entirely
The requirements workflow saves directly to `docs/lld/active/`. Consider if the drafts directory is still needed or is legacy cruft.

## Files to Change

- `agentos/workflows/lld/nodes.py` - Fix hardcoded path
- `tests/test_lld_workflow.py` - Update test paths to match

## Acceptance Criteria

- [ ] No uppercase `LLDs` directory created
- [ ] All LLD paths use consistent casing
- [ ] Tests updated to match