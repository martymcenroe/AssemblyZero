# Issue #155: fix: Mock-heavy tests verify mocks, not actual behavior

## Severity: LOW-MEDIUM

## Problem

Tests use extensive mocking that verifies the mocking framework works, not that the actual code works. Real integrations can be completely broken and tests still pass.

## Location

**File:** `tests/test_designer.py`

**Pattern throughout:**
```python
with patch("agentos.nodes.designer.subprocess.run") as mock_run:
with patch("agentos.nodes.designer.GeminiClient") as mock_client_class:
with patch("agentos.nodes.designer._load_generator_instruction") as mock_load:
with patch("agentos.nodes.designer.LLD_DRAFTS_DIR", temp_drafts_dir):
with patch("agentos.nodes.designer.ReviewAuditLog") as mock_log_class:
```

## Impact

- Tests pass even if real subprocess calls would fail
- Tests pass even if real GeminiClient is broken
- Tests pass even if real file paths don't exist
- No confidence that code works in production

## Expected Behavior

Balance of:
1. **Unit tests with mocks** - Test logic in isolation (current approach, overused)
2. **Integration tests without mocks** - Test real subprocess, real API calls
3. **Contract tests** - Verify mock behavior matches real behavior

## Suggested Fix

Add integration test suite that runs with real dependencies:

```python
@pytest.mark.integration
def test_designer_real_subprocess():
    """Test with real subprocess - requires claude CLI."""
    # No mocking - test actual behavior
    result = subprocess.run(["claude", "--version"], capture_output=True)
    assert result.returncode == 0
```

Run integration tests separately:
```bash
pytest -m integration  # Real dependencies
pytest -m "not integration"  # Fast unit tests
```

## Found By

Comprehensive codebase scan for stub implementations.