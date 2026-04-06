# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 2.0
**Last Updated:** 2026-04-05

---

## Purpose

The human steps when creating a new repo. Most of the work is automated by `new_repo_setup.py` — it creates the local scaffold, GitHub repo, branch protection, workflow files, and initial push in one command.

The human handles only what the script can't: Cerberus secret deployment (requires a .pem from the GitHub UI) and wiki setup (a human decision).

---

## Checklist

### 1. Run the setup script

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo_setup.py {name} [--public] [--license mit]
```

The script handles all of the following automatically:
- Local directory structure (31 dirs) + all config files
- GitHub repo creation via `gh repo create --source . --push`
- Branch protection (require PR, block force push, block deletion, pr-sentinel check)
- PR governance workflows (`pr-sentinel.yml`, `auto-reviewer.yml`)
- Wiki disable (default — override below if needed)
- `.unleashed.json`, `.claude/settings.json`, security hooks
- Initial commit and push

If `gh repo create` fails (PAT lacks create permission), the script prints manual fallback steps.

### 2. Deploy Cerberus secrets (if needed)

The auto-reviewer workflow (deployed by the script in step 1) needs two GitHub Actions secrets to approve PRs: `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY`. These are deployed **fleet-wide** — the script covers ALL repos at once, not just the new one.

**Check if secrets are already deployed:** If you've run `deploy_cerberus_secrets.py` since the last time you created a repo, the new repo might not have secrets yet. If your last fleet deploy was recent and you haven't created repos since, you're fine — skip to step 3.

**If the new repo needs secrets:**

Run all of this in your own git-bash (never an agent session):

**Step 2a: Generate a private key**

1. Go to https://github.com/settings/apps/cerberus-az
2. Scroll down to Private keys
3. Click Generate a private key
4. Browser downloads a .pem file to your Downloads folder
   (filename like cerberus-az.2026-03-18.private-key.pem)

**Important:** generating a new .pem does NOT invalidate existing keys. GitHub Apps support multiple active private keys simultaneously.

**Step 2b: Deploy to all repos**

```
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/deploy_cerberus_secrets.py /c/Users/mcwiz/Downloads/THE-FILE.pem
```

The script deploys to ALL repos. Check the output — look for OK next to your new repo name(s).

**Step 2c: Delete the .pem and revoke**

1. Delete the .pem file from Downloads immediately
2. Go back to https://github.com/settings/apps/cerberus-az > Private keys
3. Click Revoke on the key you just generated (the most recent one)
   — The secrets are already stored in GitHub Actions. The .pem is never needed again.
   — Revoking prevents the key from being used if the file wasn't fully deleted.

**What happens without secrets:** PRs on the new repo will pass pr-sentinel (the check) but won't get auto-approved (the auto-reviewer workflow will fail). You can still merge manually via the GitHub UI until secrets are deployed.

### 3. Create wiki (if needed)

Skip this step if the repo doesn't need a wiki.

**Public repos:** Enable the wiki in Settings > Features > Wikis. The wiki inherits the repo's visibility. Create the first wiki page.

**Private repos:** GitHub wikis inherit the repo's visibility — a private repo's wiki is also private. If you need a public-facing wiki for a private repo, create a separate public repo (e.g., `my-project-wiki`) and manage wiki content there instead.

---

## What's Automatic (No Human Action)

These all happen without any per-repo human intervention:

| Component | Why It's Automatic |
|-----------|-------------------|
| Cerberus-AZ app access | Fleet-wide installation ("All repositories") — new repos are covered instantly |
| pr-sentinel check (Cloudflare Worker) | Receives webhooks for all repos, authenticates with its own stored credentials |
| pr-sentinel check (GitHub Actions) | Workflow file created by setup script in initial commit |
| Auto-reviewer workflow file | Created by setup script in initial commit |
| Branch protection | Configured by setup script via GitHub API |
| Directory structure + configs | Created by setup script |

The **only** per-repo human steps are Cerberus secrets (fleet deploy covers it) and wiki setup.

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
