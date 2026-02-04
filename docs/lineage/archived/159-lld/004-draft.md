# 159 - Fix: Unicode Encoding Error in Workflow Output on Windows

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: LLD creation for Issue #159
Update Reason: Revised based on Gemini Review #1 feedback
-->

## 1. Context & Goal
* **Issue:** #159
* **Objective:** Fix Unicode encoding errors that cause workflow crashes on Windows when printing symbols like `→`, `✓`, `✗` to the console
* **Status:** Draft
* **Related Issues:** None

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Should we use ASCII fallbacks or force UTF-8? **Decision: Both - UTF-8 with ASCII fallback**
- [x] Should the fix be applied globally at startup or per-output? **Decision: At application entry points (not __init__.py)**

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/codex_arch/core/encoding.py` | Add | New module for encoding utilities and stdout wrapper |
| `src/codex_arch/core/symbols.py` | Add | Centralized Unicode symbols with ASCII fallbacks |
| `tools/run_requirements_workflow.py` | Modify | Call `configure_safe_stdout()` at entry point before any output |
| `src/codex_arch/__main__.py` | Modify | Call `configure_safe_stdout()` at entry point (if exists) |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# pyproject.toml additions (if any)
# No new dependencies required - uses stdlib only
```

### 2.3 Data Structures

```python
# Pseudocode - NOT implementation
class SymbolSet(TypedDict):
    arrow_right: str      # → or ->
    check_mark: str       # ✓ or [OK]
    cross_mark: str       # ✗ or [X]
    bullet: str           # • or *
    ellipsis: str         # … or ...

# Global symbols instance
SYMBOLS: SymbolSet  # Populated based on encoding capability detected at import
```

### 2.4 Function Signatures

```python
# src/codex_arch/core/encoding.py

def configure_safe_stdout() -> None:
    """
    Configure stdout/stderr for safe Unicode handling.
    
    Wraps sys.stdout and sys.stderr with error handling
    that replaces unencodable characters instead of crashing.
    
    NOTE: Call this at application entry points (main blocks),
    NOT at module import time. This is idempotent and safe to call multiple times.
    """
    ...

def can_encode_unicode(stream: Optional[TextIO] = None) -> bool:
    """
    Check if a stream can encode common Unicode symbols.
    
    Args:
        stream: The stream to check. If None, checks the original/underlying
                stdout encoding before any wrapper is applied.
    
    Returns:
        True if UTF-8 or compatible encoding, False otherwise.
    """
    ...

def get_original_stdout_encoding() -> str:
    """
    Get the original stdout encoding before any wrapper is applied.
    
    Returns:
        The encoding string (e.g., 'utf-8', 'cp1252').
    """
    ...

def safe_print(*args, **kwargs) -> None:
    """
    Print with automatic encoding error handling.
    
    Falls back to ASCII representation if encoding fails.
    """
    ...


# src/codex_arch/core/symbols.py

def get_symbol(name: str) -> str:
    """
    Get a display symbol with automatic ASCII fallback.
    
    Args:
        name: Symbol name (arrow_right, check_mark, etc.)
    
    Returns:
        Unicode symbol if supported, ASCII alternative otherwise.
    """
    ...

def get_symbols() -> SymbolSet:
    """
    Get all symbols as a dict for easy access.
    
    Returns:
        Dict with symbol names mapped to appropriate characters.
    """
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. At application entry point (e.g., tools/run_requirements_workflow.py main):
   - Call configure_safe_stdout() BEFORE any imports that produce output

2. configure_safe_stdout():
   a. Store original stdout encoding in module-level variable (for later detection)
   b. Check if already configured (idempotency flag)
      IF yes: return (no action needed)
   c. Check PYTHONIOENCODING environment variable
      IF set to utf-8 with error handling: return
   d. Wrap sys.stdout with TextIOWrapper:
      - encoding='utf-8'
      - errors='replace' (substitute unencodable chars with ?)
   e. Do same for sys.stderr
   f. Set idempotency flag

3. get_original_stdout_encoding():
   a. Return stored original encoding (captured before wrapping)
   b. If not captured yet, inspect underlying buffer or return current

4. can_encode_unicode(stream):
   a. Get encoding to check:
      - If stream provided: use stream.encoding
      - Else: use get_original_stdout_encoding() (NOT the wrapped encoding)
   b. Try to encode test string "→✓✗" using that encoding
   c. Return True if successful, False otherwise

5. Symbol resolution (at symbols module import time):
   a. Call can_encode_unicode() with NO argument (uses original encoding)
   b. IF True: use Unicode symbols
   c. ELSE: use ASCII fallbacks
   
   NOTE: This happens at import time, which is AFTER configure_safe_stdout()
   has captured the original encoding but the symbol decision is based on
   the ORIGINAL terminal capability, not the wrapper.

6. Workflow output:
   - Entry point calls configure_safe_stdout()
   - Subsequent imports load symbols (resolved based on original encoding)
   - Output uses wrapped stdout (safe) with appropriate symbols (readable)
```

### 2.6 Technical Approach

* **Module:** `src/codex_arch/core/encoding.py`, `src/codex_arch/core/symbols.py`
* **Pattern:** Defensive encoding with graceful degradation
* **Key Decisions:** 
  - Apply fix at application entry points (NOT `__init__.py`) to avoid global side effects
  - Capture original encoding BEFORE wrapping to ensure correct symbol resolution
  - Use `errors='replace'` rather than `errors='ignore'` to show something happened
  - Provide centralized symbols for consistent fallback behavior

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| When to apply fix | Per-print, at `__init__.py`, at entry point | At entry point | Avoids global side effects on import; library provides capability, app opts-in |
| Error handling mode | replace, ignore, backslashreplace | replace | Shows visible marker (?) when encoding fails, aids debugging |
| Symbol management | Inline fallbacks, centralized module | Centralized module | Single source of truth, easy to update/extend |
| Wrapper scope | stdout only, stdout+stderr | Both stdout and stderr | Error messages may also contain Unicode |
| Encoding detection timing | After wrapping, before wrapping | Before wrapping (capture original) | Prevents false positive detection when wrapper makes stdout appear UTF-8 capable |

**Architectural Constraints:**
- Must not break existing functionality on Unix/macOS
- Must not require environment variable setup by users
- Must work with Git Bash, PowerShell, and CMD on Windows
- Must not cause side effects when library is imported (only when app opts in)
- Must not interfere with test runners like pytest that capture stdout

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. Workflow completes without Unicode encoding errors on Windows with default console
2. Output displays reasonable ASCII fallbacks when Unicode not supported (e.g., `->` for `→`)
3. Unix/macOS behavior unchanged (still displays Unicode symbols)
4. No new external dependencies required
5. Fix applies at application entry points, not on library import
6. Test runners (pytest) work correctly without interference

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Environment variable (PYTHONIOENCODING) | Simple, no code changes | Requires user action, easy to forget | **Rejected** |
| Replace all Unicode with ASCII | Guaranteed to work everywhere | Degrades experience on capable terminals | **Rejected** |
| Wrap stdout in `__init__.py` | Automatic for all imports | Anti-pattern: causes global side effects, breaks pytest | **Rejected** |
| Wrap stdout at entry points | Explicit opt-in, no side effects | Requires adding call to each entry point | **Selected** |
| Use `print()` with explicit encoding | Fine-grained control | Requires changing every print statement | **Rejected** |

**Rationale:** Wrapping stdout at application entry points provides the best balance - it's explicit (no hidden side effects), preserves Unicode on capable systems, gracefully degrades on Windows, and doesn't interfere with test runners or library consumers.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | N/A - No external data |
| Format | N/A |
| Size | N/A |
| Refresh | N/A |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
N/A - This is a code fix, no data pipeline involved
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Mock stdout with cp1252 encoding | Generated | Simulates Windows console |
| Mock stdout with UTF-8 encoding | Generated | Simulates Unix/modern terminal |
| Unicode test strings | Hardcoded | `→✓✗•…` and edge cases |

### 5.4 Deployment Pipeline

N/A - Code change only, deployed with normal package release.

**Path Verification Note:** Verify the repository uses `src/codex_arch/` layout. If flat layout (`codex_arch/` at root), adjust paths accordingly before implementation.

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
    subgraph Entry Point
        A[Application main] --> B[configure_safe_stdout]
        B --> B1[Capture original encoding]
        B1 --> C{Already configured?}
        C -->|Yes| D[Return early]
        C -->|No| E{stdout UTF-8?}
        E -->|Yes| F[Mark configured]
        E -->|No| G[Wrap with TextIOWrapper]
        G --> H[errors='replace']
        H --> F
    end

    subgraph Symbol Resolution
        I[Import symbols module] --> J[get_original_stdout_encoding]
        J --> K{can_encode_unicode?}
        K -->|Yes| L[Use Unicode: → ✓ ✗]
        K -->|No| M[Use ASCII: -> OK X]
    end

    subgraph Runtime
        N[Workflow prints output] --> O[Uses wrapped stdout]
        O --> P{Char encodable?}
        P -->|Yes| Q[Print normally]
        P -->|No| R[Replace with ?]
    end

    D --> I
    F --> I
    L --> N
    M --> N
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Stdout wrapper injection | Only wraps with stdlib TextIOWrapper, no external code | Addressed |
| Encoding confusion attacks | Uses explicit 'utf-8' encoding, not user-controlled | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Breaking existing output | Replace mode shows `?` instead of crashing - output visible | Addressed |
| Double-wrapping stdout | Idempotency flag prevents multiple wraps | Addressed |
| Interfering with piped output | Only apply when stdout is a TTY (detect with isatty) | Addressed |
| Wrapper creation failure | Try/except around wrapping; fall back to original stdout | Addressed |
| Test runner interference | Not applied in `__init__.py`; apps opt-in explicitly | Addressed |

**Fail Mode:** Fail Open - If wrapping fails for any reason, continue with original stdout (may still crash on Unicode, but no worse than before). Logged as warning.

**Recovery Strategy:** If encoding issues persist, users can set `PYTHONIOENCODING=utf-8` as documented workaround

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Startup latency | < 1ms | Single check and wrap operation |
| Print latency | Negligible | TextIOWrapper is thin layer |
| Memory | < 1KB | Wrapper object only |

**Bottlenecks:** None expected - this is a thin wrapper on stdlib functionality

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| N/A | N/A | N/A | $0 |

**Cost Controls:**
- [x] No external services involved
- [x] No API calls
- [x] Stdlib only

**Worst-Case Scenario:** N/A - no cost implications

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | No data processing |
| Third-Party Licenses | No | Uses Python stdlib only |
| Terms of Service | No | No external services |
| Data Retention | No | No data stored |
| Export Controls | No | No restricted algorithms |

**Data Classification:** N/A

**Compliance Checklist:**
- [x] No PII involved
- [x] No third-party dependencies
- [x] No external API usage
- [x] No data retention

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** All scenarios automated using mocked stdout with different encodings.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | UTF-8 stdout preserves Unicode | Auto | `print("→✓✗")` with UTF-8 mock | `→✓✗` | Exact match |
| 020 | cp1252 stdout replaces Unicode | Auto | `print("→✓✗")` with cp1252 mock | Output contains `?` characters | `'?' in output` and no exception raised |
| 030 | Symbol fallback on cp1252 | Auto | `get_symbol("arrow_right")` with cp1252 original encoding | `->` | ASCII string returned |
| 040 | Symbol Unicode on UTF-8 | Auto | `get_symbol("arrow_right")` with UTF-8 original encoding | `→` | Unicode string returned |
| 050 | Mixed content survives | Auto | `print("Status: ✓ Done")` with cp1252 | `Status: ? Done` | No exception, `?` in output |
| 060 | Empty string handling | Auto | `print("")` | `` | No exception |
| 070 | Already-wrapped stdout | Auto | Call `configure_safe_stdout()` twice | No error | Function idempotent |
| 080 | Non-TTY stdout (piped) | Auto | Mock non-TTY stdout | Original behavior preserved | No wrapping applied |
| 090 | All symbols have fallbacks | Auto | Iterate `SYMBOLS` | Each has non-empty value | No KeyError, all values truthy |
| 100 | Workflow integration | Auto | Run mock workflow with Unicode output | Exit code 0 | Success |
| 110 | Original encoding captured correctly | Auto | Wrap stdout, check `get_original_stdout_encoding()` | Returns original encoding | Matches pre-wrap encoding |
| 120 | Wrapper failure handled gracefully | Auto | Mock TextIOWrapper to raise exception | No crash, original stdout used | Warning logged, no exception |
| 130 | pytest stdout capture unaffected | Auto | Run test with pytest capture enabled | Capture works normally | Output captured correctly |

### 10.2 Test Commands

```bash
# Run all automated tests
poetry run pytest tests/test_encoding.py -v

# Run symbol tests
poetry run pytest tests/test_symbols.py -v

# Run with coverage
poetry run pytest tests/test_encoding.py tests/test_symbols.py -v --cov=src/codex_arch/core

# Integration test (simulates Windows encoding)
poetry run pytest tests/test_encoding.py::test_workflow_integration -v
```

### 10.3 Manual Tests (Only If Unavoidable)

| ID | Scenario | Why Not Automated | Steps |
|----|----------|-------------------|-------|
| M01 | Real Windows console test | Requires actual Windows machine with specific console encoding | 1. Open CMD/PowerShell 2. Run workflow 3. Verify no crash and readable output |

*Note: CI can test with mocked encodings, but real Windows console behavior should be verified manually once before release.*

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Wrapping breaks third-party libraries | Med | Low | Only apply at entry points, not on import; check for TTY |
| Some terminals misdetect as UTF-8 capable | Low | Low | Use actual encoding test on original stream, not just name check |
| Users confused by `?` replacement characters | Low | Med | Document in changelog; symbols module provides readable fallbacks |
| Entry point missed | Med | Low | Document all entry points; provide utility function for easy integration |
| Original encoding not captured before wrap | Med | Low | Capture encoding as first action in configure_safe_stdout() |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD (#159)
- [ ] Path layout verified (src/ vs flat)

### Tests
- [ ] All test scenarios pass (010-130)
- [ ] Test coverage > 90% for new modules
- [ ] Tests pass with pytest stdout capture (no interference)

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] CHANGELOG updated with fix

### Review
- [ ] Code review completed
- [ ] Tested on actual Windows machine (manual M01)
- [ ] User approval before closing issue

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Gemini Review #1 (REVISE)

**Timestamp:** 2025-01-XX
**Reviewer:** Gemini 3 Pro
**Verdict:** REVISE

#### Comments

| ID | Comment | Implemented? |
|----|---------|--------------|
| G1.1 | "Global Side Effects on Import (Anti-Pattern): Move configure_safe_stdout() to entry points, NOT __init__.py" | YES - Section 2.1, 2.5, 2.7 updated; removed __init__.py modification |
| G1.2 | "Logic Conflict in Encoding Detection: Detect original encoding before wrapping" | YES - Section 2.4, 2.5 updated with get_original_stdout_encoding() and capture-before-wrap flow |
| G1.3 | "Weak Test Assertion (Test 020): Assert specific replacement behavior" | YES - Test 020 updated with `'?' in output` assertion |
| G1.4 | "Path Verification: Ensure src/ layout is correct" | YES - Added verification note in Section 5.4 and DoD |
| G1.5 | "Suggestion: Fail-safe try/except around wrapping" | YES - Added to Section 7.2 Safety and Test 120 |

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| Gemini #1 | 2025-01-XX | REVISE | Global side effects anti-pattern; encoding detection timing |

**Final Status:** PENDING
<!-- Note: This field is auto-updated to APPROVED by the workflow when finalized -->