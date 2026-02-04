# Issue #84: Add [F]ile Option to Issue Workflow Exit

# Add [F]ile Option to Issue Workflow Exit

## User Story
As a developer using the issue workflow,
I want to file issues directly from the drafting loop,
So that I don't have to manually copy content and run `gh` commands after approving a draft.

## Objective
Add a `[F]ile` option to `run_issue_workflow.py` that automatically creates missing labels and files the issue to GitHub in one step.

## UX Flow

### Scenario 1: Happy Path - Filing with Existing Labels
1. User completes iterating on draft and sees exit options
2. User types `F` to file directly
3. System parses draft for title, body, and labels
4. System checks each label exists (all do)
5. System runs `gh issue create` with extracted content
6. System displays: `✓ Created: https://github.com/owner/repo/issues/73`
7. System updates `003-metadata.json` with issue URL

### Scenario 2: Happy Path - Filing with Missing Labels
1. User types `F` to file
2. System finds 2 of 4 labels don't exist
3. System creates missing labels with category-appropriate colors
4. System displays creation progress for each label
5. System files issue with all labels attached
6. System displays issue URL

### Scenario 3: Error - gh CLI Not Authenticated
1. User types `F` to file
2. System attempts to verify `gh` authentication
3. System fails fast with: `Error: gh CLI not authenticated. Run 'gh auth login' first.`
4. User remains in workflow, can still use other options

### Scenario 4: Error - Malformed Draft
1. User types `F` to file
2. System cannot find H1 title in draft
3. System displays: `Error: Draft missing title (no H1 found)`
4. User remains in workflow to revise or exit manually

### Scenario 5: Warning - Malformed Labels Line
1. User types `F` to file
2. System finds title and body but labels line is unparseable
3. System warns: `Warning: Could not parse labels, filing without labels`
4. System files issue without labels
5. System displays issue URL

## Requirements

### CLI Integration
1. Verify `gh` CLI authentication before attempting any operations
2. Use `gh label list --json name` to check existing labels
3. Use `gh label create` with appropriate color for missing labels
4. Use `gh issue create --title --body --label` for filing
5. **All subprocess calls MUST use `subprocess.run()` with list arguments (NOT `shell=True`)** to prevent shell injection from draft content containing special characters

### Draft Parsing
1. Extract title from first `# ` line in draft
2. Extract body from `## User Story` through content before `## Labels`
3. Parse labels from backtick-delimited list on `## Labels` line
4. Handle missing sections gracefully with clear error messages

### Label Color Mapping
1. `enhancement`, `feature` → `#2ea44f` (green)
2. `bug`, `fix`, `breaking` → `#d73a4a` (red)
3. `tooling`, `maintenance`, `refactor` → `#6f42c1` (purple)
4. `audit`, `governance`, `compliance` → `#fbca04` (yellow)
5. `documentation`, `docs` → `#0075ca` (blue)
6. Unknown/default → `#ededed` (gray)

### Metadata Updates
1. Update `003-metadata.json` with `github_issue_url` field
2. Update `003-metadata.json` with `filed_at` timestamp
3. Preserve all existing metadata fields

## Technical Approach
- **Draft Parser:** New function `parse_draft_for_filing(draft_path)` returns `{title, body, labels}`
- **Label Manager:** New function `ensure_labels_exist(labels, repo)` creates missing labels with colors
- **Issue Filer:** New function `file_issue(title, body, labels, repo)` wraps `gh issue create`
- **Auth Check:** New function `verify_gh_auth()` fails fast if not authenticated
- **Subprocess Safety:** All `gh` CLI invocations use `subprocess.run(['gh', 'issue', 'create', '--title', title, ...])` pattern with arguments as list elements, never string interpolation

## Security Considerations
- Uses existing `gh` CLI authentication - no new credentials stored
- Only creates labels, does not delete or modify existing ones
- Draft content is read-only during filing process
- **Shell Injection Prevention:** All subprocess calls use `subprocess.run()` with argument lists (not `shell=True`) to safely handle draft content containing quotes, semicolons, or other special characters
- **Data Transmission:** Data is processed locally and transmitted solely to the configured GitHub repository via the authenticated `gh` CLI

## Files to Create/Modify
- `agentos/workflows/issue/run_issue_workflow.py` — Add `[F]ile` option to menu, integrate filing logic
- `agentos/workflows/issue/file_issue.py` — New module with `parse_draft_for_filing()`, `ensure_labels_exist()`, `file_issue()`
- `agentos/workflows/issue/label_colors.py` — New module with label category → color mapping

## Dependencies
- None - this is a standalone enhancement

## Out of Scope (Future)
- Moving draft from `active/` to `done/` — issue may not be implemented yet
- Renaming `[M]anual` to `[E]xit` — separate UX cleanup issue
- Dry-run mode to preview without filing — nice-to-have for future
- Integration with issue templates from `.github/ISSUE_TEMPLATE/` — future enhancement

## Acceptance Criteria
- [ ] `[F]ile` option appears in workflow exit menu
- [ ] Draft parsing matches the rules defined in 'Draft Parsing' requirements section (H1 for title, content for body, backticks for labels)
- [ ] Missing labels are created with category-appropriate colors
- [ ] Issue is filed via `gh issue create` and URL is displayed
- [ ] `003-metadata.json` is updated with issue URL and timestamp
- [ ] Unauthenticated `gh` CLI produces clear error without crashing
- [ ] Missing title produces clear error and keeps user in workflow
- [ ] Malformed labels line produces warning and files without labels
- [ ] All subprocess calls use list arguments (not `shell=True`)

## Definition of Done

### Implementation
- [ ] Core filing feature implemented in `run_issue_workflow.py`
- [ ] Draft parsing logic with error handling
- [ ] Label creation with color mapping
- [ ] Unit tests for draft parsing
- [ ] Unit tests for label color mapping
- [ ] Integration test with mock `gh` CLI

### Tools
- [ ] Consider extracting label logic to `tools/ensure_labels.py` for reuse

### Documentation
- [ ] Update workflow documentation with new `[F]ile` option
- [ ] Document label color conventions
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

### Manual Testing
1. Run workflow: `python agentos/workflows/issue/run_issue_workflow.py`
2. Create a draft with known labels (some existing, some new)
3. Select `[F]ile` and verify label creation output
4. Verify issue appears in GitHub with correct title, body, labels
5. Check `003-metadata.json` for issue URL

### Forcing Error States
- **Unauthenticated:** Run `gh auth logout` before testing
- **Missing title:** Manually edit draft to remove H1 line
- **Malformed labels:** Edit draft labels line to `## Labels: broken`
- **Network failure:** Disconnect network after auth check
- **Shell injection test:** Create draft with title containing `; rm -rf /` to verify safe handling

## Effort Estimate
**Size:** Small/Medium

## Labels
`enhancement` `tooling` `workflow` `developer-experience`