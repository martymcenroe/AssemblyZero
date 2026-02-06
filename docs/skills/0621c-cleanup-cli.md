# /cleanup - CLI Usage (Manual Steps)

**File:** `docs/skills/0621c-cleanup-cli.md`
**Prompt Guide:** [0621p-cleanup-prompt.md](0621p-cleanup-prompt.md)
**Version:** 2026-01-14

---

## Overview

The `/cleanup` skill is Claude-orchestrated - there's no standalone CLI tool. However, you can perform the same cleanup steps manually to save tokens.

---

## Manual Cleanup Steps

### Quick Mode (~2 min)

```bash
# 1. Check git status
git -C /c/Users/mcwiz/Projects/PROJECT status

# 2. Check branches
git -C /c/Users/mcwiz/Projects/PROJECT branch --list

# 3. Check open PRs (if GitHub repo)
gh pr list --state open --repo OWNER/REPO

# 4. Append session log manually
# Edit: C:\Users\mcwiz\Projects\PROJECT\docs\session-logs\YYYY-MM-DD.md
```

### Normal Mode (~5 min)

All of Quick mode, plus:

```bash
# 5. Check stashes
git -C /c/Users/mcwiz/Projects/PROJECT stash list

# 6. Fetch and prune
git -C /c/Users/mcwiz/Projects/PROJECT fetch --prune

# 7. Check worktrees
git -C /c/Users/mcwiz/Projects/PROJECT worktree list

# 8. Check open issues
gh issue list --state open --repo OWNER/REPO

# 9. Delete orphaned branches (remote gone, no worktree)
git -C /c/Users/mcwiz/Projects/PROJECT branch -D orphan-branch

# 10. Stage and commit
git -C /c/Users/mcwiz/Projects/PROJECT add docs/ CLAUDE.md
git -C /c/Users/mcwiz/Projects/PROJECT commit -m "docs: cleanup $(date +%Y-%m-%d)"
git -C /c/Users/mcwiz/Projects/PROJECT push
```

### Full Mode (~12 min)

All of Normal mode, plus:

```bash
# 11. Detailed branch info
git -C /c/Users/mcwiz/Projects/PROJECT branch -vv

# 12. Remote branches
git -C /c/Users/mcwiz/Projects/PROJECT branch -r

# 13. Inventory audit (manual review)
# Check docs/0003-file-inventory.md is up to date
```

---

## Session Log Format

Create/append to `docs/session-logs/YYYY-MM-DD.md`:

```markdown
## Session: session-name
- **Mode:** quick/normal/full cleanup
- **Model:** (manual)
- **Summary:** [brief description of what was done]
- **Next:** Per user direction
```

---

## Orphan Branch Detection

A branch is an orphan if:
1. Not `main` or `master`
2. Remote tracking shows `[gone]` in `git branch -vv`
3. No worktree exists for it

Safe to delete with:
```bash
git branch -D orphan-branch-name
```

---

## Known Projects

| Project | GitHub Repo |
|---------|-------------|
| Aletheia | martymcenroe/Aletheia |
| AssemblyZero | martymcenroe/AssemblyZero |
| Talos | martymcenroe/Talos |
| claude-code | anthropics/claude-code |
| maintenance | (none - skip gh commands) |

---

## When to Use Manual vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Simple end-of-session | Manual quick mode |
| Need orphan detection help | Use `/cleanup` prompt |
| Complex worktree situation | Use `/cleanup` prompt |
| Want automated commit message | Use `/cleanup` prompt |
| Saving tokens | Manual |

---

## Related Files

- Session logs: `PROJECT/docs/session-logs/YYYY-MM-DD.md`
- Skill definition: `AssemblyZero/.claude/commands/cleanup.md`
