# Issue #122: fix: reconcile --auto vs --gates none syntax across workflows

## Problem

Workflow CLI tools have inconsistent syntax for skipping gates:

| Workflow | Tool | Skip Gates Syntax |
|----------|------|-------------------|
| Requirements | `run_requirements_workflow.py` | `--gates none` |
| TDD Implementation | `run_implement_from_lld.py` | `--auto` |

This is confusing and error-prone.

## Proposed Fix

Standardize on one syntax across all workflows. Options:

**Option A: Use `--gates` everywhere**
```bash
--gates none      # Skip all gates
--gates review    # Skip only review gate  
--gates human     # Skip only human gate
```

**Option B: Use `--auto` everywhere**
```bash
--auto            # Skip all interactive gates
```

**Option C: Support both (with deprecation)**
Support both syntaxes, deprecate `--auto` in favor of `--gates none`.

## Files to Update

- `tools/run_requirements_workflow.py`
- `tools/run_implement_from_lld.py`
- `docs/runbooks/0907-unified-requirements-workflow.md`
- `docs/runbooks/0909-tdd-implementation-workflow.md`

## Acceptance Criteria

- [ ] All workflow CLIs use consistent syntax
- [ ] Runbooks updated with correct syntax
- [ ] Old syntax deprecated with warning (if keeping backwards compat)