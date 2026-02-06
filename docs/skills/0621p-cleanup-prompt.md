# /cleanup - Prompt Usage

**File:** `docs/skills/0621p-cleanup-prompt.md`
**CLI Guide:** [0621c-cleanup-cli.md](0621c-cleanup-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/cleanup              # Normal mode (default)
/cleanup --quick      # Minimal - log only, no commit
/cleanup --full       # Comprehensive - includes inventory audit
/cleanup --help       # Show help
/goodbye              # Alias for --quick
/closeout             # Alias for /cleanup
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| End of work session | **Skill** - handles everything |
| Quick status check | **CLI** - saves tokens |
| Complex orphan branches | **Skill** - Claude helps decide |
| Need commit message written | **Skill** - Claude generates |
| Just want git status | **CLI** - one command |

---

## Modes

### --quick (~2 min)

Minimal cleanup. Records session but does NOT commit.

**What it does:**
- Git status check
- Branch list
- Open PRs check
- Appends session log

**What it skips:**
- Commit and push
- Worktree analysis
- Auto-delete orphans

**Use when:** Quick break, will return soon.

### --normal (~5 min) - Default

Standard end-of-session cleanup.

**What it does:**
- Everything in quick mode
- Stash list check
- Fetch and prune remotes
- Worktree list
- Auto-delete orphaned branches
- Commit and push

**Use when:** Ending a work session.

### --full (~12 min)

Comprehensive cleanup for longer breaks.

**What it does:**
- Everything in normal mode
- Detailed branch analysis
- Remote branch list
- Inventory audit

**Use when:** Before vacation, end of feature, major milestone.

---

## Mode Comparison

| Check | Quick | Normal | Full |
|-------|:-----:|:------:|:----:|
| Git status | YES | YES | YES |
| Branch list | YES | YES | YES |
| Open PRs | YES | YES | YES |
| Session log append | YES | YES | YES |
| Commit & push | | YES | YES |
| Stash list | | YES | YES |
| Worktree list | | YES | YES |
| Auto-delete orphans | | YES | YES |
| Inventory audit | | | YES |

---

## Example Session

```
User: /cleanup

Claude: Running normal cleanup for AssemblyZero...

[Spawns Sonnet agent to execute cleanup]

## Cleanup Results

| Check | Status |
|-------|--------|
| Project | AssemblyZero |
| Git Status | Clean |
| Open PRs | 2 open |
| Open Issues | 5 |
| Branches | main, feature-123 |
| Worktrees | main only |
| Auto-Deleted | 1 branch (old-feature) |
| Stashes | None |
| Commit | Pushed |

Session logged to docs/session-logs/2026-01-14.md
```

---

## Flags

| Flag | Description |
|------|-------------|
| `--help` | Show help and exit |
| `--quick` | Minimal cleanup, no commit |
| `--normal` | Standard cleanup (default) |
| `--full` | Comprehensive cleanup |
| `--no-auto-delete` | Skip orphan branch deletion |

---

## Auto-Delete Safety

Branches are only auto-deleted if ALL conditions met:
1. Not `main` or `master`
2. Remote tracking shows `[gone]`
3. No worktree exists for it

Use `--no-auto-delete` to review manually instead.

---

## Session Log

Claude appends to `docs/session-logs/YYYY-MM-DD.md`:

```markdown
## Session: session-name
- **Mode:** normal cleanup
- **Model:** Claude Sonnet 4
- **Summary:** [what was accomplished]
- **Next:** Per user direction
```

---

## Troubleshooting

### "Project not detected"

If Claude can't detect the project:
1. Ensure you're in a project directory
2. Check the known projects registry in cleanup.md

### Orphan branches not deleted

Check:
1. Is `--no-auto-delete` set?
2. Does branch have a worktree?
3. Is remote tracking correct?

---

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `/sync-permissions` | Often run together |
| `/commit-push-pr` | Cleanup handles commits |
| `/onboard` | Opposite operation (start vs end) |

---

## Source of Truth

**Skill definition:** `AssemblyZero/.claude/commands/cleanup.md`
**User stub:** `~/.claude/commands/cleanup.md`
