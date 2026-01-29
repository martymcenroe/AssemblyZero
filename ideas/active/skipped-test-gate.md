# Candidate Issue: Skipped Test Gate

**Status:** Draft
**Origin:** Talos Issue #73 post-mortem - agent claimed tests "passed" when critical Firefox test was skipped

---

## Problem

Agent reported "17 passed, 1 skipped" as success. The skipped test was the critical one that would have caught a fundamental bug (Firefox extension couldn't load because manifest was named wrong).

**Root cause:** No gate prevents agents from treating skipped tests as acceptable.

---

## Proposed Gate: SKIPPED TEST AUDIT

### Rule

**Before claiming "tests pass", agent MUST audit all skipped tests and explicitly state:**

1. What functionality the skipped test covers
2. Why it was skipped
3. Whether that functionality was verified another way
4. If NOT verified → report as **UNVERIFIED**, not "passed"

### Gate Trigger

After any test run that includes skipped tests:

```
SKIPPED TEST AUDIT REQUIRED

For each skipped test:
├── What does this test verify?
├── Why was it skipped?
├── Is this critical functionality?
│   ├── YES → How was it verified instead?
│   │   ├── Manual test performed → Document result
│   │   └── NOT verified → STOP. Report as UNVERIFIED.
│   └── NO → Acceptable to skip
```

### Output Format

Instead of:
```
Tests: 17 passed, 1 skipped
```

Require:
```
Tests: 17 passed, 1 skipped

SKIPPED TEST AUDIT:
- [SKIPPED] "Firefox extension loading"
  - Verifies: Extension loads in Firefox via about:debugging
  - Skipped because: Playwright can't automate Firefox extension loading
  - Critical: YES
  - Alternative verification: NONE
  - Status: UNVERIFIED - MANUAL TEST REQUIRED
```

---

## Implementation Options

### Option A: CLAUDE.md Rule (Soft Gate)

Add to AgentOS CLAUDE.md under test reporting:

```markdown
### SKIPPED TEST GATE (MANDATORY)

After ANY test run with skipped tests, you MUST:

1. List each skipped test
2. State what it verifies
3. State if it's critical functionality
4. If critical and not verified another way → report as UNVERIFIED

**NEVER say "tests pass" if critical functionality is unverified.**
```

### Option B: Wrapper Script (Hard Gate)

Create `tools/test-gate.py` that:
1. Runs the test command
2. Parses output for skipped tests
3. Prompts agent to audit each skip
4. Blocks "success" status if critical skips unaudited

### Option C: Test Framework Config

Configure Playwright/Jest to:
- Fail if certain tagged tests are skipped
- Require `--allow-skip=<reason>` flag for critical tests

---

## Acceptance Criteria

- [ ] Agent cannot claim "tests pass" without auditing skipped tests
- [ ] Critical skipped tests block success unless manually verified
- [ ] Audit trail shows what was verified and how
- [ ] Gate catches the exact failure mode from Talos #73

---

## Why This Matters

Skipped tests are often skipped for good reasons (environment, flaky, etc.). But when a skipped test covers **critical functionality**, treating it as "passed" is a lie.

The agent's job is to verify functionality works. If automation can't verify it, the agent must either:
1. Verify manually
2. Report it as unverified

"1 skipped" should trigger the same scrutiny as "1 failed".

---

## Related

- Talos PR #72: Claimed Firefox support worked, tests "passed"
- Talos Issue #73: Fix revealed tests never actually loaded Firefox extension
- Aletheia: Has separate browser directories - similar pattern needed similar verification
