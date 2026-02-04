---
repo: martymcenroe/AgentOS
issue: 225
url: https://github.com/martymcenroe/AgentOS/issues/225
fetched: 2026-02-04T01:28:29.382776Z
---

# Issue #225: feat: Hard gate wrapper for skipped test enforcement (test-gate.py)

## Summary

Create a `tools/test-gate.py` wrapper script that enforces the Skipped Test Gate in CI, complementing the soft gate in CLAUDE.md.

## Background

Issue #81 adds a CLAUDE.md rule requiring agents to audit skipped tests. This is a "soft gate" - it relies on agent compliance. A hard gate would programmatically block PRs with unaudited critical skips.

## Proposed Implementation

### tools/test-gate.py

```bash
# Usage
python tools/test-gate.py pytest tests/ -v

# Wraps pytest, parses output, enforces audit
```

**Behavior:**
1. Run pytest with provided arguments
2. Parse output for skipped tests
3. Check for SKIPPED TEST AUDIT block in output or separate file
4. If skips exist without audit → exit 1 (fail CI)
5. If critical skips are UNVERIFIED → exit 1
6. Otherwise → exit with pytest's exit code

### Integration

```yaml
# In GitHub Actions
- name: Run tests with skip gate
  run: python tools/test-gate.py pytest tests/ -v
```

## Acceptance Criteria

- [ ] `test-gate.py` wraps pytest and captures output
- [ ] Detects skipped tests from pytest output
- [ ] Requires SKIPPED TEST AUDIT block when skips present
- [ ] Fails if critical tests are UNVERIFIED
- [ ] Passes through pytest exit code when no issues
- [ ] Works with common pytest flags (-v, -x, --cov, etc.)

## Related

- #81 - Soft gate (CLAUDE.md rule) - should be done first
- #116 - GitHub Actions CI workflow

## Complexity

Medium - requires pytest output parsing and audit format validation