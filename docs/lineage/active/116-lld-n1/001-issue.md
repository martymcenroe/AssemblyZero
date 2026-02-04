---
repo: martymcenroe/AgentOS
issue: 116
url: https://github.com/martymcenroe/AgentOS/issues/116
fetched: 2026-02-04T07:54:04.348456Z
---

# Issue #116: Add GitHub Actions CI workflow for automated testing

## Add GitHub Actions CI Workflow for Automated Testing

### Context

Currently there is no CI workflow - tests only run manually via `poetry run pytest`. The test suite has ~600 tests and takes ~20 minutes for full regression.

### Decision Needed: CI Strategy

Running full regression on every commit is expensive. Here are the options:

---

## Option A: Tiered by Trigger

| Trigger | Tests Run | Estimated Time |
|---------|-----------|----------------|
| PR opened/updated | Unit tests only (`tests/unit/`) | ~2 min |
| Push to main | Full regression (exclude live) | ~20 min |
| Nightly/manual | Full + live + coverage report | ~25 min |

**Pros:** Simple to understand, predictable
**Cons:** PRs might miss integration bugs

---

## Option B: Tiered by Pytest Markers

Use pytest markers to categorize tests:
- `@pytest.mark.fast` - always run (~2 min)
- `@pytest.mark.slow` - only on main (~15 min)  
- `@pytest.mark.live` - only manual, hits real APIs (~5 min)

```yaml
# On PR
pytest -m "not slow and not live"

# On main  
pytest -m "not live"

# Nightly/manual
pytest  # everything
```

**Pros:** Fine-grained control, can evolve over time
**Cons:** Requires marking all tests, maintenance burden

---

## Option C: Changed Files Detection

Only run tests related to changed files:
- `agentos/workflows/requirements/` changed → `tests/*requirements*`
- `tools/` changed → `tests/test_cli*`
- Always run a small smoke test suite

**Pros:** Fast feedback, only test what changed
**Cons:** Complex to configure, might miss cross-cutting bugs

---

## Option D: Hybrid (Recommended)

Combine A + B:

1. **PRs:** Unit tests + fast markers (~2-3 min)
2. **Push to main:** Full regression minus live tests (~20 min)
3. **Nightly:** Everything including live tests
4. **Coverage gate:** Require ≥90% coverage on new code in PRs

```yaml
on:
  pull_request:
    # Fast tests only
  push:
    branches: [main]
    # Full regression
  schedule:
    - cron: '0 6 * * *'  # 6 AM daily
    # Everything + live
```

**Pros:** Balance of speed and safety
**Cons:** More complex workflow file

---

## Other Considerations

- **Secrets:** Tests use mocks, shouldn't need API keys. Set `LANGSMITH_TRACING=false`
- **Matrix testing:** Python 3.10, 3.11, 3.12? Or just 3.11?
- **Caching:** Cache poetry dependencies for speed
- **Badge:** Add CI status badge to README

## Acceptance Criteria

- [ ] Tests run automatically on every PR
- [ ] Tests run on push to main
- [ ] Coverage report generated
- [ ] Badge in README showing CI status
- [ ] Strategy decision documented

## Next Steps

1. Decide on strategy (A, B, C, or D)
2. Implement `.github/workflows/ci.yml`
3. Add any needed pytest markers
4. Test with a PR