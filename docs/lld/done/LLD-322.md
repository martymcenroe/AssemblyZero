# 322 - Bug: Mechanical validation silently skips path checks when target_repo invalid

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #117 fix
Update Reason: Moved Verification & Testing to Section 10 (was Section 11) to match 0702c review prompt and testing workflow expectations
Previous: Added sections based on 80 blocking issues from 164 governance verdicts (2026-02-01)
-->

## 1. Context & Goal
* **Issue:** #322
* **Objective:** Fix silent path validation skip in mechanical validation when target_repo is invalid or missing, ensuring validation failures are surfaced rather than silently bypassed.
* **Status:** Approved (gemini-3-pro-preview, 2026-02-04)
* **Related Issues:** #277 (Mechanical validation framework), #188 (Enforce file paths from LLD)

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Should this be a blocking error or a warning? **Decision: Blocking error (Option A) - silent failures defeat the purpose of validation**
- [ ] Should we also validate target_repo existence earlier in `create_initial_state()`?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | Modify | Add explicit check for invalid/missing repo_root, returning blocking error instead of silent skip |
| `tests/unit/test_validate_mechanical.py` | Modify | Add test cases for missing/invalid target_repo scenarios |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

*Issue #277: Before human or Gemini review, paths are verified programmatically.*

Mechanical validation automatically checks:
- All "Modify" files must exist in repository
- All "Delete" files must exist in repository
- All "Add" files must have existing parent directories
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists

**If validation fails, the LLD is BLOCKED before reaching review.**

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# pyproject.toml additions (if any)
# None - using existing dependencies
```

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation
class ValidationResult(TypedDict):
    validation_errors: list[str]  # List of blocking error messages
    validation_warnings: list[ValidationError]  # List of warning-level issues
    lld_status: str  # "BLOCKED" | "PASSED" | "WARNINGS"
    path_validation_skipped: bool  # New flag to track if paths were validated
```

### 2.4 Function Signatures

```python
# Signatures only - implementation in source files
def validate_repo_root(repo_root: Path | None) -> tuple[bool, str | None]:
    """
    Validate that repo_root is valid and exists.
    
    Returns:
        tuple of (is_valid, error_message)
        - (True, None) if valid
        - (False, error_message) if invalid
    """
    ...

def validate_file_paths_with_repo_check(
    files: list[FileChange],
    repo_root: Path | None
) -> tuple[list[ValidationError], bool]:
    """
    Validate file paths against repo, with explicit repo validation.
    
    Returns:
        tuple of (errors, was_validated)
        - errors: List of validation errors (may include blocking repo error)
        - was_validated: Whether path validation actually ran
    """
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. Receive repo_root from state
2. Validate repo_root existence:
   IF repo_root is None OR repo_root is empty string THEN
     - Return blocking error: "Cannot validate file paths: target_repo not specified"
     - Set lld_status = "BLOCKED"
   ELSE IF repo_root does not exist on filesystem THEN
     - Return blocking error: "Cannot validate file paths: target_repo '{path}' does not exist"
     - Set lld_status = "BLOCKED"
   END IF
3. Proceed with normal path validation
4. Return validation results
```

### 2.6 Technical Approach

* **Module:** `agentos/workflows/requirements/nodes/validate_mechanical.py`
* **Pattern:** Fail-fast validation with explicit error reporting
* **Key Decisions:** 
  - Chose blocking error over warning because silent validation bypass defeats security purpose
  - Added descriptive error messages to help users diagnose misconfiguration
  - Validation happens early to avoid wasted processing

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design. This section addresses the most common category of governance feedback (23 patterns).*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Error severity | Warning (Option B), Blocking Error (Option A) | Blocking Error | Silent bypasses defeat validation purpose; hallucinated paths are high-impact |
| Validation location | Only in validate_mechanical.py, Also in create_initial_state | Only validate_mechanical.py | Keep changes minimal; upstream validation is separate concern |
| Error message style | Generic, Specific with path | Specific with path | Helps users diagnose which repo path is problematic |

**Architectural Constraints:**
- Must integrate with existing ValidationError/ValidationSeverity system
- Cannot change the function signature of `validate_file_paths()` (would break callers)
- Must maintain backward compatibility for valid repo_root cases

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. When `target_repo` is None or empty, validation returns a blocking error with descriptive message
2. When `target_repo` path does not exist on filesystem, validation returns a blocking error
3. Error messages clearly indicate the problem and affected path
4. LLD status is set to "BLOCKED" when repo validation fails
5. Existing behavior unchanged when `target_repo` is valid and exists
6. Test coverage includes all repo validation scenarios

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Option A: Blocking error (strict) | Prevents hallucinated paths; clear failure mode; matches validation intent | May break workflows with optional path validation | **Selected** |
| Option B: Warning only | Non-breaking; gentle degradation | Defeats purpose of validation; users may miss warning | Rejected |
| Option C: Configurable strictness | Flexible; satisfies both use cases | Added complexity; configuration sprawl | Rejected |

**Rationale:** The purpose of #277 mechanical validation is to catch path errors before they reach implementation. A silent bypass completely defeats this purpose and allows hallucinated paths like `src/thing.py` to slip through. Users who genuinely don't have a target repo can explicitly configure validation to skip, rather than having it silently fail.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Filesystem (target_repo path) |
| Format | Directory path string |
| Size | N/A |
| Refresh | Checked at validation time |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
State.target_repo ──read──► Path validation ──check──► Filesystem existence ──result──► ValidationResult
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Temporary directory (valid repo) | Generated via pytest tmp_path | Created fresh per test |
| Non-existent path | Hardcoded string | `/nonexistent/repo/path/12345` |
| Empty string path | Hardcoded | `""` |
| None value | Python None | Direct None assignment |

### 5.4 Deployment Pipeline

N/A - This is validation logic, no data deployment required.

**If data source is external:** N/A

## 6. Diagram
*N/A - Simple conditional logic flow, diagram would not add clarity beyond pseudocode in 2.5*

### 6.1 Mermaid Quality Gate

N/A - No diagram required for this change.

### 6.2 Diagram

N/A

## 7. Security & Safety Considerations

*This section addresses security (10 patterns) and safety (9 patterns) concerns from governance feedback.*

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Path traversal in error message | Only display the provided path, don't resolve or expand | Addressed |
| Information disclosure | Error messages only reveal path user provided, not system internals | Addressed |

### 7.2 Safety

*Safety concerns focus on preventing data loss, ensuring fail-safe behavior, and protecting system integrity.*

| Concern | Mitigation | Status |
|---------|------------|--------|
| Hallucinated paths reaching implementation | Blocking validation prevents progress with invalid paths | Addressed |
| False positives blocking valid LLDs | Only block on clearly invalid states (None, empty, non-existent) | Addressed |
| Breaking existing workflows | Only changes behavior for previously-silent-failure cases | Addressed |

**Fail Mode:** Fail Closed - If we cannot validate paths, we block rather than allow potentially invalid paths through.

**Recovery Strategy:** User must provide valid target_repo path. Error message clearly indicates what's wrong.

## 8. Performance & Cost Considerations

*This section addresses performance and cost concerns (6 patterns) from governance feedback.*

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Latency | < 1ms added | Single `Path.exists()` call |
| Memory | Negligible | No new allocations beyond error message string |
| API Calls | 0 | Filesystem check only |

**Bottlenecks:** None - this adds a single filesystem existence check.

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Compute | N/A | Negligible | $0 |

**Cost Controls:**
- N/A - No external costs

**Worst-Case Scenario:** N/A - Local filesystem check only

## 9. Legal & Compliance

*This section addresses legal concerns (8 patterns) from governance feedback.*

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | N/A |
| Third-Party Licenses | No | N/A |
| Terms of Service | No | N/A |
| Data Retention | No | N/A |
| Export Controls | No | N/A |

**Data Classification:** Internal

**Compliance Checklist:**
- [x] No PII stored without consent - N/A
- [x] All third-party licenses compatible with project license - N/A
- [x] External API usage compliant with provider ToS - N/A
- [x] Data retention policy documented - N/A

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated (e.g., visual inspection, hardware interaction). Every scenario marked "Manual" requires justification.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | test_validation_blocks_when_repo_root_none | Returns blocking error, status BLOCKED | RED |
| T020 | test_validation_blocks_when_repo_root_empty | Returns blocking error, status BLOCKED | RED |
| T030 | test_validation_blocks_when_repo_root_nonexistent | Returns blocking error with path, status BLOCKED | RED |
| T040 | test_validation_proceeds_when_repo_root_valid | Normal path validation runs, no repo errors | RED |
| T050 | test_error_message_includes_path | Error message contains the invalid path for debugging | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_validate_mechanical.py`

*Note: Update Status from RED to GREEN as implementation progresses. All tests should be RED at LLD review time.*

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | repo_root is None | Auto | `repo_root=None` | `{"validation_errors": ["...target_repo not specified..."], "lld_status": "BLOCKED"}` | Error list non-empty, status BLOCKED |
| 020 | repo_root is empty string | Auto | `repo_root=Path("")` | `{"validation_errors": ["...target_repo not specified..."], "lld_status": "BLOCKED"}` | Error list non-empty, status BLOCKED |
| 030 | repo_root does not exist | Auto | `repo_root=Path("/nonexistent/path")` | `{"validation_errors": ["...does not exist..."], "lld_status": "BLOCKED"}` | Error contains path, status BLOCKED |
| 040 | repo_root valid and exists | Auto | `repo_root=tmp_path` (pytest fixture) | Normal validation proceeds | No repo-related errors, path validation runs |
| 050 | Error message diagnostic quality | Auto | `repo_root=Path("/specific/path")` | Error message contains `/specific/path` | Substring match on error |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

**Type values:**
- `Auto` - Fully automated, runs in CI (pytest, playwright, etc.)

### 10.2 Test Commands

```bash
# Run all automated tests for this module
poetry run pytest tests/unit/test_validate_mechanical.py -v

# Run only the new repo validation tests
poetry run pytest tests/unit/test_validate_mechanical.py -v -k "repo_root"

# Run with coverage
poetry run pytest tests/unit/test_validate_mechanical.py -v --cov=agentos/workflows/requirements/nodes/validate_mechanical --cov-report=term-missing
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Breaking existing workflows that relied on silent skip | Med | Low | Behavior only changes for invalid states; valid repos unaffected |
| Users confused by new blocking behavior | Low | Med | Clear error messages explain problem and solution |
| Edge case: valid path becomes invalid during validation | Low | Low | Check happens at validation time; subsequent checks would catch |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD

### Tests
- [ ] All test scenarios pass
- [ ] Test coverage meets threshold (≥95%)

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed if applicable

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

*Issue #277: Cross-references are verified programmatically.*

Mechanical validation automatically checks:
- Every file mentioned in this section must appear in Section 2.1
- Every risk mitigation in Section 11 should have a corresponding function in Section 2.4 (warning if not)

**Files in Definition of Done:**
- `agentos/workflows/requirements/nodes/validate_mechanical.py` ✓ (in 2.1)
- `tests/unit/test_validate_mechanical.py` ✓ (in 2.1)

**If files are missing from Section 2.1, the LLD is BLOCKED.**

---

## Reviewer Suggestions

*Non-blocking recommendations from the reviewer.*

- **Documentation:** Ensure the error message for "empty string" specifically mentions that the configuration might be missing, as distinct from a "None" value, to help debugging.

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

<!-- Note: Timestamps are auto-generated by the workflow. Do not fill in manually. -->

### Review Summary

<!-- Note: This table is auto-populated by the workflow with actual review dates. -->

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | - |

**Final Status:** APPROVED
<!-- Note: This field is auto-updated to APPROVED by the workflow when finalized -->