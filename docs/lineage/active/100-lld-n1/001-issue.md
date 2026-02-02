# Issue #100: Lineage workflow integration: standardize design review artifacts

## Problem

The issue workflow and LLD workflow currently do not use the canonical `docs/lineage/` structure for storing design review artifacts. This was developed organically in RCA-PDF-extraction-pipeline and needs to be formally integrated into the AgentOS workflows.

Currently:
- Issue workflow creates artifacts but placement is inconsistent
- LLD workflow stores drafts/verdicts in various locations
- No standardized "paper trail" for the design review process

## Solution

Update both workflows to use `docs/lineage/` as the canonical location for all design review artifacts.

### Affected Workflows

1. **Issue Workflow** (`tools/issue-workflow.py`)
   - Create `docs/lineage/active/{issue-id}/` folder when starting
   - Save brief as `001-brief.md`
   - Save each draft iteration as `{NNN}-draft.md`
   - Save each Gemini verdict as `{NNN}-verdict.md`
   - Save filing metadata as `{NNN}-filed.json`
   - Move folder to `docs/lineage/done/` when filed

2. **LLD Workflow** (`tools/lld-workflow.py`)
   - If running standalone (not via issue workflow), create lineage folder
   - Store all draft/verdict iterations in lineage folder
   - Reference lineage folder in LLD status tracking

### Lineage Artifact Sequence

```
001-brief.md      # Initial idea (from ideas/active/ or inline)
002-draft.md      # First LLD draft
003-verdict.md    # Gemini review #1
004-draft.md      # Revised draft
005-verdict.md    # Gemini review #2
006-filed.json    # Filing metadata (issue URL, timestamps)
```

### Folder Naming

`{issue-number}-{short-description}/`

Examples:
- `4-footnote-handling/`
- `87-implementation-workflow/`
- `98-brief-structure/`

## Acceptance Criteria

- [ ] Issue workflow creates `docs/lineage/active/{id}/` at start
- [ ] All briefs saved as `001-brief.md` in lineage folder
- [ ] All drafts saved as `{NNN}-draft.md` with incrementing numbers
- [ ] All verdicts saved as `{NNN}-verdict.md` with incrementing numbers
- [ ] Filing metadata saved as final `{NNN}-filed.json`
- [ ] Folder moves to `docs/lineage/done/` on successful filing
- [ ] LLD workflow integrates with lineage when called from issue workflow
- [ ] Standard 0009 already updated (DONE)
- [ ] new-repo-setup.py creates `docs/lineage/active/` and `docs/lineage/done/`

## Dependencies

- Standard 0009 updated with lineage structure (DONE - commit 1d5132c)
- RCA-PDF renamed `docs/audit/` to `docs/lineage/` (DONE - commit 76a13fc)

## Out of Scope

- Migrating existing lineage folders in other projects (manual)
- Retroactively creating lineage for past issues
- Changes to the Gemini review prompts themselves