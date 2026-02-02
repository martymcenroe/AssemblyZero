# Issue #152: fix: Mock-mode branches fail silently when fixtures missing

## Severity: MEDIUM

## Problem

Mock-mode implementations return empty results `[]` when fixture files are missing, instead of failing with a clear error.

## Locations

**File:** `agentos/workflows/scout/nodes.py` (lines 55-57, 82-96)
```python
if offline_mode:
    # Load fixture data
    raw_repos = load_fixture("github_search_response.json")
    # Returns [] if fixture missing - silent failure
```

**File:** `agentos/workflows/testing/nodes/implement_code.py` (line 423-424)
```python
if state.get("mock_mode"):
    return _mock_implement_code(state)
```

**File:** `agentos/workflows/lld/nodes.py` (various mock implementations)

## Impact

- Tests pass with empty data instead of failing
- Mock mode silently degrades instead of alerting
- Hard to debug why mock mode produces no output

## Expected Behavior

When a fixture file is missing:
1. Raise clear error: `FileNotFoundError: Fixture 'github_search_response.json' not found`
2. Or log warning and use sensible default with clear indication

## Suggested Fix

```python
def load_fixture(filename: str) -> Any:
    path = FIXTURES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Fixture '{filename}' not found at {path}")
    return json.loads(path.read_text())
```

## Found By

Comprehensive codebase scan for stub implementations.