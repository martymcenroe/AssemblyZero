# Testing Strategy & Protocols

Generic testing strategy for AI-assisted development projects.

## 1. Test Pyramid

```
        ┌────────────┐
        │   E2E      │  Few, slow, high confidence
        ├────────────┤
        │Integration │  Some, medium speed
        ├────────────┤
        │   Unit     │  Many, fast, isolated
        └────────────┘
```

### Level Definitions

| Level | Scope | Speed | Tools |
|-------|-------|-------|-------|
| Unit | Single function/class | <100ms | pytest, jest |
| Integration | Multiple components | <1s | pytest, API tests |
| E2E | Full user flow | <30s | Playwright, Selenium |

## 2. Test-First Philosophy

See ADR: test-first-philosophy.md

**Core Principle:** Write tests before implementation.

1. Define expected behavior in test
2. Run test (should fail)
3. Implement minimal code to pass
4. Refactor while keeping tests green

## 3. Coverage Requirements

| Category | Target | Enforcement |
|----------|--------|-------------|
| Core Logic | 80%+ | CI gate |
| Utilities | 60%+ | Advisory |
| E2E | Critical paths | Manual review |

## 4. Test Naming Convention

```python
def test_[feature]_[scenario]_[expected_result]():
    # Example
    def test_login_invalid_password_returns_401():
        pass
```

## 5. Test Data Management

### Golden Sets
- Curated test data with known expected outputs
- Version controlled in `tests/data/`
- Updated when requirements change

### Fixtures
- Reusable test setup
- Avoid test interdependencies
- Clean up after tests

## 6. Modular Verification Protocol

After each implementation:

1. **Run affected tests:** `pytest tests/unit/test_feature.py`
2. **Check coverage:** `pytest --cov=src/feature`
3. **Run integration:** `pytest tests/integration/`
4. **Document:** Update test report

## 7. CI/CD Integration

### Required Gates
- All unit tests pass
- Coverage threshold met
- No linting errors
- Security scan clean

### Optional Gates
- E2E tests (may run nightly)
- Performance benchmarks
- Visual regression

## 8. Manual Testing Protocol

Some tests require human verification:

| Scenario | Why Manual | Protocol |
|----------|------------|----------|
| UI/UX | Subjective quality | Checklist verification |
| Accessibility | Real screen reader | WCAG checklist |
| Browser compat | Real browser behavior | Cross-browser matrix |

## 9. Test Maintenance

### When to Update Tests
- Requirements change
- Bug is found (add regression test)
- API changes

### When NOT to Update Tests
- Test is "inconvenient" to pass
- Implementation is hard
- Deadline pressure

**Tests document expected behavior. Fix the code, not the test.**

---

*Source: AssemblyZero/docs/standards/testing-strategy.md*
*Project-specific test configurations live in project documentation.*
