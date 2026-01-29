# 0113 - Template: Test Report

## Purpose

The Test Report provides **evidence that the code works**. It is the proof companion to the Implementation Report (which provides narrative).

**Analogy:**
- LLD = Architectural blueprints (the plan)
- Implementation Report = Construction journal (what happened)
- Test Report = Building inspection certificate (proof it works)

## Usage

After completing implementation and testing:
1. Create in `docs/reports/{IssueID}/test-report.md`
2. Capture automated test output
3. Record manual smoke test results from orchestrator
4. Optionally save raw pytest output to `test-output.log`

**This is the Willison Protocol evidence.** See `docs/0005-testing-strategy-and-protocols.md` Section 5.

---

## Template

```markdown
# Test Report: {Feature Name}

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #{IssueID} |
| **LLD** | `docs/1{IssueID}-{feature-name}.md` |
| **Implementation Report** | `docs/reports/{IssueID}/implementation-report.md` |
| **Raw Output** | `docs/reports/{IssueID}/test-output.log` |
| **Date** | {YYYY-MM-DD} |

## 2. Willison Protocol Compliance

### Step 1: Automated Tests Written
- **Test file:** `tests/test_{feature}.py`
- **Scenarios covered:** {count} of {total} from LLD Section 10.1

### Step 2: Tests Fail on Revert

```bash
# Revert implementation
git stash

# Run tests - MUST FAIL
poetry run pytest tests/test_{feature}.py -v
# Output: X failed, Y passed

# Restore implementation
git stash pop

# Run tests - MUST PASS
poetry run pytest tests/test_{feature}.py -v
# Output: X passed
```

**Verified:** [ ] Yes / [ ] No

### Step 3: Proof Captured

{Summary of test results - full output in test-output.log if needed}

## 3. Automated Test Results

### Summary

| Metric | Value |
|--------|-------|
| **Total tests** | {X} |
| **Passed** | {X} |
| **Failed** | {0} |
| **Skipped** | {0} |
| **Duration** | {X.Xs} |

### Output

```
{Paste pytest output here - truncate if very long, reference test-output.log}
```

### Coverage by LLD Scenario

| LLD ID | Scenario | Test Function | Result |
|--------|----------|---------------|--------|
| 010 | {Happy path} | `test_happy_path` | PASS |
| 020 | {Edge case} | `test_edge_case` | PASS |
| 030 | {Error case} | `test_error_case` | PASS |

### Warnings Summary (MANDATORY)

**Total Warnings:** {X}

| Count | Type | Source | Message |
|-------|------|--------|---------|
| {N} | `DeprecationWarning` | {package.module} | "{Summary of warning message}" |
| {N} | `FutureWarning` | {package.module} | "{Summary of warning message}" |
| {N} | `UserWarning` | {package.module} | "{Summary of warning message}" |

**Analysis:**
- {Which warnings are from dependencies (acceptable) vs project code (needs attention)}
- {Whether any warnings indicate upcoming breaking changes that need tracking}
- {Action items: None / Create issue for X / Upgrade dependency Y}

> **Note:** Every warning must be accounted for. Unexplained warnings are not acceptable.

## 4. Manual Verification (Orchestrator)

**Tester:** {Orchestrator name}
**Date:** {YYYY-MM-DD}
**Environment:** {Browser, OS, Lambda state, etc.}

### Smoke Test Checklist

{Pre-filled from LLD Section 10.4, orchestrator marks pass/fail}

| Step | Action | Expected | Result | Notes |
|------|--------|----------|--------|-------|
| 1 | {Action from LLD} | {Expected outcome} | PASS/FAIL | {Any observations} |
| 2 | {Action} | {Expected} | PASS/FAIL | |
| 3 | {Action} | {Expected} | PASS/FAIL | |

### Issues Discovered During Manual Testing

| Issue | Severity | Resolution |
|-------|----------|------------|
| {Description} | Critical/Major/Minor | Fixed in PR / Created #{IssueID} / Deferred |

## 5. Failed Tests Detail

{If any tests failed, document each here. Delete section if all passed.}

### {Test ID}: {Scenario Name}

**Expected:** {What should have happened}
**Actual:** {What actually happened}
**Root Cause:** {Analysis}
**Resolution:** {Fixed in commit X / Deferred to Issue #Y}

## 6. Regression Check

| Existing Functionality | Verified | Notes |
|------------------------|----------|-------|
| {Feature X still works} | [ ] | |
| {Feature Y still works} | [ ] | |
| {Performance acceptable} | [ ] | {No degradation observed} |

## 7. Environment

| Component | Version/State |
|-----------|---------------|
| **Python** | {3.12.x} |
| **OS** | {Windows 11 / macOS / Linux} |
| **Browser** | {Chrome 120, Firefox 121} |
| **Lambda** | {Deployed / Local / Concurrency=X} |
| **Special Config** | {Debug mode, feature flags, etc.} |

## 8. Approval

| Role | Name | Date | Status |
|------|------|------|--------|
| **Automated Tests** | {LLM} | {Date} | Executed, all pass |
| **Manual Verification** | {Orchestrator} | {Date} | Smoke test pass |
| **Ready for Merge** | {Orchestrator} | {Date} | Approved |
```

---

## Tips for Good Test Reports

1. **Willison Protocol is non-negotiable:** Must verify tests fail on revert
2. **Link to raw output:** Don't bloat the report, reference `test-output.log`
3. **Pre-fill smoke test checklist:** Pull from LLD Section 10.4 so orchestrator just marks pass/fail
4. **Be honest about failures:** Document what failed and how it was resolved
5. **Environment matters:** Future debugging may need to reproduce your exact setup
