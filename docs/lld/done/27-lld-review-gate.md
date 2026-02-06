# LLD: LLD Review Gate (#27)

**Issue:** https://github.com/mcwiz/AssemblyZero/issues/27
**Author:** Claude Agent
**Date:** 2026-01-16
**Status:** Draft - Pending Gemini Review

## 1. Problem Statement

### Current State
Agents can begin coding without any design review, leading to:
1. Rework when designs are flawed
2. Security issues not caught before implementation
3. Inconsistent approaches across issues
4. No audit trail of design decisions

### Desired State
Before ANY coding begins, the Low-Level Design (LLD) MUST be reviewed by Gemini:
1. Catch design flaws before implementation
2. Identify security concerns early
3. Ensure consistent approach
4. Create audit trail of design approval

## 2. Design Overview

### Gate Purpose
The LLD REVIEW GATE enforces that agents submit their LLD to Gemini review BEFORE writing any code. This prevents wasted implementation effort on flawed designs.

### Gate Location
**COMPACTION-SAFE RULES section** - After GEMINI SUBMISSION GATE

This placement ensures:
- Gate survives context compaction
- Gate follows the Gemini Submission Gate (which it depends on)
- Gate is part of the mandatory workflow

### Insertion Point
After the GEMINI SUBMISSION GATE section, before the `---` separator.

## 3. Detailed Design

### Gate Content to Add

```markdown
### LLD REVIEW GATE (BEFORE CODING)

**Before writing ANY code for an issue, execute this gate:**

```
LLD Review Gate Check:
├── Does an LLD exist for this issue?
│   ├── YES → Submit to Gemini for review
│   └── NO → Ask user: Create LLD or waive requirement?
│
├── Submit LLD to Gemini:
│   └── Use gemini-retry.py with LLD review prompt
│
├── Parse Gemini response:
│   ├── [APPROVE] → Gate PASSED, proceed to coding
│   ├── [BLOCK] → Gate FAILED, fix issues before coding
│   └── Quota exhausted → STOP, report to user
```

**State the gate explicitly:**
> "Executing LLD REVIEW GATE: Submitting LLD to Gemini before coding."

**LLD location:** `docs/LLDs/active/{issue-id}-*.md`

**Escape hatch:** For [HOTFIX] tagged issues, user can explicitly waive.
```

### Gate Workflow

1. Agent receives a coding task
2. Agent checks for existing LLD at `docs/LLDs/active/{issue-id}-*.md`
3. If no LLD exists:
   - Agent asks user: "Create LLD or waive?"
   - If create: Agent writes LLD, then submits for review
   - If waive: Agent documents waiver reason, proceeds
4. If LLD exists:
   - Agent submits to Gemini using gemini-retry.py
   - Agent parses response for [APPROVE] or [BLOCK]
5. If [APPROVE]: Proceed to coding
6. If [BLOCK]: Fix blocking issues, resubmit

### Integration with Other Gates

The LLD REVIEW GATE works with:
- **GEMINI SUBMISSION GATE**: LLD review MUST use gemini-retry.py
- **CODING TASK GATE**: LLD review happens AFTER worktree creation, BEFORE coding
- **REPORT GENERATION GATE**: LLD becomes part of the audit trail

## 4. Files Modified

| File | Change |
|------|--------|
| `CLAUDE.md` | Add LLD REVIEW GATE section after GEMINI SUBMISSION GATE |

## 5. Testing Strategy

### Manual Verification
1. Read back CLAUDE.md after edit
2. Verify gate is in COMPACTION-SAFE section
3. Verify gate references correct LLD location
4. Verify escape hatch is documented

## 6. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gate not visible after compaction | HIGH | Place in COMPACTION-SAFE section |
| Agents skip gate | MEDIUM | Clear "State the gate explicitly" instruction |
| No LLD template | LOW | Reference existing pattern in docs/reports/ |

## 7. Success Criteria

1. Gate is in COMPACTION-SAFE section of CLAUDE.md
2. Gate clearly requires LLD submission before coding
3. Gate specifies handling for [APPROVE] and [BLOCK]
4. Gate provides escape hatch for hotfixes
