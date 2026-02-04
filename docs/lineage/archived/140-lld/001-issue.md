# Issue #140: chore: inhume deprecated issue/ and lld/ workflows

## Summary

The standalone `workflows/issue/`, `workflows/lld/`, and `workflows/governance/` directories are deprecated. They have been superseded by the **Unified Requirements Workflow** (`workflows/requirements/`).

## The Contract

> *"We prefer the word 'inhumed'. 'Deleted' implies a lack of style."*
> â€” Lord Downey, Assassins' Guild

Per [Workflow Personas](../wiki/Workflow-Personas.md), deprecated code should be inhumed, not merely deleted.

## Targets

| Target | Status | Replacement |
|--------|--------|-------------|
| `agentos/workflows/issue/` | Deprecated | `workflows/requirements/` with `create_issue_config()` |
| `agentos/workflows/lld/` | Deprecated | `workflows/requirements/` with `create_lld_config()` |
| `agentos/workflows/governance/` | Empty placeholder | None needed |

## Inhumation Checklist

Per Lord Downey's protocol:

- [ ] Identify all tests guarding target directories
- [ ] Find all files that import from `workflows.issue`, `workflows.lld`, or `workflows.governance`
- [ ] Update imports to use `workflows.requirements`
- [ ] Remove targets and related tests atomically
- [ ] Clean import statements from referencing files
- [ ] Verify build stability post-deletion
- [ ] Rollback if witnesses remain (tests fail)

## Files to Inhume

### workflows/issue/
- `graph.py`
- `state.py`
- `audit.py`
- `nodes/*.py`
- `__init__.py`

### workflows/lld/
- `graph.py`
- `state.py`
- `audit.py`
- `nodes.py`
- `__init__.py`

### workflows/governance/
- `nodes/` (empty, just `__pycache__`)
- Entire directory is a placeholder

## Why Now

The unified requirements workflow is operational and handles both issue and LLD creation through parameterized configuration. Maintaining three workflows for two use cases creates drift risk.

---

*Nil Mortifi Sine Lucre* â€” No killing without profit