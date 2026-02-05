# 324 - Bug: Diff-based Generation for Large File Modifications

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: Issue #324
Update Reason: Initial LLD creation for diff-based generation feature
-->

## 1. Context & Goal
* **Issue:** #324
* **Objective:** Implement diff-based code generation for large files to prevent token truncation during the implementation workflow
* **Status:** Draft
* **Related Issues:** #309 (retry on validation failure), #321 (API timeout)

### Open Questions

- [x] ~~What threshold for "large file" - lines vs bytes?~~ **Resolved: 500 lines OR 15KB, whichever is first**
- [x] ~~Should we detect truncation and auto-retry with diff mode?~~ **Resolved: Yes, detect via stop_reason and retry**

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/testing/nodes/implement_code.py` | Modify | Add diff-based prompt generation and change application logic |
| `tests/unit/test_implement_code_diff.py` | Add | Unit tests for diff parsing and application |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

*Issue #277: Before human or Gemini review, paths are verified programmatically.*

Mechanical validation automatically checks:
- All "Modify" files must exist in repository
- All "Delete" files must exist in repository
- All "Add" files must have existing parent directories
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists

**If validation fails, the LLD is BLOCKED before reaching review.**

### 2.2 Dependencies

*No new dependencies required.*

```toml
# pyproject.toml additions (if any)
# None - using standard library only
```

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation
class DiffChange(TypedDict):
    description: str       # Brief description of the change
    find_block: str        # Exact text to find in file
    replace_block: str     # Text to replace with

class DiffParseResult(TypedDict):
    success: bool          # Whether parsing succeeded
    changes: list[DiffChange]  # List of parsed changes
    error: str | None      # Error message if parsing failed
```

### 2.4 Function Signatures

```python
# Signatures only - implementation in source files
def is_large_file(content: str, line_threshold: int = 500, byte_threshold: int = 15000) -> bool:
    """Check if file content exceeds size thresholds for diff mode."""
    ...

def build_diff_prompt(
    lld_content: str,
    existing_content: str,
    test_content: str,
    file_path: str
) -> str:
    """Build prompt requesting structured diff output instead of full file."""
    ...

def parse_diff_response(response_text: str) -> DiffParseResult:
    """Parse Claude's diff response into structured changes."""
    ...

def apply_diff_changes(original_content: str, changes: list[DiffChange]) -> tuple[str, list[str]]:
    """Apply diff changes to original content. Returns (modified_content, errors)."""
    ...

def detect_truncation(message_response) -> bool:
    """Check if Claude's response was truncated due to max_tokens."""
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. Receive file change request (file_path, change_type, lld_content, test_content)
2. IF change_type == "Add" THEN
   - Use existing full-file generation (no change)
3. IF change_type == "Modify" THEN
   a. Read existing file content
   b. IF is_large_file(content) THEN
      - Build diff prompt with structured output format
      - Call Claude API
      - IF detect_truncation(response) THEN
         - Log error and retry with smaller context
      - Parse diff response into changes
      - Apply changes to original content
      - IF apply errors THEN
         - Log errors, return original with warning
   c. ELSE (small file)
      - Use existing full-file generation (no change)
4. Validate generated/modified content
5. Write to file
6. Return result
```

### 2.6 Technical Approach

* **Module:** `agentos/workflows/testing/nodes/implement_code.py`
* **Pattern:** Strategy pattern - select generation strategy based on file size
* **Key Decisions:** 
  - Use FIND/REPLACE blocks for unambiguous change specification
  - Apply changes in order from top to bottom
  - Require sufficient context in FIND blocks for unique matching

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Diff format | Unified diff, JSON patches, FIND/REPLACE blocks | FIND/REPLACE blocks | Most reliable for LLM to generate correctly; no line number dependencies |
| Threshold detection | Lines only, bytes only, both | Both (OR) | Files can be large due to long lines or many short lines |
| Change application | Regex matching, exact string match, fuzzy match | Exact string match first, whitespace-normalized fallback | Precision prevents wrong-location edits |
| Truncation handling | Silent fail, error + stop, retry with diff | Retry with diff mode | Self-healing improves success rate |

**Architectural Constraints:**
- Must integrate with existing `implement_code.py` workflow node
- Cannot change the existing API for small files (backward compatible)
- Must work with any file type (not just Python)

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. Files > 500 lines OR > 15KB use diff-based generation for "Modify" operations
2. Diff changes are parsed and applied correctly to the original file
3. FIND blocks must match exactly (or with whitespace normalization) in the original file
4. Changes are applied in order, with line offsets adjusted for previous changes
5. Validation still runs on the final merged result
6. Small files continue to use full-file generation (no regression)
7. "Add" files continue to use full-file generation regardless of size
8. Truncation is detected via `stop_reason` and causes retry (not silent failure)
9. Parse/apply errors are logged with details for debugging

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| FIND/REPLACE blocks | LLM-friendly, no line numbers, human readable | Requires unique matching | **Selected** |
| Unified diff format | Standard format, tools available | LLMs often get line numbers wrong | Rejected |
| JSON patch (RFC 6902) | Precise, structured | Too verbose, LLMs struggle with syntax | Rejected |
| Increase max_tokens | Simple fix | Just delays the problem, hits API limits | Rejected |
| Chunk large files | Handle any size | Complex, risk of breaking code at chunk boundaries | Rejected |

**Rationale:** FIND/REPLACE blocks are the most reliable format for LLMs to generate. They don't depend on line numbers (which LLMs frequently miscalculate), and the format is simple enough to parse reliably. The "sufficient context" requirement prevents ambiguous matches.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Local filesystem (existing source files) |
| Format | Plain text (Python, JS, etc.) |
| Size | Targeting files 500+ lines / 15KB+ |
| Refresh | Per-request (read fresh each time) |
| Copyright/License | N/A - user's own code |

### 5.2 Data Pipeline

```
Existing File ──read──► is_large_file() ──yes──► build_diff_prompt() ──Claude API──► parse_diff_response() ──► apply_diff_changes() ──write──► Modified File
                           │
                           └──no──► Existing full-file flow (unchanged)
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Large Python file (600 lines) | Generated | Synthetic but realistic class structure |
| Small Python file (50 lines) | Generated | Verify small files bypass diff mode |
| Sample diff response | Hardcoded | Valid FIND/REPLACE format |
| Malformed diff response | Hardcoded | Missing sections, bad format |
| Ambiguous FIND block | Hardcoded | Tests duplicate detection |

### 5.4 Deployment Pipeline

No data deployment required - this is code logic only.

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [x] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Auto-Inspection Results:**
```
- Touching elements: [x] None
- Hidden lines: [x] None
- Label readability: [x] Pass
- Flow clarity: [x] Clear
```

### 6.2 Diagram

```mermaid
flowchart TD
    A[Receive Modify Request] --> B{File Size Check}
    B -->|Small file| C[Full-File Generation]
    B -->|Large file| D[Build Diff Prompt]
    D --> E[Call Claude API]
    E --> F{Truncated?}
    F -->|Yes| G[Log Warning & Retry]
    G --> D
    F -->|No| H[Parse Diff Response]
    H --> I{Parse OK?}
    I -->|No| J[Log Error & Fallback]
    I -->|Yes| K[Apply Changes]
    K --> L{Apply OK?}
    L -->|No| M[Log Errors & Return Original]
    L -->|Yes| N[Write Modified File]
    C --> N
    J --> C
    M --> O[Return with Warnings]
    N --> P[Validate & Return]
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Code injection via diff | Changes only applied to specified file path | Addressed |
| Path traversal | File path validated by existing workflow | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Data loss on bad apply | Original content preserved until successful apply | Addressed |
| Partial changes applied | All-or-nothing: either all changes apply or none | Addressed |
| Infinite retry loop | Max retry count (3) before falling back to full-file | Addressed |
| Wrong location edit | Require unique FIND match; fail if ambiguous | Addressed |

**Fail Mode:** Fail Closed - If diff application fails, preserve original file and report error

**Recovery Strategy:** On failure, log detailed error with original content, FIND block, and all match locations. User can manually inspect and retry.

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Parse time | < 100ms | Simple regex-based parsing |
| Apply time | < 100ms | String operations only |
| API calls | Same as before (1 per file) | No additional calls unless truncation retry |

**Bottlenecks:** None expected - diff parsing is fast string operations

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Claude API (input) | ~$3/MTok | Reduced (no full file in response) | Lower than before |
| Claude API (output) | ~$15/MTok | Significantly reduced | **Savings** |

**Cost Controls:**
- [x] Diff mode reduces output tokens by ~80% for large files
- [x] Truncation retry limited to 3 attempts

**Worst-Case Scenario:** If all files are large, diff mode is always used - this is actually optimal for token usage.

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Only processes user's own source code |
| Third-Party Licenses | No | No new dependencies |
| Terms of Service | No | Standard Claude API usage |
| Data Retention | No | No data stored beyond request |
| Export Controls | N/A | N/A |

**Data Classification:** Internal (user's source code, processed locally)

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

**TDD Requirement:** Tests MUST be written and failing BEFORE implementation begins.

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | test_is_large_file_by_lines | Returns True for 501+ line file | RED |
| T020 | test_is_large_file_by_bytes | Returns True for 15001+ byte file | RED |
| T030 | test_is_large_file_small | Returns False for small file | RED |
| T040 | test_parse_diff_valid | Parses valid FIND/REPLACE blocks | RED |
| T050 | test_parse_diff_multiple | Parses multiple changes | RED |
| T060 | test_parse_diff_malformed | Returns error for bad format | RED |
| T070 | test_apply_single_change | Applies one change correctly | RED |
| T080 | test_apply_multiple_changes | Applies ordered changes | RED |
| T090 | test_apply_ambiguous_find | Errors on duplicate matches | RED |
| T100 | test_apply_no_match | Errors when FIND not found | RED |
| T110 | test_detect_truncation | Detects max_length stop reason | RED |
| T120 | test_build_diff_prompt | Includes required format instructions | RED |
| T130 | test_whitespace_normalization | Matches with different indentation | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_implement_code_diff.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Large file by lines | Auto | 501 line file | `is_large_file() == True` | Threshold correctly detected |
| 020 | Large file by bytes | Auto | 15001 byte file | `is_large_file() == True` | Threshold correctly detected |
| 030 | Small file bypass | Auto | 100 line, 3KB file | `is_large_file() == False` | Below both thresholds |
| 040 | Parse valid diff | Auto | Valid FIND/REPLACE text | List of DiffChange | All changes extracted |
| 050 | Parse multiple changes | Auto | 3 FIND/REPLACE blocks | 3 DiffChange items | Order preserved |
| 060 | Parse malformed diff | Auto | Missing REPLACE section | `success=False, error set` | Graceful error handling |
| 070 | Apply single change | Auto | Original + 1 change | Modified content | Change at correct location |
| 080 | Apply multiple changes | Auto | Original + 3 changes | Modified content | All changes, order preserved |
| 090 | Ambiguous FIND error | Auto | FIND matches 2 locations | Error with locations | No partial application |
| 100 | FIND not found error | Auto | FIND doesn't exist | Error with FIND block | Clear error message |
| 110 | Truncation detection | Auto | Response with `stop_reason='max_tokens'` | `True` | Truncation flagged |
| 120 | Diff prompt format | Auto | File content + LLD | Prompt with FIND/REPLACE instructions | Format documented |
| 130 | Whitespace fallback | Auto | FIND with different indent | Match found | Normalization works |

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/unit/test_implement_code_diff.py -v

# Run with coverage
poetry run pytest tests/unit/test_implement_code_diff.py -v --cov=agentos/workflows/testing/nodes/implement_code --cov-report=term-missing

# Run specific test
poetry run pytest tests/unit/test_implement_code_diff.py::test_apply_multiple_changes -v
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| FIND block not unique in file | High | Medium | Require sufficient context; error on ambiguous match |
| LLM generates malformed diff | Medium | Medium | Robust parsing with clear error messages; fallback to full-file |
| Whitespace differences prevent match | Medium | High | Whitespace-normalized fallback matching |
| Changes conflict with each other | High | Low | Apply in order; adjusted offsets; validate final result |
| Edge case: FIND spans change boundary | Medium | Low | Document limitation; user can split FIND blocks |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD (#324)
- [ ] Functions documented with docstrings

### Tests
- [ ] All 13 test scenarios pass
- [ ] Test coverage ≥95% for new code
- [ ] Integration test with real large file

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Inline comments explain diff format choice

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

*Issue #277: Cross-references are verified programmatically.*

Mechanical validation automatically checks:
- Every file mentioned in this section must appear in Section 2.1
- Every risk mitigation in Section 11 should have a corresponding function in Section 2.4 (warning if not)

**Files in Definition of Done:**
- `agentos/workflows/testing/nodes/implement_code.py` ✓ (in 2.1)
- `tests/unit/test_implement_code_diff.py` ✓ (in 2.1)

**Risk → Function mapping:**
- "Require sufficient context; error on ambiguous match" → `apply_diff_changes()` ✓
- "Robust parsing with clear error messages" → `parse_diff_response()` ✓
- "Whitespace-normalized fallback matching" → `apply_diff_changes()` ✓
- "Validate final result" → existing validation flow ✓

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Awaiting review |

**Final Status:** PENDING