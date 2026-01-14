# /commit-push-pr - Prompt Usage

**File:** `docs/skills/0626p-commit-push-pr-prompt.md`
**CLI Guide:** [0626c-commit-push-pr-cli.md](0626c-commit-push-pr-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/commit-push-pr                    # Full workflow
/commit-push-pr --title "..."      # Custom PR title
/commit-push-pr --draft            # Create as draft PR
/commit-push-pr --help             # Show help
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| Need commit message generated | **Skill** |
| Complex changes to describe | **Skill** |
| Quick simple commit | **CLI** |
| Want PR body written | **Skill** |
| Saving tokens | **CLI** |

---

## What It Does

1. Creates branch if on main
2. Stages all changes
3. Generates conventional commit message
4. Pushes to remote
5. Creates PR with summary and test plan

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--title` | Custom PR title |
| `--draft` | Create as draft PR |
| `--help` | Show help |

---

## Example Session

```
User: /commit-push-pr

Claude: I'll commit your changes and create a PR.

[Checks git status]
[Stages changes]

Creating commit:
```
feat: add permission friction detection

- Add giant permission detection (>300 chars)
- Add embedded content detection
- Add JSON validation before save

Co-Authored-By: Claude <noreply@anthropic.com>
```

[Pushes to origin]
[Creates PR]

PR created: https://github.com/owner/repo/pull/456

## Summary
- Added giant permission detection for permissions over 300 characters
- Added embedded content detection for newlines, markdown, code
- Added JSON validation with atomic writes

## Test plan
- [ ] Run --clean --dry-run to verify detection
- [ ] Test with corrupted settings file
- [ ] Verify backup creation
```

---

## Commit Message Format

Claude generates conventional commits:

```
type: brief description (under 72 chars)

Detailed explanation if needed.

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Types
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `refactor` - Code restructuring
- `test` - Test changes
- `chore` - Maintenance

---

## PR Body Format

```markdown
## Summary
- Bullet points of changes

## Test plan
- [ ] Test checklist items

🤖 Generated with Claude Code
```

---

## Rules Followed

- One command per Bash call
- Uses `git -C /path` for operations
- Respects .gitignore
- Won't commit secrets
- Asks before force-push
- Adds Co-Authored-By trailer

---

## Source of Truth

**Skill definition:** `~/.claude/commands/commit-push-pr.md`
