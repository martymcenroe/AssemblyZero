# LLD Review: 159-Fix: Unicode Encoding Error in Workflow Output on Windows

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD addresses a critical stability issue on Windows. The goal and general approach (safe encoding wrapper + symbol fallbacks) are sound. However, the proposal to apply the fix globally at module import time (`__init__.py`) is an architectural anti-pattern that creates side effects, complicates testing, and creates logic conflicts with the symbol resolution strategy.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation pending Tier 2 fixes.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Global Side Effects on Import (Anti-Pattern):** The design proposes calling `configure_safe_stdout()` inside `src/codex_arch/__init__.py`.
    *   **Risk:** Importing a library should not change global state (`sys.stdout`). This will interfere with test runners (like `pytest` which captures stdout), other libraries, and embedded usage.
    *   **Recommendation:** Move the call to `configure_safe_stdout()` to the application entry point (e.g., `tools/run_requirements_workflow.py` and `main` blocks), NOT `__init__.py`. The library should provide the capability, but the application should opt-in.
- [ ] **Logic Conflict in Encoding Detection:**
    *   **Issue:** The logic flow (Section 2.5) suggests wrapping stdout with `encoding='utf-8'` *before* checking `can_encode_unicode()`.
    *   **Risk:** If you wrap stdout with UTF-8, `sys.stdout.encoding` becomes `utf-8`. Subsequent checks will think the terminal supports Unicode. The code will attempt to print `→`. If the actual Windows console is CP1252, sending it UTF-8 bytes (because the wrapper thinks it's fine) often results in mojibake (garbage characters) rather than a clean ASCII fallback.
    *   **Recommendation:** Detect the *original* encoding capabilities and resolve symbols (ASCII vs Unicode) *before* applying the safety wrapper, or ensure the detection logic inspects the underlying buffer/stream, not the wrapped object.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Weak Test Assertion (Test 020):**
    *   **Issue:** Test 020 expects "No exception, output produced".
    *   **Recommendation:** This assertion is too vague. The test must assert that the output contains the specific replacement behavior expected (e.g., `assert '?' in output` or `assert '???' in output`).
- [ ] **Path Verification:**
    *   **Issue:** The LLD specifies `src/codex_arch/...`.
    *   **Recommendation:** Ensure the repository actually uses the `src/` layout. If the repo uses a flat layout (`codex_arch/` at root), this path is incorrect. Verify before implementation.

## Tier 3: SUGGESTIONS
- **Symbol Module:** Consider using `functools.lru_cache` for symbol lookups if the detection logic is expensive, though typically simple boolean checks are fast enough.
- **Fail-Safe:** In `configure_safe_stdout`, consider a try/except block around the wrapping logic itself to ensure that if the wrapper fails (e.g. strict permissions), the application continues with the original stdout (Fail Open).

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision