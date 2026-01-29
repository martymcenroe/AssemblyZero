# Add [F]ile Option to Issue Workflow Exit

## User Story
As a developer using the issue drafting workflow,
I want to file issues directly from the workflow,
So that I can complete the full issue creation process without manual CLI steps or label management.

## Objective
Add a `[F]ile` option to `run_issue_workflow.py` that creates missing labels and files the issue to GitHub in one step.

## UX Flow

### Scenario 1: Happy Path - File with Existing Labels
1. User completes draft iteration, reaches satisfactory state
2. User selects `[F]ile` option
3. System parses draft for title, body, and labels
4. System checks all labels exist (they do)
5. System runs `gh issue create` with extracted content
6. System displays: `✓ Created: https://github.com/owner/repo/issues/123`
7. System updates `003-metadata.json` with issue URL

### Scenario 2: File with Missing Labels
1. User selects `[F]ile` option
2. System parses draft and finds 4 labels
3. System checks labels: 2 exist, 2 missing
4. System creates missing labels with category-appropriate colors
5. System displays creation progress:
   ```
   Checking labels...
     ✓ enhancement (exists)
     ✓ tooling (exists)
     ✓ audit (creating...)
     ✓ maintenance (creating...)
   ```
6. System files issue with all 4 labels attached
7. Result: Issue created with full label set

### Scenario 3: Draft Missing Title
1. User selects `[F]ile` option
2. System attempts to parse draft, finds no H1 heading
3. System displays: `✗ Error: Draft missing title (no H1 found)`
4. System returns to options prompt without filing

### Scenario 4: GitHub CLI Not Authenticated
1. User selects `[F]ile` option
2. System attempts `gh` command, auth check fails
3. System displays: `✗ Error: GitHub CLI not authenticated. Run 'gh auth login' first.`
4. System returns to options prompt

## Requirements

### Draft Parsing
1. Extract title from first `# ` line in draft
2. Extract body from `## User Story` through content before `## Labels`
3. Parse labels from backtick-delimited list on `## Labels` line
4. Handle malformed labels line gracefully (warn and continue without labels)

### Label Management
1. Check label existence via `gh label list --search`
2. Create missing labels with category-based color scheme:
   - `enhancement`, `feature` → `#238636` (green)
   - `bug`, `fix` → `#d73a4a` (red)
   - `tooling`, `maintenance` → `#7057ff` (purple)
   - `audit`, `governance` → `#fbca04` (yellow)
   - Unknown category → `#6e7681` (gray)
3. Display progress for each label check/creation

### Issue Filing
1. Use `gh issue create` with `--title`, `--body`, and `--label` flags
2. Capture and display resulting issue URL
3. Update `003-metadata.json` with `github_issue_url` field

### UX Polish
1. Rename `[M]anual` option to `[E]xit` for clarity
2. Add `[F]ile` to options display between `[A]pprove` and `[E]xit`
3. Show spinner or progress indicators during GitHub operations

## Technical Approach
- **Draft Parser:** Add `parse_issue_draft()` function to extract title, body, labels from markdown
- **Label Manager:** Add `ensure_labels_exist()` function with color mapping and `gh label create` calls
- **GitHub Integration:** Add `file_issue()` function wrapping `gh issue create` with proper escaping
- **Metadata Update:** Extend existing `003-metadata.json` writer to include issue URL

## Security Considerations
- Uses existing `gh` CLI authentication; no credential storage
- Label creation limited to repository scope of authenticated user
- No sensitive data extracted from drafts

## Files to Create/Modify
- `agentos/workflows/issue/run_issue_workflow.py` — Add `[F]ile` option handler, integrate new functions
- `agentos/workflows/issue/draft_parser.py` — New file for markdown parsing logic
- `agentos/workflows/issue/github_integration.py` — New file for `gh` CLI wrapper functions
- `agentos/workflows/issue/label_colors.py` — New file for label category → color mapping

## Dependencies
- None - standalone enhancement

## Out of Scope (Future)
- Moving draft from `active/` to `done/` after filing — deferred until issue lifecycle is clearer
- Automatic assignment of filed issues — future enhancement
- PR linking from filed issues — separate workflow concern

## Acceptance Criteria
- [ ] `[F]ile` option appears in workflow prompt after `[A]pprove`
- [ ] Selecting `[F]` with valid draft creates GitHub issue
- [ ] Missing labels are created with appropriate colors before filing
- [ ] Issue URL is displayed after successful creation
- [ ] `003-metadata.json` is updated with `github_issue_url`
- [ ] Draft with no H1 displays clear error and returns to prompt
- [ ] Unauthenticated `gh` CLI displays clear error and returns to prompt
- [ ] Malformed labels line warns but still files issue
- [ ] `[M]anual` option renamed to `[E]xit`

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing
- [ ] Integration test with mock `gh` CLI responses

### Tools
- [ ] Shared label-checking logic extracted for use by `tools/backfill_issue_audit.py`
- [ ] Document `--dry-run` flag for testing without actual GitHub API calls

### Documentation
- [ ] Update wiki pages affected by this change
- [ ] Update README.md if user-facing
- [ ] Update relevant ADRs or create new ones
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS (if security-relevant)
- [ ] Run 0810 Privacy Audit - PASS (if privacy-relevant)
- [ ] Run 0817 Wiki Alignment Audit - PASS (if wiki updated)

## Testing Notes
- Use `--dry-run` flag to test parsing and label checking without creating GitHub resources
- Test with draft files that have: no title, no labels line, malformed labels, all labels existing, some labels missing
- Test unauthenticated state by running `gh auth logout` before workflow

## Labels
`enhancement`, `tooling`, `workflow`, `dx`