# /commit-push-pr - CLI Usage (Manual Steps)

**File:** `docs/skills/0626c-commit-push-pr-cli.md`
**Prompt Guide:** [0626p-commit-push-pr-prompt.md](0626p-commit-push-pr-prompt.md)
**Version:** 2026-01-14

---

## Overview

The `/commit-push-pr` skill automates the git workflow. For manual execution, follow these steps.

---

## Manual Workflow

### Step 1: Create Branch (if on main)

```bash
# Check current branch
git -C /c/Users/mcwiz/Projects/PROJECT branch --show-current

# Create feature branch if on main
git -C /c/Users/mcwiz/Projects/PROJECT checkout -b feature-description
```

### Step 2: Stage Changes

```bash
# Stage all changes
git -C /c/Users/mcwiz/Projects/PROJECT add .

# Or stage specific files
git -C /c/Users/mcwiz/Projects/PROJECT add path/to/file
```

### Step 3: Create Commit

```bash
# View staged changes
git -C /c/Users/mcwiz/Projects/PROJECT diff --staged

# Commit with conventional message
git -C /c/Users/mcwiz/Projects/PROJECT commit -m "feat: add new feature

Detailed description here.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Step 4: Push to Remote

```bash
# Push with tracking
git -C /c/Users/mcwiz/Projects/PROJECT push -u origin HEAD
```

### Step 5: Create Pull Request

```bash
# Create PR
gh pr create --repo OWNER/REPO --title "feat: add new feature" --body "## Summary
- Added X
- Fixed Y

## Test plan
- [ ] Test A
- [ ] Test B"
```

---

## Conventional Commit Types

| Type | Use For |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `refactor` | Code refactoring |
| `test` | Test changes |
| `chore` | Maintenance |

---

## When to Use Manual vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Simple commit | **CLI** |
| Need commit message help | **Skill** |
| Complex PR body needed | **Skill** |
| Quick push | **CLI** |
| Saving tokens | **CLI** |

---

## Related Commands

```bash
# Check status
git -C /c/Users/mcwiz/Projects/PROJECT status

# View PR
gh pr view --repo OWNER/REPO

# View commit log
git -C /c/Users/mcwiz/Projects/PROJECT log --oneline -5
```

---

## Related Files

- Skill definition: `~/.claude/commands/commit-push-pr.md`
