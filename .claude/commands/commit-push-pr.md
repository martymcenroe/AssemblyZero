---
description: Commit, push, and open a PR
argument-hint: "[--title \"...\"] [--draft]"
---

# Commit, Push, and PR

**Model hint:** Can use **Haiku** - simple git workflow with straightforward commit message generation.

Quick workflow to commit current changes, push to remote, and create a pull request.

---

## Context Gathering

First, gather the current state:
- Current git status: `git status`
- Current git diff (staged and unstaged): `git diff HEAD`
- Current branch: `git branch --show-current`
- Recent commits for message style: `git log --oneline -5`

---

## Execution

Based on the gathered context:

### Step 1: Create Branch (if on main)

If current branch is `main` or `master`:
```bash
git checkout -b feature/descriptive-name
```

### Step 2: Stage Changes

```bash
git add .
```

Or stage specific files if the user specified them.

### Step 3: Create Commit

Analyze the changes and create an appropriate commit message:
- Use conventional commit format: `type: description`
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Keep the first line under 72 characters
- Add body if changes are complex

```bash
git commit -m "$(cat <<'EOF'
type: brief description

Longer explanation if needed.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 4: Push to Remote

```bash
git push -u origin HEAD
```

### Step 5: Create Pull Request

```bash
gh pr create --title "type: brief description" --body "$(cat <<'EOF'
## Summary
- Bullet points describing changes

## Test plan
- [ ] How to verify the changes

---
Generated with Claude Code
EOF
)"
```

If `--draft` flag was provided:
```bash
gh pr create --draft --title "..." --body "..."
```

### Step 6: Report

Output the PR URL and summary:
```
Created PR #XXX: [title]
URL: https://github.com/owner/repo/pull/XXX
```

---

## Notes

- Detects the GitHub repo automatically via `gh repo view`
- If not a GitHub repo, stops after push
