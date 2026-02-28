# Brief: Verdict Analyzer Document Sync

**Status:** Active
**Created:** 2026-02-02
**Updated:** 2026-02-28
**Effort:** Medium
**Priority:** Medium
**Tracking Issue:** None

---

## Problem

The verdict analyzer updates templates (issue template, LLD template) based on patterns found in Gemini review verdicts. When a template's section numbering changes, downstream documents that reference specific section numbers break silently. This has already happened: Issue #117 identified Section 10/11 drift in the LLD template, and `workflows/testing/nodes/load_lld.py` now handles both Section 10 (LLD format) and Section 9 (Implementation Spec format) as a workaround.

The workaround proves the problem recurs. Each time a template changes, someone must manually find and update all documents that reference its sections.

## What Already Exists

- **`tools/verdict-analyzer.py`** — subcommands: `scan` (populate verdict database), `stats` (statistics), `recommend` (generate template recommendations), `clear` (reset database)
- **`tools/verdict_analyzer/`** — module with `database.py`, `parser.py`, `patterns.py`, `scanner.py`, `template_updater.py`
- **`workflows/testing/nodes/load_lld.py`** — handles both Section 10 and Section 9 as evidence of recurring section drift
- **`workflows/implementation_spec/nodes/load_lld.py`** — reads Section 2.1 (Files to Modify table) from LLDs

## The Gap

- No registry of which documents depend on which template sections
- No validation that section references are still valid after a template change
- `recommend --apply` can update a template but has no way to propagate changes to dependents

## Proposed Solution

### 1. Dependency Registry

A YAML file (`docs/standards/template-dependencies.yaml`) mapping templates to their dependents:

```yaml
templates:
  docs/standards/0101-issue-creation-template.md:
    dependents:
      - path: assemblyzero/workflows/requirements/nodes/draft_issue.py
        sections: ["Section 3: Acceptance Criteria"]
  docs/standards/0301-lld-design-template.md:
    dependents:
      - path: assemblyzero/workflows/testing/nodes/load_lld.py
        sections: ["Section 9", "Section 10"]
      - path: assemblyzero/workflows/implementation_spec/nodes/load_lld.py
        sections: ["Section 2.1"]
```

### 2. `validate-sync` Subcommand

New subcommand for `verdict-analyzer.py`:

```
poetry run python tools/verdict-analyzer.py validate-sync
```

- Reads the dependency registry
- For each template, checks if referenced sections still exist (by heading text match)
- Reports mismatches: "Section 10 referenced by `load_lld.py` not found in template (renamed to Section 11?)"

### 3. Pre-apply Validation

Before `recommend --apply` modifies a template, run `validate-sync` and warn if the change would break dependents. Do not block — warn and proceed (the human decides).

## Integration Points

- **Verdict analyzer** (`tools/verdict-analyzer.py`) — new `validate-sync` subcommand
- **Template updater** (`verdict_analyzer/template_updater.py`) — pre-apply validation hook
- **CI** — optional: run `validate-sync` on PRs that touch template files

## Acceptance Criteria

- [ ] Dependency registry (YAML) maps templates to dependent files and sections
- [ ] `validate-sync` detects section reference mismatches
- [ ] `validate-sync` reports clear, actionable output (which file, which section, what's wrong)
- [ ] `recommend --apply` warns (does not block) when changes affect dependents
- [ ] Registry covers existing known dependencies (LLD template → load_lld.py)

## Dependencies & Cross-References

- **Issue #117** — original Section 10/11 drift issue
- **`tools/verdict-analyzer.py`** — the tool being enhanced
- **`workflows/testing/nodes/load_lld.py`** — primary example of section-dependent code
