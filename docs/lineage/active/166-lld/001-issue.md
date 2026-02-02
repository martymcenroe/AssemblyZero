# Issue #166: feat: Add mechanical test plan validation to requirements workflow (pre-Gemini gate)

## Problem

LLDs pass Gemini review (0702c) but get blocked by N1 test plan review during implementation. This wastes time and creates frustrating loops.

**Root cause:** Gemini is probabilistic. Even with explicit instructions (added in #126, v2.1.0), Gemini can:
- See a coverage gap but classify it as Tier 3 suggestion instead of blocking
- Make qualitative assessments instead of counting requirements vs tests
- Miss edge cases in the test plan

**Evidence (LLD-141):**
- Gemini approved with "No high-priority issues found"
- Gemini noted "Success Detection" as Tier 3 SUGGESTION
- N1 mechanical review: 5/6 = 83% coverage â†’ BLOCKED
- Gemini saw the gap but didn't block on it

## Proposed Solution

Add a **mechanical pre-check** to the requirements workflow that runs the SAME checks N1 runs, BEFORE calling Gemini:

```
Requirements Workflow (current):
  N1_draft â†’ N2_gemini_review â†’ N3_finalize

Requirements Workflow (proposed):
  N1_draft â†’ N1b_mechanical_validation â†’ N2_gemini_review â†’ N3_finalize
                    â†“ (BLOCK)
               N1_draft (loop with feedback)
```

### Mechanical Checks (deterministic, not LLM)

| Check | Method | Threshold |
|-------|--------|-----------|
| Requirement coverage | Count Section 3 reqs, map to Section 10 tests | â‰¥95% |
| Test assertions | Regex for vague phrases ("verify it works") | 0 violations |
| Human delegation | Regex for "manual", "visual check", etc. | 0 violations |
| Test type consistency | Parse type column, validate against mock guidance | Warnings only |

### Benefits

1. **Deterministic** - Same input always produces same output
2. **Fast** - No API calls, runs in milliseconds
3. **Consistent** - Requirements workflow and implementation workflow agree
4. **Saves Gemini calls** - Don't send garbage to Gemini for review

## Files to Create

- `agentos/workflows/requirements/validation/test_plan_validator.py` - Mechanical checks
- `agentos/workflows/requirements/nodes/validate_test_plan.py` - N1b node

## Files to Modify

- `agentos/workflows/requirements/graph.py` - Insert N1b between draft and review
- `agentos/workflows/requirements/state.py` - Add validation fields

## Acceptance Criteria

- [ ] Requirements workflow includes mechanical test plan validation
- [ ] Validation runs BEFORE Gemini review
- [ ] If validation fails, draft loops with specific feedback
- [ ] LLD that passes requirements workflow also passes N1 in implementation workflow
- [ ] No more "Gemini approved but N1 blocked" scenarios

## Related

- #126 (closed) - Added checks to Gemini prompt, but Gemini is probabilistic
- #147 - Implementation Completeness Gate (similar pattern, different phase)