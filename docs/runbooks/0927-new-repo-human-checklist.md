# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 1.3
**Last Updated:** 2026-04-05

---

## Purpose

Every step the human must do when creating a new GitHub repo. The agent PAT (fine-grained) cannot create repos or configure rulesets. Cerberus-AZ app installation is fleet-wide (All repositories), but its GitHub Actions secrets must be deployed per-repo.

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

### 2. Enable wiki (if needed)

Skip this step if the repo doesn't need a wiki.

**Public repos:** Enable the wiki in Settings > Features > Wikis. The wiki inherits the repo's visibility.

**Private repos:** GitHub wikis inherit the repo's visibility — a private repo's wiki is also private. If you need a public-facing wiki for a private repo, create a separate public repo (e.g., `my-project-wiki`) and manage wiki content there instead.

### 3. Set up branch protection

Follow [0926 - Branch Protection Setup](0926-branch-protection-setup.md), quick reference:

1. https://github.com/martymcenroe/REPO/settings/rules > New branch ruleset
2. Name: main, Enforcement: Active
3. Add target > Include default branch
4. Check (in UI order): Restrict deletions, Require PR (1 approval), Block force pushes
5. Create

### 4. Deploy Cerberus secrets

Cerberus-AZ needs two GitHub Actions secrets (REVIEWER_APP_ID, REVIEWER_APP_PRIVATE_KEY) to approve PRs. The Cerberus app installation is fleet-wide, but GitHub Actions secrets are per-repo on personal accounts. New repos don't inherit secrets from existing repos.

**Important: generating a new .pem does NOT invalidate existing keys.** GitHub Apps support multiple active private keys simultaneously. Your existing repos keep working. You can generate and delete .pem files freely.

Run all of this in your own git-bash (never an agent session):

**Step 4a: Generate a private key**

1. Go to https://github.com/settings/apps/cerberus-az
2. Scroll down to Private keys
3. Click Generate a private key
4. Browser downloads a .pem file to your Downloads folder
   (filename like cerberus-az.2026-03-18.private-key.pem)

**Step 4b: Deploy to new repo(s)**

```
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/deploy_cerberus_secrets.py /c/Users/mcwiz/Downloads/THE-FILE.pem
```

The script deploys to all repos. Check the output — look for OK next to your new repo name(s).

(Future: #763 will add auto-detection of repos missing secrets, so you only deploy where needed.)

**Step 4c: Delete the .pem and revoke**

1. Delete the .pem file from Downloads immediately
2. Go back to https://github.com/settings/apps/cerberus-az > Private keys
3. Click Revoke on the key you just generated (the most recent one)
   — The secrets are already stored in GitHub Actions. The .pem is never needed again.
   — Revoking prevents the key from being used if the file wasn't fully deleted.

**If you skip this step:** PRs on the new repo will hang on the 1-approval requirement with no way to merge. Cerberus cannot approve without the secrets.

### 5. Hand off to agent

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
| 2026-03-18 | v1.1: Added Step 4 — Cerberus secrets deployment. App is fleet-wide but secrets are per-repo. |
| 2026-03-18 | v1.2: Expanded Step 4 with full .pem walkthrough. Clarified that new keys don't invalidate existing ones. Added revoke step. Referenced #763 for future auto-detection. |
| 2026-04-05 | v1.3: Made wiki step conditional with public/private guidance. Private repo wikis inherit visibility — use a separate public repo for public-facing wikis. |
