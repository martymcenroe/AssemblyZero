# 111 - Fix: test_gemini_client exhausted credentials returns wrong error type

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: LLD creation for Issue #111
Update Reason: Initial LLD for test assertion fix
-->

## 1. Context & Goal
* **Issue:** #111
* **Objective:** Determine correct error type for "all credentials exhausted" scenario and align test expectation with intended behavior
* **Status:** Draft
* **Related Issues:** #108 (credential loading), #109 (429 rotation), #110 (529 backoff)

### Open Questions

- [x] Is `QUOTA_EXHAUSTED` the correct error type when all credentials fail due to quota limits? **Yes - see Section 2.6**
- [x] What was the original intent of returning `UNKNOWN`? **Likely placeholder or oversight**

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describes exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/test_gemini_client.py` | Modify | Update test expectation from `UNKNOWN` to `QUOTA_EXHAUSTED` |

### 2.2 Dependencies

*No new packages required.*

```toml
# No changes to pyproject.toml
```

### 2.3 Data Structures

*No new data structures - existing `GeminiErrorType` enum is correct.*

```python
# Existing enum (reference only)
class GeminiErrorType(Enum):
    QUOTA_EXHAUSTED = 'quota'
    RATE_LIMITED = 'rate'
    UNKNOWN = 'unknown'
    # ... other types
```

### 2.4 Function Signatures

*No changes to function signatures - this is a test expectation fix.*

### 2.5 Logic Flow (Pseudocode)

```
Current behavior (CORRECT):
1. Client attempts request
2. All credentials return 429 (quota exhausted)
3. Client exhausts credential list
4. Client raises GeminiError with type=QUOTA_EXHAUSTED

Test expectation (INCORRECT):
1. Test expects type=UNKNOWN

Fix:
1. Update test to expect type=QUOTA_EXHAUSTED
```

### 2.6 Technical Approach

* **Module:** `tests/test_gemini_client.py`
* **Pattern:** Test assertion correction
* **Key Decisions:** 
  - `QUOTA_EXHAUSTED` is semantically correct when all credentials fail due to quota limits
  - The error type should reflect the *reason* for failure, not the *mechanism* (exhausting credentials)
  - `UNKNOWN` should be reserved for truly unclassifiable errors

**Rationale:** When a client rotates through multiple credentials and each one fails with a quota error, the underlying cause is still quota exhaustion. The fact that rotation was attempted is an implementation detail. Users care about *why* the request failed, which is "quota exhausted across all available credentials."

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Error type when all credentials exhausted | `UNKNOWN`, `QUOTA_EXHAUSTED`, new `CREDENTIALS_EXHAUSTED` | `QUOTA_EXHAUSTED` | Reflects root cause; adding new type is unnecessary complexity |
| Fix location | Production code, test code | Test code | Production behavior is correct |

**Architectural Constraints:**
- Must maintain backward compatibility for error handling consumers
- Error type must accurately reflect the underlying cause for proper retry logic

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. `test_110_all_credentials_exhausted` passes
2. Test expects `GeminiErrorType.QUOTA_EXHAUSTED` instead of `UNKNOWN`
3. Production code remains unchanged (confirms current behavior is correct)

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Fix test expectation | Simple, production code is correct | None | **Selected** |
| Change code to return UNKNOWN | Matches original test | Loses semantic information about failure cause | Rejected |
| Add new CREDENTIALS_EXHAUSTED type | More specific | Over-engineering; consumers don't need this distinction | Rejected |

**Rationale:** The production code correctly identifies the root cause as quota exhaustion. The test expectation was likely written before the error classification logic was finalized, or was a placeholder.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | N/A - mock-based test |
| Format | N/A |
| Size | N/A |
| Refresh | N/A |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
Mock HTTP responses ──pytest──► Test assertions
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Mock 429 responses | Generated in test | Simulates quota exhaustion for all credentials |

### 5.4 Deployment Pipeline

*Standard test run - no special deployment considerations.*

## 6. Diagram

*N/A - Simple test assertion fix; no architectural changes.*

### 6.1 Mermaid Quality Gate

N/A - No diagram required for single-line test fix.

### 6.2 Diagram

N/A

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| N/A | Test-only change | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Incorrect error type could affect retry logic | `QUOTA_EXHAUSTED` is correct for quota-based failures | Addressed |

**Fail Mode:** N/A - Test change only

**Recovery Strategy:** N/A

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| N/A | N/A | Test-only change |

**Bottlenecks:** None

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| N/A | N/A | N/A | $0 |

**Cost Controls:** N/A

**Worst-Case Scenario:** N/A

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | N/A | Test code only |
| Third-Party Licenses | N/A | No new dependencies |
| Terms of Service | N/A | No external services |
| Data Retention | N/A | No data storage |
| Export Controls | N/A | No restricted algorithms |

**Data Classification:** N/A

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | All credentials exhausted returns QUOTA_EXHAUSTED | Auto | Mock all credentials returning 429 | `GeminiErrorType.QUOTA_EXHAUSTED` | Assertion passes |
| 020 | Test file runs without failures | Auto | `pytest tests/test_gemini_client.py -v` | All tests pass | Exit code 0 |

### 10.2 Test Commands

```bash
# Run the specific test
poetry run pytest tests/test_gemini_client.py::test_110_all_credentials_exhausted -v

# Run all Gemini client tests
poetry run pytest tests/test_gemini_client.py -v
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Other code depends on UNKNOWN for credentials exhausted | Medium | Low | Grep codebase for handling of UNKNOWN from this context |
| Related issues (#108, #109, #110) may have different root cause | Low | Medium | Investigate #108 first as potential root cause |

## 12. Definition of Done

### Code
- [ ] Test assertion updated from `UNKNOWN` to `QUOTA_EXHAUSTED`
- [ ] Code comment explaining why QUOTA_EXHAUSTED is correct

### Tests
- [ ] `test_110_all_credentials_exhausted` passes
- [ ] All other Gemini client tests still pass

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Awaiting initial review |

**Final Status:** PENDING