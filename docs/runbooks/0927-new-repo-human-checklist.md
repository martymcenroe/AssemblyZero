# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-03-18

---

## Purpose

Every step the human must do when creating a new GitHub repo. The agent PAT cannot create repos or configure rulesets. Cerberus-AZ is fleet-wide (All repositories) so it covers new repos automatically.

After completing this checklist, hand off to the agent for scaffolding (CLAUDE.md, directory structure, poetry init, etc.).

---

## Checklist

### 1. Create the repo

Go to: https://github.com/new

| Field | Value |
|-------|-------|
| Repository name | the repo name (lowercase, hyphenated) |
| Description | one-line description of what it does |
| Visibility | Private (unless intentionally public) |
| Initialize with | check Add a README file |

Click Create repository.

### 2. Enable the wiki

Go to: https://github.com/martymcenroe/REPO/settings

Scroll to Features section. Check Wikis. Click Save (or it auto-saves).

### 3. Set up branch protection

Follow [0926 - Branch Protection Setup](0926-branch-protection-setup.md), quick reference:

1. https://github.com/martymcenroe/REPO/settings/rules > New branch ruleset
2. Name: main, Enforcement: Active
3. Add target > Include default branch
4. Check (in UI order): Restrict deletions, Require PR (1 approval), Block force pushes
5. Create

### 4. Hand off to agent

Tell the agent the repo is ready. The agent will:
- Clone locally via gh repo clone (HTTPS, never SSH)
- Create CLAUDE.md
- Set up directory structure
- Initialize poetry if applicable
- Push and verify

---

## Related Documents

- [0901 - New Project Setup](0901-new-project-setup.md) — Agent-side scaffolding
- [0926 - Branch Protection Setup](0926-branch-protection-setup.md) — Detailed branch protection steps

---

## History

| Date | Change |
|------|--------|
| 2026-03-18 | Initial runbook created |
