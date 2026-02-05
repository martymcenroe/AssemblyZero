# 297 - Bug: test_claude_dependency_uses_skipif failing

## 1. Context & Goal
* **Issue:** #297
* **Objective:** Fix failing meta-test that validates claude CLI skipif decorator usage
* **Status:** Approved (gemini-3-pro-preview, 2026-02-04)
* **Related Issues:** None identified

### Open Questions
*None - root cause identified through investigation.*

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/unit/test_explicit_skips.py` | Modify | Update meta-test to handle new test patterns or fix detection logic |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

*Issue #277: Before human or Gemini review, paths are verified programmatically.*

Mechanical validation automatically checks:
- All "Modify" files must exist in repository ✓
- All "Delete" files must exist in repository N/A
- All "Add" files must have existing parent directories N/A
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists ✓

**If validation fails, the LLD is BLOCKED before reaching review.**

### 2.2 Dependencies

*No new dependencies required.*

```toml
# pyproject.toml additions (if any)
# None
```

### 2.3 Data Structures

```python
# No new data structures - this is a test fix
```

### 2.4 Function Signatures

```python
# Existing test function to be modified
def test_claude_dependency_uses_skipif(self) -> None:
    """Verify tests depending on claude CLI use proper skipif decorators."""
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. Scan test files for patterns indicating claude CLI dependency
2. For each file with claude dependency:
   a. Parse the file's AST or content
   b. Check for @pytest.mark.skipif decorator with shutil.which('claude')
   c. IF skipif found THEN mark as compliant
   d. ELSE collect as violation
3. IF violations exist THEN fail with descriptive message
4. ELSE pass
```

### 2.6 Technical Approach

* **Module:** `tests/unit/test_explicit_skips.py`
* **Pattern:** Meta-test / Test infrastructure validation
* **Key Decisions:** 
  - Need to identify why current detection is failing
  - Options: (a) tests are missing decorators, or (b) detection pattern is too strict/incorrect

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Fix approach | Fix tests missing decorators vs. fix detection logic | Investigate first | Need to determine root cause before deciding |
| Detection method | Regex vs. AST parsing | Keep existing | Maintain consistency unless existing approach is fundamentally broken |

**Architectural Constraints:**
- Must not weaken the meta-test's enforcement (defeats the purpose)
- Must remain compatible with existing test patterns

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. `test_claude_dependency_uses_skipif` passes
2. All tests that depend on claude CLI have proper `@pytest.mark.skipif(shutil.which('claude') is None, ...)` decorators
3. Full test suite passes

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Fix tests missing decorators | Maintains strict enforcement | May require changes to multiple test files | Selected if root cause is missing decorators |
| Relax detection pattern | Quick fix | Could allow non-compliant tests through | Rejected unless current pattern is incorrect |
| Delete meta-test | Fastest fix | Removes enforcement entirely, bad practice | **Rejected** |

**Rationale:** Need to investigate root cause first. The meta-test exists for good reason - ensuring tests skip gracefully when claude CLI isn't available.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Test files in repository |
| Format | Python source files |
| Size | N/A - scanning existing codebase |
| Refresh | N/A - static analysis |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
Test files ──AST/Regex scan──► Violations list ──assertion──► Pass/Fail
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| N/A | N/A | This is fixing a meta-test, no new fixtures needed |

### 5.4 Deployment Pipeline

N/A - test infrastructure fix

## 6. Diagram

### 6.1 Mermaid Quality Gate

*N/A - Simple test fix doesn't require architectural diagram.*

### 6.2 Diagram

N/A - The logic is straightforward enough to describe in text.

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| N/A - test infrastructure | No production code affected | N/A |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Breaking other tests | Run full test suite after fix | Pending |
| Weakening enforcement | Ensure fix maintains or strengthens validation | Pending |

**Fail Mode:** Fail Closed - meta-test should fail if unsure, not pass silently

**Recovery Strategy:** If fix causes issues, revert commit

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Test runtime | < 5s | File scanning is already fast |

**Bottlenecks:** None - meta-tests are lightweight

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| CI minutes | N/A | Negligible change | $0 |

**Cost Controls:** N/A

**Worst-Case Scenario:** N/A - local test infrastructure

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | N/A |
| Third-Party Licenses | No | N/A |
| Terms of Service | No | N/A |
| Data Retention | No | N/A |
| Export Controls | No | N/A |

**Data Classification:** N/A

**Compliance Checklist:** N/A - internal test infrastructure

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Run failing meta-test | Currently fails, should pass after fix | RED |
| T020 | Full test suite | All tests pass including meta-test | RED |
| T030 | Verify skipif decorators present | All claude-dependent tests have proper decorators | RED |

**Coverage Target:** N/A - fixing existing test

**TDD Checklist:**
- [x] Test already exists (meta-test)
- [x] Test currently RED (failing)
- [x] Test ID matches scenario
- [x] Test file: `tests/unit/test_explicit_skips.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Meta-test passes | Auto | Run pytest on test_explicit_skips.py | No assertion errors | Test passes |
| 020 | Full suite passes | Auto | Run full pytest suite | All tests pass | Exit code 0 |
| 030 | Claude CLI tests skip gracefully | Auto | Run tests without claude installed | Tests skip, not fail | Skipped status |

### 10.2 Test Commands

```bash
# Run the specific failing test
poetry run pytest tests/unit/test_explicit_skips.py::TestSkipifDecoratorUsage::test_claude_dependency_uses_skipif -v

# Run all explicit skip meta-tests
poetry run pytest tests/unit/test_explicit_skips.py -v

# Run full test suite to verify no regressions
poetry run pytest -v
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Fix causes other tests to fail | Med | Low | Run full test suite before merging |
| Root cause not obvious | Low | Med | Examine git history for recent changes |
| Multiple tests need decorator updates | Low | Med | Update all affected tests systematically |

## 12. Definition of Done

### Code
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Code comments reference this LLD (#297)

### Tests
- [ ] `test_claude_dependency_uses_skipif` passes
- [ ] Full test suite passes

### Documentation
- [ ] LLD updated with root cause findings
- [ ] Implementation Report (0103) completed

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

*Issue #277: Cross-references are verified programmatically.*

- `tests/unit/test_explicit_skips.py` - listed in Section 2.1 ✓

---

## Reviewer Suggestions

*Non-blocking recommendations from the reviewer.*

- Ensure the fix handles both `import shutil` + `shutil.which` AND `from shutil import which` + `which` patterns if possible, to make the meta-test robust against refactoring.

## Appendix: Investigation Notes

### Likely Root Causes to Check

1. **New test added without skipif decorator** - A recent test that uses claude CLI was added without the required decorator
2. **Pattern change in existing tests** - Existing tests modified in a way that broke detection
3. **Detection regex too strict** - The meta-test's pattern matching is failing on valid decorators
4. **Import pattern change** - Tests using `from shutil import which` instead of `shutil.which`

### Investigation Commands

```bash
# Find tests that reference 'claude' CLI
grep -r "claude" tests/ --include="*.py" | grep -v "__pycache__"

# Check the meta-test's detection logic
cat tests/unit/test_explicit_skips.py | grep -A 50 "test_claude_dependency_uses_skipif"

# Check recent changes to test files
git log --oneline -20 -- tests/
```

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| 1 | 2026-02-04 | APPROVED | `gemini-3-pro-preview` |
| - | - | - | Pending initial review |

**Final Status:** APPROVED