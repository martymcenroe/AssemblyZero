# 1285 - Bug: Integration Tests Run by Default

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: LLD creation for Issue #285
Update Reason: Initial LLD for fixing integration test default behavior
-->

## 1. Context & Goal
* **Issue:** #285
* **Objective:** Configure pytest to skip integration tests by default, requiring explicit flag to run tests that make real API calls
* **Status:** Draft
* **Related Issues:** None

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Should we add an `e2e` marker in addition to `integration`? **Yes - per issue specification**
- [x] Should we add an `expensive` marker for quota-heavy tests? **Yes - per issue specification**

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` | Modify | Add pytest configuration with markers and default exclusions |
| `tests/test_integration_workflow.py` | Modify | Add `@pytest.mark.integration` to API-calling tests |
| `tests/test_testing_workflow.py` | Modify | Add `@pytest.mark.integration` to API-calling tests |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

*Issue #277: Before human or Gemini review, paths are verified programmatically.*

Mechanical validation automatically checks:
- All "Modify" files must exist in repository ✓
- All "Delete" files must exist in repository ✓
- All "Add" files must have existing parent directories ✓
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists ✓

**If validation fails, the LLD is BLOCKED before reaching review.**

### 2.2 Dependencies

*No new dependencies required.*

```toml
# No pyproject.toml additions needed - pytest markers are built-in
```

### 2.3 Data Structures

```python
# No new data structures - configuration only
# N/A
```

### 2.4 Function Signatures

```python
# No new functions - configuration and marker decorators only
# N/A
```

### 2.5 Logic Flow (Pseudocode)

```
1. pytest invoked with `pytest tests/`
2. pytest reads pyproject.toml configuration
3. addopts applies: "-m 'not integration and not e2e'"
4. Tests marked with @pytest.mark.integration are DESELECTED
5. Tests marked with @pytest.mark.e2e are DESELECTED
6. Only unmarked tests run by default
7. User can override: `pytest tests/ -m integration`
```

### 2.6 Technical Approach

* **Module:** `pyproject.toml` (configuration)
* **Pattern:** Pytest marker-based test selection
* **Key Decisions:** 
  - Use `addopts` for default exclusion rather than conftest fixtures
  - Explicit markers rather than directory-based separation
  - Multiple marker types for granular control

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Exclusion mechanism | addopts in config, conftest hooks, env vars | addopts in pyproject.toml | Simplest, most visible, standard pytest pattern |
| Marker granularity | Single "integration" marker, Multiple markers | Multiple (integration, e2e, expensive) | Allows fine-grained test selection for different CI scenarios |
| Default behavior | Include all, Exclude integration | Exclude integration and e2e | Prevents accidental API calls and quota waste |

**Architectural Constraints:**
- Must not break existing CI pipelines (they can add `-m integration` if needed)
- Must be transparent in pytest output (shows deselected count)
- Must work with existing pytest plugins in use

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. `pytest tests/` runs without making any real API calls by default
2. `pytest tests/ -m integration` runs only integration-marked tests
3. `pytest tests/ -m "integration or e2e"` runs all external-service tests
4. Test markers are documented in pyproject.toml
5. Deselected test count is visible in pytest output

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| addopts in pyproject.toml | Standard, visible, easy to override | Requires explicit flag to run integration | **Selected** |
| Environment variable check | Flexible, CI-friendly | Hidden behavior, easy to forget | Rejected |
| Separate test directories | Clear separation | Major refactor, breaks imports | Rejected |
| conftest.py skip logic | Flexible conditions | Hidden, harder to override | Rejected |

**Rationale:** The addopts approach is the standard pytest pattern, requires minimal changes, and makes the default behavior explicit and easily overridable.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | N/A - Configuration only |
| Format | TOML |
| Size | ~10 lines |
| Refresh | Manual |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
N/A - No data pipeline for configuration change
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| N/A | N/A | No fixtures needed - testing pytest behavior itself |

### 5.4 Deployment Pipeline

Configuration change applies immediately upon merge. No deployment steps required.

**If data source is external:** N/A

## 6. Diagram
*N/A - Configuration change only, no architectural components to diagram*

### 6.1 Mermaid Quality Gate

N/A - No diagram required for this configuration change.

### 6.2 Diagram

N/A

## 7. Security & Safety Considerations

*This section addresses security (10 patterns) and safety (9 patterns) concerns from governance feedback.*

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| API key exposure in tests | Not applicable - this change reduces API calls | N/A |
| No security concerns | Configuration-only change | Addressed |

### 7.2 Safety

*Safety concerns focus on preventing data loss, ensuring fail-safe behavior, and protecting system integrity.*

| Concern | Mitigation | Status |
|---------|------------|--------|
| Breaking CI pipelines | Document change, update CI configs if needed | Addressed |
| Accidentally skipping important tests | Clear marker naming, visible deselection count | Addressed |
| Forgetting to run integration tests | Document in CONTRIBUTING.md, CI job for integration | Pending |

**Fail Mode:** Fail Safe - Tests are skipped rather than making unwanted API calls

**Recovery Strategy:** Add `-m integration` to run integration tests when needed

## 8. Performance & Cost Considerations

*This section addresses performance and cost concerns (6 patterns) from governance feedback.*

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Default test suite time | < 5 minutes | Skip 1-3 hour integration tests |
| CI feedback loop | < 10 minutes | Fast unit tests only by default |
| API Calls | 0 by default | Marker-based exclusion |

**Bottlenecks:** Integration tests were the bottleneck (1-3 hours). Now excluded by default.

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| LLM API calls (before) | ~$0.01 per call | ~100 calls/day (CI) | ~$30/month |
| LLM API calls (after) | ~$0.01 per call | ~5 calls/week (explicit) | ~$2/month |

**Cost Controls:**
- [x] Integration tests require explicit flag
- [x] Clear documentation of when to run integration tests
- [ ] CI job for periodic integration test runs (separate issue)

**Worst-Case Scenario:** Someone runs `pytest -m integration` frequently. Cost remains bounded by manual invocation requirement.

## 9. Legal & Compliance

*This section addresses legal concerns (8 patterns) from governance feedback.*

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Configuration change only |
| Third-Party Licenses | No | Using built-in pytest features |
| Terms of Service | No | Reduces API usage, improves compliance |
| Data Retention | No | No data involved |
| Export Controls | No | Not applicable |

**Data Classification:** N/A - Configuration only

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** This change is verified by observing pytest behavior, not by adding new tests.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** For configuration changes, verification is behavioral observation.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Default pytest run excludes integration | `pytest tests/` shows deselected integration tests | RED |
| T020 | Explicit marker runs integration tests | `pytest -m integration` runs only marked tests | RED |
| T030 | Combined run works | `pytest -m "not integration"` excludes integration | RED |

**Coverage Target:** N/A - Configuration change

**TDD Checklist:**
- [x] Verification approach defined
- [x] Expected behaviors documented
- [x] Manual verification steps clear

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Default run excludes integration | Manual | `pytest tests/ --collect-only` | Shows "X deselected" | Integration tests not collected |
| 020 | Explicit integration flag works | Manual | `pytest tests/ -m integration --collect-only` | Shows only integration tests | Only marked tests collected |
| 030 | Markers registered | Auto | `pytest --markers` | Shows integration, e2e, expensive | All markers documented |
| 040 | No API calls on default run | Manual | `pytest tests/` with network monitor | Zero external API calls | No HTTP to API endpoints |

**Type values:**
- `Auto` - Marker registration can be checked automatically
- `Manual` - Behavioral verification requires human observation

### 10.2 Test Commands

```bash
# Verify default behavior (should NOT call APIs)
pytest tests/ --collect-only | grep deselected

# Verify markers are registered
pytest --markers | grep -E "(integration|e2e|expensive)"

# Verify explicit integration run works
pytest tests/ -m integration --collect-only

# Run default tests (fast, no API)
pytest tests/ -v

# Run integration tests explicitly
pytest tests/ -m integration -v
```

### 10.3 Manual Tests (Only If Unavoidable)

**Manual tests required due to behavioral nature of verification:**

| ID | Scenario | Why Not Automated | Steps |
|----|----------|-------------------|-------|
| 010 | Default exclusion | Verifying test behavior requires external observation | 1. Run `pytest tests/` 2. Check output for "deselected" 3. Verify no API calls made |
| 040 | No API calls | Network monitoring not part of pytest | 1. Run `pytest tests/` 2. Monitor network traffic 3. Confirm no external API requests |

*Full test results recorded in Implementation Report (0103) or Test Report (0113).*

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| CI pipelines break due to missing tests | Medium | Low | Document change in PR, update CI if needed |
| Integration tests never run | High | Medium | Add periodic CI job for integration tests |
| Markers applied inconsistently | Low | Medium | Code review, grep for API calls |
| Override syntax confusion | Low | Low | Document in pyproject.toml comments |

## 12. Definition of Done

### Code
- [ ] pyproject.toml updated with pytest configuration
- [ ] Integration test files updated with markers
- [ ] Code comments explain marker purpose

### Tests
- [ ] All verification scenarios pass
- [ ] Default pytest run shows deselected integration tests
- [ ] Explicit `-m integration` runs only integration tests

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

*Issue #277: Cross-references are verified programmatically.*

Files in Definition of Done:
- `pyproject.toml` ✓ (Section 2.1)
- `tests/test_integration_workflow.py` ✓ (Section 2.1)
- `tests/test_testing_workflow.py` ✓ (Section 2.1)

**All files traced to Section 2.1.**

---

## Appendix: Implementation Details

### pyproject.toml Changes

```toml
[tool.pytest.ini_options]
# Default: exclude integration and e2e tests (they make real API calls)
# Run integration tests explicitly: pytest -m integration
# Run all tests including integration: pytest -m ""
addopts = "-m 'not integration and not e2e'"
markers = [
    "integration: tests that call real external services (deselect with '-m \"not integration\"')",
    "e2e: end-to-end workflow tests requiring sandbox repo",
    "expensive: tests that use significant API quota",
]
```

### Test File Marker Additions

**tests/test_integration_workflow.py:**
```python
import pytest

@pytest.mark.integration
def test_claude_headless_generates_output():
    """Calls real Claude API - 'Respond with exactly: TEST_PASSED'"""
    ...

@pytest.mark.integration
def test_claude_headless_with_unicode():
    """Calls real Claude API - 'Echo back: → ← ↑ ↓ • ★'"""
    ...
```

**tests/test_testing_workflow.py:**
```python
import pytest

@pytest.mark.integration
def test_call_claude_headless_returns_tuple():
    """Calls real Claude API - 'What is 2+2?'"""
    ...
```

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Awaiting review |

**Final Status:** PENDING