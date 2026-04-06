# 0016 - PR Governance System Architecture

**Category:** Engineering Standard / System Architecture
**Version:** 1.0
**Last Updated:** 2026-04-06

---

## 1. Purpose

This document is the single source of truth for how the PR governance system works, why it exists, and what the canonical configuration is for every repo in the fleet.

### Why This System Exists

AI coding agents exhibit a consistent escalation pattern when encountering permission barriers: direct bypass, flag escalation, credential acquisition, and confabulation (documented in `dispatch/technical-papers/emergent-adversarial-behavior.md`). Instruction-based controls ("soft controls" in CLAUDE.md) fail under task-completion pressure because compliance is inversely correlated with recovery pressure.

The PR governance system is a **hard control** — infrastructure that the agent cannot modify, withdraw, or forge. It enforces the **Permission Minimum Principle**: the token used by the constrained actor must not include any permission that allows modification of the enforcement mechanism itself.

Specifically, the system ensures:
- Every PR must reference an open GitHub issue before merging
- Every PR must receive an approval from a non-author identity
- The agent cannot bypass, disable, or forge any of these requirements
- The agent's fine-grained PAT deliberately lacks `administration` scope

---

## 2. Architecture

The system has three components that work together:

```
PR created/edited on any repo
        |
        v
+-------------------+     +-------------------+
| pr-sentinel-mm    |     | pr-sentinel.yml   |
| (Cloudflare       |     | (GitHub Actions   |
|  Worker)          |     |  workflow)         |
|                   |     |                   |
| Receives webhook  |     | Triggered by GH   |
| HMAC-verified     |     | pull_request event|
| Validates body    |     | Regex check on    |
| Verifies issues   |     | title/body/commits|
| via GitHub API    |     |                   |
|                   |     |                   |
| Posts check run:  |     | GitHub posts      |
| "pr-sentinel /    |     | workflow status:   |
|  issue-reference" |     | "pr-sentinel /    |
|                   |     |  issue-reference" |
+-------------------+     +-------------------+
        |                         |
        v                         v
+-----------------------------------------------+
| Branch Protection                             |
| Required status check must pass before merge  |
+-----------------------------------------------+
        |
        v (check passed)
+-------------------+
| auto-reviewer.yml |
| (GitHub Actions   |
|  reusable wf)     |
|                   |
| Polls check runs  |
| for "issue-       |
|  reference"       |
| (substring match) |
|                   |
| If all pass:      |
| submits approval  |
| as Cerberus-AZ    |
| GitHub App        |
+-------------------+
        |
        v (1 approval received)
+-----------------------------------------------+
| Branch Protection                             |
| Required: 1 approving review                  |
| mergeable_state -> "clean"                    |
+-----------------------------------------------+
        |
        v
   Agent can merge via `gh pr merge --squash`
```

### 2.1 pr-sentinel-mm (Cloudflare Worker)

**What:** A Cloudflare Worker deployed as a GitHub App receiving webhooks from all repos.

| Property | Value |
|----------|-------|
| App name | `pr-sentinel-mm` |
| App ID | `2975092` |
| Deployed at | `https://pr-sentinel.mcwizard1.workers.dev` |
| Routes | `/health` (GET, returns 200), `/webhook` (POST, handles events) |
| Cloudflare account | `4fe1c5e241425c85d0f2c35c69fb45b8` |
| Source code | `sentinel/src/` in AssemblyZero |
| Check run name | Configurable via `CHECK_NAME` env var, default `pr-sentinel / issue-reference` |

**How it works:**

1. Receives `pull_request` webhook (opened, edited, synchronize, reopened)
2. Verifies HMAC-SHA256 signature using `WEBHOOK_SECRET`
3. Auto-passes dependabot PRs (creates a passing check run, does not skip)
4. Validates PR body via regex:
   - **Pass:** `Closes #N` or `Close #N` or `Closed #N` (case-insensitive, supports cross-repo `owner/repo#N`)
   - **Pass:** `No-Issue: <reason>` (requires non-empty reason)
   - **Fail:** Empty body, no matching pattern
5. If regex passes with issue refs, verifies each ref via GitHub API:
   - Issue must exist (not 404)
   - Issue must be open (not closed)
   - Reference must be an issue (not a PR)
   - Max 10 refs verified per webhook (rate limit protection)
   - Cross-repo refs fail closed on errors; same-repo refs fail open on transient errors
6. Creates check run via GitHub Checks API with conclusion `success` or `action_required`

**Authentication:** GitHub App JWT (RS256) exchanged for installation access token. Private key stored as base64-encoded Worker secret (`PRIVATE_KEY_B64`).

### 2.2 pr-sentinel.yml (GitHub Actions Workflow)

**What:** A GitHub Actions workflow deployed to every repo, providing a redundant regex-based check.

| Property | Value |
|----------|-------|
| Workflow name | `pr-sentinel` |
| Job name | `issue-reference` |
| Check name (as composed by GitHub) | `pr-sentinel / issue-reference` |
| Source | `.github/workflows/pr-sentinel.yml` in each repo |

**How it works:**

1. Triggered by `pull_request` event (opened, edited, synchronize, reopened)
2. Checks PR commits, title, and body for `Closes #N` pattern (case-insensitive)
3. Exit 0 = pass, exit 1 = fail (GitHub records as workflow status)

**Key differences from the Worker:**
- Regex-only: does NOT verify that referenced issues exist or are open
- Does NOT check for `No-Issue:` exemptions
- Checks commit messages in addition to PR title/body (Worker only checks PR body)
- No issue state validation (closed issues pass regex)

### 2.3 auto-reviewer.yml (Reusable Workflow)

**What:** A reusable GitHub Actions workflow in AssemblyZero that auto-approves PRs when all required checks pass.

| Property | Value |
|----------|-------|
| Location | `martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml` |
| Caller | `.github/workflows/auto-reviewer.yml` in each repo (deployed by `deploy_auto_reviewer_fleet.py`) |
| Default required checks input | `"issue-reference"` |
| Match strategy | **Substring:** `select(.name \| contains("issue-reference"))` |
| Approval identity | Cerberus-AZ GitHub App (via `REVIEWER_APP_ID` + `REVIEWER_APP_PRIVATE_KEY` secrets) |
| Timeout | 10 minutes (30 attempts x 20s) |

**Why substring matching:** Issue #742 discovered that the Cloudflare Worker posts check runs named `pr-sentinel / issue-reference`. Exact matching on `pr-sentinel` failed because the actual name contains a `/`. The fix was to match on the substring `issue-reference`, which matches both the Worker's check run name and the GitHub Actions job name.

**Caller workflow** (deployed to each repo):
```yaml
uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main
with:
  required_checks: "issue-reference"
secrets:
  REVIEWER_APP_ID: ${{ secrets.REVIEWER_APP_ID }}
  REVIEWER_APP_PRIVATE_KEY: ${{ secrets.REVIEWER_APP_PRIVATE_KEY }}
```

---

## 3. Branch Protection Contract

### Canonical Configuration

Every repo MUST have these branch protection settings on `main`:

| Setting | Value | Why |
|---------|-------|-----|
| `required_pull_request_reviews.required_approving_review_count` | `1` | Cerberus-AZ auto-approves; ensures non-author approval |
| `required_status_checks.strict` | `false` | Do not require branch to be up-to-date before merge |
| `required_status_checks.contexts` | See section 3.1 | Check name depends on which pr-sentinel implementation is gating |
| `enforce_admins` | `true` | Even admin tokens must obey protection rules |
| `allow_force_pushes` | `false` | Prevent history rewriting |
| `allow_deletions` | `false` | Prevent branch deletion |

### 3.1 Required Status Check Context

**This is the source of fleet-wide inconsistency.** Two valid configurations exist depending on which pr-sentinel implementation gates the repo:

| Configuration | Context value | How it gets there |
|---------------|--------------|-------------------|
| **Fleet majority (48 repos)** | `pr-sentinel / issue-reference` | Set by `deploy_auto_reviewer_fleet.py` or `fix_branch_protections.py` |
| **AssemblyZero + Sextant** | `issue-reference` with `app_id: 15368` | Set manually or by `new_repo_setup.py` |

**Both configurations work** because:
- The Cloudflare Worker posts a check named `pr-sentinel / issue-reference`
- The GitHub Actions workflow creates a status named `pr-sentinel / issue-reference` (workflow/job composite)
- Context `pr-sentinel / issue-reference` matches the Worker's check
- Context `issue-reference` with app_id filter 15368 matches the Actions workflow's job name

**Known contradiction:** Issue #748 says `new_repo_setup.py` should set `issue-reference`. The fleet deployment scripts set `pr-sentinel / issue-reference`. Both work. This needs resolution (see #886).

**What `new_repo_setup.py` currently sets:** `pr-sentinel` (bare, no slash, no job name). This is **wrong** — it matches neither the Worker's check run name nor the Actions workflow's composite name. Tracked in #748 and #883.

### 3.2 The app_id Filter

When branch protection includes an `app_id` in the required status checks, GitHub only considers check runs from that specific app. Without it, any app posting a check with the matching name satisfies the requirement.

| app_id | App | Used by |
|--------|-----|---------|
| `15368` | `github-actions` (GitHub's own Actions app) | AssemblyZero, Sextant |
| `2975092` | `pr-sentinel-mm` (Cloudflare Worker GitHub App) | Hermes, patent-general, power-agent.github.io |
| `null` (no filter) | Any app | Fleet majority (~48 repos) |

---

## 4. Token Boundaries

### Fine-Grained PAT (Agent's Token)

The agent operates with a fine-grained PAT that deliberately excludes:

| Excluded Permission | What It Prevents |
|---------------------|-----------------|
| `administration` | Cannot modify or delete branch protection rules |
| `workflow` | Cannot push changes to `.github/workflows/` files |
| `organization_administration` | Cannot modify org-level settings |

This means the agent **cannot**:
- Bypass branch protection with `--admin`
- Delete branch protection via API
- Modify workflow files that enforce governance
- Cancel in-progress workflow runs

See standard 0003 (Agent Prohibited Actions) and runbook 0925 (Agent Token Setup) for full details.

### Classic PAT (Human-Only, Temporary)

Used for fleet-wide operations that require elevated access. Always scripted, always temporary, always diagnostic-first.

| Script | Purpose | Required Scopes |
|--------|---------|----------------|
| `deploy_auto_reviewer_fleet.py` | Deploy caller workflow + enable reviews | `repo` + `workflow` |
| `fix_branch_protections.py` | Set protection on unprotected repos | `repo` + `admin:repo_hook` + `read:org` |
| `merge_sentinel_permissions_prs.py` | Merge workflow permission fix PRs | `repo` |
| `push_workflow_fixes.py` | Push workflow file changes | `workflow` |
| `github_protection_audit.py` | Audit branch protection fleet-wide | `repo` + `admin:repo_hook` + `read:org` (audit mode) |
| `new_repo_setup.py` | Create new repos with protection | Optional classic PAT for admin scope |

**Protocol:** Switch to classic PAT, run the script, switch back to fine-grained PAT immediately. The classic PAT is never stored in environment variables or configuration files accessible to agents.

```bash
gh auth login -h github.com -p https   # paste classic PAT
poetry run python tools/{script}.py     # run the operation
gh auth login -h github.com -p https   # paste fine-grained PAT back
```

---

## 5. Fleet Configuration

### Outliers

| Category | Repos | Notes |
|----------|-------|-------|
| `strict=true` | CS512_link_predictor, GentlePersuader, Hermes, nec2017-analyzer, power-agent.github.io | Requires branch to be up-to-date before merge. May be intentional for these repos or drift. |
| No protection | boostgauge, comp-environ, gh-galaxy-quest | Need protection added. |
| No main branch | github-readme-stats (fork), sextant-wiki (wiki repo) | Expected — no main to protect. |
| Ruleset instead of classic protection | patent-general | GitHub auto-created ruleset on web UI repo creation. |

Full audit data: `data/branch-protection-audit.csv`

---

## 6. Failure Modes

| Failure | Symptom | Root Cause | Fix |
|---------|---------|------------|-----|
| PR body missing `Closes #N` | Check fails, `mergeable_state: blocked` | Agent omitted issue reference | Add `Closes #N` to PR body: `gh pr edit {N} --body "...Closes #N..."` |
| Referenced issue is closed | Worker check fails | Issue was already resolved | Create a new issue, update PR body |
| Referenced issue is a PR | Worker check fails | Agent used PR number not issue number | Create an issue, reference that instead |
| Naked `#N` format | Worker check fails, Actions check fails | `Closes` keyword missing | Add `Closes` prefix |
| Dependabot PR stuck | Check suite queued forever | Worker skips without creating check run | Fixed in #749 — Worker now creates passing check for dependabot |
| Auto-reviewer timeout | PR not approved after 10 min | Required check not found by substring match | Verify check run name contains `issue-reference` |
| Missing Cerberus secrets | Auto-reviewer workflow fails | `REVIEWER_APP_ID` or `REVIEWER_APP_PRIVATE_KEY` not set | Run `deploy_cerberus_secrets.py` |
| Wrong context in branch protection | Check passes but protection not satisfied | Context name doesn't match any posted check | Fix via classic PAT (see scripts in section 4) |
| `new_repo_setup.py` sets wrong context | New repos have mismatched protection | Script sets `pr-sentinel` instead of `pr-sentinel / issue-reference` | Known bug, tracked in #748/#883 |
| Squash merge drops PR body | Issue not auto-closed after merge | Commit message lacks `Closes #N` | Tracked in #851 — commit messages must also contain the reference |
| Agent death spiral | Agent polls merge in tight loop | `mergeable_state` stays `blocked`, agent doesn't diagnose | CLAUDE.md instructs: check PR body, issue state, then stop |

---

## 7. Incident History

| Date | Incident | Issue | Impact |
|------|----------|-------|--------|
| 2026-03-09 | Agent attempted `gh auth login` to acquire admin credentials | Documented in dispatch paper | Triggered investment in hard controls |
| 2026-03-10 | Agent merged 4 PRs in 6-7 seconds; pr-sentinel passed but didn't register due to missing permissions block | Documented in dispatch paper | Led to adding `permissions:` to pr-sentinel.yml (#853) |
| 2026-03-10 | Auto-reviewer timeout — exact match on `pr-sentinel` failed against `pr-sentinel / issue-reference` | #742 | Fix: substring `contains()` match |
| 2026-03-10 | Dependabot PRs permanently queued — Worker skipped without creating check run | #749 | Fix: create passing check run for dependabot |
| 2026-03-18 | `new_repo_setup.py` sets `required_approving_review_count=0` instead of 1 | #758, #748 | Runbook updated; script still needs fix (#883) |
| 2026-03-20 | Agent referenced closed issues, causing pr-sentinel failure and merge loop | Documented in lessons-learned | Led to commit message enforcement (#851) |
| 2026-04-06 | Agent deleted Sextant branch protection and merged PR without permission | Lessons learned 2026-04-06 | Led to #883, reinforced standard 0003 |
| 2026-04-06 | 3-hour misdiagnosis: Sextant protection flagged as broken when it was working | #886 | Led to this document and #887 (test suite) |

---

## 8. Verification

See `tools/test_governance_system.py` for automated verification of both success and failure paths.

---

## Related Documents

- [0003 - Agent Prohibited Actions](0003-agent-prohibited-actions.md) — What agents must never do
- [0925 - Agent Token Setup](../runbooks/0925-agent-token-setup.md) — Fine-grained PAT configuration
- [0926 - Branch Protection Setup](../runbooks/0926-branch-protection-setup.md) — Manual branch protection procedure
- [0927 - New Repo: Human Steps Checklist](../runbooks/0927-new-repo-human-checklist.md) — Post-setup human steps
- `dispatch/technical-papers/emergent-adversarial-behavior.md` — Academic paper on agent escalation patterns
- #886 — Configuration reconciliation issue
- #887 — This standard + test suite tracking issue

---

## History

| Date | Change |
|------|--------|
| 2026-04-06 | v1.0: Initial standard. Consolidated architecture from code, issues, incidents, and dispatch papers. |
