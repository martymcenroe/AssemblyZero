# Test Fixtures

This directory contains test fixtures for the backfill_issue_audit.py tool.

## Files

### sample_issues.json

Sample GitHub issue data in the format returned by `gh issue list --json`.

Contains:
- **Issue #42**: Open enhancement issue with labels, assignee, and comments
- **Issue #17**: Closed bug issue with multiple assignees and comments
- **Issue #99**: Open documentation issue with no assignees or comments

### sample_comments.json

Sample GitHub comment data in the format returned by `gh api repos/{owner}/{repo}/issues/{number}/comments`.

Contains comments for issues #42, #17, and #99 (empty array).

## Usage in Tests

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent.parent / "tools" / "fixtures"

def load_sample_issues():
    with open(FIXTURES_DIR / "sample_issues.json") as f:
        return json.load(f)

def load_sample_comments():
    with open(FIXTURES_DIR / "sample_comments.json") as f:
        return json.load(f)
```

## Data Format

### Issue Object

```json
{
  "number": 42,
  "title": "Issue title",
  "body": "Issue body in markdown",
  "state": "open",
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-20T14:45:00Z",
  "closedAt": null,
  "author": {"login": "username"},
  "labels": [{"name": "label1"}],
  "assignees": [{"login": "username"}],
  "url": "https://github.com/owner/repo/issues/42",
  "comments": 2
}
```

### Comment Object

```json
{
  "id": 1001,
  "user": {"login": "username"},
  "body": "Comment body",
  "created_at": "2024-01-16T11:00:00Z",
  "html_url": "https://github.com/owner/repo/issues/42#issuecomment-1001"
}
```
