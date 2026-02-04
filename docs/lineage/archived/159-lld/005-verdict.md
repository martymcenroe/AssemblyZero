# LLD Review: 159 - Fix: Unicode Encoding Error in Workflow Output on Windows

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a strong foundation for fixing Unicode issues, with excellent test coverage and a defensive design pattern. However, there is a **critical logic conflict** between the proposed implementation (forcing UTF-8) and the test expectations (expecting replacement characters). Forcing UTF-8 on a Windows console that expects cp1252 will result in Mojibake (garbled text) rather than the intended fallback behavior, and it will cause Test 020 to fail because no encoding error will occur to trigger the replacement.

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
- [ ] **Logic Conflict in Section 2.5 vs Test 020:** Section 2.5 (Logic Flow) Step 2d proposes wrapping stdout with `encoding='utf-8'`.
    - **Problem:** If you force UTF-8 encoding, Python will successfully encode `→` to bytes (`\xE2\x86\x92`). The `errors='replace'` handler will *never* trigger because UTF-8 can encode all characters.
    - **Consequence:**
        1.  Test 020 (Expect `?` in output) will **FAIL** because the output will be bytes, not `?`.
        2.  On a real Windows machine (cp1252), the terminal will display these UTF-8 bytes as Mojibake (`â†’`) instead of a clean replacement or symbol.
    - **Recommendation:** Modify Section 2.5 Step 2d to use `sys.stdout.reconfigure(errors='replace')` (if Python 3.7+) or wrap using the *original* encoding, not hardcoded `'utf-8'`. This ensures `UnicodeEncodeError` is caught and replaced with `?` as intended.

- [ ] **Path Structure Verification:** The LLD assumes a `src/codex_arch/` layout but notes in Section 5.4 that this must be verified.
    - **Action:** Ensure `files changed` reflects the *actual* repository structure. If the repo is flat (`codex_arch/` at root), the LLD paths are incorrect.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Test 020 Realism:** As noted above, this test relies on the stdout wrapper *retaining* a limited encoding (like cp1252) to trigger the `?` replacement. Ensure the test setup mocks the *original* stdout as cp1252, and the *wrapper* uses that same encoding (with replace errors).

## Tier 3: SUGGESTIONS
- **Implementation Detail:** Use `sys.stdout.reconfigure(errors='replace')` where available (Python 3.7+) as it is cleaner than creating a new `TextIOWrapper` on top of the buffer.
- **Debugging:** Consider using `errors='backslashreplace'` instead of `'replace'` for development builds, as it makes it clearer *what* character is failing (e.g., `\u2192` instead of `?`).

## Questions for Orchestrator
1. Can you confirm if the repository uses a `src/` layout or a flat layout? This determines if the file paths in the LLD need adjustment.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision