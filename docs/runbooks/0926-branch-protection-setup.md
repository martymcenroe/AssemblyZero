# 0926 - Branch Protection Setup (Manual)

**Category:** Runbook / Operational Procedure
**Version:** 2.2
**Last Updated:** 2026-05-23

---

## Purpose

Configure **classic Branch Protection** for a repo when the script flow cannot do it. The fine-grained PAT deliberately excludes `Administration: write` (see [0925](0925-agent-token-setup.md)), so branch protection must be set either:

- **Preferred:** re-run the script's `configure_branch_protection()` step with the classic PAT via the in-process pattern (ADR-0216)
- **Fallback (this runbook):** manually via the browser, using classic Branch Protection (NOT the newer Rulesets UI)

**When to use the manual fallback:** after creating a new repo and pushing at least one commit, AND the script's branch-protection step has failed AND re-running it with the classic PAT is not viable.

**Why classic, not Rulesets:** every script in the fleet (`tools/new_repo_setup.py`, `tools/fix_branch_protections.py`, `tools/deploy_auto_reviewer_fleet.py`, `tools/github_protection_audit.py`, `tools/remediate_patent_general_protection.py`, `tools/remediate_fleet_branch_protection.py`) uses the classic Branch Protection API (`PUT /repos/{O}/{R}/branches/main/protection`). All 48+ protected repos in the fleet use classic protection. Per #1203 Option A (2026-05-22), the lone Rulesets outlier (patent-general) was migrated to classic on 2026-05-23 for fleet uniformity. Manual steps should match the fleet, not create a new outlier.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Repo exists on GitHub | `gh repo view martymcenroe/REPO` |
| At least one commit pushed to main | Branch must exist before it can be protected |
| Cerberus-AZ installed | Already fleet-wide (All repositories) — no action needed |

---

## Steps

### 1. Navigate to classic Branch Protection

Go to: **https://github.com/martymcenroe/REPO/settings/branches**

Under **Branch protection rules**, click **Add classic branch protection rule**.

> ⚠️ Do NOT use the **Add ruleset** path or navigate to `/settings/rules`. Rulesets are the wrong mechanism for this fleet; the classic Branch Protection rule is what every script targets.

### 2. Set Branch name pattern

| Field | Value (type exactly, no quotes) |
|-------|--------------------------------|
| Branch name pattern | `main` |

### 3. Set Protection Rules

Check exactly the following options. Leave everything else unchecked.

| Rule | Setting | Why |
|------|---------|-----|
| **Require a pull request before merging** | Checked | Forces PR workflow, no direct pushes |
| ↳ Required approvals | `1` | Cerberus-AZ auto-approves after pr-sentinel passes |
| ↳ Dismiss stale pull request approvals when new commits are pushed | Unchecked | Matches `CLASSIC_PROTECTION_BODY` (`dismiss_stale_reviews: false`) |
| ↳ Require review from Code Owners | Unchecked | Matches `CLASSIC_PROTECTION_BODY` (`require_code_owner_reviews: false`) |
| **Require status checks to pass before merging** | Checked | Gates merge on pr-sentinel result |
| ↳ Require branches to be up to date before merging | Unchecked | Matches `CLASSIC_PROTECTION_BODY` (`strict: false`) |
| ↳ Status checks that are required | Add: `pr-sentinel / issue-reference` | The single required check fleet-wide |
| **Do not allow bypassing the above settings** | Checked | Enforces protection against admins too (`enforce_admins: true`) |
| **Allow force pushes** | Unchecked | Matches `allow_force_pushes: false` |
| **Allow deletions** | Unchecked | Matches `allow_deletions: false` |
| **Restrict who can push to matching branches** | Unchecked | Matches `restrictions: null` — no per-user allowlist; admin-only via API only |

### 4. Save

Scroll to the bottom and click **Create** (green button).

---

## Verification

After saving, verify the rule is active and matches fleet standard:

### UI check

The Branch protection rules section should now list one rule:
- Branch name pattern: `main`
- Required reviews: `1`
- Required checks: `pr-sentinel / issue-reference`
- Includes administrators

### API check

```bash
gh api repos/martymcenroe/REPO/branches/main/protection --jq '{
    enforce_admins: .enforce_admins.enabled,
    required_approving_review_count: .required_pull_request_reviews.required_approving_review_count,
    required_checks: (.required_status_checks.contexts // []),
    allow_force_pushes: .allow_force_pushes.enabled,
    allow_deletions: .allow_deletions.enabled
}'
```

Expected output:

```json
{
  "enforce_admins": true,
  "required_approving_review_count": 1,
  "required_checks": ["pr-sentinel / issue-reference"],
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

### Direct-push refusal test

Optional (only if you want to confirm the rule blocks pushes):

```bash
cd /c/Users/mcwiz/Projects/REPO
echo "test" >> README.md
git add README.md && git commit -m "test direct push"
git push origin main
# Expected: remote rejected (protected branch hook declined)
git reset HEAD~1  # clean up
git checkout -- README.md
```

---

## Quick Reference (30-second version)

1. `https://github.com/martymcenroe/REPO/settings/branches` → **Add classic branch protection rule** (NOT `/settings/rules`)
2. Branch name pattern: `main`
3. Check: Require PR (1 approval), Require status checks (`pr-sentinel / issue-reference`), Do not allow bypassing, Block force pushes, Block deletions
4. Create

---

## Related Documents

- [0901 - New Project Setup](0901-new-project-setup.md) — Repo scaffolding (triggers this runbook)
- [0925 - Agent Token Setup](0925-agent-token-setup.md) — Why the fine-grained PAT can't do this directly
- `docs/standards/0017-classic-pat-fleet-tooling-reference-architecture.md` — Patterns for the in-process classic PAT (preferred over manual fallback)
- `tools/remediate_patent_general_protection.py` — Reference one-shot tool: shows the canonical `CLASSIC_PROTECTION_BODY` shape this manual procedure must match
- `tools/new_repo_setup.py:configure_branch_protection()` — The canonical body the manual steps mirror

---

## History

| Date | Change |
|------|--------|
| 2026-03-09 | Initial runbook created (from patent-general setup experience) |
| 2026-03-18 | v2.0: Reordered rules to match GitHub UI top-to-bottom. Added Cerberus-AZ step. Changed required approvals from 0 to 1 (Cerberus auto-approves). Removed smart quotes and ambiguous backtick formatting from values. |
| 2026-04-18 | v2.1: Added mechanism-mismatch warning. Manual steps used Rulesets; fleet uses classic Branch Protection. (Tracked under #924, closed without alignment.) |
| 2026-05-23 | v2.2: Rewrote manual steps to use classic Branch Protection (matches the fleet and every script). Removed the mechanism-mismatch warning (no longer applicable). Verification step uses API call to match expected `CLASSIC_PROTECTION_BODY`. Driven by #1203 Option A (patent-general migrated FROM Rulesets TO classic) and #1211 (this rewrite). |
