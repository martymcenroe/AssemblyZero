---
repo: martymcenroe/AgentOS
issue: 285
url: https://github.com/martymcenroe/AgentOS/issues/285
fetched: 2026-02-05T02:22:28.228931Z
---

# Issue #285: bug: integration tests run by default, making real API calls

## Problem

Integration tests run by default on every `pytest tests/`, making real API calls that:
- Waste API quota
- Add significant latency (1-3 hours for full suite)
- Provide no meaningful coverage of workflow logic

## Root Cause

No pytest configuration to skip integration tests by default:

```toml
# MISSING from pyproject.toml:
[tool.pytest.ini_options]
addopts = "-m 'not integration'"
markers = [
    "integration: tests that call real external services",
]
```

## Tests Making Real API Calls

| File | Test | API Call |
|------|------|----------|
| `test_integration_workflow.py:87` | `test_claude_headless_generates_output` | "Respond with exactly: TEST_PASSED" |
| `test_integration_workflow.py:102` | `test_claude_headless_with_unicode` | "Echo back: → ← ↑ ↓ • ★" |
| `test_testing_workflow.py:1508` | `test_call_claude_headless_returns_tuple` | "What is 2+2?" |

These are **trivial ping tests**, not workflow tests.

## What's Actually Needed

Real workflow integration tests should:
1. Run synthetic issues through the requirements workflow
2. Run synthetic LLDs through the testing workflow  
3. Use **recorded responses** (VCR cassettes) or **fixtures** - NOT real API calls
4. Verify state machine transitions and file outputs
5. Run against a **sandbox repo** for GitHub operations

## Current Gap

There are **no actual workflow integration tests**. The "integration" label is misused for CLI availability checks that should be:
- Skipped by default
- Run only when explicitly requested: `pytest -m integration`

## Fix

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-m 'not integration and not e2e'"
markers = [
    "integration: tests that call real external services (deselect with '-m \"not integration\"')",
    "e2e: end-to-end workflow tests requiring sandbox repo",
    "expensive: tests that use significant API quota",
]
```

## Verification

After fix:
```bash
# Default run - no API calls
pytest tests/

# Explicitly run integration tests
pytest tests/ -m integration
```