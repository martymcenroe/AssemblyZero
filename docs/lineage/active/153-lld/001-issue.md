# Issue #153: fix: Weak tests only check object existence, not behavior

## Severity: MEDIUM

## Problem

Multiple tests only verify that objects are not None, without testing actual behavior. These tests pass even if the underlying functionality is completely broken.

## Locations

**File:** `tests/test_issue_workflow.py` line 532
```python
workflow = build_issue_workflow()
assert workflow is not None
```

**File:** `tests/test_testing_workflow.py` line 440
```python
assert workflow is not None
```

**File:** `tests/test_lld_workflow.py` line 295
```python
assert workflow is not None
```

**File:** `tests/unit/test_requirements_graph.py` lines 21, 32, 40
```python
assert graph is not None
assert compiled is not None
```

## Impact

- Workflow structure can be completely broken and tests still pass
- Tests provide false confidence
- Regressions go undetected

## Expected Behavior

Tests should verify:
1. Graph has expected nodes
2. Graph has expected edges
3. Entry point is correct
4. Conditional routing works
5. State transformations are correct

## Example Fix

```python
def test_issue_workflow_structure():
    workflow = build_issue_workflow()
    assert workflow is not None
    
    # Verify nodes exist
    assert "N1_draft" in workflow.nodes
    assert "N2_review" in workflow.nodes
    
    # Verify entry point
    assert workflow.entry_point == "N0_load_input"
    
    # Verify edges
    assert ("N0_load_input", "N1_draft") in workflow.edges
```

## Found By

Comprehensive codebase scan for stub implementations.