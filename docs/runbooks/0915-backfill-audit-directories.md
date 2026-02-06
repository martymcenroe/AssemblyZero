# Runbook 0915: Backfill Audit Directories

## Overview

The `backfill_issue_audit.py` tool creates standardized audit directories for existing GitHub issues that predate the governance workflow.

## When to Run

- **New repository setup**: After adopting AssemblyZero governance workflow
- **Periodic maintenance**: To capture issues created outside the workflow
- **Migration**: When transitioning from another issue tracking system

## Prerequisites

1. **gh CLI authenticated**: Run `gh auth status` to verify
2. **Repository access**: Read access to the target repository
3. **Local repository**: Run from within a git repository

## Usage

### Basic Usage

```bash
# Dry run to preview (recommended first step)
poetry run python tools/backfill_issue_audit.py --repo owner/name --dry-run

# Process all issues
poetry run python tools/backfill_issue_audit.py --repo owner/name --verbose
```

### Common Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview without writing files |
| `--skip-existing` | Don't update existing audit directories |
| `--force` | Overwrite managed files (001-, 002-, 003-*) |
| `--verbose` | Show detailed progress |
| `--quiet` | Suppress non-error output |
| `--delay N` | Seconds between API calls (default: 0.5) |
| `--limit N` | Process only first N issues |

### Examples

```bash
# Process with verbose output
poetry run python tools/backfill_issue_audit.py --repo martymcenroe/AssemblyZero --verbose

# Skip existing directories (safe for re-runs)
poetry run python tools/backfill_issue_audit.py --repo martymcenroe/AssemblyZero --skip-existing

# Force update managed files only
poetry run python tools/backfill_issue_audit.py --repo martymcenroe/AssemblyZero --force

# Test with limited issues
poetry run python tools/backfill_issue_audit.py --repo martymcenroe/AssemblyZero --limit 5 --dry-run

# Slow down for rate limits
poetry run python tools/backfill_issue_audit.py --repo martymcenroe/AssemblyZero --delay 2.0
```

## Output Structure

### Directory Layout

```
docs/audit/
├── active/          # Open issues
│   ├── 42-add-user-auth/
│   │   ├── 001-issue.md
│   │   ├── 002-comments.md
│   │   └── 003-metadata.json
│   └── ...
└── done/            # Closed issues
    ├── 17-fix-db-leak/
    │   ├── 001-issue.md
    │   ├── 002-comments.md
    │   └── 003-metadata.json
    └── ...
```

### File Descriptions

| File | Contents |
|------|----------|
| `001-issue.md` | Issue title, body, author, labels, dates |
| `002-comments.md` | Chronological list of all comments |
| `003-metadata.json` | Structured metadata for programmatic access |

### Managed Files

Files with prefixes `001-`, `002-`, `003-` are considered "managed" and can be safely overwritten with `--force`. Custom files (e.g., `notes.md`, `analysis.md`) are never touched.

## Troubleshooting

### Rate Limits

**Symptom**: "Rate limited" messages, slow progress

**Solution**:
```bash
# Increase delay between requests
poetry run python tools/backfill_issue_audit.py --repo owner/name --delay 2.0
```

The tool automatically uses exponential backoff for 429 errors.

### Authentication Failures

**Symptom**: "gh CLI not authenticated" error

**Solution**:
```bash
# Check auth status
gh auth status

# Re-authenticate if needed
gh auth login
```

### Network Timeouts

**Symptom**: "Timeout" errors for specific issues

**Behavior**: Tool skips the issue and continues (fail-open strategy)

**Solution**: Re-run with `--skip-existing` to process failed issues

### Permission Denied

**Symptom**: Cannot write to docs/audit/

**Solution**: Check file permissions and ensure you're in the correct directory

## Example Output

```
$ poetry run python tools/backfill_issue_audit.py --repo martymcenroe/AssemblyZero --verbose --limit 3

Fetching issues from martymcenroe/AssemblyZero...
Found 3 issues
DRY RUN: No files will be written

[1/3] [OPEN] #42: Add user authentication...
  Fetching comments for #42...
  [+] created: Files: 001-issue.md, 002-comments.md, 003-metadata.json

[2/3] [CLOSED] #17: Fix database connection leak...
  Fetching comments for #17...
  [+] created: Files: 001-issue.md, 002-comments.md, 003-metadata.json

[3/3] [OPEN] #99: Documentation: API reference...
  Fetching comments for #99...
  [+] created: Files: 001-issue.md, 002-comments.md, 003-metadata.json

==================================================
Summary
==================================================
  Created: 3
  Updated: 0
  Skipped: 0
  Errors:  0
  Total:   3
==================================================
```

## Related

- [0904-issue-governance-workflow.md](0904-issue-governance-workflow.md) - Issue creation workflow
- [0906-lld-governance-workflow.md](0906-lld-governance-workflow.md) - LLD governance workflow
