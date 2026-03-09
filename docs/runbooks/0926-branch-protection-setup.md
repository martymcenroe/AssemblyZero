# 0926 - Branch Protection Setup (Manual)

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-03-09

---

## Purpose

Configure branch protection for new repos when the agent PAT cannot do it. The fine-grained PAT deliberately excludes Administration scope (see [0925](0925-agent-token-setup.md)), so branch protection must be set manually via browser.

**When to use:** After creating a new repo with `new_repo_setup.py --no-github` and pushing, or after any repo creation where the agent reports a 403 on branch protection.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Repo exists on GitHub | `gh repo view martymcenroe/REPO` |
| At least one commit pushed to `main` | Branch must exist before it can be protected |

---

## Steps

### 1. Navigate to Branch Rules

Go to: `https://github.com/martymcenroe/REPO/settings/rules`

Click **"New ruleset"** → **"New branch ruleset"**

### 2. Configure Ruleset Header

| Field | Value |
|-------|-------|
| **Ruleset Name** | `main` |
| **Enforcement status** | **Active** (NOT Disabled) |

### 3. Add Target Branch

Under **"Target branches"**:
1. Click **"Add target"**
2. Select **"Include default branch"**

This targets `main`. The warning "This ruleset does not target any resources" should disappear.

### 4. Set Branch Rules

Check the following:

| Rule | Check? | Why |
|------|--------|-----|
| **Restrict deletions** | Yes | Prevent deleting `main` |
| **Block force pushes** | Yes | Prevent `git push --force` to `main` |
| **Require a pull request before merging** | Yes | Force PR workflow, no direct pushes |

Under **"Require a pull request before merging"** additional settings:

| Setting | Value | Why |
|---------|-------|-----|
| **Required approvals** | **0** | Solo developer — enforces PR workflow without needing a reviewer |
| Everything else | Unchecked | Not needed for solo workflow |

Leave all other rules unchecked (Restrict creations, Restrict updates, Require status checks, etc.) unless the repo has CI.

### 5. Leave Bypass List Empty

The bypass list should stay empty. No roles, teams, or apps should bypass protection.

### 6. Save

Click **"Create"** (green button at bottom).

---

## Verification

After saving, verify the ruleset is active:

1. The ruleset page should show **"Active"** (not "Disabled")
2. The target should show **"Default branch"** or **"main"**
3. Test from the agent:

```bash
# This should FAIL with "protected branch" error
cd /c/Users/mcwiz/Projects/REPO
echo "test" >> README.md
git add README.md && git commit -m "test direct push"
git push origin main
# Expected: remote rejected (protected branch hook declined)
git reset HEAD~1  # clean up
git checkout -- README.md
```

---

## Quick Reference (30-Second Version)

For when you've done this before and just need the checklist:

1. `https://github.com/martymcenroe/REPO/settings/rules` → New branch ruleset
2. Name: `main`, Enforcement: **Active**
3. Add target → Include default branch
4. Check: Restrict deletions, Block force pushes, Require PR (0 approvals)
5. Create

---

## Related Documents

- [0901 - New Project Setup](0901-new-project-setup.md) — Repo scaffolding (triggers this runbook)
- [0925 - Agent Token Setup](0925-agent-token-setup.md) — Why the PAT can't do this
- `docs/standards/0003-agent-prohibited-actions.md` — Agent safety rules

---

## History

| Date | Change |
|------|--------|
| 2026-03-09 | Initial runbook created (from patent-general setup experience) |
