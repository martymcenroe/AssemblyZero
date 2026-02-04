---
repo: martymcenroe/AgentOS
issue: 257
url: https://github.com/martymcenroe/AgentOS/issues/257
fetched: 2026-02-04T04:20:26.347546Z
---

# Issue #257: fix: Review node should update draft with resolved open questions

## Problem

When Gemini resolves open questions and provides suggestions in the verdict, the draft is NOT updated. The mechanical validation then blocks because it checks the draft (which still has `- [ ]` unchecked questions).

**Example from #180:**
- Verdict says: `Open Questions: RESOLVED` and lists all resolutions
- Verdict contains Tier 3 suggestions for improvement
- Draft still has: `- [ ] Should N9_cleanup be triggered...`
- Validation: `BLOCKED: Unresolved open questions remain`

## Root Cause

The review node saves the verdict but doesn't update the draft with:
1. Resolved open questions
2. Suggestions from the approved verdict

## Solution

After review, if verdict is APPROVED:
1. Parse the resolutions from the verdict
2. Parse Tier 3 suggestions from the verdict
3. Update the draft's Open Questions section:
   - Change `- [ ]` to `- [x]`
   - Add strikethrough and RESOLVED text
4. Add suggestions to appropriate sections (or append as "Reviewer Suggestions" section)
5. Save updated draft as the **final version** for the LLD

The final LLD should be a complete document incorporating all feedback from the approved verdict.

## Files to Modify

| File | Change |
|------|--------|
| `agentos/workflows/requirements/nodes/review.py` | Add draft update logic after approval |
| `agentos/workflows/requirements/nodes/finalize.py` | Use the updated draft for final LLD |

## Acceptance Criteria

- [ ] Resolved questions are merged back into draft
- [ ] Tier 3 suggestions from approved verdict are incorporated
- [ ] Final LLD has checked boxes with RESOLVED text
- [ ] Final LLD is a complete, self-contained document
- [ ] No manual intervention needed after Gemini approves