# LLD Review: 1225-Feature: Hard gate wrapper for skipped test enforcement (test-gate.py)

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid, standalone solution for enforcing test skip auditing without introducing heavy dependencies. The logic flow is sound, and the architectural choice of a wrapper script maximizes portability. However, the Requirements Coverage falls slightly below the strict 95% threshold due to a missing test case regarding the automatic injection of pytest flags, which is critical for the parser's operation.

## Open Questions Resolved
- [x] ~~Should the audit block be embedded in pytest output (via fixtures/plugins) or in a separate file (e.g., `.skip-audit.md`)?~~ **RESOLVED: Support both, but prioritize the file (`.skip-audit.md`) as the primary mechanism for CI/PR persistence. Embedded output is better suited for ad-hoc debugging.**
- [x] ~~What constitutes a "critical" test vs non-critical? Should severity be inferred or explicitly marked?~~ **RESOLVED: Use explicit `@pytest.mark.critical` as the primary source of truth. Name-based heuristics (e.g., "security") should be a secondary fallback that warns but perhaps doesn't block without manual confirmation to avoid false positives.**
- [x] ~~Should the gate have a bypass mechanism for emergencies (e.g., `--skip-gate-bypass` flag with justification)?~~ **RESOLVED: Yes. The `--skip-gate-bypass` flag is mandatory for "break glass" scenarios but must require a non-empty string argument for the justification to ensure traceability.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | `test-gate.py` executes pytest with all provided arguments unchanged | T010, T160 | ✓ Covered |
| 2 | Script detects skipped tests from pytest verbose output (`-v` flag auto-added if missing) | T030, T040 | **GAP** |
| 3 | When skips exist, requires SKIPPED TEST AUDIT block (stdout or file) | T100, T070, T080 | ✓ Covered |
| 4 | Fails (exit 1) if any skipped test lacks audit entry | T110 | ✓ Covered |
| 5 | Fails (exit 1) if any critical test has UNVERIFIED status | T120 | ✓ Covered |
| 6 | Passes through pytest exit code when gate passes | T020, T130, T150 | ✓ Covered |
| 7 | Works with common pytest flags: `-v`, `-x`, `--cov`, `-k`, `-m`, `--tb` | T160 | ✓ Covered |
| 8 | Provides clear error messages identifying which tests need attention | T110, T120 | ✓ Covered |
| 9 | Supports `--skip-gate-bypass` flag for emergencies (logged) | T140 | ✓ Covered |

**Coverage Calculation:** 8 requirements covered / 9 total = **88.8%**

**Verdict:** **BLOCK** (Must be ≥95%)

**Missing Test Scenarios:**
- **Requirement 2 Gap:** Tests T030 and T040 verify the *parser* works if given verbose output. However, there is no test verifying the *logic* that automatically appends `-v` to the subprocess call if the user didn't provide it. If this logic fails, the parser receives standard output and the gate silently fails to detect skips.
    - Add Test: `test_auto_add_verbose_flag` | Input: `args=[]` | Expected: `subprocess called with ['-v']`

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
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** Coverage is 88.8% (<95%). You must add the missing test scenario for Requirement 2 (auto-injection of `-v` flag) to the Test Scenarios table in Section 10.1 and the TDD Plan in Section 10.0.

## Tier 3: SUGGESTIONS
- **Signal Handling:** Consider how the wrapper handles `Ctrl+C` (SIGINT). Ensure the wrapper forwards the signal to the pytest subprocess immediately so the test run stops cleanly, rather than the wrapper dying and leaving the subprocess orphaned or running.
- **Fail Mode Clarity:** In Section 7.2, "Fail Open with Warning" is specified for parser failures. Ensure this is explicitly logged as a "WARNING" so it doesn't get lost in CI logs.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision