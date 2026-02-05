---
repo: martymcenroe/AgentOS
issue: 297
url: https://github.com/martymcenroe/AgentOS/issues/297
fetched: 2026-02-05T04:34:14.556321Z
---

# Issue #297: bug: test_claude_dependency_uses_skipif failing

## Problem

Meta-test `test_explicit_skips.py::TestSkipifDecoratorUsage::test_claude_dependency_uses_skipif` is failing.

```
FAILED tests/unit/test_explicit_skips.py::TestSkipifDecoratorUsage::test_claude_dependency_uses_skipif
AssertionError: Tests depending on claude CLI should use @pytest.mark.skipif decorator with shutil.which('claude') check
```

## Context

This is a meta-test that checks if tests depending on claude CLI use proper skipif decorators. Something changed that broke this enforcement.

## Acceptance Criteria

- [ ] Investigate what changed
- [ ] Fix the test or the code it's checking
- [ ] All tests pass