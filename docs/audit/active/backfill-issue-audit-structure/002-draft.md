# Backfill Audit Directory Structure for Existing GitHub Issues

## User Story
As a project maintainer,
I want to backfill the `docs/audit/` directory structure for all existing GitHub issues across repos,
So that historical issues have the same audit trail as issues created under the new governance workflow (#62).

## Objective
Create a Python CLI tool that fetches existing GitHub issues and generates the standardized audit directory structure (`001-issue.md`, `002-comments.md`, `003-metadata.json`) for each one.

## UX Flow

### Scenario 1: Backfill a Single Repo
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS`
2. Tool fetches all issues (open + closed) via `gh issue list`
3. Tool generates slug for each issue (e.g., `62-governance-workflow-stategraph`)
4. Tool creates `docs/audit/done/{slug}/` for closed issues, `docs/audit/active/{slug}/` for open issues
5. Tool writes `001-issue.md`, `002-comments.md`, `003-metadata.json` into each directory
6. Result: Complete audit trail for all existing issues

### Scenario 2: Dry Run
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --dry-run`
2. Tool fetches issues and computes directories
3. Tool prints what would be created without writing anything
4. Result: User previews changes before committing

### Scenario 3: Directory Already Exists
1. User runs the tool with `--skip-existing`
2. Tool encounters an issue whose slug directory already exists
3. Tool skips that issue and logs a message
4. Result: No data is overwritten

### Scenario 4: All Registered Repos
1. User runs `python tools/backfill_issue_audit.py --all-registered`
2. Tool reads `project-registry.json` for the list of repos
3. Tool processes each repo sequentially
4. Result: All repos backfilled in one command

### Scenario 5: GitHub CLI Not Authenticated
1. User runs the tool without `gh auth login`
2. Tool catches the auth error from `gh`
3. Tool prints: `Error: GitHub CLI not authenticated. Run 'gh auth login' first.`
4. Result: Clear failure message, no partial writes

## Requirements

### Slug Generation
1. Lowercase the issue title
2. Replace spaces and underscores with hyphens
3. Remove all characters except `[a-z0-9-]`
4. Collapse consecutive hyphens into one
5. Strip leading/trailing hyphens
6. Prepend issue number: `{number}-{slug}`

### File Generation
1. `001-issue.md` — Issue title as `#` heading, followed by issue body verbatim
2. `002-comments.md` — All comments formatted with `## @username (YYYY-MM-DD)` headings; file omitted if no comments
3. `003-metadata.json` — Issue number, URL, state, labels, linked PR (if closed by PR), timestamps, `backfilled_at` timestamp

### CLI Options
1. `--repo OWNER/NAME` — Target a single repo
2. `--all-registered` — Process all repos in `project-registry.json`
3. `--dry-run` — Print planned actions without writing files
4. `--skip-existing` — Skip issues whose audit directory already exists
5. `--open-only` — Only process open issues

### Data Integrity
1. Use `gh issue list --json` and `gh issue view --json` for structured data (no HTML scraping)
2. Write files atomically (write to temp, then rename) to avoid partial writes on failure
3. Log each directory created to stdout

## Technical Approach
- **CLI parsing:** `argparse` — no external dependencies required
- **GitHub data:** Shell out to `gh issue list --repo {repo} --state all --json number,title,body,state,labels,createdAt,closedAt,url --limit 999` and `gh issue view {number} --repo {repo} --json comments`
- **Slug generation:** Pure Python function matching `agentos/workflows/issue/audit.py` algorithm
- **File I/O:** `pathlib` for directory creation, `json.dumps` for metadata, plain string writes for markdown
- **Registry lookup:** Load `project-registry.json` from repo root for `--all-registered`

## Security Considerations
- Tool only reads from GitHub API (via `gh`) and writes to local filesystem under `docs/audit/`
- No secrets handled; relies on existing `gh` authentication
- No network writes; all output is local files

## Files to Create/Modify
- `tools/backfill_issue_audit.py` — New CLI tool (main script)
- `docs/audit/active/` — Created directories for open issues
- `docs/audit/done/` — Created directories for closed issues

## Dependencies
- Issue #62 (governance workflow) should be merged first so the audit directory convention is established
- `gh` CLI must be installed and authenticated

## Out of Scope (Future)
- **Incremental sync** — Re-running to pick up new comments added after backfill (future issue)
- **LLM-generated summaries** — This is raw data capture only; synthesis is a separate concern
- **Cross-repo linking** — Mapping issues that reference other repos' issues
- **PR body capture** — Only issue + comments are captured; PR review threads are deferred

## Acceptance Criteria
- [ ] Running `--repo martymcenroe/AgentOS` creates `docs/audit/done/{slug}/` for every closed issue and `docs/audit/active/{slug}/` for every open issue
- [ ] Each slug directory contains `001-issue.md`, `002-comments.md` (if comments exist), and `003-metadata.json`
- [ ] Slug generation matches the algorithm in `agentos/workflows/issue/audit.py` (lowercase, hyphens, number-prefixed)
- [ ] `--dry-run` produces no filesystem changes and prints planned actions
- [ ] `--skip-existing` skips directories that already exist without error
- [ ] `--all-registered` processes every repo listed in `project-registry.json`
- [ ] Tool exits with clear error message if `gh` is not authenticated
- [ ] No external Python dependencies required (stdlib only)

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing

### Tools
- [ ] `tools/backfill_issue_audit.py` created and executable
- [ ] Document tool usage in script docstring and `--help` output

### Documentation
- [ ] Update wiki pages affected by this change
- [ ] Update README.md if user-facing
- [ ] Update relevant ADRs or create new ones
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes
- Test with `--dry-run` first to verify slug generation and directory mapping
- To test error handling: run without `gh` authenticated, or point to a nonexistent repo
- To test `--skip-existing`: run the tool twice and verify second run skips all directories
- Spot-check a few `001-issue.md` files against the actual GitHub issue to confirm body fidelity