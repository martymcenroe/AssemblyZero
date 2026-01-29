# Ideas

This folder is the **staging area** for issue creation. Ideas live here before they're ready for the GitHub issue tracker.

**Encrypted:** This folder's contents are encrypted in git. Only authorized users with the key can read these files.

## Folder Structure

```
ideas/
├── active/     # Ideas ready to work on (inbox)
├── done/       # Ideas filed as issues (auto-moved)
└── someday/    # "Maybe never" concepts
```

## Workflow Integration

The issue creation workflow can pick ideas directly from `active/`:

```bash
# Interactive picker - select from ideas/active/
python tools/run_issue_workflow.py --select

# Direct path (unchanged, backwards compatible)
python tools/run_issue_workflow.py --brief ideas/active/my-idea.md
```

**Lifecycle:**
1. Create idea in `ideas/active/my-idea.md`
2. Run `--select`, pick the idea
3. Workflow processes: brief → draft → review → file
4. After filing: idea moves to `ideas/done/{issue#}-my-idea.md`

## Naming Convention

- `YYYY-MM-slug.md` - Dated ideas
- `someday/` - "Maybe never" concepts
- Freeform names for evergreen ideas

## Security

**NEVER** use `echo "KEY" | base64 -d > file` - this leaks the key to shell history.

Use clipboard methods or save directly from your password manager:
```bash
# macOS
pbpaste | base64 -d > /tmp/repo.key
git-crypt unlock /tmp/repo.key
rm /tmp/repo.key

# Linux
xclip -selection clipboard -o | base64 -d > /tmp/repo.key
```
