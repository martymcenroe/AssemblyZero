# Issue #154: fix: Environmental test skips hide failures instead of failing clearly

## Severity: LOW-MEDIUM

## Problem

Tests skip instead of failing when environmental dependencies are missing. This hides issues and makes CI results misleading.

## Locations

**File:** `tests/test_issue_78.py` line 327
```python
else:
    pytest.skip("Source .gitignore not accessible from test location")
```

**File:** `tests/test_integration_workflow.py` lines 84, 100
```python
if "'code' command not found" in str(e):
    pytest.skip("claude command not found in PATH")
```

## Impact

- CI shows green when tests didn't actually run
- Environmental issues are silently ignored
- Coverage numbers are misleading

## Expected Behavior

Options:
1. **Mark as integration tests** - Use `@pytest.mark.integration` and skip in CI
2. **Fail with clear message** - If dependency required, fail don't skip
3. **Mock the dependency** - If testing logic, mock the external call

## Suggested Fix

```python
@pytest.mark.integration
@pytest.mark.skipif(
    not shutil.which("claude"),
    reason="claude CLI not installed (integration test)"
)
def test_integration_with_claude():
    ...
```

This makes the skip EXPLICIT and CONFIGURED, not hidden in test body.

## Found By

Comprehensive codebase scan for stub implementations.