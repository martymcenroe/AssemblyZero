---
repo: martymcenroe/AgentOS
issue: 172
url: https://github.com/martymcenroe/AgentOS/issues/172
fetched: 2026-02-05T01:46:56.481808Z
---

# Issue #172: feat: Add smoke test that actually runs the workflow after TDD completion

## Problem

PR #165 tests passed but the actual workflow was completely broken. Unit tests with mocks don't catch integration breaks.

**Root cause:** No integration smoke test that runs the actual program.

## Proposed Solution

Add a LangGraph workflow node after green phase that:

1. Runs the actual program/workflow (not just pytest)
2. Uses `--mock` mode to avoid external API calls
3. Verifies no ImportError or immediate crashes
4. Fails the TDD workflow if smoke test fails

### Implementation Approach

```python
def integration_smoke_test(state: WorkflowState) -> dict:
    """Run actual program after unit tests pass."""
    # Identify the entry point (tools/run_*.py)
    # Run with --mock --help or minimal invocation
    # Capture ImportError, ModuleNotFoundError
    # Fail if any import errors occur
    pass
```

### Example Smoke Tests

```bash
# For requirements workflow changes:
poetry run python tools/run_requirements_workflow.py --help

# For implementation workflow changes:
poetry run python tools/run_implement_from_lld.py --help

# Catches: ImportError, missing dependencies, syntax errors
```

## Acceptance Criteria

- [ ] TDD workflow runs smoke test after green phase passes
- [ ] Smoke test imports and runs the actual entry point
- [ ] ImportError/ModuleNotFoundError fails the workflow
- [ ] Clear error message shows what import failed

## Related

- Issue #168: Bug that would have been caught by smoke test
- PR #165: The breaking change