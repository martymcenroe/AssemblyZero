# Verdict Analyzer: Document Dependency Sync

When the verdict analyzer updates a template, related documents can become out of sync. This causes cascading failures in workflows that depend on consistent section numbers, field names, or structure.

## Problem Statement

The verdict analyzer (Issue #104) updates templates based on governance patterns. However:
1. Templates reference section numbers (e.g., "Section 10 Test Scenarios")
2. Review prompts reference the same section numbers
3. Workflow code parses sections by number/name

When a template is updated (sections renumbered, renamed, or restructured), **related documents are not updated**, causing:
- Review prompts referencing wrong sections
- Workflow parsers failing to find content
- Confusion between what Gemini expects and what workflows expect

### Concrete Example (Issue #117)

| Document | Test Scenarios Location |
|----------|------------------------|
| `0102-feature-lld-template.md` | Section **11** |
| `0702c-LLD-Review-Prompt.md` | References Section **10** |
| `testing/nodes/load_lld.py` | Expects Section **10** |

The template was updated (possibly by verdict analyzer) but the review prompt and workflow code were not synced.

## User Story

As a workflow maintainer,
I want the verdict analyzer to track document dependencies and sync related documents when a template changes,
So that templates, review prompts, and workflow parsers stay consistent.

## Proposed Solution

### Document Dependency Registry

Create a registry mapping templates to their dependent documents:

```yaml
# docs/templates/document-dependencies.yaml
0102-feature-lld-template.md:
  sync_targets:
    - docs/skills/0702c-LLD-Review-Prompt.md
    - assemblyzero/workflows/testing/nodes/load_lld.py
  sync_fields:
    - section_numbers:
        - "Test Scenarios": ["Section 10", "Section 11"]
        - "Verification": ["Section 10", "Section 11"]
    - field_names:
        - issue_number
        - test_plan_section
```

### Verdict Analyzer Extension

Add a `--sync-deps` flag to the `recommend` command:

```bash
# Check for sync issues (dry-run)
poetry run python tools/verdict-analyzer.py recommend \
  docs/templates/0102-feature-lld-template.md --sync-deps

# Apply template changes AND sync dependencies
poetry run python tools/verdict-analyzer.py recommend \
  docs/templates/0102-feature-lld-template.md --apply --sync-deps --no-dry-run
```

### Sync Actions

When `--sync-deps` is specified:
1. Load dependency registry for the template
2. After applying template changes, check each dependent document
3. For each sync field (section numbers, field names):
   - Find occurrences in dependent documents
   - Update to match new template structure
4. Report changes made or conflicts found

### Validation Mode

Add a `validate-sync` command to check for existing drift:

```bash
# Check if all documents are in sync
poetry run python tools/verdict-analyzer.py validate-sync

# Output:
# SYNC OK: 0101-issue-template.md
# SYNC DRIFT: 0102-feature-lld-template.md
#   - 0702c-LLD-Review-Prompt.md: References "Section 10" but template has "Section 11"
#   - load_lld.py: Expects "Section 10" but template has "Section 11"
```

## Requirements

1. Create document dependency registry (`docs/templates/document-dependencies.yaml`)
2. Extend verdict analyzer with `--sync-deps` flag
3. Add `validate-sync` command for drift detection
4. Update runbook 0910 with sync workflow

## Acceptance Criteria

- [ ] Dependency registry exists and covers LLD template
- [ ] `validate-sync` command detects the #117 drift
- [ ] `--sync-deps` flag updates dependent documents when template changes
- [ ] Runbook updated with sync workflow

## Technical Notes

- Section number extraction: regex for `## N. Title` patterns
- Review prompt updates: find/replace section references
- Workflow code updates: may require manual review (flag for human attention)

## Related

- Issue #117: LLD template Section 11 out of sync with workflows expecting Section 10
- Issue #104: Verdict Analyzer
- Runbook 0910: Verdict Analyzer
