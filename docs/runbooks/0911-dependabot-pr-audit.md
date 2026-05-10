# 0911 - Dependabot PR Audit

**Category:** Runbook / Security Maintenance
**Version:** 2.3
**Last Updated:** 2026-05-10

---

## Purpose

Safely review, approve, and merge Dependabot PRs with regression verification. Dependency updates land on main only after the full test suite passes against the bumped versions in an isolated worktree. On test failure, PRs are commented and left for human review; multi-package PRs are split via `@dependabot recreate`.

**Key principle (unchanged from v1.0):** Trust exit codes, not LLM interpretation of test output.

**New in v2.0:**
- Test-then-merge order (v1.0 merged-then-tested — wrong order on branch-protected repos)
- Author gate: tool refuses any PR not authored by `dependabot[bot]`
- `No-Issue:` body injection so pr-sentinel's exemption path passes (v1.0 predated this)
- Explicit approval step attributing to the invoking user (Code Review profile stat accrues to the user, not to Cerberus-AZ)
- Multi-package split via `@dependabot recreate` on failure
- Poetry venv eviction integrated (#944 / Fix 5 pattern) so worktrees remove cleanly on Windows
- Mechanical implementation: `tools/dependabot_review.py`

**New in v2.1 (#1091):**
- Failure-path comments now use `gh pr review --comment` (creates a `PullRequestReview` event) instead of `gh pr comment` (creates an unattributed issue comment). Result: deferred PRs also accrue Code Review credit for the operator who audited them.
- `--fleet` flag enumerates user-owned Poetry repos via `gh repo list` and processes dependabot PRs across all of them. Multiplies review-event volume. Single-repo mode unchanged when the flag is omitted.

**New in v2.2 (#1092):**
- Windows Task Scheduler integration. `tools/run_dependabot_fleet.ps1` wraps the `--fleet` invocation; `Claude-DependabotFleet` runs daily at 06:00 with the operator's gh credentials so review-event attribution stays correct. See §Integration → Daily Schedule.

**New in v2.3 (#1093):**
- `--workers N` flag (default 3) enables cross-repo parallelism in `--fleet` mode. PRs within a single repo remain sequential (subsequent PRs need to test against the post-merge HEAD); only repos run in parallel. Substantially shortens fleet-sweep wall-clock time when many repos have queued PRs.
- Summary now prints a review-event counter line (`N APPROVED + M COMMENTED = N+M total`) so the Code Review profile-stat math is visible per-run. Lets the operator verify each fleet sweep is delivering the expected credit.

---

## Implementation

The manual procedure in v1.0 has been replaced by a deterministic Python tool at `tools/dependabot_review.py` invokable via the `/dependabot` skill.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero

# Single-repo (default — AssemblyZero only)
poetry run python tools/dependabot_review.py [--dry-run]

# Specific repo
poetry run python tools/dependabot_review.py --repo martymcenroe/Aletheia

# Fleet — every user-owned Poetry repo (#1091)
poetry run python tools/dependabot_review.py --fleet
```

Or via the skill: `/dependabot` (single-repo) or `/dependabot --fleet` (fleet mode).

---

## Prerequisites

| Requirement | Check |
|---|---|
| Clean working directory on main | `git status` |
| Poetry installed | `poetry --version` |
| GitHub CLI authenticated | `gh auth status` |
| Must NOT run from inside a worktree | `git rev-parse --show-toplevel` matches main repo path |

---

## Hard gates (enforced by the tool)

### Author gate

For each PR returned by `gh pr list --author app/dependabot`, the tool re-verifies `pr.author.login == "dependabot[bot]"` before any action. Any mismatch is a hard refusal — no approval, no merge, status recorded as `errored`.

This prevents the tool from ever operating on a PR it wasn't designed to handle. Even if someone crafts an unrelated PR and passes it through this tool, it won't be approved or merged.

### Exit-code gate

`poetry run pytest -q --tb=short` must exit 0. Any non-zero exit means:
- No approval, no merge
- A comment is posted on the PR noting the exit code and the forensics worktree path
- The PR is recorded as `deferred`
- The worktree is NOT cleaned up — it's left in place so the user can investigate
- If the PR updates multiple packages, `@dependabot recreate` is posted to split it into per-package PRs

No human judgment is applied to the exit code. No LLM is consulted about whether "the failures look related." Trust the exit code.

---

## End-to-end flow (per PR)

```
1. Create audit worktree from current main at ../AssemblyZero-dependabot-<N>
2. `gh pr checkout <N>` into the worktree — brings the dependabot bump in
3. Evict cached poetry venv (Fix 5 / #944) so locks release
4. `poetry install` — fresh install of updated dependencies
5. `poetry run pytest -q --tb=short` — capture exit code

   --- exit != 0 ---
6a. Comment on PR with exit code + worktree path (forensics)
6b. If multi-package, comment `@dependabot recreate`
6c. Leave worktree in place; move to next PR

   --- exit == 0 ---
6a. `gh pr edit <N> --body "<body>\n\nNo-Issue: automated dependency update (...)"`
     — satisfies pr-sentinel Worker's No-Issue exemption
6b. Wait 5s for pr-sentinel to re-evaluate
6c. `gh pr review <N> --approve --body "..."` — PullRequestReview event
     attributed to the invoking user (Code Review profile stat accrues to that user)
6d. Poll `mergeable_state` until `clean` (up to 5 min)
6e. `gh pr merge <N> --squash`
6f. Evict worktree's poetry venv; `git worktree remove`; `git branch -D` the
     audit branch
```

---

## Why the invoking user approves (not Cerberus-AZ)

Cerberus-AZ auto-approves Marty-authored PRs after pr-sentinel passes. Its approval events are attributed to the Cerberus-AZ GitHub App, not to the user. GitHub's Code Review profile stat counts reviews authored by the user.

For dependabot PRs specifically — where the user did NOT author the code — the correct attribution is the user. The tool uses the invoking user's `gh` credentials to create the approval event. This is a bounded, author-gated, exit-code-gated scope; the same credentials do NOT approve anything else.

Constraints embedded in the tool:
- Author must be `dependabot[bot]` (hard gate)
- Tests must exit 0 (hard gate)
- Approval body explicitly names the tool and its gates

Outside this specific tool, agent-initiated approvals remain disallowed.

---

## On stale dependabot branches (#994)

Dependabot PRs can sit open for days or weeks while main moves forward. By the time the tool runs, the PR's base SHA may be far behind current `main`. Tests that pass on current `main` can fail on the PR's branch — not because of the upgrade, but because the PR is missing fixes that landed since.

**Today's pattern that motivated this:** torch-2.10.0 PR #479 deferred for 20 test failures. All 20 matched the failure inventory of #954, which was fixed by PR #955 four days earlier. The PR was created before #955 landed and was running against the unfixed baseline. After `@dependabot rebase`, the branch picked up #955's fix and the same 20 tests passed.

**The tool now diagnoses this automatically.** On the deferral path, after posting the test-failure comment:

1. Compares the PR's `base.sha` to current `main` HEAD via `gh api`
2. If they differ (branch is stale): posts `@dependabot rebase` as a second comment
3. If they match AND the PR is multi-package: falls back to the `@dependabot recreate` flow described below

Staleness check supersedes recreate — rebasing is cheaper and the more likely fix. If the rebased branch fails again, the next `/dependabot` run will treat it as multi-package recreate (or single-package real-incompatibility) territory.

**Manual fallback:** if you ever see a deferral that the tool DIDN'T auto-rebase (because the SHAs happened to match at scrape-time), you can post `@dependabot rebase` by hand and re-run `/dependabot` after dependabot finishes the rebase (~1-2 min).

---

## On multi-package PRs

Dependabot PR bodies include one `` Updates `<package>` `` block per bumped package. The tool counts these via regex. If a multi-package PR fails tests AND the branch is current with main:

1. The failure comment is posted
2. `@dependabot recreate` is posted as a second comment — dependabot listens for this and splits the grouped update into per-package PRs
3. The next `/dependabot` run processes the smaller PRs, and typically only one of the per-package splits actually fails

This is bisect-by-dependabot, not bisect-by-us. Dependabot does the splitting; our tool processes whatever dependabot produces.

(Per #994: if the multi-package PR is ALSO stale, rebase fires instead of recreate. Rebase is cheaper and may resolve the failure without recreating. If the rebased PR fails again on the next run, multi-package handling resumes.)

---

## Forensics on failure

When the tool leaves a worktree in place, it's at `C:/Users/mcwiz/Projects/AssemblyZero-dependabot-<N>`. You can:

```bash
cd C:/Users/mcwiz/Projects/AssemblyZero-dependabot-<N>
poetry run pytest --tb=long <path_to_failing_test> -x
```

When done investigating:

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry env remove --all
git worktree remove ../AssemblyZero-dependabot-<N>
git branch -D dependabot-audit-<N>
```

The cleanup skill will also catch this as an orphan directory per Fix 5's logic.

---

## Summary output

At end of run, the tool prints:

```
=== Summary ===
  Merged:   [756, 741]
  Deferred: [479]
  Errored:  []
```

- **Merged:** PR passed both gates and is on main.
- **Deferred:** PR failed a gate (test failure or poetry install failure). Worktree retained, comment posted, possibly `@dependabot recreate` posted.
- **Errored:** Infrastructure failure (couldn't create worktree, couldn't checkout PR, couldn't approve, etc.). Worktree is cleaned up; the PR needs manual attention.

---

## Integration

Run this audit:

- **On demand** via `/dependabot` (single-repo) or `/dependabot --fleet` (cross-repo).
- **Daily passive** via Windows Task Scheduler (#1092) — see §Daily Schedule below.
- Before shipping a batch of features (so dependencies stay current).

### Daily Schedule (#1092)

The fleet sweep is wired to a Windows Scheduled Task `Claude-DependabotFleet` so dependabot PRs are processed automatically each morning regardless of whether the operator remembers to run `/dependabot`. The task uses the operator's logged-in account so the `gh pr review` events still attribute to the user (Code Review profile-stat credit accrues correctly).

**Setup (run once on a fresh machine):**

```powershell
$action = New-ScheduledTaskAction `
  -Execute 'powershell.exe' `
  -Argument '-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\AssemblyZero\tools\run_dependabot_fleet.ps1'
$trigger = New-ScheduledTaskTrigger -Daily -At 06:00
Register-ScheduledTask `
  -TaskName 'Claude-DependabotFleet' `
  -Action $action -Trigger $trigger `
  -Description 'Daily fleet-wide dependabot PR review + merge (#1091, #1092)'
```

**Manual invocation (between scheduled runs):**

```powershell
Start-ScheduledTask -TaskName 'Claude-DependabotFleet'
```

**Disable / re-enable:**

```powershell
Disable-ScheduledTask -TaskName 'Claude-DependabotFleet'
Enable-ScheduledTask -TaskName 'Claude-DependabotFleet'
```

**View the log:**

```bash
tail -50 /c/Users/mcwiz/Projects/dependabot-fleet.log
```

The PowerShell wrapper at `tools/run_dependabot_fleet.ps1` is the durable definition of what the task runs — the schedule above just points at it. Modifying the wrapper changes future runs without touching the task registration.

**Why daily, not hourly?** Dependabot opens PRs at most a few times per day across the fleet. Hourly runs would add noise without adding value. 06:00 was chosen so the run completes before the operator's typical 09:00 start; merged PRs are visible in the morning git pull.

**Why not use the `/schedule` skill?** That skill creates remote agents on Anthropic infra. Those agents wouldn't have access to the operator's local `gh` credentials, so the review attribution would land on whatever bot/PAT the remote agent authenticated as — defeating the entire Code Review profile-stat purpose of #1091. Local Task Scheduler keeps credentials and review-event attribution co-located with the operator.

---

## Related Documents

- `tools/dependabot_review.py` — the implementation
- `.claude/commands/dependabot.md` — the skill wrapper
- `docs/standards/0016-pr-sentinel-system-architecture.md` — pr-sentinel `No-Issue:` semantics
- #949 — tracking issue for v2.0
- #692 — auto-merge variant (related; different goal — this runbook keeps a human-in-the-loop via the review attribution)
- #944 / PR #945 — poetry venv eviction (Fix 5), reused here

---

## History

| Date | Change |
|------|--------|
| 2026-02-15 | v1.0: Initial runbook — manual procedure, merge-first / test-after, no pr-sentinel integration |
| 2026-04-19 | v2.0 (#949): Rewritten for current branch protection + pr-sentinel. Test-then-merge order. Author gate, exit-code gate, `No-Issue:` body injection, approval attributed to invoking user (Code Review stat), multi-package split via `@dependabot recreate`, poetry venv eviction. Mechanical implementation at `tools/dependabot_review.py` and `/dependabot` skill. |
| 2026-05-10 | v2.1 (#1091): Failure-path comments switched to `gh pr review --comment` so deferred PRs also accrue Code Review credit. `--fleet` flag added — enumerates user-owned Poetry repos and processes dependabot PRs across the fleet for cross-repo coverage. |
| 2026-05-10 | v2.2 (#1092): Windows Task Scheduler integration — `tools/run_dependabot_fleet.ps1` + daily `Claude-DependabotFleet` task at 06:00. Passive cross-repo processing with operator-credentialed review attribution. |
| 2026-05-10 | v2.3 (#1093): Cross-repo parallelism via `--workers N` (default 3) for shorter fleet sweeps. Summary now reports review-event count (APPROVED + COMMENTED) so Code Review profile-stat math is visible per run. |
