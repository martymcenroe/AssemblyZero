# Backfill Audit Directory Structure for Existing GitHub Issues

## User Story
As a project maintainer,
I want to automatically generate audit directories for existing GitHub issues,
So that all issues (past and present) have consistent local audit trails matching our governance workflow.

## Objective
Create a Python CLI tool that backfills the `docs/audit/` directory structure for all existing GitHub issues across registered repositories.

## UX Flow

### Scenario 1: Backfill Single Repository
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS`
2. Tool fetches all issues (open and closed) via `gh issue list --state all --json number,title,state,labels,createdAt,closedAt,url`
3. Tool generates slug for each issue (e.g., `62-governance-workflow-stategraph`)
4. Tool creates directories under `docs/audit/done/` (closed) or `docs/audit/active/` (open)
5. Tool writes `001-issue.md`, `002-comments.md`, `003-metadata.json` to each directory
6. Result: Complete audit trail for all issues in that repo

### Scenario 2: Dry Run Mode
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS --dry-run`
2. Tool fetches and processes issues
3. Tool prints tree-like output showing what would be created:
   ```
   [DRY RUN] Would create:
   + docs/audit/done/62-governance-workflow-stategraph/
     + 001-issue.md
     + 002-comments.md
     + 003-metadata.json
   + docs/audit/active/19-review-audit-classes/
     + 001-issue.md
     + 002-comments.md
     + 003-metadata.json
   ```
4. Result: User previews changes before committing

### Scenario 3: Skip Existing Directories
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS --skip-existing`
2. Tool encounters issue #62 which already has `docs/audit/done/62-governance-workflow-stategraph/`
3. Tool skips this issue and continues to next
4. Result: Only new issues get backfilled, existing audit trails preserved

### Scenario 4: Backfill All Registered Repos
1. User runs `python -m tools.backfill_issue_audit --all-registered`
2. Tool validates schema of `project-registry.json` before processing
3. Tool reads `project-registry.json` for list of repos
4. Tool iterates through each repo and backfills
5. Result: Audit directories created across entire project ecosystem

### Scenario 5: Issue Has No Comments
1. Tool processes issue #45 which has no comments
2. Tool creates `001-issue.md` and `003-metadata.json`
3. Tool creates `002-comments.md` containing only the text `No comments found.`
4. Result: Graceful handling of issues without discussion

### Scenario 6: Verbose Debugging Mode
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS --verbose`
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
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS --limit 5`
2. Tool processes only the first 5 issues
3. Result: Quick debugging loop before running full batch

### Scenario 11: Import Error Handling
1. User runs tool without having installed `agentos` package in editable mode
2. Tool catches `ImportError` for the `agentos` module
3. Tool prints explicit message: "Please install package in editable mode via `pip install -e .`"
4. Tool aborts with non-zero exit code
5. Result: Clear guidance for users who miss the editable install requirement

### Scenario 12: Issue Title Only Contains Emojis
1. Tool processes issue #77 with title "🚀🔥💯"
2. Slug algorithm removes all emoji characters (non-alphanumeric)
3. Resulting string is empty after processing
4. Tool applies `untitled` fallback
5. Tool logs warning to stdout: "Warning: Issue #77 title resolved to 'untitled' (original title contained only non-alphanumeric characters)"
6. Result: Directory created as `docs/audit/active/77-untitled/`

### Scenario 13: Issue Title Extremely Long
1. Tool processes issue #88 with a 200-character title
2. Slug algorithm processes and truncates to maximum 80 characters
3. Result: Directory created with truncated slug, no filesystem path errors

### Scenario 14: Force Overwrite Existing Directories
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS --force`
2. Tool encounters issue #62 which already has `docs/audit/done/62-governance-workflow-stategraph/`
3. Tool overwrites **only the tool-managed files** (`001-issue.md`, `002-comments.md`, `003-metadata.json`) with fresh data, preserving any manual sidecar files (e.g., `004-analysis.md`)
4. Result: Existing audit trails are updated with latest GitHub data while manual artifacts are preserved

### Scenario 15: Closed Issue Without Closing Event in Timeline
1. Tool processes issue #99 which has state "closed" but no closing event in timeline (migrated issue)
2. Tool correctly identifies state from issue metadata rather than timeline events
3. Result: Directory created in `docs/audit/done/` based on issue state field

### Scenario 16: Issue Renamed After Previous Backfill
1. Tool processes issue #62 which was previously backfilled as `62-old-title`
2. Issue has since been renamed to "New Title" on GitHub
3. Tool scans for existing directories matching pattern `62-*` in both `docs/audit/done/` and `docs/audit/active/` to detect previous backfill
4. Tool logs warning: "Issue #62 has existing directory '62-old-title' but current slug is '62-new-title'. Use --force to update or manually reconcile."
5. Tool skips this issue (counts as skipped, not error)
6. Result: No duplicate directories created; user alerted to reconciliation need

### Scenario 17: Force Overwrite with Renamed Issue (Sidecar Migration)
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/AgentOS --force`
2. Tool encounters issue #62 which was previously backfilled as `62-old-title` but current title generates slug `62-new-title`
3. Tool scans old directory `62-old-title` for non-generated sidecar files (files not matching `001-issue.md`, `002-comments.md`, `003-metadata.json`)
4. Tool creates new directory `62-new-title`
5. Tool migrates any sidecar files (e.g., `004-analysis.md`) from old directory to new directory
6. Tool removes the old directory `62-old-title` only after successful migration
7. Result: Renamed issues are properly migrated with manual artifacts preserved, no orphan directories

### Scenario 18: Large Repository Rate Limit Warning
1. User runs `python -m tools.backfill_issue_audit --repo martymcenroe/LargeRepo`
2. Tool fetches issue list and detects >1000 issues
3. Tool prints pre-flight warning: "Warning: Repository has 4500 issues. Processing may take significant time and could approach API rate limits (5000 req/hour). Consider using --limit for testing."
4. Tool continues processing unless user cancels
5. Result: User is informed of potential duration/rate limit impact before committing to full run

## Requirements

### CLI Interface
1. Accept `--repo OWNER/REPO` flag for single repository targeting
2. Accept `--all-registered` flag to process all repos in `project-registry.json`
3. Accept `--dry-run` flag to preview without writing
4. Accept `--skip-existing` flag to preserve existing audit directories
5. Accept `--force` flag to explicitly overwrite existing directories (mutually exclusive with `--skip-existing`)
6. Accept `--open-only` flag to process only open issues
7. Accept `--verbose` flag for detailed debug output
8. Accept `--limit N` flag to process only the first N issues (for debugging)
9. Accept `--delay N` flag (optional) to add N seconds delay between requests for manual throttling
10. Accept `--quiet` flag to suppress non-error output (for CI pipelines)
11. Provide clear progress output showing issues processed

### Slug Generation
1. Import slug algorithm from shared utility module `agentos/workflows/issue/audit.py` to prevent drift (see Technical Approach for import strategy)
2. Lowercase the title
3. Replace spaces and underscores with hyphens
4. Remove special characters (keep alphanumeric and hyphens only via regex `[^a-z0-9-]`)
5. Collapse multiple consecutive hyphens to single hyphen (via regex `-+` → `-`)
6. Strip leading/trailing hyphens
7. If resulting string is empty, set string to `untitled`
8. Truncate slug to maximum 80 characters to prevent filesystem path length errors
9. Prepend issue number: `{number}-{slug}`
10. Handle edge cases: empty titles become `{number}-untitled`, all-special-character titles (including emoji-only) become `{number}-untitled`

### File Generation
1. Create `001-issue.md` with issue title as H1 and body as content; include HTML comment header `<!-- GENERATED FILE: DO NOT EDIT -->`
2. Create `002-comments.md` with all comments, each prefixed by author and date; if no comments exist, file contains only `No comments found.`; include HTML comment header `<!-- GENERATED FILE: DO NOT EDIT -->`
3. Create `003-metadata.json` with issue metadata (number, URL, state, labels, timestamps, linked PRs)
4. Place files in `docs/audit/done/{slug}/` for closed issues
5. Place files in `docs/audit/active/{slug}/` for open issues

### Data Fetching
1. Use `gh issue list --state all` with JSON output for issue enumeration (fetches both open and closed issues)
2. Use `gh issue view` with explicit JSON fields: `--json number,title,body,state,labels,createdAt,closedAt,url,comments` for full issue details including comments
3. For linked PR detection: first attempt to fetch `timelineItems` field; if payload causes issues (large size, timeouts, exceeds 100 events), fall back to parsing issue body/comments for PR references using regex pattern `#\d+` or `github.com/.*/pull/\d+`
4. Handle pagination for repos with many issues using `--limit <high_number>` or pagination loop

### Duplicate Detection
1. Before creating a new directory, scan for existing directories matching pattern `{number}-*` in both `docs/audit/done/` and `docs/audit/active/`
2. If a matching directory exists with a different slug (indicating issue was renamed), log a warning and skip unless `--force` is specified
3. If `--force` is specified, migrate sidecar files and remove the old directory (see Sidecar Migration)
4. This prevents orphan directories from renamed issues accumulating over time

### Overwrite Behavior (`--force` flag)
1. When `--force` is used on an existing directory with matching slug, overwrite **only** the tool-managed files: `001-issue.md`, `002-comments.md`, `003-metadata.json`
2. Preserve any manual sidecar files (e.g., `004-analysis.md`, `005-notes.md`) that users may have added
3. When `--force` is used and the issue was renamed (different slug detected), perform sidecar migration before removing the old directory
4. Audit directories for tool-managed files are considered ephemeral and regenerable; manual artifacts are always preserved

### Sidecar Migration (Renamed Issues)
1. Define "tool-managed files" as exactly: `001-issue.md`, `002-comments.md`, `003-metadata.json`
2. Any other files in the directory are considered "sidecar files" (e.g., `004-analysis.md`, `notes.txt`)
3. When migrating a renamed issue with `--force`:
   a. Create the new directory with the current slug
   b. Generate fresh tool-managed files in the new directory
   c. Copy all sidecar files from the old directory to the new directory
   d. Verify copy success before removing old directory
   e. Remove the old directory only after successful migration
4. If sidecar migration fails, abort the rename operation for that issue (Fail Open), log error, and continue to next issue

### Error Handling Strategy
1. **Fail Open (Log and Continue):** For individual issue processing errors (API timeouts, malformed data, sidecar migration failures), log the error to stderr and continue processing remaining issues
2. **Fail Fast:** For fatal errors (invalid repo, authentication failure, filesystem permission denied), abort immediately with non-zero exit code
3. **Fail Fast with Exponential Backoff:** For HTTP 429 (Rate Limit) errors, implement exponential backoff (1s, 2s, 4s, 8s, up to 60s max) with 5 retry attempts; if retries exhausted, abort immediately with non-zero exit code — **do NOT use Fail Open for rate limits** as subsequent requests will also fail
4. At completion, report summary: total issues, successful, skipped, and failed counts
5. Exit with code 0 if all issues processed successfully, exit with code 1 if any issues failed

## Technical Approach
- **CLI Parsing:** `argparse` for command-line interface
- **GitHub API:** `subprocess` calls to `gh` CLI using list argument format (e.g., `subprocess.run(['gh', 'issue', 'list', '--repo', repo_name, '--state', 'all', '--json', 'number,title,state'], ...)`) — **never use `shell=True`** to prevent command injection
- **Startup Validation:** Verify `gh` CLI is installed and authenticated before processing; verify `gh --version` meets minimum requirements (require `gh >= 2.0`) for expected JSON output schema; implement specific version parsing check in startup code
- **Registry Validation:** Validate schema of `project-registry.json` before processing to prevent runtime errors
- **Slug Generation:** Pure Python string manipulation (no external dependencies); import logic from shared utility module in `agentos/workflows/issue/audit.py` rather than duplicating to prevent drift; verify regex `[^a-z0-9-]` aligns exactly with the referenced utility
- **Import Strategy:** The tool MUST be run either as a module (`python -m tools.backfill_issue_audit`) OR the `agentos` package MUST be installed in editable mode (`pip install -e .`) to enable imports from `agentos/workflows/issue/audit.py`. **Runtime `sys.path` manipulation is NOT permitted** as it breaks static analysis (mypy/pylint) and IDE autocompletion. Include explicit `ImportError` handling with a try/catch block that prints "Please install package in editable mode via `pip install -e .`" for clear user guidance.
- **File I/O:** `pathlib` for cross-platform path handling
- **JSON Handling:** Standard library `json` module
- **Date Formatting:** `datetime` for ISO timestamp parsing and formatting; require Python 3.11+ for `fromisoformat` handling of 'Z' timezones, or use `dateutil` for earlier versions
- **Rate Limit Handling:** `time.sleep()` with exponential backoff for 429 responses; mock must simulate specific `gh` CLI error message format (stderr output) rather than HTTP code directly
- **Sidecar Detection:** Use glob pattern to list all files in directory, filter out tool-managed files (`001-issue.md`, `002-comments.md`, `003-metadata.json`), remaining files are sidecars

## Security Considerations
- Tool only reads from GitHub API (no write operations to remote)
- Respects existing `gh` CLI authentication
- No sensitive data stored—all content accessible to the authenticated user (note: if `project-registry.json` includes private repos, content is still handled as Local-Only)
- Local file writes restricted to `docs/audit/` directory tree (Local-Only data residency)
- **All `subprocess` calls MUST use list argument format** (e.g., `['gh', 'issue', 'list', ...]`) and **MUST NOT use `shell=True`** to prevent shell injection attacks via malformed `--repo` arguments

## Files to Create/Modify
- `tools/backfill_issue_audit.py` — Main CLI tool (new file)
- `tests/tools/test_backfill_issue_audit.py` — Unit tests for the backfill tool (new file)
- `tools/fixtures/` — Static JSON fixtures for offline unit testing (new directory)
- `tools/fixtures/README.md` — Documents standard schema for fixture files to enable reusability by other tooling; includes version field to track schema changes
- `docs/audit/done/` — Directory for closed issue audits (created by tool)
- `docs/audit/active/` — Directory for open issue audits (created by tool)

## Dependencies
- Requires `gh` CLI installed and authenticated (minimum version 2.0 required)
- Requires `project-registry.json` for `--all-registered` mode
- Requires `agentos` package installed in editable mode (`pip install -e .`) for slug utility imports
- **Dependency Status:** `agentos/workflows/issue/audit.py` exists in `main` branch with stable slug logic (verified)

## Out of Scope (Future)
- **Incremental sync** — detecting new comments since last backfill (future enhancement)
- **PR audit backfill** — separate tool for pull request audit trails
- **Cross-repo linking** — detecting references between repos
- **LLM summarization** — generating brief/summary from issue content
- **GraphQL batching** — using `gh api graphql` for performance optimization on extremely large repos
- **Folder sharding** — organizing by year (e.g., `docs/audit/done/2025/{slug}`) for large repos; current flat structure acceptable for expected volume
- **Automatic cleanup without --force** — tool warns about renamed issues but does not auto-delete unless `--force` is used; manual reconciliation otherwise required

## Acceptance Criteria
- [ ] Running `--repo martymcenroe/AgentOS` creates audit directories for all issues
- [ ] Closed issues appear under `docs/audit/done/`
- [ ] Open issues appear under `docs/audit/active/`
- [ ] Slug format matches `{number}-{slugified-title}` pattern
- [ ] Slug is truncated to maximum 80 characters before prepending issue number
- [ ] `001-issue.md` contains issue title and body with `<!-- GENERATED FILE: DO NOT EDIT -->` header
- [ ] `002-comments.md` contains all comments with author and timestamp with `<!-- GENERATED FILE: DO NOT EDIT -->` header
- [ ] `003-metadata.json` contains valid JSON with required fields
- [ ] `--dry-run` prints tree-like output of actions without creating files
- [ ] `--skip-existing` preserves directories that already exist
- [ ] `--force` overwrites only tool-managed files (`001-issue.md`, `002-comments.md`, `003-metadata.json`) while preserving manual sidecar files
- [ ] `--force` with renamed issue migrates sidecar files to new directory before removing old directory
- [ ] `--all-registered` processes multiple repos from registry
- [ ] `--verbose` outputs detailed debug information including API responses and file operations
- [ ] `--limit N` processes only the first N issues for quick debugging loops
- [ ] `--delay N` adds N seconds between API requests for manual throttling
- [ ] `--quiet` suppresses non-error output for CI pipeline usage
- [ ] Tool handles issues with no comments by creating `002-comments.md` containing `No comments found.`
- [ ] Tool handles issues with special characters in titles using the slug algorithm: lowercase → replace spaces/underscores with hyphens → remove non-alphanumeric characters except hyphens → collapse consecutive hyphens → strip leading/trailing hyphens → check for empty string and set to `untitled` if empty → truncate to 80 characters → prepend issue number
- [ ] Tool handles emoji-only titles by resolving to `{number}-untitled` and logging warning
- [ ] Tool detects renamed issues (existing `{number}-*` directory with different slug) and logs warning
- [ ] Tool logs errors for individual issue failures and continues processing (Fail Open)
- [ ] Tool aborts immediately on fatal errors (invalid repo, auth failure) (Fail Fast)
- [ ] Tool implements exponential backoff for HTTP 429 rate limit errors and aborts after 5 failed retries (Fail Fast with Backoff)
- [ ] Tool reports processing summary at completion (total, successful, skipped, failed)
- [ ] All `subprocess` calls use list argument format without `shell=True`
- [ ] Slug logic is imported from shared utility module (no duplication)
- [ ] Tool validates `gh` CLI version (>= 2.0) on startup before processing
- [ ] Tool catches `ImportError` and prints explicit install instructions
- [ ] Sidecar files are preserved during all overwrite operations
- [ ] Sidecar files are migrated to new directory when issue is renamed with `--force`
- [ ] Tool prints pre-flight warning when repository has >1000 issues

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing using static JSON fixtures (offline-capable)
- [ ] Integration test with real GitHub repo

### Tools
- [ ] `tools/backfill_issue_audit.py` created and executable
- [ ] `tools/fixtures/` directory with mock `gh` CLI JSON responses for unit tests
- [ ] Fixture files follow a standard schema documented in `tools/fixtures/README.md` for reusability; schema includes version field
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
- Test with issue titles that are extremely long (verify truncation to 80 chars and no path length issues)
- Test with issue title that is *only* emojis (verify resolves to `{number}-untitled` and logs warning)
- Test with closed issue that has no closing event in timeline (migrated issues)
- Test with issue description larger than filesystem block size (robustness check)
- Test `--dry-run` actually creates no files (check filesystem before/after)
- Test `--skip-existing` by pre-creating one directory
- Test `--force` overwrites only tool-managed files and preserves manual sidecar files
- Test `--force` with renamed issue (sidecar files should be migrated, old directory removed, new one created)
- Test `--limit N` processes exactly N issues and stops
- Test `--delay N` adds appropriate delay between requests
- Test `--quiet` suppresses output for CI usage
- **Offline Unit Tests:** Use static JSON fixtures in `tools/fixtures/` to test parsing logic without network access; mock `subprocess.run` to return fixture data
- **Error Handling Tests:** Simulate API timeout by mocking subprocess to raise `TimeoutExpired`; verify tool logs error and continues
- **Injection Tests:** Pass malicious `--repo` values (e.g., `foo; rm -rf /`) and verify no shell execution occurs
- **Rate Limit Tests:** Mock `429` response from subprocess (simulating `gh` CLI stderr output); verify exponential backoff is attempted and tool aborts after max retries (Fail Fast with Backoff)
- **Empty Slug Tests:** Test issue titles that result in empty slugs after processing (e.g., title of `!!!` or empty string or `🚀🔥`) to verify `untitled` fallback is applied
- **Import Error Tests:** Verify explicit error message when `agentos` package not installed
- **gh Version Tests:** Verify startup check validates minimum `gh` CLI version (2.0+)
- **Renamed Issue Tests:** Pre-create directory `62-old-title`, run tool with issue #62 now titled "New Title", verify warning logged and no duplicate created
- **Sidecar Preservation Tests:** Pre-create directory with `001-issue.md` and manual `004-analysis.md`, run with `--force`, verify `004-analysis.md` is preserved
- **Sidecar Migration Tests:** Pre-create directory `62-old-title` with `001-issue.md` and `004-analysis.md`, run with `--force` where issue #62 now has different title, verify `004-analysis.md` exists in new directory `62-new-title` and old directory is removed
- **TimelineItems Fallback Tests:** Mock large timelineItems response that causes timeout; verify tool falls back to regex parsing of issue body for PR links
- **Large Repo Warning Tests:** Mock issue list response with >1000 issues; verify pre-flight warning is printed

## Labels
`enhancement`, `tooling`, `maintenance`, `audit`, `backfill`, `python`, `governance`

## Effort Estimate
**Medium** — Edge case handling, sidecar migration logic, and fixture creation add complexity beyond straightforward CRUD operations.