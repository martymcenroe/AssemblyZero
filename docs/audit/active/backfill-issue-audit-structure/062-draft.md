# Backfill Audit Directory Structure for Existing GitHub Issues

## User Story
As a **governance maintainer**,
I want **a CLI tool that backfills audit directory structures for existing GitHub issues**,
So that **historical issues have the same audit trail as new issues created under the governance workflow**.

## Objective
Create a Python CLI tool that fetches existing GitHub issues via `gh` CLI and generates standardized audit directories with issue content, comments, and metadata files.

## UX Flow

### Scenario 1: Single Repository Backfill (Happy Path)
1. User runs `python tools/backfill_issue_audit.py --repo owner/repo`
2. Tool validates `gh` CLI is authenticated and version >= 2.0
3. Tool fetches all issues (open and closed) from the repository
4. For each issue, tool generates slug and creates directory structure
5. Tool writes `001-issue.md`, `002-comments.md`, `003-metadata.json`
6. Result: User sees progress output with count of created directories

### Scenario 2: Dry Run Mode
1. User runs `python tools/backfill_issue_audit.py --repo owner/repo --dry-run`
2. Tool performs all validation and fetching
3. Tool outputs tree-like structure showing what would be created
4. Result: No files written; user sees preview of changes

### Scenario 3: Skip Existing Directories
1. User runs `python tools/backfill_issue_audit.py --repo owner/repo --skip-existing`
2. Tool encounters issue #42 with existing `docs/audit/done/42-some-title/`
3. Tool logs "Skipping issue #42: directory exists" and continues
4. Result: Only new issues are backfilled; existing directories untouched

### Scenario 4: All Registered Repositories
1. User runs `python tools/backfill_issue_audit.py --all-registered`
2. Tool reads `project-registry.json` for list of repositories
3. Tool processes each repository sequentially
4. Result: All registered repos have audit directories backfilled

### Scenario 5: Authentication Failure (Fail Fast)
1. User runs tool without `gh` CLI authenticated
2. Tool detects auth failure on first API call
3. Tool exits immediately with error code 1
4. Result: Clear error message: "Authentication failed. Run `gh auth login` first."

### Scenario 6: Network Timeout on Single Issue (Fail Open)
1. Tool is processing issue #50 of 100
2. Network timeout occurs fetching issue #50 details
3. Tool logs warning: "Failed to fetch issue #50: timeout. Skipping."
4. Tool continues to issue #51
5. Result: 99 issues processed; summary shows 1 failure

### Scenario 7: Rate Limit Exceeded (Exponential Backoff)
1. Tool receives HTTP 429 response from GitHub API
2. Tool logs: "Rate limit hit. Waiting 60 seconds..."
3. Tool waits with exponential backoff (60s, then 120s if repeated)
4. Tool retries the request
5. Result: Processing continues after rate limit resets

### Scenario 8: Issue with No Comments
1. Tool processes issue #15 which has no comments
2. Tool creates `002-comments.md` with content: "# Comments\n\nNo comments on this issue."
3. Result: Consistent file structure maintained

### Scenario 9: Issue with Special Characters in Title
1. Issue title: "Fix: user@domain.com parsing [URGENT]"
2. Slug generated: `42-fix-userdomain-com-parsing-urgent`
3. Result: Directory created with sanitized name

### Scenario 10: Issue with Emoji-Only Title
1. Issue title: "🚀🔥💯"
2. Slug generation removes all emojis, resulting in empty string
3. Tool applies fallback: `77-untitled`
4. Tool logs warning: "Issue #77 has empty slug after sanitization, using 'untitled'"
5. Result: Directory `77-untitled/` created

### Scenario 11: Missing agentos Package
1. User runs tool without `pip install -e .`
2. Tool catches `ImportError` for `agentos` module
3. Tool exits with clear message: "Error: agentos package not found. Please install with: pip install -e ."
4. Result: User knows exactly how to fix the issue

### Scenario 12: Very Long Issue Title
1. Issue title is 200 characters
2. Slug generation truncates title portion to 80 characters
3. Final directory: `123-first-eighty-chars-of-title.../`
4. Result: Filesystem path length limits respected

### Scenario 13: Open Issues vs Closed Issues
1. Tool processes open issue #19
2. Tool creates `docs/audit/active/19-some-feature/`
3. Tool processes closed issue #62
4. Tool creates `docs/audit/done/62-completed-work/`
5. Result: Issues routed to correct status directory

### Scenario 14: Force Overwrite Mode
1. User runs `python tools/backfill_issue_audit.py --repo owner/repo --force`
2. Tool encounters existing directory `42-old-title/`
3. Tool overwrites ONLY managed files (`001-issue.md`, `002-comments.md`, `003-metadata.json`)
4. Manual sidecar files (e.g., `004-analysis.md`) are preserved
5. Result: Generated content updated; user artifacts retained

### Scenario 15: Verbose Output Mode
1. User runs `python tools/backfill_issue_audit.py --repo owner/repo --verbose`
2. Tool outputs detailed information for each issue processed
3. Result: User can debug any issues with processing

### Scenario 16: Quiet Mode for CI
1. User runs `python tools/backfill_issue_audit.py --repo owner/repo --quiet`
2. Tool suppresses all output except errors
3. Result: Clean CI logs with only actionable information

### Scenario 17: Issue Renamed Since Last Backfill
1. Issue #42 was titled "Old Title" → directory `42-old-title/` exists
2. Issue #42 renamed to "New Title" on GitHub
3. User runs tool with `--force`
4. Tool detects existing `42-*` directory with different slug
5. Tool migrates sidecar files from `42-old-title/` to `42-new-title/`
6. Tool removes old directory after migration
7. Result: Audit trail follows issue rename; manual files preserved

### Scenario 18: Offline Testing with Fixtures
1. Developer sets environment variable `BACKFILL_USE_FIXTURES=1`
2. Tool reads from `tools/fixtures/` instead of calling `gh` CLI
3. Result: Full test coverage without network access

## Requirements

### CLI Interface
1. Accept `--repo owner/name` argument for single repository
2. Accept `--all-registered` flag to process all repos in `project-registry.json`
3. Validate `project-registry.json` schema before processing
4. Support `--dry-run` flag to preview without writing
5. Support `--skip-existing` flag to preserve existing directories
6. Support `--force` flag to overwrite managed files only
7. Support `--open-only` flag to process only open issues
8. Support `--verbose` flag for detailed debugging output
9. Support `--quiet` flag for CI pipeline usage
10. Support `--delay N` flag for manual request throttling (seconds)
11. Support `--limit N` flag for processing first N issues (debugging)
12. Validate `gh` CLI version >= 2.0 at startup
13. Exit with code 0 on success, 1 on fatal error, 2 on partial failure

### Data Fetching
1. Use `gh issue list --state all --json number,title,state,labels,createdAt,closedAt,body,comments,author` for issue listing
2. Use `gh issue view` with explicit `--json` fields for detailed data
3. Fetch linked PRs by parsing issue body/comments for PR URL patterns (e.g., `#123`, `owner/repo#123`)
4. Handle pagination for repositories with >100 issues (use `--limit 1000` or loop)
5. Store all fetched data locally only (never upload)

### Slug Generation
1. Convert title to lowercase
2. Replace spaces and underscores with hyphens
3. Remove all characters not matching `[a-z0-9-]`
4. Collapse multiple consecutive hyphens to single hyphen
5. Strip leading and trailing hyphens
6. If resulting string is empty, set to `untitled`
7. Truncate slug to maximum 80 characters
8. Prepend issue number: `{number}-{slug}`
9. Import slug logic from `agentos/workflows/issue/audit.py` to prevent drift

### Directory Structure
1. Create `docs/audit/done/{slug}/` for closed issues
2. Create `docs/audit/active/{slug}/` for open issues
3. Create parent directories if they don't exist
4. Handle renamed issues by detecting `{number}-*` pattern conflicts

### File Generation
1. Generate `001-issue.md` with issue title as H1 and body content
2. Generate `002-comments.md` with chronological comments or "No comments on this issue." placeholder
3. Generate `003-metadata.json` with structured issue metadata
4. Add header comment to markdown files: `<!-- GENERATED FILE: Modifications may be overwritten by backfill tool -->`
5. Preserve non-managed files (anything not `001-*`, `002-*`, `003-*`) during overwrites

### Error Handling Strategy
| Error Type | Strategy | Behavior |
|------------|----------|----------|
| Auth failure | Fail Fast | Exit immediately with code 1 |
| Invalid `--repo` format | Fail Fast | Exit with usage error |
| `gh` CLI not found | Fail Fast | Exit with installation instructions |
| `gh` version < 2.0 | Fail Fast | Exit with upgrade instructions |
| `agentos` import error | Fail Fast | Exit with `pip install -e .` instructions |
| Network timeout (single issue) | Fail Open | Log warning, skip issue, continue |
| Malformed issue data | Fail Open | Log warning, skip issue, continue |
| File write permission error | Fail Open | Log error, skip issue, continue |
| Rate limit (HTTP 429) | Exponential Backoff | Wait 60s, retry up to 3 times, then Fail Fast |
| Timeline fetch timeout | Fail Open | Skip PR linking for that issue, log warning |

### Subprocess Security
1. **MANDATORY:** Use list argument format for all `subprocess` calls
2. **MANDATORY:** Never use `shell=True`
3. Example: `subprocess.run(['gh', 'issue', 'list', '--repo', repo_name, '--json', fields], ...)`
4. Validate and sanitize all user inputs before passing to subprocess

## Technical Approach

- **CLI Parsing:** Use `argparse` for argument handling with mutually exclusive groups
- **GitHub API:** Shell out to `gh` CLI with JSON output parsing via `subprocess.run()`
- **Slug Generation:** Import from `agentos/workflows/issue/audit.py` (requires `pip install -e .`)
- **File I/O:** Use `pathlib.Path` for cross-platform path handling
- **JSON Handling:** Use `json` module from standard library
- **Date Parsing:** Use `datetime.fromisoformat()` (Python 3.11+) or `dateutil.parser` for compatibility
- **Rate Limiting:** Implement exponential backoff with `time.sleep()`
- **Offline Testing:** Check `BACKFILL_USE_FIXTURES` environment variable to load from `tools/fixtures/`

### Subprocess Call Example
```python
import subprocess
import json

def fetch_issues(repo: str) -> list[dict]:
    result = subprocess.run(
        ['gh', 'issue', 'list', '--repo', repo, '--state', 'all', '--limit', '1000',
         '--json', 'number,title,state,labels,createdAt,closedAt,body,comments,author'],
        capture_output=True,
        text=True,
        check=True  # Raises CalledProcessError on non-zero exit
    )
    return json.loads(result.stdout)
```

## Security Considerations

- **Data Residency:** Local-Only — all data written to `docs/audit/` within repository; no external uploads
- **Input Sanitization:** Slug generation removes all special characters; subprocess uses list arguments only
- **Shell Injection Prevention:** Explicit prohibition of `shell=True`; all arguments passed as list elements
- **Path Traversal Prevention:** Slugs stripped of `.`, `..`, and `/` characters via regex
- **Credential Handling:** Uses existing `gh` CLI authentication; no credential storage in tool
- **Privacy:** Processes content accessible to authenticated user (may include private repos if user has access)

## Files to Create/Modify

- `tools/backfill_issue_audit.py` — Main CLI tool implementation
- `tools/fixtures/` — Directory for offline test fixtures
- `tools/fixtures/README.md` — Documentation for fixture format and versioning
- `tools/fixtures/sample_issues.json` — Sample issue list response
- `tools/fixtures/sample_issue_detail.json` — Sample single issue response
- `tests/tools/test_backfill_issue_audit.py` — Unit and integration tests

## Dependencies

- **External:** `gh` CLI version >= 2.0 (installed and authenticated)
- **Internal:** `agentos/workflows/issue/audit.py` must exist with `generate_slug()` function
- **Python:** Version 3.11+ (for `fromisoformat` timezone handling) OR include `python-dateutil` as fallback
- **Schema:** `project-registry.json` must exist with `repositories` array containing `owner/name` strings

**Note:** The `agentos/workflows/issue/audit.py` module provides the canonical slug generation logic. If this file is being created in a parallel branch, link that PR/Issue here: _{link to be added by implementer}_

## Out of Scope (Future)

- **GraphQL Optimization** — Using `gh api graphql` for batch fetching (current N+1 REST calls acceptable for maintenance tool)
- **Incremental Sync** — Only fetching issues modified since last run
- **Webhook Integration** — Real-time backfill on issue events
- **PR Audit Directories** — Creating audit structure for pull requests
- **Custom Templates** — User-configurable file templates
- **Remote Storage** — Uploading audit data to external services
- **Directory Sharding** — Organizing by year (e.g., `docs/audit/done/2025/`) for very large repos

## Acceptance Criteria

- [ ] Tool runs successfully with `--repo owner/name` argument
- [ ] Tool runs successfully with `--all-registered` flag
- [ ] Tool validates `gh` CLI is installed and version >= 2.0
- [ ] Tool validates `gh` CLI is authenticated before processing
- [ ] Tool creates `docs/audit/done/{slug}/` for closed issues
- [ ] Tool creates `docs/audit/active/{slug}/` for open issues
- [ ] Tool generates valid `001-issue.md` with H1 title and body content
- [ ] Tool generates valid `002-comments.md` with chronological comments
- [ ] Tool generates `002-comments.md` with "No comments on this issue." when empty
- [ ] Tool generates valid `003-metadata.json` with all required fields
- [ ] Tool handles issues with emoji-only titles (creates `{number}-untitled`)
- [ ] Tool handles issues with very long titles (truncates slug to 80 chars)
- [ ] Tool handles special characters in titles (sanitizes to `[a-z0-9-]`)
- [ ] Tool implements `--dry-run` with tree-like preview output
- [ ] Tool implements `--skip-existing` to preserve existing directories
- [ ] Tool implements `--force` overwriting only managed files (`001-*`, `002-*`, `003-*`)
- [ ] Tool preserves manual sidecar files during `--force` overwrite
- [ ] Tool migrates sidecar files when issue is renamed (with `--force`)
- [ ] Tool exits with code 1 on authentication failure (Fail Fast)
- [ ] Tool logs and continues on network timeout for single issue (Fail Open)
- [ ] Tool implements exponential backoff on HTTP 429 rate limit
- [ ] Tool uses list arguments for all subprocess calls (no `shell=True`)
- [ ] Tool provides clear error message when `agentos` package not installed
- [ ] Tool supports `--verbose` flag for debug output
- [ ] Tool supports `--quiet` flag for CI usage
- [ ] Offline tests pass using static fixtures in `tools/fixtures/`

## Definition of Done

### Implementation
- [ ] Core CLI tool implemented in `tools/backfill_issue_audit.py`
- [ ] All acceptance criteria verified
- [ ] Unit tests written and passing for slug generation, file creation, error handling
- [ ] Integration test with real GitHub repo passes
- [ ] Offline tests using fixtures pass without network access

### Tools
- [ ] Tool is executable via `python tools/backfill_issue_audit.py`
- [ ] Tool usage documented in `--help` output
- [ ] Static fixtures created in `tools/fixtures/` with README

### Documentation
- [ ] Tool usage documented in `tools/README.md` or `--help`
- [ ] Fixture format documented in `tools/fixtures/README.md` with version field

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS (subprocess injection prevention verified)
- [ ] Fixtures anonymize any real PII if copied from production repos

## Testing Notes

### Manual Testing
```bash
# Dry run to preview
python tools/backfill_issue_audit.py --repo owner/repo --dry-run

# Process single repo
python tools/backfill_issue_audit.py --repo owner/repo --verbose

# Process all registered repos
python tools/backfill_issue_audit.py --all-registered --skip-existing

# Force update with rate limiting
python tools/backfill_issue_audit.py --repo owner/repo --force --delay 1
```

### Edge Cases to Test
- Issue with title containing only emojis → should create `{number}-untitled`
- Issue with title > 200 characters → slug should be truncated to 80 chars
- Issue with no comments → `002-comments.md` should have placeholder text
- Issue with 100+ comments → all comments should be captured
- Repository with 0 issues → should complete successfully with no directories created
- Repository with 500+ issues → should handle pagination correctly
- Rate limit simulation → mock 429 response, verify backoff behavior
- Renamed issue with sidecar files → verify migration preserves files
- Closed issue that was reopened → should be in `active/` not `done/`

### Offline Testing
```bash
# Set environment variable to use fixtures
export BACKFILL_USE_FIXTURES=1
python -m pytest tests/tools/test_backfill_issue_audit.py -v
```

### Fixture Schema
Fixtures in `tools/fixtures/` should match `gh` CLI JSON output:
```json
{
  "schema_version": "1.0",
  "source": "gh issue list --json ...",
  "issues": [
    {
      "number": 42,
      "title": "Example Issue",
      "state": "closed",
      "body": "Issue description...",
      "comments": [],
      "labels": [{"name": "bug"}],
      "createdAt": "2026-01-15T10:00:00Z",
      "closedAt": "2026-01-20T15:30:00Z"
    }
  ]
}
```

## Labels
`enhancement`, `tooling`, `audit`, `maintenance`