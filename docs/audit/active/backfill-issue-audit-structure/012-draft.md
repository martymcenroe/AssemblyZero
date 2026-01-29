# Backfill Audit Directory Structure for Existing GitHub Issues

## User Story
As a project maintainer,
I want to automatically generate audit directories for existing GitHub issues,
So that all issues (past and present) have consistent local audit trails matching our governance workflow.

## Objective
Create a Python CLI tool that backfills the `docs/audit/` directory structure for all existing GitHub issues across registered repositories.

## UX Flow

### Scenario 1: Backfill Single Repository
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS`
2. Tool fetches all issues via `gh issue list --json`
3. Tool generates slug for each issue (e.g., `62-governance-workflow-stategraph`)
4. Tool creates directories under `docs/audit/done/` (closed) or `docs/audit/active/` (open)
5. Tool writes `001-issue.md`, `002-comments.md`, `003-metadata.json` to each directory
6. Result: Complete audit trail for all issues in that repo

### Scenario 2: Dry Run Mode
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --dry-run`
2. Tool fetches and processes issues
3. Tool prints what would be created without writing files
4. Result: User previews changes before committing

### Scenario 3: Skip Existing Directories
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --skip-existing`
2. Tool encounters issue #62 which already has `docs/audit/done/62-governance-workflow-stategraph/`
3. Tool skips this issue and continues to next
4. Result: Only new issues get backfilled, existing audit trails preserved

### Scenario 4: Backfill All Registered Repos
1. User runs `python tools/backfill_issue_audit.py --all-registered`
2. Tool reads `project-registry.json` for list of repos
3. Tool iterates through each repo and backfills
4. Result: Audit directories created across entire project ecosystem

### Scenario 5: Issue Has No Comments
1. Tool processes issue #45 which has no comments
2. Tool creates `001-issue.md` and `003-metadata.json`
3. Tool creates `002-comments.md` containing only the text `No comments found.`
4. Result: Graceful handling of issues without discussion

### Scenario 6: Verbose Debugging Mode
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --verbose`
2. Tool outputs detailed logging including API responses, slug transformations, and file write operations
3. Result: User can debug issues with specific issue processing

### Scenario 7: API Timeout During Batch Processing (Fail Open)
1. Tool is processing issue #50 of 100
2. `gh issue view` times out or returns an error
3. Tool logs the error with issue number and error message to stderr
4. Tool increments error counter and continues to issue #51
5. Result: At completion, tool reports "Processed 99/100 issues. 1 error(s) logged."

### Scenario 8: Fatal Error - Authentication Failure (Fail Fast)
1. User runs tool without valid `gh` authentication
2. Tool attempts first API call
3. Tool receives authentication error
4. Tool aborts immediately with non-zero exit code and error message
5. Result: No partial processing, clear error for user to fix auth

### Scenario 9: Rate Limit Handling (Fail Fast with Exponential Backoff)
1. Tool is processing a large repository with 200+ issues
2. GitHub API returns `429 Too Many Requests` response
3. Tool logs the rate limit warning to stderr
4. Tool implements exponential backoff: wait 1s, retry; if still 429, wait 2s, retry; then 4s, 8s, up to max 60s
5. If retries exhausted (5 attempts), tool aborts with Fail Fast behavior and non-zero exit code
6. Result: Tool gracefully handles transient rate limits but fails fast on persistent rate limiting; user can re-run with `--skip-existing` to resume

### Scenario 10: Limit Processing for Debugging
1. User runs `python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS --limit 5`
2. Tool processes only the first 5 issues
3. Result: Quick debugging loop before running full batch

## Requirements

### CLI Interface
1. Accept `--repo OWNER/REPO` flag for single repository targeting
2. Accept `--all-registered` flag to process all repos in `project-registry.json`
3. Accept `--dry-run` flag to preview without writing
4. Accept `--skip-existing` flag to preserve existing audit directories
5. Accept `--open-only` flag to process only open issues
6. Accept `--verbose` flag for detailed debug output
7. Accept `--limit N` flag to process only the first N issues (for debugging)
8. Provide clear progress output showing issues processed

### Slug Generation
1. Implement slug algorithm matching `agentos/workflows/issue/audit.py` (import from shared utility module if available to prevent drift)
2. Lowercase the title
3. Replace spaces and underscores with hyphens
4. Remove special characters (keep alphanumeric and hyphens only via regex `[^a-z0-9-]`)
5. Collapse multiple consecutive hyphens to single hyphen (via regex `-+` → `-`)
6. Strip leading/trailing hyphens
7. If resulting string is empty, set string to `untitled`
8. Prepend issue number: `{number}-{slug}`
9. Handle edge cases: empty titles become `{number}-untitled`, all-special-character titles become `{number}-untitled`

### File Generation
1. Create `001-issue.md` with issue title as H1 and body as content
2. Create `002-comments.md` with all comments, each prefixed by author and date; if no comments exist, file contains only `No comments found.`
3. Create `003-metadata.json` with issue metadata (number, URL, state, labels, timestamps, linked PRs)
4. Place files in `docs/audit/done/{slug}/` for closed issues
5. Place files in `docs/audit/active/{slug}/` for open issues

### Data Fetching
1. Use `gh issue list` with JSON output for issue enumeration
2. Use `gh issue view` with JSON output for full issue details including comments
3. Handle pagination for repos with many issues
4. Include linked PR detection from timeline events or issue body references

### Error Handling Strategy
1. **Fail Open (Log and Continue):** For individual issue processing errors (API timeouts, malformed data), log the error to stderr and continue processing remaining issues
2. **Fail Fast:** For fatal errors (invalid repo, authentication failure, filesystem permission denied), abort immediately with non-zero exit code
3. **Fail Fast with Exponential Backoff:** For HTTP 429 (Rate Limit) errors, implement exponential backoff (1s, 2s, 4s, 8s, up to 60s max) with 5 retry attempts; if retries exhausted, abort immediately with non-zero exit code
4. At completion, report summary: total issues, successful, skipped, and failed counts
5. Exit with code 0 if all issues processed successfully, exit with code 1 if any issues failed

## Technical Approach
- **CLI Parsing:** `argparse` for command-line interface
- **GitHub API:** `subprocess` calls to `gh` CLI using list argument format (e.g., `subprocess.run(['gh', 'issue', 'list', '--repo', repo_name, '--json', 'number,title,state'], ...)`) — **never use `shell=True`** to prevent command injection
- **Slug Generation:** Pure Python string manipulation (no external dependencies); verify if logic can be imported from a shared utility module in `agentos/workflows/issue/audit.py` rather than duplicated to prevent drift
- **File I/O:** `pathlib` for cross-platform path handling
- **JSON Handling:** Standard library `json` module
- **Date Formatting:** `datetime` for ISO timestamp parsing and formatting
- **Rate Limit Handling:** `time.sleep()` with exponential backoff for 429 responses

## Security Considerations
- Tool only reads from GitHub API (no write operations to remote)
- Respects existing `gh` CLI authentication
- No sensitive data stored—all content already public in GitHub issues
- Local file writes restricted to `docs/audit/` directory tree
- **All `subprocess` calls MUST use list argument format** (e.g., `['gh', 'issue', 'list', ...]`) and **MUST NOT use `shell=True`** to prevent shell injection attacks via malformed `--repo` arguments

## Files to Create/Modify
- `tools/backfill_issue_audit.py` — Main CLI tool (new file)
- `tools/fixtures/` — Static JSON fixtures for offline unit testing (new directory)
- `docs/audit/done/` — Directory for closed issue audits (created by tool)
- `docs/audit/active/` — Directory for open issue audits (created by tool)

## Dependencies
- Requires `gh` CLI installed and authenticated
- Requires `project-registry.json` for `--all-registered` mode

## Out of Scope (Future)
- **Incremental sync** — detecting new comments since last backfill (future enhancement)
- **PR audit backfill** — separate tool for pull request audit trails
- **Cross-repo linking** — detecting references between repos
- **LLM summarization** — generating brief/summary from issue content
- **GraphQL batching** — using `gh api graphql` for performance optimization on extremely large repos

## Acceptance Criteria
- [ ] Running `--repo martymcenroe/AgentOS` creates audit directories for all issues
- [ ] Closed issues appear under `docs/audit/done/`
- [ ] Open issues appear under `docs/audit/active/`
- [ ] Slug format matches `{number}-{slugified-title}` pattern
- [ ] `001-issue.md` contains issue title and body
- [ ] `002-comments.md` contains all comments with author and timestamp
- [ ] `003-metadata.json` contains valid JSON with required fields
- [ ] `--dry-run` prints actions without creating files
- [ ] `--skip-existing` preserves directories that already exist
- [ ] `--all-registered` processes multiple repos from registry
- [ ] `--verbose` outputs detailed debug information including API responses and file operations
- [ ] `--limit N` processes only the first N issues for quick debugging loops
- [ ] Tool handles issues with no comments by creating `002-comments.md` containing `No comments found.`
- [ ] Tool handles issues with special characters in titles using the slug algorithm: lowercase → replace spaces/underscores with hyphens → remove non-alphanumeric characters except hyphens → collapse consecutive hyphens → strip leading/trailing hyphens → check for empty string and set to `untitled` if empty → prepend issue number
- [ ] Tool logs errors for individual issue failures and continues processing (Fail Open)
- [ ] Tool aborts immediately on fatal errors (invalid repo, auth failure) (Fail Fast)
- [ ] Tool implements exponential backoff for HTTP 429 rate limit errors and aborts after 5 failed retries (Fail Fast with Backoff)
- [ ] Tool reports processing summary at completion (total, successful, skipped, failed)
- [ ] All `subprocess` calls use list argument format without `shell=True`

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing using static JSON fixtures (offline-capable)
- [ ] Integration test with real GitHub repo

### Tools
- [ ] `tools/backfill_issue_audit.py` created and executable
- [ ] `tools/fixtures/` directory with mock `gh` CLI JSON responses for unit tests
- [ ] Tool usage documented in script docstring

### Documentation
- [ ] Update wiki with audit directory structure explanation
- [ ] Update README.md with backfill tool usage
- [ ] Add tool to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes
- Test with a repo that has: 0 issues, 1 issue, 50+ issues
- Test with issues containing markdown, code blocks, images
- Test with issue titles containing emojis, quotes, slashes
- Test `--dry-run` actually creates no files (check filesystem before/after)
- Test `--skip-existing` by pre-creating one directory
- Test `--limit N` processes exactly N issues and stops
- **Offline Unit Tests:** Use static JSON fixtures in `tools/fixtures/` to test parsing logic without network access; mock `subprocess.run` to return fixture data
- **Error Handling Tests:** Simulate API timeout by mocking subprocess to raise `TimeoutExpired`; verify tool logs error and continues
- **Injection Tests:** Pass malicious `--repo` values (e.g., `foo; rm -rf /`) and verify no shell execution occurs
- **Rate Limit Tests:** Mock `429` response from subprocess; verify exponential backoff is attempted and tool aborts after max retries (Fail Fast with Backoff)
- **Empty Slug Tests:** Test issue titles that result in empty slugs after processing (e.g., title of `!!!` or empty string) to verify `untitled` fallback is applied

## Labels
`enhancement`, `tooling`, `maintenance`, `audit`, `backfill`, `python`

## Effort Estimate
**Medium** — Edge case handling and fixture creation add complexity beyond straightforward CRUD operations.