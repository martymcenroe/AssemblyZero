# Standard 0012: Lineage File Versioning

## Overview

When an LLD is regenerated for an issue, a new lineage directory is created. This standard defines how to preserve historical lineage data while maintaining a clean active directory.

## Directory Structure

```
docs/lineage/
├── active/           # Current/in-progress lineage
│   ├── 78-lld/       # Latest lineage for issue 78
│   ├── 78-lld-n1/    # Previous attempt (if regenerated)
│   └── 78-lld-n2/    # Two attempts ago (if regenerated again)
│
└── done/             # Completed issues (all versions)
    ├── 53-lld/       # Final version
    ├── 53-lld-n1/    # Previous attempts preserved
    └── ...
```

## Workflow: Generating an LLD

### Pre-Generation Check (REQUIRED)

Before generating an LLD, the requirements workflow MUST:

1. **Check for existing LLD:** Look for `docs/lld/active/LLD-{issue}.md`
2. **Check for existing lineage:** Look for `docs/lineage/active/{issue}-lld/`

If either exists:

```
WARNING: LLD already exists for issue {issue}.
  - LLD file: docs/lld/active/LLD-{issue}.md
  - Lineage: docs/lineage/active/{issue}-lld/

Regenerating will:
  - Delete the existing LLD file
  - Move existing lineage to {issue}-lld-n1

Type YES to proceed, or anything else to abort:
```

**User must type YES (exact match) to proceed.**

### Regeneration Steps

When user confirms YES:

1. **Delete existing LLD file:**
   ```bash
   rm docs/lld/active/LLD-{issue}.md
   ```

2. **Shift existing lineage versions:**
   ```bash
   # If n1 exists, shift to n2
   mv active/{issue}-lld-n1 active/{issue}-lld-n2

   # Rename current to n1
   mv active/{issue}-lld active/{issue}-lld-n1
   ```

3. **Generate new LLD** - creates fresh files

4. **Verdict analyzer** will automatically pick up all versions (no code changes needed)

## Workflow: Issue Completed

When an issue is merged and closed:

1. **Move LLD to done:**
   ```bash
   mv docs/lld/active/LLD-{issue}.md docs/lld/done/
   ```

2. **Move ALL lineage versions to done:**
   ```bash
   mv active/{issue}-lld done/
   mv active/{issue}-lld-n1 done/     # if exists
   mv active/{issue}-lld-n2 done/     # if exists
   mv active/{issue}-testing done/    # if exists
   ```

3. **Verdict analyzer** continues to track them (filepath is primary key)

## Verdict Analyzer Compatibility

No code changes required. The scanner searches:
- `docs/lineage/active/` (default)
- `docs/lineage/` (broader, includes done/)

Database uses `filepath` as primary key, so all versions coexist:
- `active/78-lld/verdict.md` = one record
- `active/78-lld-n1/verdict.md` = different record
- `done/78-lld/verdict.md` = different record

## Implementation Note

The pre-generation check should be implemented in:
- `tools/run_requirements_workflow.py` (CLI entry point)
- Or `assemblyzero/workflows/requirements/nodes/load_input.py` (workflow node)

This is a **manual check** until automated (see Issue #XXX if created).

## Stale Test Directories

Orphaned test directories (from development/debugging) can be deleted:
```
test-simple-feature/
test-timer-feature/
test-workflow-auto-routing/
test-working-version/
backfill-issue-audit-structure/
parallel-workflow-execution/
```

These have no associated issues and are development artifacts.
