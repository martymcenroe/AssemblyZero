# LLD: Implementation Review Gate (#28)

**Issue:** https://github.com/mcwiz/AgentOS/issues/28
**Author:** Claude Agent
**Date:** 2026-01-16
**Status:** Draft - Pending Gemini Review

## 1. Problem Statement

### Current State
Agents can create PRs without any code review, leading to:
1. Bugs reaching main branch
2. Security vulnerabilities not caught
3. Code quality issues
4. No audit trail of implementation review

### Desired State
Before ANY PR is created, the implementation MUST be reviewed by Gemini:
1. Catch bugs before PR creation
2. Identify security issues
3. Verify code quality
4. Create audit trail of review approval

## 2. Design Overview

### Gate Purpose
The IMPLEMENTATION REVIEW GATE enforces that agents submit their implementation to Gemini review BEFORE creating a PR. This provides automated code review as a quality gate.

### Gate Location
**COMPACTION-SAFE RULES section** - After REPORT GENERATION GATE

This placement ensures:
- Gate survives context compaction
- Gate follows the workflow order (LLD → Code → Reports → Implementation Review → PR)
- Gate is part of the mandatory workflow

### Insertion Point
After the REPORT GENERATION GATE section, before the `---` separator.

## 3. Detailed Design

### Gate Content to Add

```markdown
### IMPLEMENTATION REVIEW GATE (BEFORE PR)

**Before creating ANY PR, execute this gate:**

```
Implementation Review Gate Check:
├── Do reports exist?
│   ├── YES → Proceed
│   └── NO → Execute REPORT GENERATION GATE first
│
├── Submit to Gemini:
│   └── Use gemini-retry.py with implementation-review prompt
│
├── Parse Gemini response:
│   ├── [APPROVE] → Gate PASSED, create PR
│   ├── [BLOCK] → Gate FAILED, fix issues before PR
│   └── Quota exhausted → STOP, report to user, do NOT create PR
```

**State the gate explicitly:**
> "Executing IMPLEMENTATION REVIEW GATE: Submitting to Gemini before PR."

**CRITICAL:** If Gemini returns [BLOCK], you MUST NOT create the PR.
```

### Gate Workflow

1. Agent completes implementation
2. Agent executes REPORT GENERATION GATE
3. Agent prepares review prompt with:
   - Implementation report
   - Test report
   - Diff of changes
4. Agent submits to Gemini using gemini-retry.py
5. Agent parses response for [APPROVE] or [BLOCK]
6. If [APPROVE]: Create PR
7. If [BLOCK]: Fix issues, resubmit

### Integration with Other Gates

The IMPLEMENTATION REVIEW GATE works with:
- **GEMINI SUBMISSION GATE**: Review MUST use gemini-retry.py
- **REPORT GENERATION GATE**: Reports must exist before review
- **LLD REVIEW GATE**: Implementation should match approved LLD

## 4. Files Modified

| File | Change |
|------|--------|
| `CLAUDE.md` | Add IMPLEMENTATION REVIEW GATE section after REPORT GENERATION GATE |

## 5. Testing Strategy

### Manual Verification
1. Read back CLAUDE.md after edit
2. Verify gate is in COMPACTION-SAFE section
3. Verify gate requires reports before review
4. Verify gate blocks PR on [BLOCK] response

## 6. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gate not visible after compaction | HIGH | Place in COMPACTION-SAFE section |
| Agents skip gate | MEDIUM | Clear "CRITICAL" instruction |
| PR created despite [BLOCK] | HIGH | Bold warning in gate text |

## 7. Success Criteria

1. Gate is in COMPACTION-SAFE section of CLAUDE.md
2. Gate clearly requires reports before review
3. Gate specifies handling for [APPROVE] and [BLOCK]
4. Gate has clear "CRITICAL" instruction about blocking PR
