# 1272 - Bug: Implementation Node Claude Gives Summary Instead of Code

<!-- Template Metadata
Last Updated: 2025-01-13
Updated By: Issue #272 implementation
Update Reason: Initial LLD creation for file-by-file implementation pattern
-->

## 1. Context & Goal
* **Issue:** #272
* **Objective:** Prevent Claude from producing summary lists instead of code by switching from batch prompting to file-by-file prompting with mechanical validation and hard failure.
* **Status:** Draft
* **Related Issues:** #225 (failed implementation that exposed the bug)

### Open Questions

- [x] Should we support modification of existing files or only new file creation? → Support both
- [x] What is the minimum line threshold for non-trivial files? → 5 lines
- [x] Should syntax validation be language-specific or Python-only initially? → Python-only initially, extensible

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/nodes/implement_code.py` | Modify | Replace single-shot batch prompting with file-by-file loop |
| `src/nodes/implement_code.py` | Modify | Add LLD file list parser |
| `src/nodes/implement_code.py` | Modify | Add context accumulation logic |
| `src/nodes/implement_code.py` | Modify | Add mechanical validation gate |
| `src/nodes/implement_code.py` | Modify | Add hard failure mode (no retries) |
| `src/models/state.py` | Modify | Add `completed_files` field to track accumulated context |

### 2.2 Dependencies

*No new packages required. Uses existing standard library modules.*

```toml
# No additions - uses ast (stdlib), re (stdlib)
```

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation
class FileSpec(TypedDict):
    filepath: str          # Relative path from repo root
    change_type: str       # "Add" | "Modify" | "Delete"
    description: str       # Brief description from LLD

class CompletedFile(TypedDict):
    filepath: str          # Path that was implemented
    content: str           # Full file contents
    
class ValidationResult(TypedDict):
    valid: bool            # Whether validation passed
    error: str | None      # Error message if failed
    details: dict          # Additional validation metadata

# State extension
class ImplementationState(TypedDict):
    # ... existing fields ...
    completed_files: list[CompletedFile]  # Accumulating context
    current_file_index: int               # Progress tracker
```

### 2.4 Function Signatures

```python
# Signatures only - implementation in source files

def parse_lld_files_section(lld_content: str) -> list[FileSpec]:
    """Extract ordered list of files from LLD Section 2.1."""
    ...

def build_single_file_prompt(
    filepath: str,
    lld_content: str,
    completed_files: list[CompletedFile]
) -> str:
    """Build prompt for a single file with accumulated context."""
    ...

def extract_code_block(response: str) -> str | None:
    """Extract code block content. Returns None if no valid code found."""
    ...

def validate_code_response(
    code: str,
    filepath: str
) -> ValidationResult:
    """Mechanically validate code output. No LLM judgment."""
    ...

def fail_hard(
    filepath: str,
    response: str,
    validation_result: ValidationResult
) -> NoReturn:
    """Print error details and exit immediately. No retries."""
    ...

def implement_file_by_file(
    lld_content: str,
    state: ImplementationState
) -> ImplementationState:
    """Main loop: iterate through files with accumulating context."""
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. Parse LLD Section 2.1 to extract files_to_create: list[FileSpec]

2. Initialize completed_files = []

3. FOR EACH file_spec IN files_to_create:
   
   a. Build prompt with:
      - Full LLD content
      - All completed_files (accumulated context)
      - Instruction: "Write complete contents of {filepath}. Output ONLY the file."
   
   b. Send to Claude, receive response
   
   c. Extract code block from response:
      - IF no code block found → FAIL HARD
   
   d. Validate code mechanically:
      - Has content (not empty)
      - Meets minimum line count (>5 for non-trivial)
      - Parses without syntax error (Python: ast.parse)
      - IF ANY validation fails → FAIL HARD
   
   e. Add to completed_files for next iteration
   
   f. Write file to disk

4. Return updated state with all completed_files
```

### 2.6 Technical Approach

* **Module:** `src/nodes/implement_code.py`
* **Pattern:** Sequential pipeline with hard failure semantics
* **Key Decisions:** 
  - File-by-file iteration prevents "summary" responses
  - Accumulated context ensures cross-file consistency
  - Mechanical validation removes LLM judgment from quality gate
  - Hard failure forces fix at source, not workarounds

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Prompting strategy | Batch all files, File-by-file | File-by-file | Prevents summary responses, enables context accumulation |
| Validation approach | LLM-based review, Mechanical checks | Mechanical | LLMs ignore instructions unpredictably; mechanical is deterministic |
| Failure handling | Retry with backoff, Graceful degradation, Hard failure | Hard failure | Retries waste tokens; partial output useless; forces root cause fix |
| Context accumulation | None, File contents only, File + path | File + path | Enables accurate imports and references across files |

**Architectural Constraints:**
- Must integrate with existing LangGraph node structure
- Cannot change LLD format (parse existing Section 2.1 format)
- Exit code must be non-zero on failure for CI integration

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. Implementation node iterates file-by-file through LLD's file list
2. Each file prompt includes full LLD + all previously completed files as context
3. Each response is mechanically validated (code block exists, not empty, parses)
4. First validation failure kills workflow immediately with clear error
5. No retries - one shot per file
6. Error message clearly identifies which file failed and why
7. Previously-failing #225 scenario produces code (not summary)

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Prompt engineering ("output code not summary") | No code changes | Unreliable; LLMs ignore instructions | **Rejected** |
| Retry with exponential backoff | May eventually succeed | Wastes tokens; doesn't fix root cause | **Rejected** |
| Parse summary and generate skeleton code | Recovers something | Skeleton useless; masks real failure | **Rejected** |
| File-by-file with mechanical validation | Structural control; deterministic | More API calls; longer runtime | **Selected** |

**Rationale:** Structural control (what Claude *can* do) beats instruction control (what we *tell* Claude to do). The extra API calls are worth the reliability.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | LLD document (Section 2.1) |
| Format | Markdown table |
| Size | 5-20 file entries typically |
| Refresh | Per-implementation |
| Copyright/License | N/A - internal documents |

### 5.2 Data Pipeline

```
LLD Markdown ──parse_lld_files_section──► list[FileSpec] ──iterate──► Claude API ──validate──► Disk
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Valid LLD with file table | Generated | Synthetic test data |
| LLD with edge case formatting | Generated | Tests parser robustness |
| Mock Claude responses (valid) | Generated | Proper code block output |
| Mock Claude responses (summary) | From #225 | Real failure case |
| Mock Claude responses (empty) | Generated | Edge case |

### 5.4 Deployment Pipeline

Local development → PR → CI tests → Merge to main

No external data dependencies.

## 6. Diagram

### 6.1 Mermaid Quality Gate

- [x] **Simplicity:** Components minimal
- [x] **No touching:** Visual separation maintained
- [x] **No hidden lines:** All arrows visible
- [x] **Readable:** Labels clear
- [ ] **Auto-inspected:** Pending agent render

**Auto-Inspection Results:**
```
- Touching elements: [ ] None / [ ] Found: ___
- Hidden lines: [ ] None / [ ] Found: ___
- Label readability: [ ] Pass / [ ] Issue: ___
- Flow clarity: [ ] Clear / [ ] Issue: ___
```

### 6.2 Diagram

```mermaid
sequenceDiagram
    participant N4 as N4: Implementation Node
    participant Parser as LLD Parser
    participant Builder as Prompt Builder
    participant Claude as Claude API
    participant Validator as Mechanical Validator
    participant Disk as File System

    N4->>Parser: Parse LLD Section 2.1
    Parser-->>N4: files_to_create[]

    loop For each file
        N4->>Builder: Build prompt (LLD + completed_files)
        Builder-->>N4: Single-file prompt
        N4->>Claude: Request file contents
        Claude-->>N4: Response
        
        N4->>Validator: extract_code_block(response)
        alt No code block
            Validator-->>N4: None
            N4->>N4: FAIL HARD - Exit
        else Code extracted
            Validator-->>N4: code_content
        end
        
        N4->>Validator: validate_code_response(code)
        alt Validation failed
            Validator-->>N4: {valid: false, error: "..."}
            N4->>N4: FAIL HARD - Exit
        else Validation passed
            Validator-->>N4: {valid: true}
        end
        
        N4->>Disk: Write file
        N4->>N4: completed_files.append(file)
    end
    
    N4-->>N4: Return success state
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Code injection via LLD | LLD is internal; file paths validated | Addressed |
| Path traversal in filepath | Validate paths stay within repo root | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Partial file writes on failure | Write to temp, atomic move on success | Addressed |
| Overwriting existing files unexpectedly | Check change_type; confirm Modify vs Add | Addressed |
| Runaway loop on malformed LLD | Limit max files per implementation (e.g., 50) | Addressed |

**Fail Mode:** Fail Closed - Any validation failure stops entire workflow

**Recovery Strategy:** User reviews error output, fixes LLD or underlying issue, re-runs workflow

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Latency per file | < 30s | Single focused prompt |
| Total latency | < 10 min for 20 files | Sequential processing |
| Memory | < 256MB | Stream responses, don't buffer all |

**Bottlenecks:** Sequential API calls (intentional for context accumulation)

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Claude API (input) | $3/1M tokens | ~10K tokens/file × 20 files × 50 runs | $30 |
| Claude API (output) | $15/1M tokens | ~2K tokens/file × 20 files × 50 runs | $30 |

**Cost Controls:**
- [x] Hard failure prevents runaway retries (saves tokens)
- [x] Context accumulation only includes actual code (not repeated LLD)
- [ ] Budget alerts configured at $100 threshold

**Worst-Case Scenario:** If LLD has 50 files (max), one run costs ~$15. Still bounded by hard failure.

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Code generation only |
| Third-Party Licenses | No | Internal tooling |
| Terms of Service | Yes | API usage within Claude ToS |
| Data Retention | N/A | Generated code managed by user |
| Export Controls | No | No restricted algorithms |

**Data Classification:** Internal

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

### 10.0 Test Plan (TDD - Complete Before Implementation)

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | Parse valid LLD file table | Returns list[FileSpec] with correct fields | RED |
| T020 | Parse LLD with no file table | Returns empty list or raises clear error | RED |
| T030 | Extract valid code block | Returns code content string | RED |
| T040 | Extract from response with no code block | Returns None | RED |
| T050 | Validate valid Python code | Returns {valid: True} | RED |
| T060 | Validate empty code block | Returns {valid: False, error: "empty"} | RED |
| T070 | Validate Python syntax error | Returns {valid: False, error: "syntax"} | RED |
| T080 | Build prompt with accumulated context | Includes all previous files | RED |
| T090 | Integration: file-by-file produces code | All files written to disk | RED |
| T100 | Integration: summary response triggers hard failure | Process exits non-zero | RED |

**Coverage Target:** ≥95% for all new code

**TDD Checklist:**
- [ ] All tests written before implementation
- [ ] Tests currently RED (failing)
- [ ] Test IDs match scenario IDs in 10.1
- [ ] Test file created at: `tests/unit/test_implement_code.py`

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Parse standard LLD | Auto | LLD with 3-file table | 3 FileSpec objects | All fields correct |
| 020 | Parse empty LLD | Auto | LLD with no table | Empty list | No crash |
| 030 | Extract code from valid response | Auto | Response with ```python block | Code string | Content matches |
| 040 | Extract code from summary response | Auto | #225 actual response | None | Returns None |
| 050 | Validate correct Python | Auto | `def foo(): pass` | valid=True | Passes |
| 060 | Validate empty code | Auto | Empty string | valid=False | Error message present |
| 070 | Validate syntax error | Auto | `def foo(` | valid=False | Error mentions syntax |
| 080 | Accumulated context includes previous files | Auto | 2 completed files | Prompt contains both | String contains filepaths |
| 090 | End-to-end success | Auto | Mock Claude returns code | All files written | Files exist on disk |
| 100 | End-to-end hard failure | Auto | Mock Claude returns summary | Exit non-zero | Process terminated |

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/unit/test_implement_code.py -v

# Run only fast/mocked tests (exclude live)
poetry run pytest tests/unit/test_implement_code.py -v -m "not live"

# Run live integration tests (uses real Claude API)
poetry run pytest tests/unit/test_implement_code.py -v -m live
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claude still produces invalid code even for single file | High | Low | Hard failure surfaces issue; manual fix required |
| LLD file table format varies unexpectedly | Medium | Medium | Parser handles common variations; fail clearly on unknown |
| Accumulated context exceeds context window | High | Low | Track token count; warn if approaching limit |
| Hard failure frustrates users | Low | Medium | Clear error messages explain what went wrong |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD (#272)

### Tests
- [ ] All test scenarios pass
- [ ] Test coverage ≥95% for new code

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
| - | - | - | - |

**Final Status:** PENDING