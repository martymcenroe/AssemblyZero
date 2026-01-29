# Skipped Test Gate: Mandatory Audit Before Claiming Tests Pass

## User Story
As an agent working on a project with automated tests,
I want a mandatory gate that forces me to audit skipped tests,
So that I never claim "tests pass" when critical functionality remains unverified.

## Objective
Prevent agents from treating skipped tests as acceptable without explicit verification that the skipped functionality was tested another way.

## UX Flow

### Scenario 1: Test Run With Non-Critical Skip
1. Agent runs test suite, result: "17 passed, 1 skipped"
2. Gate triggers: Agent must audit skipped test
3. Agent identifies: skipped test covers "date formatting in locale X"
4. Agent assesses: Not critical to core functionality
5. Agent documents: "Skipped due to missing locale data, non-critical"
6. Result: Tests reported as PASS with documented skip

### Scenario 2: Test Run With Critical Unverified Skip
1. Agent runs test suite, result: "17 passed, 1 skipped"
2. Gate triggers: Agent must audit skipped test
3. Agent identifies: skipped test covers "Firefox extension loading"
4. Agent assesses: CRITICAL - this is the core feature being delivered
5. Agent checks: No alternative verification performed
6. Result: Tests reported as **UNVERIFIED** - manual test required before merge

### Scenario 3: Critical Skip With Manual Verification
1. Agent runs test suite, result: "17 passed, 1 skipped"
2. Gate triggers: Agent must audit skipped test
3. Agent identifies: skipped test covers "Firefox extension loading"
4. Agent assesses: CRITICAL
5. Agent performs manual verification and documents result
6. Result: Tests reported as PASS with documented manual verification

### Scenario 4: All Tests Pass (No Skips)
1. Agent runs test suite, result: "18 passed"
2. No gate triggered
3. Result: Tests reported as PASS

## Requirements

### Gate Behavior
1. Gate MUST trigger after any test run that includes skipped tests
2. Gate MUST require explicit audit of each skipped test
3. Gate MUST block "success" status if critical skips are unaudited
4. Gate MUST distinguish between "skipped-but-verified" and "skipped-unverified"

### Audit Content
1. For each skipped test, agent MUST document:
   - What functionality the test verifies
   - Why the test was skipped
   - Whether the functionality is critical
   - How it was verified alternatively (if critical)
2. Audit MUST be included in test output, not just agent thinking

### Reporting Requirements
1. Agent MUST NOT use phrase "tests pass" if any critical functionality is unverified
2. Agent MUST use "UNVERIFIED" status for critical skipped tests without alternative verification
3. Agent MUST document manual verification steps when performed

## Technical Approach

### Implementation: CLAUDE.md Rule (Soft Gate)

Add to project CLAUDE.md under testing section:

```markdown
### SKIPPED TEST GATE (MANDATORY)

After ANY test run with skipped tests:

1. **AUDIT each skipped test:**
   - What does this test verify?
   - Why was it skipped?
   - Is this critical functionality?

2. **If critical and not verified another way:**
   - Status = UNVERIFIED
   - NEVER say "tests pass"
   - Require manual test before merge

3. **Output format:**
   ```
   SKIPPED TEST AUDIT:
   - [SKIPPED] "{test name}"
     - Verifies: {what it tests}
     - Skip reason: {why skipped}
     - Critical: YES/NO
     - Alt verification: {method or NONE}
     - Status: VERIFIED/UNVERIFIED
   ```
```

### Future Enhancement: Wrapper Script (Hard Gate)
- `tools/test-gate.py` that wraps test runner
- Parses output for skipped tests
- Blocks CI if critical skips unaudited
- Deferred to future issue for hard enforcement

## Security Considerations
No security implications - this is a process gate for test reporting accuracy.

## Files to Create/Modify
- `CLAUDE.md` — Add SKIPPED TEST GATE section under testing rules
- `docs/adr/NNNN-skipped-test-gate.md` — Document rationale and implementation decision

## Dependencies
- None - can be implemented immediately

## Out of Scope (Future)
- Hard gate via wrapper script — requires more implementation
- Test framework configuration for tagged critical tests — framework-specific
- Automated detection of "critical" tests — requires heuristics or tagging
- CI integration to block PRs — requires pipeline changes

## Acceptance Criteria
- [ ] CLAUDE.md contains SKIPPED TEST GATE rule with exact audit format
- [ ] Agent audits skipped tests before claiming success (verified via test run)
- [ ] Critical skipped tests without alternative verification show UNVERIFIED status
- [ ] Audit output includes: test name, what it verifies, skip reason, criticality, verification status
- [ ] The exact failure mode from Talos #73 would be caught (Firefox extension skip → UNVERIFIED)

## Definition of Done

### Implementation
- [ ] SKIPPED TEST GATE rule added to CLAUDE.md
- [ ] Rule includes exact output format for audit
- [ ] Rule clearly defines when "tests pass" can/cannot be claimed

### Tools
- [ ] N/A for MVP (soft gate via CLAUDE.md only)

### Documentation
- [ ] ADR created explaining gate rationale and failure mode it prevents
- [ ] README updated if testing section exists
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Manually verify gate triggers on test run with skips
- [ ] Verify agent produces audit in correct format
- [ ] Verify UNVERIFIED status appears for critical unverified skips

## Testing Notes

To test this gate:

1. **Trigger condition:** Run any test suite that has a skipped test
2. **Expected behavior:** Agent should produce SKIPPED TEST AUDIT block
3. **Force failure mode:** 
   - Skip a test that covers core functionality
   - Attempt to claim "tests pass" without audit
   - Gate should prevent this

**Regression test for Talos #73:**
- Run Playwright tests where Firefox extension loading test is skipped
- Agent must report UNVERIFIED, not "passed"
- Agent must not claim Firefox support works without manual verification

## Related Issues
- Talos PR #72: Original failure - claimed Firefox support worked
- Talos Issue #73: Post-mortem that identified this gate need
- Aletheia: Similar pattern with browser-specific testing