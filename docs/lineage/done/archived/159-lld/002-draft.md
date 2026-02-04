# 159 - Fix: Unicode Encoding Error in Workflow Output on Windows

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: LLD creation for Issue #159
Update Reason: Initial LLD for Windows Unicode encoding fix
-->

## 1. Context & Goal
* **Issue:** #159
* **Objective:** Fix Unicode encoding errors that cause workflow crashes on Windows when printing symbols like `→`, `✓`, `✗` to the console
* **Status:** Draft
* **Related Issues:** None

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Should we use ASCII fallbacks or force UTF-8? **Decision: Both - UTF-8 with ASCII fallback**
- [x] Should the fix be applied globally at startup or per-output? **Decision: Global at startup**

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/codex_arch/core/encoding.py` | Add | New module for encoding utilities and stdout wrapper |
| `src/codex_arch/__init__.py` | Modify | Initialize safe encoding at import time |
| `tools/run_requirements_workflow.py` | Modify | Import encoding module at top to ensure early initialization |
| `src/codex_arch/core/symbols.py` | Add | Centralized Unicode symbols with ASCII fallbacks |

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
SYMBOLS: SymbolSet  # Populated based on encoding capability
```

### 2.4 Function Signatures

```python
# src/codex_arch/core/encoding.py

def configure_safe_stdout() -> None:
    """
    Configure stdout/stderr for safe Unicode handling.
    
    Wraps sys.stdout and sys.stderr with error handling
    that replaces unencodable characters instead of crashing.
    """
    ...

def can_encode_unicode() -> bool:
    """
    Check if current stdout can encode common Unicode symbols.
    
    Returns:
        True if UTF-8 or compatible encoding, False otherwise.
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
1. At module import (codex_arch.__init__):
   - Call configure_safe_stdout()

2. configure_safe_stdout():
   a. Check if stdout is already UTF-8
      IF yes: return (no action needed)
   b. Check PYTHONIOENCODING environment variable
      IF set to utf-8: return
   c. Wrap sys.stdout with TextIOWrapper:
      - encoding='utf-8'
      - errors='replace' (substitute unencodable chars with ?)
   d. Do same for sys.stderr

3. can_encode_unicode():
   a. Try to encode test string "→✓✗" using stdout.encoding
   b. Return True if successful, False otherwise

4. Symbol resolution (at import time):
   a. Call can_encode_unicode()
   b. IF True: use Unicode symbols
   c. ELSE: use ASCII fallbacks

5. Workflow output:
   - Import from codex_arch (triggers safe stdout)
   - Use symbols.ARROW, symbols.CHECK, etc.
   - Output automatically handles encoding
```

### 2.6 Technical Approach

* **Module:** `src/codex_arch/core/encoding.py`, `src/codex_arch/core/symbols.py`
* **Pattern:** Defensive encoding with graceful degradation
* **Key Decisions:** 
  - Apply fix at import time to catch all output
  - Use `errors='replace'` rather than `errors='ignore'` to show something happened
  - Provide centralized symbols for consistent fallback behavior

### 2.7 Architecture Decisions

*Document key architectural decisions that affect the design.*

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| When to apply fix | Per-print, at startup, env var only | At startup (import) | Catches all output automatically without code changes |
| Error handling mode | replace, ignore, backslashreplace | replace | Shows visible marker (?) when encoding fails, aids debugging |
| Symbol management | Inline fallbacks, centralized module | Centralized module | Single source of truth, easy to update/extend |
| Wrapper scope | stdout only, stdout+stderr | Both stdout and stderr | Error messages may also contain Unicode |

**Architectural Constraints:**
- Must not break existing functionality on Unix/macOS
- Must not require environment variable setup by users
- Must work with Git Bash, PowerShell, and CMD on Windows

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. Workflow completes without Unicode encoding errors on Windows with default console
2. Output displays reasonable ASCII fallbacks when Unicode not supported (e.g., `->` for `→`)
3. Unix/macOS behavior unchanged (still displays Unicode symbols)
4. No new external dependencies required
5. Fix applies automatically without user configuration

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Environment variable (PYTHONIOENCODING) | Simple, no code changes | Requires user action, easy to forget | **Rejected** |
| Replace all Unicode with ASCII | Guaranteed to work everywhere | Degrades experience on capable terminals | **Rejected** |
| Wrap stdout with error handling | Automatic, preserves Unicode where possible | Slightly more complex | **Selected** |
| Use `print()` with explicit encoding | Fine-grained control | Requires changing every print statement | **Rejected** |

**Rationale:** Wrapping stdout at startup provides the best balance - it's automatic (no user action), preserves Unicode on capable systems, and gracefully degrades on Windows. The centralized symbols module provides additional safety and consistency.

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
    subgraph Initialization
        A[Import codex_arch] --> B[configure_safe_stdout]
        B --> C{stdout UTF-8?}
        C -->|Yes| D[No action needed]
        C -->|No| E[Wrap with TextIOWrapper]
        E --> F[errors='replace']
    end

    subgraph Symbol Resolution
        G[Import symbols] --> H{can_encode_unicode?}
        H -->|Yes| I[Use Unicode: → ✓ ✗]
        H -->|No| J[Use ASCII: -> OK X]
    end

    subgraph Runtime
        K[Workflow prints output] --> L[Uses wrapped stdout]
        L --> M{Char encodable?}
        M -->|Yes| N[Print normally]
        M -->|No| O[Replace with ?]
    end

    D --> G
    F --> G
    I --> K
    J --> K
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
| Double-wrapping stdout | Check if already wrapped before applying | Addressed |
| Interfering with piped output | Only apply when stdout is a TTY (detect with isatty) | Addressed |

**Fail Mode:** Fail Open - If wrapping fails, use original stdout (may still crash on Unicode, but no worse than before)

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
| 020 | cp1252 stdout replaces Unicode | Auto | `print("→✓✗")` with cp1252 mock | `???` or similar | No exception, output produced |
| 030 | Symbol fallback on cp1252 | Auto | `get_symbol("arrow_right")` with cp1252 | `->` | ASCII returned |
| 040 | Symbol Unicode on UTF-8 | Auto | `get_symbol("arrow_right")` with UTF-8 | `→` | Unicode returned |
| 050 | Mixed content survives | Auto | `print("Status: ✓ Done")` with cp1252 | `Status: ? Done` | No exception |
| 060 | Empty string handling | Auto | `print("")` | `` | No exception |
| 070 | Already-wrapped stdout | Auto | Call `configure_safe_stdout()` twice | No error | Function idempotent |
| 080 | Non-TTY stdout (piped) | Auto | Mock non-TTY stdout | Original behavior preserved | No wrapping applied |
| 090 | All symbols have fallbacks | Auto | Iterate `SYMBOLS` | Each has value | No KeyError |
| 100 | Workflow integration | Auto | Run mock workflow with Unicode output | Exit code 0 | Success |

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
| M01 | Real Windows console test | Requires actual Windows machine | 1. Open CMD/PowerShell 2. Run workflow 3. Verify no crash and readable output |

*Note: CI can test with mocked encodings, but real Windows console behavior should be verified manually once before release.*

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Wrapping breaks third-party libraries | Med | Low | Only wrap if stdout is TTY; check for existing wrapper |
| Some terminals misdetect as UTF-8 capable | Low | Low | Use actual encoding test, not just name check |
| Users confused by `?` replacement characters | Low | Med | Document in changelog; symbols module provides readable fallbacks |
| Fix doesn't apply in all entry points | Med | Med | Apply in `__init__.py` so any import triggers it |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD (#159)

### Tests
- [ ] All test scenarios pass (010-100)
- [ ] Test coverage > 90% for new modules

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

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Awaiting review |

**Final Status:** PENDING
<!-- Note: This field is auto-updated to APPROVED by the workflow when finalized -->