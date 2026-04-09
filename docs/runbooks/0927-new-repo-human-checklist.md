# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 3.0
**Last Updated:** 2026-04-08

---

## Purpose

The human steps when creating a new repo. Most of the work is automated by `new_repo_setup.py` — it creates the local scaffold, GitHub repo, branch protection, workflow files, and initial push in one command.

The human handles only what the script can't: PAT switching for workflow files, Cerberus secret deployment, and optional wiki/domain setup.

---

## Checklist

### 1. Switch to classic PAT (required for workflow files)

The setup script creates `.github/workflows/` files. Pushing these requires a PAT with `workflow` scope. The fine-grained PAT deliberately lacks this scope (agents must not modify their own guardrails).

```bash
gh auth login -h github.com -p https
# Paste classic PAT with: repo + workflow scopes
# Get one from: https://github.com/settings/tokens
```

### 2. Run the setup script

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo_setup.py {name} [--public] [--license mit]
```

The script handles all of the following automatically:
- Local directory structure + all config files
- GitHub repo creation (forced lowercase) via `gh repo create --source . --push`
- Repo settings: wiki disabled, projects disabled, squash-only merge, delete branch on merge
- Branch protection: require PR (1 review), block force push, block deletion, enforce_admins, pr-sentinel check
- PR governance workflows (`pr-sentinel.yml`, `auto-reviewer.yml`)
- `.unleashed.json`, `.claude/settings.json`, security hooks
- Initial commit and push

The script prints a summary showing what succeeded and what failed. If push fails, it prints manual steps.

### 3. Switch back to fine-grained PAT (immediately)

```bash
gh auth login -h github.com -p https
# Paste fine-grained PAT
```

**Do this immediately.** The classic PAT has broader permissions than agents should ever have access to. Every minute it stays active is a risk window.

### 4. Deploy Cerberus secrets (if needed)

The auto-reviewer needs two secrets per repo: `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY`. These are deployed **fleet-wide** — the script covers ALL repos at once, not just the new one.

**Skip this step if** you've deployed Cerberus secrets since the last time you created a repo (the new repo is already covered by the fleet-wide install).

**If the new repo needs secrets**, follow this checklist as one uninterrupted sequence. Run all commands in your own git-bash (never an agent session):

1. Go to https://github.com/settings/apps/cerberus-az > Private keys
2. Click **Generate a private key** — browser downloads a `.pem` file
   (generating a new key does NOT invalidate existing keys)
3. Deploy to all repos:
   ```bash
   cd /c/Users/mcwiz/Projects/AssemblyZero
   poetry run python tools/deploy_cerberus_secrets.py /c/Users/mcwiz/Downloads/THE-FILE.pem
   ```
4. **Verify:** Look for `OK` next to your new repo name in the output
5. **Delete the .pem file immediately:**
   ```bash
   rm /c/Users/mcwiz/Downloads/THE-FILE.pem
   ```
6. Go back to https://github.com/settings/apps/cerberus-az > Private keys
7. Click **Revoke** on the key you just generated (most recent one)
   - The secrets are already stored in GitHub Actions — the .pem is never needed again
   - Revoking prevents the key from being used if the file wasn't fully deleted
   - **Note:** GitHub Apps require at least one active key. If only one key exists, you cannot revoke it. File deletion (step 5) is your only protection.
8. **Done.** Secrets deployed, .pem deleted, key revoked.

**What happens without secrets:** PRs pass pr-sentinel but don't get auto-approved. You can merge manually via the GitHub UI until secrets are deployed.

### 5. Create wiki (if needed)

Skip this step if the repo doesn't need a wiki.

**Public repos:** Enable the wiki in Settings > Features > Wikis. The wiki inherits the repo's visibility. Create the first wiki page.

**Private repos (shadow wiki):** GitHub wikis inherit the repo's visibility — a private repo's wiki is also private. Create a separate public repo using the naming convention `{repo}-wiki`:

```bash
gh repo create martymcenroe/{name}-wiki --public --description "{Name} public wiki" --repo martymcenroe/{name}-wiki
```

Then initialize it with a Home page:
```bash
gh repo clone martymcenroe/{name}-wiki /c/Users/mcwiz/Projects/{name}-wiki
cd /c/Users/mcwiz/Projects/{name}-wiki
echo "# {Name} Wiki" > Home.md
git add . && git commit -m "docs: initialize wiki"
git push
```

---

## What's Automatic (No Human Action)

These all happen without any per-repo human intervention:

| Component | Why It's Automatic |
|-----------|-------------------|
| Cerberus-AZ app access | Fleet-wide installation ("All repositories") — new repos are covered instantly |
| pr-sentinel check (Cloudflare Worker) | Receives webhooks for all repos, authenticates with its own stored credentials |
| pr-sentinel check (GitHub Actions) | Workflow file created by setup script in initial commit |
| Auto-reviewer workflow file | Created by setup script in initial commit |
| Repo settings | Configured by setup script: wiki off, projects off, squash-only, delete-branch-on-merge |
| Branch protection | Configured by setup script: 1 review, enforce_admins, pr-sentinel check, strict=false |
| Directory structure + configs | Created by setup script |

The **per-repo human steps** are: PAT switch (before/after), Cerberus secrets (fleet deploy), and optional wiki/domain setup.

---

## Related Documents

- [0901 - New Project Setup](0901-new-project-setup.md) — Script reference and file details
- [0926 - Branch Protection Setup](0926-branch-protection-setup.md) — Manual branch protection steps (fallback if script fails)
- [0925 - Agent Token Setup](0925-agent-token-setup.md) — PAT permissions and rotation

---

## History

| Date | Change |
|------|--------|
| 2026-03-18 | Initial runbook created |
| 2026-03-18 | v1.1: Added Cerberus secrets deployment. App is fleet-wide but secrets are per-repo. |
| 2026-03-18 | v1.2: Expanded .pem walkthrough. Clarified multi-key support. Added revoke step. |
| 2026-04-05 | v1.3: Made wiki step conditional with public/private guidance. |
| 2026-04-05 | v2.0: Complete rewrite. Script now handles repo creation, branch protection, and workflow deployment. Human steps reduced to Cerberus secrets (fleet-wide) and wiki setup. |
| 2026-04-08 | v3.0: Added PAT switch protocol (steps 1/3). Expanded repo settings (projects, merge, delete-branch). Rewrote Cerberus section as numbered checklist with .pem lifecycle notes. Added shadow wiki creation steps. (#883) |
