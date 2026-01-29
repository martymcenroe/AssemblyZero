# Candidate Issue: Add [F]ile Option to Issue Workflow Exit

**Status:** Draft
**Origin:** User friction during issue #72 creation via `run_issue_workflow.py`

---

## Problem

When using `run_issue_workflow.py` to build an issue through the Claude-powered drafting loop, there's no way to file the issue directly from the workflow. The user has to:

1. Reach a satisfactory draft
2. Type `[M]` to exit (manual mode? merge? unclear)
3. Python program just exits
4. Manually file the issue using `gh` CLI or Claude Code
5. Manually ensure labels exist before filing

This is friction-heavy, especially when labels don't exist yet.

---

## Desired Behavior

Add `[F]` (File) as an exit option that:

1. Reads the final draft from the audit directory
2. Extracts the title (first H1)
3. Extracts labels from the `## Labels` line at the bottom
4. **Creates any missing labels** with sensible defaults
5. Files the issue via `gh issue create`
6. Returns the issue URL to the user
7. Optionally moves the draft to appropriate audit directory

---

## UX Flow

```
Current draft saved to: docs/audit/active/backfill-issue-audit/062-draft.md

Options:
  [R]evise - Request changes to the draft
  [A]pprove - Mark draft as approved, continue to next step
  [M]anual - Exit workflow (file issue manually)
  [F]ile - File issue to GitHub now    <-- NEW

> F

Checking labels...
  ✓ enhancement (exists)
  ✓ tooling (creating...)
  ✓ audit (creating...)
  ✓ maintenance (creating...)

Filing issue...
✓ Created: https://github.com/martymcenroe/AgentOS/issues/72

Workflow complete.
```

---

## Implementation Notes

### Label Creation Logic

When filing, for each label in the `## Labels` line:
1. Check if label exists: `gh label list --repo X --search "name"`
2. If missing, create with default color based on category:
   - `enhancement`, `feature` → green tones
   - `bug`, `fix` → red tones
   - `tooling`, `maintenance` → purple/blue tones
   - `audit`, `governance` → yellow tones
   - Unknown → gray

### Draft Parsing

The draft follows a predictable format:
- Title: First `# ` line
- Body: Everything from `## User Story` through content before `## Labels`
- Labels: Parse the backtick-delimited list on the `## Labels` line

### Error Handling

- If `gh` CLI not authenticated → fail fast with clear message
- If draft has no title → fail with "Draft missing title (no H1 found)"
- If labels line malformed → warn and file without labels

---

## Questions to Resolve

1. Should `[F]` also move the draft from `active/` to `done/`?
   - Probably not - issue may not be implemented yet

2. Should we update `003-metadata.json` with the issue URL?
   - Yes - this links the audit trail to the filed issue

3. What about the `[M]` option - should it be renamed to `[E]xit` for clarity?

---

## Related

- Issue #72: Filed manually after workflow exit friction
- `agentos/workflows/issue/run_issue_workflow.py`: Main entry point
- `tools/backfill_issue_audit.py`: Similar label-checking logic could be shared
