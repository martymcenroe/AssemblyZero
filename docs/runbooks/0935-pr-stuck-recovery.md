# 0935 - PR Stuck on `mergeable_state=blocked` or `behind`: Recovery Procedures

**Category:** Runbook / Operational Procedure
**Version:** 1.3
**Last Updated:** 2026-10-21

---

## Purpose

Diagnose and recover when a PR stays at `mergeable_state=blocked` long after creation. Standard 0016 documents the PR governance architecture; this runbook documents recovery when that architecture rejects a PR for a non-obvious reason.

**Use when:** `gh api repos/{owner}/{repo}/pulls/{N} --jq '.mergeable_state'` returns:

- **`blocked`** a minute or more after the PR opened. pr-sentinel posts `issue-reference` and approves as Cerberus in one request, seconds after the PR opens (Step 4). Follow Steps 1–7 below.
- **`behind`** and stays there indefinitely (branch protection's "Require branches to be up to date" gate; the standard poll-until-clean loop never terminates). Follow the "Behind-State Recovery" section after Step 7.

**Do NOT use this for:** legitimate failures where pr-sentinel reported `failure` (those are diagnosed by reading the check output and fixing the actual problem). This runbook is for the harder cases: a check that stays `pending` forever, a PR whose body is correct but which has no review at all (the "No Review At All" section), or branch protection requiring an update that the standard merge sequence doesn't perform.

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

If `state=closed` OR `is_pr=true`, the worker posts `action_required` on `issue-reference` and does not approve. The PR stays `blocked`, and the merge driver stops at `poll_timeout`. **This is the failure.**

---

## Step 4: How the PR Gets Approved

pr-sentinel does the whole approval in one webhook request (`AssemblyZero/sentinel/src/webhook.js`, #3663). It runs on the `opened`, `edited`, `reopened` and `synchronize` events, and in order it:

1. checks the body for a closing directive (Step 3's regex);
2. confirms each referenced number is an open issue;
3. checks the merge driver's stamp;
4. posts the `issue-reference` check-run, `success` or `action_required`;
5. when the check passed and the author is not Dependabot, approves the head commit as Cerberus, unless Cerberus already approved that commit (`sentinel/src/cerberus.js`).

A failed approval request is written to the Worker's log and does not change the check. The fine-grained PAT can read neither the check-runs nor that log.

**Auto Review is retired.** Before #3663 a separate workflow, `.github/workflows/auto-reviewer.yml`, polled for `issue-reference` and then approved. It now carries `if: false`, so the retired Auto Review job concludes `skipped` in about two seconds on every PR. A `skipped` Auto Review run is normal, and it is never the reason a PR is stuck.

---

## Step 5: Recovery — Re-phrase the Body

Edit the PR body to remove the parasitic match. Replacement phrasings:

| Avoid | Use instead |
|-------|-------------|
| `Does not close #N` | `Leaves #N open` / `#N stays open` |
| `Won't auto-close #N` | `#N remains pending` |
| `Closes none of the related issues (#A, #B)` | `Related (kept open): #A, #B` |
| Example: `` `Closes #N` `` (in instructional text) | `<directive> #N` (use placeholder) |

Write the rephrased body to a file in the repo's `data/scratch-<date>-<topic>/` and apply it. The shell guard refuses an inline `--body` (#3803):

```bash
gh pr edit {N} --repo {owner}/{repo} --body-file {body_file}
```

Pass the same file to the merge driver when you rerun it, so the body it checks is the body on the PR. The `edited` webhook re-fires sentinel. Worker re-evaluates against the new body and posts a fresh check-run. If body now passes regex + all extracted refs are open issues, conclusion is `success`, and the same request approves as Cerberus (Step 4).

---

## Step 6: Nothing Else to Re-trigger

pr-sentinel acts on `edited`, so the body edit in Step 5 already re-ran the check and the approval. The merge driver's rerun in Step 7 stamps the body, which is another edit. No other job has to be woken.

**Do not close and reopen the PR.** Earlier versions of this runbook did, to wake Auto Review, which no longer runs (Step 4).

**DO NOT** push an empty commit to re-trigger. It pollutes git history, and a force-push to "clean up" the noise commit afterward is BANNED.

---

## Step 7: Rerun the Merge Driver

Rerun the merge driver with the same arguments as the run that stopped (root `CLAUDE.md`, "Merging PRs (Universal)"). It finds the open PR and reuses it, stamps it so pr-sentinel re-evaluates, waits for `clean`, merges, verifies the squash on `origin/main`, and removes the worktree and the branch. Never merge, fast-forward, remove the worktree or delete the branch by hand (#3803).

If the driver fails again at the same stage, stop and report its output (Two-Strike Rule).

---

## No Review At All: `skipped`, `REVIEW_REQUIRED`, Body Correct

| Symptom | Step that works | If it fails |
|---------|-----------------|-------------|
| Auto Review `skipped`, no review, `REVIEW_REQUIRED`, body correct, worker healthy | Rerun the merge driver once (Step 7) | Stop and report (below) |

**What it looks like.** The driver stops at `poll_timeout` with the PR still `blocked`. Then:

- the branch's Auto Review run concluded `skipped`, which is normal (Step 4);
- the PR has no review at all, and `reviewDecision` is `REVIEW_REQUIRED`;
- Steps 2 and 3 find the body correct: each closing directive names an open issue, and nothing parasitic;
- Step 1's `/health` returns `200`.

Read the review state and the runs with:

```bash
gh pr view {N} --repo {owner}/{repo} --json reviewDecision,reviews
gh run list --repo {owner}/{repo} --branch {branch} --limit 3
```

**Step that works.** Rerun the merge driver once, with the same arguments (Step 7), as the root `CLAUDE.md` route for `poll_timeout` says. It reuses the open PR and stamps its body. The stamp is an `edited` event, so pr-sentinel runs again and approves if the check passes. On 2026-10-21 one rerun was enough: the PR went `clean` three polls later and merged.

**If the rerun also stops at `poll_timeout` with no review,** stop and report. Do not edit the body, close and reopen the PR, or push a commit to provoke the Worker. The report gives:

- the PR number, its head commit, and the time it opened, in Central;
- both driver stage lines;
- the `reviewDecision`, review and run output above;
- that the body and `/health` checked clean.

The cause is in the Worker's log, which only the operator can read. A cause found there is tracked in its own issue. This runbook does not guess at it.

---

## Behind-State Recovery: `mergeable_state=behind`

**Symptom:** Polling `gh api repos/{owner}/{repo}/pulls/{N} --jq '.mergeable_state'` returns `behind` and stays there. The standard merge-sequence poll-until-`clean` loop never terminates because `behind` is neither `clean` nor any of the failure states it knows to abort on.

**Distinct from:**

| State | What it means | Action |
|-------|---------------|--------|
| `blocked` | pr-sentinel failure or required-check failed | Steps 1–7 above |
| `behind` | Branch behind main, branch-protection gate requires up-to-date | This section |
| `unstable` | Required checks still running | Just wait — not this runbook |
| `unknown` | GitHub hasn't computed yet | Wait a few seconds, usually resolves transiently |
| `dirty` | The branch conflicts with main | Merge `origin/main` in the worktree, as for `behind` below |

**Cause:** Branch protection has "Require branches to be up to date before merging" enabled (the operator's fleet-wide default). The PR's branch is N commits behind main on origin; the gate refuses merge until the branch is updated.

**The wrong fix:** manually rebasing the branch + force-pushing (banned — see "Banned Recovery Actions" below). Manual rebase + force-push violates the no-force-push rule even if technically it would work.

**The right fix:** merge `origin/main` into the branch in its worktree, run the full test suite, and rerun the merge driver (#3803). A merge adds a commit on top of what was pushed, so the driver's push is an ordinary fast-forward:

```bash
git -C {worktree} fetch origin
git -C {worktree} merge origin/main
```

Resolve any conflict by keeping both sides, never with `--theirs`. A `dirty` PR is recovered the same way: the conflicts surface in this merge, in the worktree, where the tests can run.

**Never rebase a branch the driver has already pushed.** A rebased branch can only be published by a force push, which is banned. Rebasing is fine only before the first push.

**Do not use GitHub's `update-branch` API while landing with the driver.** It adds a merge commit to the remote branch that the local branch lacks, so the driver's next push is refused as non-fast-forward and the run stops at `push_failed`. The API was the right fix for the hand-merge sequence this runbook used to teach (Hermes PR #475, below).

**Documented incident:** Hermes PR #475 (2026-05-27). The PR sat `mergeable_state=behind` after a close+reopen cycle; main had moved by one commit while the PR was being unblocked from a different pr-sentinel issue. The standard poll-until-`clean` loop would have spun forever. The Hermes-side agent worked out the `update-branch` recovery during execution and persisted the lesson to `docs/lessons-learned.md` (PR #488). Closes AssemblyZero #1347.

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
| Pushing empty / noise commits to re-trigger workflows | Git history pollution; a body edit, or the driver's rerun, re-fires pr-sentinel without a commit |
| Closing and reopening the PR to re-trigger a review | It wakes nothing a body edit does not: Auto Review is retired, and pr-sentinel already runs on `edited` (Step 6) |
| `gh pr merge --auto` | `allow_auto_merge=false` on all repos (Standard 0016) |
| `gh pr merge`, worktree removal or branch deletion by hand | The merge driver does all three; a hand-finished landing is how worktrees and branches get left behind. Rerun the driver (Step 7) |
| `git checkout` in any form | The shell guard refuses every form of it |
| Rebasing a branch the driver already pushed | It can only be published by a force push. Merge `origin/main` instead (Behind-State Recovery) |
| `git checkout --theirs` / `git rebase --theirs` | Discards one side of a conflict; it destroyed two days of code once |
| Rerunning the driver after its PR merged | It finds no open PR and opens a duplicate. Follow the root `CLAUDE.md` route for the stage it printed |

---

## Diagnostic Decision Tree

```
mergeable_state == "blocked"
│
├─ Step 1: Worker /health returns non-200
│   └─→ Worker DOWN, escalate, do not proceed
│
├─ Step 2: PR body lacks `Closes #N`
│   └─→ Step 5 (add it), then Step 7
│
├─ Step 2: PR body has `Closes #ISSUE_N` but ISSUE_N is closed
│   └─→ Create new issue, Step 5 with new ref, Step 7
│
├─ Step 3: PR body has parasitic match (close/closed/closes near non-target #N)
│   └─→ Step 5 (rephrase), Step 7
│
└─ All above pass, Auto Review `skipped`, no review, `REVIEW_REQUIRED`
    └─→ "No Review At All": rerun the driver once (Step 7)
        └─→ still no review: stop and report

mergeable_state == "behind"
│
└─→ "Behind-State Recovery" section above
    └─→ merge origin/main into the branch in the worktree
    └─→ full test suite, commit, rerun the merge driver

mergeable_state == "unstable" / "unknown"
│
└─→ Wait — required checks running or GitHub still computing.
    NOT this runbook. Re-read mergeable_state every 10s; usually
    resolves to `clean` or `blocked` within ~20s.

mergeable_state == "dirty"
│
└─→ Merge conflicts: the same as "behind". Merge origin/main into
    the branch in the worktree, keep both sides of each conflict,
    run the full test suite, commit, rerun the merge driver.
```

---

## Related Documents

- [0016 - PR Governance System Architecture](../standards/0016-pr-sentinel-system-architecture.md) — How the system works (sentinel Worker, Cerberus-AZ App, branch protection, auto-reviewer)
- [0021 - Workflow Error Recovery](../standards/0021-workflow-error-recovery.md) — Recovery for LLM/LangGraph workflows (different system)
- [0217 - Squash-merge Orphan Graft Cleanup](../adrs/0217-squash-merge-orphan-graft-cleanup.md) — When `git branch -d` refuses on squash-merged branches
- Project-root `CLAUDE.md` "Merging PRs (Universal)" — the merge driver, and the route to follow for each stage at which it fails

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-10 | Initial. Captures the PR #527 incident (negation-parsed-as-Closes) and codifies the broader recovery procedures. |
| 1.1 | 2026-05-27 | Added "Behind-State Recovery" section for `mergeable_state=behind`. Documents the `update-branch` API technique discovered during Hermes PR #475 unblock and persisted to Hermes `docs/lessons-learned.md` (PR #488). Decision tree extended to handle `behind`, `unstable`, `unknown`, `dirty`. Closes #1347. |
| 1.2 | 2026-10-07 | #3803: every recovery ends in a rerun of the merge driver. Removed the hand merge, checkout, fast-forward and branch deletion from Step 7, the inline `--body` from Step 5, and the `update-branch` loop, which makes the driver's push fail. `behind` and `dirty` merge `origin/main` in the worktree. Five rows added to the banned table. |
| 1.3 | 2026-10-21 | #4189: Auto Review was retired by #3663. Step 4 now describes pr-sentinel's approval as Cerberus; Step 6 no longer closes and reopens the PR. New section "No Review At All" for a `skipped` Auto Review with no review and a correct body, with its branch in the decision tree. |
