# 1121 - Fix: Inconsistent LLD Drafts Directory Path (uppercase vs lowercase)

<!-- Template Metadata
Last Updated: 2026-02-02
Updated By: Issue #117 fix
Update Reason: Moved Verification & Testing to Section 10 (was Section 11) to match 0702c review prompt and testing workflow expectations
Previous: Added sections based on 80 blocking issues from 164 governance verdicts (2026-02-01)
-->

## 1. Context & Goal
* **Issue:** #121
* **Objective:** Fix inconsistent directory casing for LLD drafts paths by replacing hardcoded `docs/LLDs/drafts` with the canonical constant from `config.py`.
* **Status:** Draft
* **Related Issues:** N/A

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [ ] Should we eliminate the drafts directory entirely since requirements workflow saves directly to `docs/lld/active/`? (Option B in issue)
- [ ] Are there any existing files in `docs/LLDs/` that need migration?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/lld/nodes.py` | Modify | Replace hardcoded path on line 957 with `LLD_DRAFTS_DIR` constant |
| `tests/test_lld_workflow.py` | Modify | Update test paths to use consistent lowercase `docs/llds/drafts` |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# pyproject.toml additions (if any)
# None - no new dependencies required
```

### 2.3 Data Structures

```python
# No new data structures required
# Using existing constant from config.py:
# LLD_DRAFTS_DIR = "docs/llds/drafts"  # Line 66 in config.py
```

### 2.4 Function Signatures

```python
# No new functions required
# Modification is to import and use existing constant
from agentos.core.config import LLD_DRAFTS_DIR
```

### 2.5 Logic Flow (Pseudocode)

```
1. In nodes.py line ~957:
   BEFORE: drafts_dir = repo_root / "docs" / "LLDs" / "drafts"
   AFTER:  drafts_dir = repo_root / LLD_DRAFTS_DIR

2. In tests:
   BEFORE: Assert paths contain "docs/LLDs/drafts" or hardcoded variations
   AFTER:  Assert paths use LLD_DRAFTS_DIR constant or "docs/llds/drafts"
```

### 2.6 Technical Approach

* **Module:** `agentos/workflows/lld/nodes.py`
* **Pattern:** Configuration centralization (single source of truth)
* **Key Decisions:** Use existing constant rather than creating new one; lowercase is the canonical form per existing `config.py`

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Path constant source | A: Use config.py constant, B: Define locally | A: Use config.py | Single source of truth, already exists |
| Casing convention | A: lowercase `llds`, B: UPPERCASE `LLDs` | A: lowercase | Matches existing config.py and audit.py conventions |
| Drafts directory existence | A: Keep drafts dir, B: Eliminate entirely | A: Keep | Separate concern; elimination should be its own issue if needed |

**Architectural Constraints:**
- Must use existing `LLD_DRAFTS_DIR` constant from `agentos/core/config.py`
- Cannot change the canonical path value (lowercase `docs/llds/drafts`)

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. No uppercase `LLDs` directory is created by any workflow
2. All LLD-related paths use consistent lowercase casing (`docs/llds/`)
3. `nodes.py` imports and uses `LLD_DRAFTS_DIR` constant instead of hardcoding
4. All tests pass with updated path expectations
5. Existing functionality for saving LLD drafts is preserved

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| A: Use existing `LLD_DRAFTS_DIR` constant | Minimal change, follows DRY, uses existing config | None significant | **Selected** |
| B: Eliminate drafts directory entirely | Cleaner architecture if not needed | Larger scope change, may break workflows, requires analysis | Rejected (separate issue) |
| C: Standardize on uppercase `LLDs` | Matches common acronym conventions | Requires changing config.py, audit.py, and more files | Rejected |

**Rationale:** Option A is the minimal, targeted fix that addresses the immediate inconsistency without scope creep. Option B may be valid but should be evaluated and implemented as a separate issue if desired.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Local filesystem paths |
| Format | Directory paths (string/Path objects) |
| Size | N/A - configuration constants |
| Refresh | N/A - static configuration |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
config.py constant ──import──► nodes.py ──Path()──► filesystem directory
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Mock repo root | Generated in test setup | Temporary directory |
| Expected path strings | Hardcoded in tests | Must match `LLD_DRAFTS_DIR` |

### 5.4 Deployment Pipeline

N/A - This is a code change, not data migration. Path change takes effect immediately upon deployment.

**If data source is external:** N/A

## 6. Diagram
*N/A - This is a simple constant substitution fix that doesn't require architectural diagrams.*

### 6.1 Mermaid Quality Gate

N/A - No diagram required for this fix.

### 6.2 Diagram

N/A

## 7. Security & Safety Considerations

*This section addresses security (10 patterns) and safety (9 patterns) concerns from governance feedback.*

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Path traversal | Using constant ensures no user-controlled path components | Addressed |
| Directory creation permissions | No change to permission model | N/A |

### 7.2 Safety

*Safety concerns focus on preventing data loss, ensuring fail-safe behavior, and protecting system integrity.*

| Concern | Mitigation | Status |
|---------|------------|--------|
| Existing files in `docs/LLDs/` | This fix doesn't migrate/delete existing files; manual cleanup may be needed | Documented |
| Draft file loss | Path change doesn't affect existing saved files | Addressed |

**Fail Mode:** Fail Closed - If path doesn't exist, `Path.mkdir(parents=True)` creates it safely

**Recovery Strategy:** If any files exist in old `docs/LLDs/drafts` location, they remain accessible and can be manually moved

## 8. Performance & Cost Considerations

*This section addresses performance and cost concerns (6 patterns) from governance feedback.*

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Latency | No change | Import adds negligible overhead |
| Memory | No change | Single constant import |
| API Calls | No change | No external calls |

**Bottlenecks:** None - this is a simple constant substitution

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| N/A | N/A | N/A | $0 |

**Cost Controls:**
- N/A - No external services or resources involved

**Worst-Case Scenario:** N/A - No cost implications

## 9. Legal & Compliance

*This section addresses legal concerns (8 patterns) from governance feedback.*

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | No data handling changes |
| Third-Party Licenses | No | No new dependencies |
| Terms of Service | No | No external services |
| Data Retention | No | No data storage changes |
| Export Controls | No | No restricted data/algorithms |

**Data Classification:** N/A - Code change only

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** All scenarios are automated. This fix is a simple constant substitution with clear pass/fail criteria.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | LLD draft saves to correct path | Auto | LLD workflow execution | File saved to `docs/llds/drafts/` | Path contains lowercase `llds` |
| 020 | No uppercase `LLDs` directory created | Auto | Full workflow run | Filesystem check | No `docs/LLDs/` directory exists |
| 030 | Import resolves correctly | Auto | `from agentos.core.config import LLD_DRAFTS_DIR` | No ImportError | Import succeeds |
| 040 | Path constant value is lowercase | Auto | Check `LLD_DRAFTS_DIR` value | `"docs/llds/drafts"` | String matches expected |
| 050 | Existing tests pass | Auto | Run test suite | All tests pass | Exit code 0 |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/test_lld_workflow.py -v

# Run specific path consistency tests
poetry run pytest tests/test_lld_workflow.py -v -k "path or directory"

# Verify no uppercase directories exist
find docs -type d -name "LLDs" 2>/dev/null && echo "FAIL: uppercase found" || echo "PASS: no uppercase"
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Existing files in `docs/LLDs/` orphaned | Low | Low | Document in release notes; files still accessible |
| Tests depend on uppercase path | Med | Med | Update tests in same PR |
| Other files hardcode `LLDs` path | Med | Low | Grep codebase for "LLDs" before merging |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD (Issue #121)
- [ ] No other hardcoded `LLDs` paths remain in codebase

### Tests
- [ ] All test scenarios pass
- [ ] `grep -r "LLDs" --include="*.py" .` returns no production code matches

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed if applicable

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
<!-- Note: This field is auto-updated to APPROVED by the workflow when finalized -->