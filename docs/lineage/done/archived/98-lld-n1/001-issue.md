# Issue #98: Brief Structure and Placement Standard

# Brief Structure and Placement Standard

## User Story
As a developer working across multiple projects,
I want a consistent standard for where briefs (ideas, proposals, technical debt notes) live and how they're structured,
So that I can quickly find, create, and manage working documents without confusion about naming or location.

## Objective
Establish a project-wide standard for brief placement (`ideas/` directory), naming (unnumbered kebab-case), structure (standard template), and lifecycle (draft â†’ active â†’ promoted/done).

## UX Flow

### Scenario 1: Creating a New Idea
1. Developer has a new idea for the project
2. Developer creates `ideas/backlog/my-new-idea.md` using the brief template
3. Developer fills in Problem and Proposal sections, sets Status to Draft
4. Result: Idea is captured in a consistent location with standard structure

### Scenario 2: Promoting a Brief to Active Work
1. Developer decides a backlog idea is ready for implementation
2. Developer moves file from `ideas/backlog/` to `ideas/active/`
3. Developer updates Status from Draft to Active
4. Result: Active work items are clearly separated from speculative ideas

### Scenario 3: Brief Becomes a GitHub Issue
1. Active brief needs tracking, collaboration, or formal prioritization
2. Developer creates GitHub issue from brief content
3. Issue gets assigned number (e.g., 10045)
4. Developer deletes brief or archives it
5. Result: Clear handoff from informal brief to formal issue with no number collision

### Scenario 4: Brief Completed Without Issue
1. Small active brief is implemented directly
2. Developer updates Status to Done
3. Developer deletes brief or moves to archive
4. Result: Clean lifecycle without unnecessary issue overhead

## Requirements

### Directory Structure
1. `ideas/` directory at project root (not inside `docs/`)
2. `ideas/active/` subdirectory for actionable briefs
3. `ideas/backlog/` subdirectory for draft/speculative ideas
4. Both directories created by `new-repo-setup.py`

### Naming Convention
1. Files use kebab-case: `header-normalization.md`
2. Files are NOT numbered: no `004-header-normalization.md`
3. Title format: `# Idea: [Title]`

### Template Structure
1. Frontmatter: Status, Effort, Value, Blocked by
2. Required sections: Problem, Proposal
3. Optional sections: Implementation, Next Steps
4. Status values: Draft, Active, Blocked, Done, Rejected

### Lifecycle Rules
1. Draft briefs live in `backlog/`
2. Active briefs live in `active/`
3. Promoted briefs become GitHub issues and are deleted
4. Done briefs are deleted or archived
5. Rejected briefs are deleted or moved to backlog with rejection note

## Technical Approach
- **Standard Update:** Add `ideas/` to `0009-canonical-project-structure.md` with rationale
- **Tooling Update:** Modify `new-repo-setup.py` to create `ideas/active/` and `ideas/backlog/`
- **Template Creation:** Create `docs/templates/0110-brief-template.md` with full structure
- **Inventory Update:** Add template to `docs/0003-file-inventory.md`

## Files to Create/Modify

| File | Change |
|------|--------|
| `docs/standards/0009-canonical-project-structure.md` | Add `ideas/` to root structure with rationale |
| `tools/new-repo-setup.py` | Add `ideas/active` and `ideas/backlog` to OTHER_STRUCTURE |
| `docs/templates/0110-brief-template.md` | Create new template file |
| `docs/0003-file-inventory.md` | Add new template to inventory |

## Dependencies
- None â€” this is a foundational standard

## Out of Scope (Future)
- Automated brief-to-issue promotion tooling â€” future enhancement
- Brief archival system â€” delete for now, archive pattern can come later
- Cross-project brief aggregation â€” out of scope for single-project standard

## Acceptance Criteria
- [ ] `ideas/` directory structure documented in canonical structure standard
- [ ] `new-repo-setup.py` creates `ideas/active/` and `ideas/backlog/` directories
- [ ] Brief template exists at `docs/templates/0110-brief-template.md`
- [ ] Template includes all required frontmatter fields (Status, Effort, Value)
- [ ] Template includes Problem and Proposal sections
- [ ] Lifecycle diagram included in standard documentation
- [ ] "What Goes Where" reference table included

## Definition of Done

### Implementation
- [ ] Standard document updated with `ideas/` directory specification
- [ ] `new-repo-setup.py` modified and tested
- [ ] Brief template created with all sections

### Tools
- [ ] `new-repo-setup.py` creates ideas directories on new projects
- [ ] Verify tool works on fresh directory

### Documentation
- [ ] Canonical structure standard updated
- [ ] Template documented with usage instructions
- [ ] Add files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Existing briefs migrated to new structure (if any)
- [ ] New project creation includes `ideas/` directories

## Testing Notes
1. Run `new-repo-setup.py` on a fresh directory and verify `ideas/active/` and `ideas/backlog/` are created
2. Create a brief using the template and verify all sections render correctly
3. Verify no conflicts with existing `docs/` directory structure