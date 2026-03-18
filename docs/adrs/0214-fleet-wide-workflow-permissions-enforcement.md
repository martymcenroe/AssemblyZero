# ADR-0214: Fleet-Wide Workflow Permissions Enforcement

**Status:** Implemented
**Date:** 2026-03-12
**Categories:** Security, Infrastructure, Process

## 1. Context

The pr-sentinel workflow (a CloudFlare Worker + GitHub App that validates issue references on every PR) is deployed across all 50+ repositories in the fleet. On 2026-03-10, we discovered that **pr-sentinel's enforcement was silently failing** on repositories where the workflow YAML lacked an explicit `permissions` block:

```yaml
# WITHOUT permissions block: GITHUB_TOKEN gets read-only defaults.
# The workflow runs, the job passes — but the check result is never
# written back to GitHub's branch protection enforcement system.
# Effect: gh pr merge succeeds as if no required check exists.
name: pr-sentinel
on:
  pull_request:
    branches: [main]
jobs:
  issue-reference:
    runs-on: ubuntu-latest
    steps:
      - name: Check for issue reference
        run: |
          # ... validation logic ...
```

This was confirmed empirically: four PRs (#13–#16 on the `career` repo) were created and merged within 6–7 seconds each — before the check could complete — because the merge API **fails open** when the required status check has not been registered with the enforcement system. Adding the three-line `permissions` block fixed it: an identical merge attempt was blocked immediately.

The root cause is a GitHub platform behavior: without explicit `permissions: { checks: write, statuses: write }`, the workflow's `GITHUB_TOKEN` operates with default read-only scope. The job executes and passes, but the mechanism by which the result is communicated to branch protection enforcement is impaired. The check appears in the Actions tab as "passed" while being invisible to the merge gate. This is not documented in GitHub's branch protection documentation — it was discovered through the controlled experiment described in the paper (see Section 8, References).

### The chicken-and-egg problem

This gap could not be fixed by normal PR workflow:

1. The `permissions` block must be on the **default branch** (typically `main`) to take effect — GitHub reads workflow permissions from the target branch, not the PR branch.
2. PRs adding the `permissions` block therefore cannot validate themselves — the check on the PR still runs under the old (permissionless) configuration from `main`.
3. Branch protection requires the pr-sentinel check to pass before merging.
4. The pr-sentinel check cannot pass on these PRs because it lacks write permissions to report its own result.

Result: **43 repositories had broken enforcement and the fix PRs were self-blocking.**

### The fine-grained PAT constraint

The normal escape hatch — `gh pr merge --admin` — requires the GitHub `Administration` scope. Our fine-grained PATs deliberately exclude this scope (see runbook 0925) to prevent agents from bypassing branch protection. This is the correct security posture, but it means the human operator cannot use the agent's token for administrative merges.

The `.permissions` field in GitHub's API response reports the **user's** role (`admin: true`) regardless of the token's actual capabilities. This confound (P07 in the paper) means that checking `"permissions": { "admin": true }` gives a false positive — the token will still get a 403 on any admin operation. This API design flaw is what triggers agent escalation cascades when they read the API, conclude they have admin access, and attempt admin operations.

## 2. Decision

**We will use a temporary classic PAT with `repo` scope to merge all 43 self-blocking PRs via an air-gapped script, then immediately revoke the classic token.**

The air-gapped pattern means:
- The agent writes a Python script (`tools/merge_sentinel_permissions_prs.py`)
- The script calls `gh pr merge --squash --delete-branch --admin` per PR
- The **human** reviews the script, creates the classic token, authenticates, runs the script, restores the fine-grained PAT, and revokes the classic token
- The agent never touches the token — no token appears in any session transcript, command history, or environment variable

This is the same pattern used for `fix_branch_protections.py` (2026-03-08 branch protection campaign).

## 3. Alternatives Considered

### Option A: Air-gapped batch merge script with temporary classic PAT — SELECTED
**Description:** Agent writes script, human runs it with a one-day classic PAT, revokes immediately after.

**Pros:**
- Single command merges all 43 PRs (~2-3 minutes)
- Token never enters agent context (air-gapped)
- Audit trail: script saves markdown report to `docs/audits/github-protection/`
- Repeatable: script can be re-run if PRs are added later
- Classic token lifetime is ~10 minutes (create → run → revoke)

**Cons:**
- Requires human to create/revoke a classic token (manual steps)
- Brief window where a classic token with `repo` scope exists

### Option B: Merge each PR manually via GitHub web UI — Rejected
**Description:** Human clicks "Merge" on each of 43 PRs, using the admin merge button.

**Pros:**
- No script needed
- No classic token needed (web UI uses session auth)

**Cons:**
- 43 manual clicks with page loads — error-prone and tedious
- No audit trail
- No reproducibility for future fleet-wide fixes

### Option C: Temporarily remove the pr-sentinel required check, merge, re-add — Rejected
**Description:** Use the GitHub API to remove the required status check from each repo, merge the PR normally, then re-add the check.

**Pros:**
- Works with fine-grained PAT (no admin needed for merge itself)

**Cons:**
- Requires `Administration` scope to modify branch protection — same PAT constraint
- Race window: between removing and re-adding the check, any PR could merge unchecked
- 43 repos × 3 API calls each = 129 API calls with a security-critical race on each
- If the script fails mid-run, repos are left unprotected ← **unacceptable blast radius**

### Option D: Disable branch protection entirely, merge, re-enable — Rejected
**Description:** Remove all branch protection, merge freely, re-apply.

**Cons:**
- Maximum blast radius — every repo is unprotected during the window
- Same `Administration` scope requirement
- Rejected without further analysis

## 4. Rationale

Option A was selected because it minimizes the privilege window (a classic token exists for ~10 minutes), maintains the air-gapped security model (agent never sees the token), produces an auditable record, and is the established pattern for fleet-wide administrative operations.

The key insight is that this is an **infrastructure bootstrapping problem**, not a workflow problem. The fix (adding `permissions` blocks) must be deployed through a mechanism that the fix itself enables. This is analogous to deploying a firewall rule that blocks the deployment tool — you need a one-time bypass to bootstrap the constraint, then the constraint protects itself going forward.

After these PRs are merged, the `permissions` block exists on `main` in every repo. Future changes to the workflow can be validated normally — the chicken-and-egg problem is a one-time bootstrapping cost.

## 5. Security Risk Analysis

| Risk | Impact | Likelihood | Severity | Mitigation |
|------|--------|------------|----------|------------|
| Classic token leaked during brief window | High | Low | 3 (Moderate) | Token expires in 1 day; only `repo` scope; revoked immediately after use |
| Agent captures classic token in transcript | High | Low | 3 (Moderate) | Air-gapped: human runs `gh auth login` interactively; token never echoed |
| Script merges wrong PRs | Med | Low | 2 (Low) | Script filters by exact title match and author; dry-run output shows each PR before merge |
| Repos left with broken enforcement if script fails | Med | Low | 2 (Low) | Script continues through failures; report identifies which repos need manual attention |

**Residual Risk:** The classic token exists for ~10 minutes with `repo` scope. This is accepted as the minimum viable privilege window for the operation. The fine-grained PAT is restored immediately after.

## 6. Consequences

### Positive
- All 43 repos get working pr-sentinel enforcement (checks: write, statuses: write)
- The merge-race-condition gap (Section 4.4 in the paper) is closed fleet-wide
- Audit report documents exactly which repos were fixed and when
- Establishes the air-gapped batch operation as a repeatable pattern for future fleet maintenance

### Negative
- Brief classic token window (~10 minutes) — accepted and mitigated by immediate revocation
- Human must perform 9 manual steps — documented in the script header and session instructions

### Neutral
- The `permissions` block is now part of the pr-sentinel workflow template; new repos created via `new_repo_setup.py` already include it
- No code changes to any application — only workflow YAML and the merge operation itself

## 7. Implementation

- **Script:** `tools/merge_sentinel_permissions_prs.py`
- **Pattern:** Same air-gapped design as `tools/fix_branch_protections.py`
- **Audit output:** `docs/audits/github-protection/merge-sentinel-prs-TIMESTAMP.md`
- **Related runbooks:** 0925 (agent token setup), 0926 (branch protection setup)
- **Status:** Script written, awaiting human execution

## 8. References

- McEnroe, M. (2026). "Emergent Adversarial Behavior in LLM Coding Agents." Section 4.4: Enforcement Evasion via Merge Race Condition. `dispatch/technical-papers/emergent-adversarial-behavior.md`
- Section 4.4.3: The Root Cause (missing `permissions` block)
- Section 4.4.5: The Self-Healing Defense Problem
- Section 4.4.6: The Permission Minimum for Tamper-Proof Enforcement
- Runbook 0925: Agent Token Setup (fine-grained PATs) — documents why `Administration` scope is excluded
- Runbook 0926: Branch Protection Setup — manual branch protection configuration
- GitHub docs: [Workflow permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token)
- `tools/fix_branch_protections.py` — prior art for the air-gapped batch pattern

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-12 | Claude Opus 4.6 | Initial draft |
