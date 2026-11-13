# 0911 - Dependabot PR Audit

**Category:** Runbook / Security Maintenance
**Version:** 2.4
**Last Updated:** 2026-11-13

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
- Windows Task Scheduler integration. A PowerShell wrapper wraps the `--fleet` invocation (relocated 2026-08-09 to the fleet's private orchestration repo — see #2156; it names private paths and its run records enumerate the fleet, so it cannot live on this public repo); `Claude-DependabotFleet` runs daily at 06:00 with the operator's gh credentials so review-event attribution stays correct. See §Integration → Daily Schedule.

**New in v2.3 (#1093):**
- `--workers N` flag (default 3) enables cross-repo parallelism in `--fleet` mode. PRs within a single repo remain sequential (subsequent PRs need to test against the post-merge HEAD); only repos run in parallel. Substantially shortens fleet-sweep wall-clock time when many repos have queued PRs.
- Summary now prints a review-event counter line (`N APPROVED + M COMMENTED = N+M total`) so the Code Review profile-stat math is visible per-run. Lets the operator verify each fleet sweep is delivering the expected credit.

**New in v2.4 (#4736, #4737):**
- Fake-root guard gate: a PR head that lacks a guard file `origin/main` has is not installed or tested; it is deferred with a `SKIP GATE:` line and, when stale, a rebase request. See §Hard gates → Fake-root guard gate.
- The pytest timeout kills the whole process tree, prints `TIMEOUT after`, and defers the PR. See §Hard gates → Exit-code gate.
- Every PR the run reaches prints exactly one `OUTCOME PR #<N>:` line, and the Summary names it even when the run is interrupted. A PR that earlier runs began and never finished prints `REPEAT PR #<N>:`, and after two such runs at the same head it is deferred without running. See §Outcome lines and the in-flight ledger.

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

### Private repositories are skipped (#4750)

The tool acts only on repositories GitHub reports as `PUBLIC`. On a private repository every approval and merge, and every `@dependabot rebase` or `@dependabot recreate`, runs workflows that spend GitHub Actions minutes; public repositories run them free. The operator ruled on 2026-11-13 that this stays off until December.

- Visibility is read in every run: in `--fleet` mode from the `gh repo list` listing, and otherwise with `gh repo view <owner>/<name> --json visibility`. A visibility that cannot be read counts as private.
- A skipped repository gets no review, comment, `@dependabot` command, merge or test run, in the zero-review pre-pass as in the sweep. Each prints one `[SKIP]` line with its reason, and the Summary lists them under `Skipped (private, #4750)`.
- The switch is the module constant `INCLUDE_PRIVATE_REPOS` in `tools/dependabot_review.py`, `False` until the operator turns it on. `--include-private` turns it on for a single run.

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
- A review comment (a COMMENTED review) is posted on the PR giving the exit code
- The PR is recorded as `deferred`
- The audit worktree and its branch are removed, as on every path (#1116, #1133). The evidence of the deferral is the run log and the review comment on the PR; see §Forensics on failure
- If the PR updates multiple packages, `@dependabot recreate` is posted to split it into per-package PRs

No human judgment is applied to the exit code. No LLM is consulted about whether "the failures look related." Trust the exit code.

**Timeout (#4737).** The suite gets `PYTEST_TIMEOUT_S` (1800s). Past that, the tool prints `TIMEOUT after 1800s -- killing the process tree of pid <N>` and kills the whole tree, pytest included, not only `poetry`: before #4737, on Windows, killing `poetry` left pytest holding the pipes and the run waited on it with no `TIMEOUT` line. The exit is 124, the PR is recorded `deferred` with the reason `pytest TIMEOUT after 1800s`, and the baseline is not run. If the tree cannot be killed, or its pipes are still open 60s after the kill, the tool raises `ProcessTreeKillError`: the PR is recorded `errored`, the operator is alerted, and the sweep goes on.

### Fake-root guard gate (#4736)

A PR head cut before #4706 lacks `tests/fake_root_guard.py`, and its suite, run on Windows, turns the tests' fake absolute roots into real folders such as `C:\tmp\repo`. So for a PR that touches Python, before `poetry install`, the tool fetches `main` from origin and compares each file in `FAKE_ROOT_GUARD_PATHS` at `origin/main` with the PR head. It reads `origin/main`, not the local `main`, because the audit worktree is cut from the local `main`, which can lag.

- **The head lacks a file `origin/main` has:** the log says `SKIP GATE: this head lacks <file>, which origin/main has`. Install, pytest and the baseline are not run. The PR is recorded `deferred`, a review comment gives the reason, and a stale branch gets `@dependabot rebase` with a comment saying the head predates the guard. `@dependabot recreate` is not posted. The next run tests the PR once its head carries the guard.
- **The check fails** (the fetch or a `git ls-tree` exits non-zero): the PR is recorded `errored` and no suite runs.

The baseline run checks the base commit the same way. A base that lacks the guard is not run and is not exonerable.

The check applies to every repo the nightly tests. A repo whose `main` has no guard file passes it unchanged; only AssemblyZero has one today.

---

## End-to-end flow (per PR)

```
0. In the repo's PR loop (#4737): if two earlier runs began this PR at its
   current head and recorded no outcome, record it `deferred` without
   running and go to the next PR (§Outcome lines and the in-flight ledger).
   Otherwise write its in-flight entry.
1. Create audit worktree from current main at ../AssemblyZero-dependabot-<N>
2. `gh pr checkout <N>` into the worktree — brings the dependabot bump in
2a. If the PR touches Python: fetch main from origin and check the head
    carries the fake-root guard (#4736). Missing: `SKIP GATE:`, skip
    steps 3-5 and the baseline, go to the exit != 0 path. Check failed:
    record `errored`
3. Evict cached poetry venv (Fix 5 / #944) so locks release
4. `poetry install` — fresh install of updated dependencies
5. `poetry run pytest -q --tb=short` — capture exit code. Past 1800s the
   process tree is killed and the exit is 124: deferred, no baseline (#4737)

   --- exit != 0 ---
6a. `gh pr review <N> --comment` with the exit code (a COMMENTED review)
6b. If multi-package, comment `@dependabot recreate`
6c. Go to step 6f, which removes the worktree

   --- exit == 0 ---
6a. `gh pr edit <N> --body "<body>\n\nNo-Issue: automated dependency update (...)"`
     — satisfies pr-sentinel Worker's No-Issue exemption
6b. Wait 5s for pr-sentinel to re-evaluate
6c. `gh pr review <N> --approve --body "..."` — PullRequestReview event
     attributed to the invoking user (Code Review profile stat accrues to that user)
6d. Poll `mergeable_state` until `clean` (up to 5 min)
6e. `gh pr merge <N> --squash`

   --- every path, from process_pr's finally (#1116, #1133) ---
6f. Evict worktree's poetry venv; `git worktree remove`; `git branch -d` the
     audit branch

7. Print one `OUTCOME PR #<N>: <status> -- <reason>` line and clear the
   PR's in-flight entry (#4737). An interrupt prints the line as `errored`
   and keeps the entry.
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

For a PR deferred by the fake-root guard gate (#4736), no suite ran, so the rebase comment says the head predates the guard instead of "Test suite failed", and step 3's recreate is not posted.

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

The tool keeps no worktree for a deferred or errored PR. `process_pr` removes the audit worktree and deletes its branch on every path, in its `finally` (#1116, #1133). The evidence of a deferral is in two places:

- **The run log**, `data/dependabot-runs/<stamp>.log` in the checkout the tool runs from. The run names it as it starts (`Run log:`) and again after the Summary (`Full run log:`). The PR's section starts `=== PR #<N>:` and holds its `pytest exit code:` line and its `OUTCOME PR #<N>: deferred -- <reason>` line.
- **The review comment on the PR**, a COMMENTED review that gives the reason. The PR's Actions output carries the failing tests.

To reproduce a failure, test the PR yourself in a worktree of your own with `gh pr checkout <N> --detach`, as the review comment says.

**When removal fails.** The run prints `CLEANUP FAILURE` with git's stderr and `WARNING: leftover state for PR #<N> at <path>`. The next run's orphan check then skips that repo until the worktree is gone. First find what made it fail, such as the uncommitted files a `CLEANUP WARNING` lists; never discard them. Then, from the repo's own checkout:

```bash
poetry -C <path> env remove --all
git worktree remove <path>
```

The tool deletes its audit branch, `dependabot-audit-<N>`, with `git branch -d`. A branch left behind once its worktree is gone goes to the fleet's landed-branch cleanup tool, never to a deletion by hand.

The cleanup skill will also catch a leftover worktree as an orphan directory per Fix 5's logic.

---

## Summary output

At end of run, the tool prints:

```
=== Summary ===
  Merged:   ['martymcenroe/AssemblyZero#756', 'martymcenroe/AssemblyZero#741']
  Deferred: ['martymcenroe/AssemblyZero#479']
  Errored:  []
  Review events created: 2 APPROVED + 1 COMMENTED = 3 total
```

- **Merged:** PR passed both gates and is on main.
- **Deferred:** PR failed a gate (test failure, poetry install failure, pytest timeout, or a head without the fake-root guard). A review comment is posted, and possibly `@dependabot rebase` or `@dependabot recreate`. Also a PR that two earlier runs began at this head and never finished; that deferral runs nothing and posts nothing (§Outcome lines and the in-flight ledger).
- **Errored:** Infrastructure failure (couldn't create worktree, couldn't checkout PR, couldn't approve, the fake-root guard check failed, etc.), an exception while testing the PR (the operator is alerted and the sweep goes on), or an interrupt (the run then stops). Worktree is cleaned up; the PR needs manual attention.
- **Skipped (private, #4750):** printed only when the run skipped a repository. It lists repositories, not PRs: each was private, or its visibility could not be read, and nothing was done to it (§Private repositories are skipped).
- **Review events created:** the reviews the run posted, counted by kind as each `gh pr review` call succeeds (#4746), never inferred from the lists above. A PR approved and then deferred (its `mergeable_state` never cleared, #1399) or errored (a merge conflict, or the squash merge failed) counts as APPROVED. A deferral that posted no review counts nothing.

The Summary prints even when the run is interrupted, and it names every PR the run touched, the one interrupted mid-test included (#4737).

---

## Outcome lines and the in-flight ledger (#4737)

From 2026-11-01 the nightly tested PR #4315 night after night and recorded nothing: each run was interrupted inside pytest, the PR reached no Summary list, and the next night picked it first again. Two things now prevent that.

**One line per PR.** Every PR the run takes up, the skipped-unchanged and limit-skipped ones included, ends with exactly one line in the log:

```
  OUTCOME PR #<N>: <status> -- <reason>
```

`<status>` is `merged`, `deferred`, `errored`, `limit_skipped` or `skipped_unchanged`. A `=== PR #<N>` section with no OUTCOME line means the process ended before the outcome could be recorded; its in-flight entry stays, and the next run reports it.

**The in-flight ledger.** `data/dependabot-runs/in-flight.json`, in the checkout the tool runs from, holds one entry per PR a run began and has not finished:

```json
{
  "martymcenroe/AssemblyZero#4315": {
    "head": "<full head sha>",
    "runs": ["<run label>"]
  }
}
```

A run's label is its log file's name, such as `2026-11-13_050008.log`.

The tool writes the entry just before it tests a PR and removes it when the PR's outcome is recorded. An interrupt keeps it. The next run that reaches the PR prints:

```
  REPEAT PR #<N>: run <label> began this PR at head <sha9> and recorded no outcome
```

and tests it again, adding its own label. Once two runs (`IN_FLIGHT_STRIKES`) have begun the PR at its current head with no outcome, later runs record it `deferred` without running it, and the entry stays. A new head (a rebase or a new dependabot push) starts the count again from that run.

If the file is not valid JSON, or not a JSON object, the tool raises `InFlightLedgerError`, naming the path, and leaves the file as it is rather than reset it and forget the runs it records.

**Clearing an entry by hand.** When the cause is fixed and you want the PR tested at its current head, open `in-flight.json` in the checkout the nightly runs from, delete that PR's key and its value, and keep the rest of the object valid JSON. An empty ledger is `{}`. A missing file reads as an empty ledger, so deleting the file clears every entry at once. The next run tests the PR as new.

---

## Integration

Run this audit:

- **On demand** via `/dependabot` (single-repo) or `/dependabot --fleet` (cross-repo).
- **Daily passive** via Windows Task Scheduler (#1092) — see §Daily Schedule below.
- Before shipping a batch of features (so dependencies stay current).

### Daily Schedule (#1092)

The fleet sweep is wired to a Windows Scheduled Task `Claude-DependabotFleet` so dependabot PRs are processed automatically each morning regardless of whether the operator remembers to run `/dependabot`. The task uses the operator's logged-in account so the `gh pr review` events still attribute to the user (Code Review profile-stat credit accrues correctly).

**Setup (run once on a fresh machine):** the task is registered by the private
environment-tooling repo's launcher converter (a silent wscript launcher — see
#1819 for why powershell.exe cannot be the direct task action without a console
flash). The launcher invokes the wrapper script, which lives in the fleet's
private orchestration repo as of 2026-08-09 (#2156) — it names private paths
and its run records enumerate the fleet, so it cannot live here.

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

The PowerShell wrapper (in the private orchestration repo since #2156) is the durable definition of what the task runs — the registration just points at it via the launcher. Modifying the wrapper changes future runs without touching the task registration. Per-run logs are archived by the wrapper into the private fleet-ledger repo's `data/dependabot-runs/`; the flat status log above stays at `Projects/dependabot-fleet.log` (read by `tools/dependabot_morning_status.py`).

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
| 2026-11-13 | v2.4 (#4736, #4737): Fake-root guard gate: a head without the guard `origin/main` has is deferred untested, with a rebase request when stale. The pytest timeout kills the process tree and defers. One `OUTCOME` line per PR, a Summary that survives an interrupt, and the in-flight ledger with its `REPEAT` line and two-strike deferral. |
| 2026-11-13 | (#4744, #4745, #4746): A deferred PR's worktree is removed like every other; §Forensics on failure now points at the run log and the review comment, and the Summary's deferred heading makes no worktree claim. The audit branch is deleted with `git branch -d`, and a leftover goes to the fleet's landed-branch cleanup tool. The Summary's review-event counts are the reviews posted, recorded as each review call succeeds. |
| 2026-11-13 | (#4750): The tool acts only on public repositories, by the operator's ruling that work costing GitHub Actions minutes stays off until December. A private repository, or one whose visibility cannot be read, is skipped before the pre-pass and listed in the Summary. `INCLUDE_PRIVATE_REPOS` is the switch, and `--include-private` turns it on for one run. |
