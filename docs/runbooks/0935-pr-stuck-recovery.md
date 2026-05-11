# 0935 - PR Stuck on `mergeable_state=blocked`: Recovery Procedures

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-05-10

---

## Purpose

Diagnose and recover when a PR stays at `mergeable_state=blocked` long after creation. Standard 0016 documents the PR governance architecture; this runbook documents recovery when that architecture rejects a PR for a non-obvious reason.

**Use when:** `gh api repos/{owner}/{repo}/pulls/{N} --jq '.mergeable_state'` returns `blocked` and the typical 30-second auto-approval window has passed (Cerberus-AZ should approve within 10–30s after pr-sentinel passes).

**Do NOT use this for:** legitimate failures where pr-sentinel reported `failure` (those are diagnosed by reading the check output and fixing the actual problem). This runbook is for the harder case where a check stays `pending` forever or `action_required` is silently misclassified.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| `gh` CLI authenticated with fine-grained PAT | `gh auth status` |
| Issue referenced by PR exists and is open | `gh issue view {N} --jq '.state'` returns `open` |
| Worker `/health` reachable | See Step 1 |

---

## Step 0: Grep Lessons-Learned First

This runbook exists because the same traps recur. Before any diagnostic action:

```bash
grep -nE "sentinel|blocked|action_required|stuck.*PR" /c/Users/mcwiz/Projects/AssemblyZero/docs/lessons-learned.md
```

If a known trap matches your symptoms, follow that lesson's prescription instead of running this runbook from the top.

**Known recurring traps:**
- 2026-04-21: PR body example text parsed by sentinel — extracted `#42` as a Closes ref (PR #989, #974).
- 2026-05-10: PR body negation phrasing parsed by sentinel — `Does not close #523` extracted as Closes #523 (PR #527).

---

## Step 1: Confirm pr-sentinel-mm Worker Is Up

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://pr-sentinel.mcwizard1.workers.dev/health
```

Expected: `200`. If non-200, the Worker is genuinely down — escalate to operator (this runbook does not cover Worker outages). Skip remaining steps.

---

## Step 2: Read the PR Body Sentinel Sees

```bash
gh api repos/{owner}/{repo}/pulls/{N} --jq '.body'
```

Verify body contains `Closes #ISSUE_N` where `ISSUE_N` is an **open issue** (not a PR). The fine-grained PAT cannot read check-runs (`gh api .../check-runs` returns 403), so symptom-based diagnosis is required.

---

## Step 3: Audit Body for Parasitic Issue Extraction

Sentinel's regex (`AssemblyZero/sentinel/src/validate.js`):

```regex
/\b(?:close[sd]?)\s+(?:([\w.-]+)\/([\w.-]+))?#(\d+)/gi
```

This matches ANY occurrence of `close`/`closes`/`closed` followed by whitespace and `#N`, regardless of:

| Form | Extracted? |
|------|-----------|
| `Closes #N` (intended) | YES |
| `Does not close #N` | YES (negation does not block) |
| `auto-close #N` | YES (hyphen is a word boundary) |
| `` `Closes #N` `` (backticked example) | YES (worker doesn't parse markdown) |
| `"Closes #N"` (quoted) | YES |
| `Won't close #N` | YES |
| `(close #N)` | YES |
| `from #N`, `diagnoses #N`, `Leaves #N open` | NO (no `close` keyword) |

Run the same regex against the PR body locally:

```bash
gh api repos/{owner}/{repo}/pulls/{N} --jq '.body' \
  | grep -niE '\b(close[sd]?)\s+#[0-9]+'
```

For EACH match, verify the referenced `#N` is an open issue (not closed, not a PR):

```bash
gh api repos/{owner}/{repo}/issues/{N} --jq '{state: .state, is_pr: (.pull_request != null)}'
```

If `state=closed` OR `is_pr=true` → worker rejects → posts `action_required` → Auto Review treats as pending → 10-minute timeout → repeat. **This is the failure.**

---

## Step 4: Why Auto Review Says "pending" When Worker Already Failed

Auto Review (`AssemblyZero/.github/workflows/auto-reviewer.yml`) poll-loop branch logic:

```bash
if [ "$STATUS" = "success" ]; then
  echo "  ✅ ${check_name}: passed"
elif [ "$STATUS" = "failure" ] || [ "$STATUS" = "cancelled" ]; then
  echo "  ❌ ${check_name}: ${STATUS} — will NOT approve"
  exit 1
else
  echo "  ⏳ ${check_name}: pending (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})"
  ALL_PASSED=false
fi
```

The check-run conclusion `action_required` is neither `success`, `failure`, nor `cancelled` — it falls through to the `else` branch and prints `⏳ pending`. The poll runs 30 attempts × 20s = 10 min, then times out. The check ran and FAILED at second 0 — Auto Review just doesn't classify the failure correctly.

**Symptomatic signature:** Auto Review log shows 30 consecutive `⏳ ... pending` lines, never `❌`, then `Timed out waiting for checks after 600s`.

(Bug worth filing against `AssemblyZero/.github/workflows/auto-reviewer.yml` to handle `action_required` and `timed_out` as failures.)

---

## Step 5: Recovery — Re-phrase the Body

Edit the PR body to remove the parasitic match. Replacement phrasings:

| Avoid | Use instead |
|-------|-------------|
| `Does not close #N` | `Leaves #N open` / `#N stays open` |
| `Won't auto-close #N` | `#N remains pending` |
| `Closes none of the related issues (#A, #B)` | `Related (kept open): #A, #B` |
| Example: `` `Closes #N` `` (in instructional text) | `<directive> #N` (use placeholder) |

Apply via:

```bash
gh pr edit {N} --repo {owner}/{repo} --body "...rephrased body..."
```

The `edited` webhook re-fires sentinel. Worker re-evaluates against the new body and posts a fresh check-run. If body now passes regex + all extracted refs are open issues, conclusion is `success`.

---

## Step 6: Re-trigger Auto Review (Without a New Commit)

Auto Review only triggers on `pull_request` event types `[opened, synchronize, reopened]` — NOT `edited`. After Step 5, sentinel's check is fresh but Auto Review is still showing the stale failed run.

The fine-grained PAT cannot `gh run rerun` (needs `actions:write`). The non-destructive trigger:

```bash
gh pr close {N}  --repo {owner}/{repo}
gh pr reopen {N} --repo {owner}/{repo}
```

`reopened` is in Auto Review's trigger list. New run starts, polls for issue-reference (now `success`), Cerberus-AZ submits the approving review.

**DO NOT** push an empty commit to re-trigger — git history pollution. Force-push to "clean up" the noise commit afterward is BANNED.

---

## Step 7: Wait for `clean`, Merge, Cleanup

```bash
until [ "$(gh api repos/{owner}/{repo}/pulls/{N} --jq '.mergeable_state')" = "clean" ]; do sleep 20; done
gh pr merge {N} --squash --repo {owner}/{repo}
git checkout main && git fetch origin && git merge origin/main --ff-only && git branch -d {branch}
```

Squash merge collapses any noise commits on the branch into ONE commit on main with the PR title — so even if you accidentally pushed extra commits during diagnosis, main history stays clean.

---

## Banned Recovery Actions

These have all been attempted; all violate user-set rules. Memory: `feedback_never_force_overwrite_user_data`. Root CLAUDE.md "Hard Rules" section.

| Action | Why banned |
|--------|-----------|
| `git push --force` / `--force-with-lease` | Overwrites user data (lost session names 2026-04-11) |
| `git reset --hard` then push | Same effect as force-push |
| `git branch -D` | For squash-merge orphans use ADR-0217's `git replace --graft`, not `-D` |
| `gh pr merge --admin` | Bypasses branch protection; governance requires non-author approval |
| `gh pr review --approve` (self-approve) | GitHub blocks; would bypass governance even if it worked |
| Asking user to manually approve | Cerberus-AZ exists for this — its job to approve, not user's |
| Pushing empty / noise commits to re-trigger workflows | Git history pollution; `gh pr close && gh pr reopen` works without a commit |
| `gh pr merge --auto` | `allow_auto_merge=false` on all repos (Standard 0016) |

---

## Diagnostic Decision Tree

```
mergeable_state == "blocked"
│
├─ Step 1: Worker /health returns non-200
│   └─→ Worker DOWN, escalate, do not proceed
│
├─ Step 2: PR body lacks `Closes #N`
│   └─→ Step 5 (add it), then Step 6 (close/reopen), then Step 7
│
├─ Step 2: PR body has `Closes #ISSUE_N` but ISSUE_N is closed
│   └─→ Create new issue, Step 5 with new ref, Step 6, Step 7
│
├─ Step 3: PR body has parasitic match (close/closed/closes near non-target #N)
│   └─→ Step 5 (rephrase), Step 6 (close/reopen), Step 7
│
└─ All above pass + Auto Review last run >10 min ago
    └─→ Step 6 (close/reopen) to re-trigger, Step 7
```

---

## Related Documents

- [0016 - PR Governance System Architecture](../standards/0016-pr-sentinel-system-architecture.md) — How the system works (sentinel Worker, Cerberus-AZ App, branch protection, auto-reviewer)
- [0021 - Workflow Error Recovery](../standards/0021-workflow-error-recovery.md) — Recovery for LLM/LangGraph workflows (different system)
- [0217 - Squash-merge Orphan Graft Cleanup](../adrs/0217-squash-merge-orphan-graft-cleanup.md) — When `git branch -d` refuses on squash-merged branches
- Project-root `CLAUDE.md` "If `mergeable_state` stays `blocked`" section — Quick-reference summary

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-10 | Initial. Captures the PR #527 incident (negation-parsed-as-Closes) and codifies the broader recovery procedures. |
