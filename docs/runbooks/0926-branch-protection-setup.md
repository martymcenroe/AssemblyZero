# 0926 - Branch Protection Setup (Manual)

**Category:** Runbook / Operational Procedure
**Version:** 2.1
**Last Updated:** 2026-04-18

---

## Purpose

Configure branch protection for new repos when the agent PAT cannot do it. The fine-grained PAT deliberately excludes Administration scope (see [0925](0925-agent-token-setup.md)), so branch protection must be set manually via browser.

**When to use:** After creating a new repo and pushing at least one commit, or after any repo creation where the agent reports a 403 on branch protection.

> ### ⚠️ Mechanism mismatch — read before following these steps
>
> This runbook uses GitHub's newer **Rulesets** UI. However, `tools/new_repo_setup.py` uses the **classic Branch Protection API** (`PUT /repos/{owner}/{repo}/branches/main/protection`), as does every script in the fleet (`fix_branch_protections.py`, `deploy_auto_reviewer_fleet.py`, `github_protection_audit.py`). All 48+ protected repos in the fleet use classic branch protection, not rulesets.
>
> **If the script ran successfully:** you do NOT need this runbook. The script already set classic branch protection correctly.
>
> **If you follow the manual steps below:** the resulting ruleset works functionally (same rules enforced), but the repo will appear as a ruleset-protected outlier in `data/branch-protection-audit.csv` instead of matching the fleet majority. Known outlier of this type: `patent-general` (#748 history).
>
> **Preferred recovery path when the script fails on branch protection:** re-run only the `configure_branch_protection()` step with a classic PAT. This keeps the repo consistent with the fleet. Full alignment to classic-protection manual steps is tracked under #924.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Repo exists on GitHub | `gh repo view martymcenroe/REPO` |
| At least one commit pushed to main | Branch must exist before it can be protected |
| Cerberus-AZ installed | Already fleet-wide (All repositories) — no action needed |

---

## Steps

### 1. Navigate to Branch Rules

Go to: https://github.com/martymcenroe/REPO/settings/rules

Click New ruleset > New branch ruleset

### 2. Configure Ruleset Header

| Field | Value (type exactly, no quotes) |
|-------|--------------------------------|
| Ruleset Name | main |
| Enforcement status | Active (NOT Disabled) |

### 3. Add Target Branch

Under Target branches:
1. Click Add target
2. Select Include default branch

The warning about no targeted resources should disappear.

### 4. Set Branch Rules

Rules are listed in the order they appear in the GitHub UI. Check only these three, leave everything else unchecked:

| UI Position | Rule | Check? | Why |
|-------------|------|--------|-----|
| 3rd | Restrict deletions | Yes | Prevent deleting main |
| 7th | Require a pull request before merging | Yes | Force PR workflow, no direct pushes |
| 9th | Block force pushes | Yes | Prevent git push --force to main |

Under Require a pull request before merging, expand the additional settings:

| Setting | Value | Why |
|---------|-------|-----|
| Required approvals | 1 | Cerberus-AZ auto-approves after pr-sentinel passes |
| Everything else | Unchecked | Not needed |

### 5. Leave Bypass List Empty

No roles, teams, or apps should bypass protection.

### 6. Save

Click Create (green button at bottom).

---

## Verification

After saving, verify the ruleset is active:

1. The ruleset page should show Active (not Disabled)
2. The target should show Default branch or main
3. Agent verification:

```bash
# This should FAIL with protected branch error
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

1. https://github.com/martymcenroe/REPO/settings/rules > New branch ruleset
2. Name: main, Enforcement: Active
3. Add target > Include default branch
4. Check (in UI order): Restrict deletions, Require PR (1 approval), Block force pushes
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
| 2026-03-18 | v2.0: Reordered rules to match GitHub UI top-to-bottom. Added Cerberus-AZ step. Changed required approvals from 0 to 1 (Cerberus auto-approves). Removed smart quotes and ambiguous backtick formatting from values. |
| 2026-04-18 | v2.1: Added mechanism-mismatch warning. Manual steps use Rulesets; the script and fleet use classic Branch Protection API. (Closes #924) |
