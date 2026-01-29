# Backfill Issue Audit Structure

## Problem

We have a new governance workflow (#62) that creates `docs/audit/active/{slug}/` directories with sequential numbered files for each issue. But we have dozens of existing issues across multiple repos (AgentOS, Aletheia, Talos) that predate this structure.

Currently these repos have no audit trail for historical issues - no record of the original brief, drafts, or review verdicts.

## Goal

Create a Python tool that backfills the audit directory structure for existing GitHub issues:

1. **Fetch** all issues from a repo via `gh issue list`
2. **Generate slugs** from issue titles (pure Python, no LLM needed)
3. **Create** `docs/audit/done/{slug}/` directory for each closed issue
4. **Create** `docs/audit/active/{slug}/` for open issues
5. **Save** issue body as `001-issue.md` (the "filed" artifact, working backwards)

## Slug Generation

Use the same algorithm from `agentos/workflows/issue/audit.py`:
- Lowercase
- Replace spaces/underscores with hyphens
- Remove special characters
- Collapse multiple hyphens
- Prepend issue number: `{number}-{slug}` (e.g., `62-governance-workflow-stategraph`)

## Output Structure

```
docs/audit/done/
├── 62-governance-workflow-stategraph/
│   ├── 001-issue.md          # Issue title + body (the "source of truth")
│   ├── 002-comments.md       # All comments (if any)
│   └── 003-metadata.json     # Labels, PR links, timestamps
└── ...

docs/audit/active/
├── 19-review-audit-classes-tiers/
│   ├── 001-issue.md
│   ├── 002-comments.md
│   └── 003-metadata.json
└── ...
```

## File Contents

**001-issue.md:**
```markdown
# {Issue Title}

{Issue body as-is from GitHub}
```

**002-comments.md:**
```markdown
# Comments

## @username (2026-01-15)
{comment body}

## @username (2026-01-16)
{comment body}
```

**003-metadata.json:**
```json
{
  "issue_number": 62,
  "issue_url": "https://github.com/.../issues/62",
  "state": "closed",
  "labels": ["enhancement", "langgraph"],
  "closed_by_pr": "https://github.com/.../pull/63",
  "created_at": "2026-01-25T...",
  "closed_at": "2026-01-27T...",
  "backfilled_at": "2026-01-27T..."
}
```

## CLI Interface

```bash
python tools/backfill_issue_audit.py --repo martymcenroe/AgentOS
python tools/backfill_issue_audit.py --repo martymcenroe/Aletheia
python tools/backfill_issue_audit.py --all-registered  # All repos in project-registry.json
```

Options:
- `--dry-run` - Show what would be created without creating
- `--skip-existing` - Don't overwrite if slug directory exists
- `--open-only` - Only process open issues (default: all issues)

## Why Store Locally?

The audit structure is the **local source of truth**. Even though issues live on GitHub:
- Offline access without API calls
- Complete audit trail (matches governance workflow output)
- Batch processing without rate limits
- Historical snapshots (GitHub edits don't affect local copy)

## Labels

`enhancement`, `tooling`, `backfill`
