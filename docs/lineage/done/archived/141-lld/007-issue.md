# Issue #141: fix: Implementation workflow should archive LLD and reports to done/ on completion

## Summary

When the implementation workflow completes successfully, the LLD and reports remain in `active/` directories. They should be moved to `done/`.

## Current Behavior

1. LLD workflow saves approved LLD to `docs/lld/active/LLD-{issue}.md`
2. Implementation workflow creates reports in `docs/reports/active/`
3. Workflow completes successfully
4. **Files stay in `active/`** - requires manual cleanup

## Expected Behavior

On successful workflow completion, the `finalize` node should:

1. Move LLD from `docs/lld/active/` â†’ `docs/lld/done/`
2. Move reports from `docs/reports/active/` â†’ `docs/reports/done/`
3. Log the archival in audit trail

## Evidence

LLD-106 was left in `active/` after Issue #106 was closed and merged. Discovered during repo state review (commit 117321a).

## Implementation

Modify `agentos/workflows/testing/nodes/finalize.py` (will be `workflows/implementation/` after #139):

```python
def finalize(state: TestingWorkflowState) -> dict[str, Any]:
    # ... existing report generation ...
    
    # Archive LLD to done/
    lld_path = Path(state.get("lld_path", ""))
    if lld_path.exists() and "active" in lld_path.parts:
        done_path = lld_path.parent.parent / "done" / lld_path.name
        done_path.parent.mkdir(parents=True, exist_ok=True)
        lld_path.rename(done_path)
        print(f"    Archived LLD: {done_path}")
    
    # Archive reports to done/
    # ... similar pattern ...
```

## Related

- #139 - Rename workflows/testing/ to workflows/implementation/
- #140 - Inhume deprecated issue/ and lld/ workflows