# LLD: Report Generation Gate (#29)

**Issue:** https://github.com/mcwiz/AgentOS/issues/29
**Author:** Claude Agent
**Date:** 2026-01-16
**Status:** Draft - Pending Gemini Review

## 1. Problem Statement

### Current State
Agents can complete implementation without generating reports, leading to:
1. No documentation of what was done
2. No test evidence
3. Incomplete audit trail
4. Difficulty reviewing PRs

### Desired State
After implementation and before review, reports MUST be generated:
1. Implementation report documenting changes
2. Test report showing test execution
3. Standardized location and format
4. Audit trail for compliance

## 2. Design Overview

### Gate Purpose
The REPORT GENERATION GATE enforces that agents create implementation and test reports after coding and before submitting for implementation review.

### Gate Location
**COMPACTION-SAFE RULES section** - After LLD REVIEW GATE

This placement ensures:
- Gate survives context compaction
- Gate follows the workflow order (LLD → Code → Reports → Review → PR)
- Gate is part of the mandatory workflow

### Insertion Point
After the LLD REVIEW GATE section, before the IMPLEMENTATION REVIEW GATE section.

## 3. Detailed Design

### Gate Content to Add

```markdown
### REPORT GENERATION GATE (AFTER CODING)

**Before implementation review, generate required reports:**

Required files:
- `docs/reports/active/{issue-id}-implementation-report.md`
- `docs/reports/active/{issue-id}-test-report.md`

Where `{issue-id}` is the GitHub issue integer (e.g., `docs/reports/active/27-implementation-report.md`).

**Implementation Report minimum content:**
- Issue reference (link)
- Files changed
- Design decisions
- Known limitations

**Test Report minimum content:**
- Test command executed
- Full test output (not paraphrased)
- Skipped tests with reasons
- Coverage metrics (if available)

**State the gate explicitly:**
> "Executing REPORT GENERATION GATE: Creating implementation and test reports."
```

### Report Templates

The gate references templates at `.claude/templates/reports/`:
- `implementation-report.md.template`
- `test-report.md.template`

### Integration with Other Gates

The REPORT GENERATION GATE works with:
- **LLD REVIEW GATE**: Happens after coding, which requires LLD approval
- **IMPLEMENTATION REVIEW GATE**: Reports must exist before implementation review

## 4. Files Modified

| File | Change |
|------|--------|
| `CLAUDE.md` | Add REPORT GENERATION GATE section after LLD REVIEW GATE |
| `.claude/templates/reports/implementation-report.md.template` | Create new |
| `.claude/templates/reports/test-report.md.template` | Create new |

## 5. Testing Strategy

### Manual Verification
1. Read back CLAUDE.md after edit
2. Verify gate is in COMPACTION-SAFE section
3. Verify gate specifies correct report location
4. Verify templates exist and have required sections

## 6. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gate not visible after compaction | HIGH | Place in COMPACTION-SAFE section |
| Agents skip gate | MEDIUM | Clear instructions in gate text |
| Wrong report location | LOW | Specify path pattern explicitly |

## 7. Success Criteria

1. Gate is in COMPACTION-SAFE section of CLAUDE.md
2. Gate clearly specifies report requirements
3. Gate specifies correct file locations
4. Templates are created
