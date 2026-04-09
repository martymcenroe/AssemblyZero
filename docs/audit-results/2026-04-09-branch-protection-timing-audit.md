# Branch Protection Timing Audit — 2026-04-09

## Context

Batch deployment of a one-line config fix (`.unleashed.json` model override, unleashed#186) across 5 repos revealed significant timing discrepancies in merge readiness. All 5 PRs were identical in scope (remove one JSON field), yet time-to-merge ranged from **20 seconds to 130 seconds** — a 6.5x spread.

This audit documents the timing data and identifies the root cause.

## Raw Timing Data (from poll log)

Source: `unleashed/logs/fix-model-batch.log` (batch run 2026-04-09 01:55:20 - 02:00:10 CDT)

### Per-Repo Merge Timeline

| Repo | PR | Blocked | Unstable | Clean | Total to Merge | Notes |
|------|----|---------|----------|-------|----------------|-------|
| unleashed | #187 | ~10s | ~0s | ~10s | **~10-20s** | Manual merge (pre-batch) |
| career | #737 | 20s | 10s | 40s | **~50s** | Includes 2s sleep between repos |
| AssemblyZero | #904 | 30s | 90s | 130s | **~140s** | `test` workflow is the bottleneck |
| sextant | #25 | 20s | 10s | 40s | **~50s** | Identical profile to career |
| patent-general | #12 | 10s | 0s | 20s | **~30s** | Fastest — went blocked to clean in 2 polls |

### Merge State Transitions (10s poll intervals)

```
career:         blocked → blocked → unstable → clean          (4 polls)
AssemblyZero:   blocked → blocked → blocked → unstable x9 → clean  (13 polls)
sextant:        blocked → blocked → unstable → clean          (4 polls)
patent-general: blocked → clean                               (2 polls)
```

## Check Run Details (where API access available)

### unleashed (3 checks)

| Check | Started | Completed | Duration | Result |
|-------|---------|-----------|----------|--------|
| pr-sentinel / issue-reference | 06:17:10 | 06:17:10 | **0s** | success |
| issue-reference | 06:17:15 | 06:17:19 | **4s** | success |
| auto-review / auto-review | 06:17:13 | 06:17:39 | **26s** | success |

### AssemblyZero (4 checks)

| Check | Started | Completed | Duration | Result |
|-------|---------|-----------|----------|--------|
| pr-sentinel / issue-reference | 06:56:26 | 06:56:26 | **0s** | success |
| issue-reference | 06:56:30 | 06:56:33 | **3s** | success |
| auto-review / auto-review | 06:56:29 | 06:56:55 | **26s** | success |
| test | 06:56:31 | 06:58:35 | **124s** | success |

### career, sextant, patent-general

Check-runs API returned HTTP 403 (fine-grained PAT lacks `checks:read` on these repos). Timing inferred from poll data.

## Analysis

### Why AssemblyZero is 3x slower

AssemblyZero has a **`test` workflow** that runs on PRs, taking **124 seconds (2m 4s)**. No other repo in this batch has this check. This is the sole cause of the 90s unstable period — pr-sentinel and auto-review complete within 30s (matching other repos), but the merge is blocked until `test` finishes.

### Merge State Semantics

| State | Meaning | What's happening |
|-------|---------|------------------|
| `blocked` | Required checks have not passed | pr-sentinel running, Cerberus not yet triggered |
| `unstable` | Some checks passed, not all | pr-sentinel passed, Cerberus approved, but `test` (AZ) still running |
| `clean` | All checks pass + approval received | Ready to merge |

### Check Configuration Profiles (Inferred)

| Profile | Repos | Checks | Typical Time to Clean |
|---------|-------|--------|----------------------|
| **Minimal** | patent-general | pr-sentinel only? | **~20s** |
| **Standard** | career, sextant, unleashed | pr-sentinel + issue-reference + auto-review | **~30-40s** |
| **Full** | AssemblyZero | pr-sentinel + issue-reference + auto-review + test | **~130s** |

### Discrepancies and Questions

1. **patent-general skipped `unstable` entirely** — went from `blocked` directly to `clean` in one poll cycle. This suggests it may have fewer required checks (possibly just pr-sentinel), or its checks all complete within 10 seconds.

2. **career and sextant are identical** — same 4-poll pattern, same 40s to clean. Likely same branch protection ruleset.

3. **Check-runs API access is inconsistent** — the fine-grained PAT can read check runs on unleashed and AssemblyZero but not career, sextant, or patent-general. This suggests the `checks:read` permission is not uniformly granted across repos.

4. **AssemblyZero `test` workflow runs on a config-only change** — the `test` check ran for 124s on a PR that changed a single JSON config file. If the test suite doesn't exercise `.unleashed.json`, this is wasted CI time. Consider adding path filters to the test workflow.

5. **No test workflow on unleashed** — unleashed has no `test` check despite being a Python project with source code. Either tests are run differently, or there's a gap.

## Recommendations

1. **Audit branch protection rulesets across all repos** — Requires admin-scope PAT or GitHub UI review. Document which checks are required where.

2. **Add path filters to AssemblyZero test workflow** — Skip the test suite when only config files (`.unleashed.json`, `*.md`, etc.) change. This would have saved 2 minutes on this PR.

3. **Standardize check-runs PAT permissions** — The fine-grained PAT should have `checks:read` on all repos to enable automated auditing.

4. **Consider adding a test workflow to unleashed** — If unleashed has tests, they should run on PRs.

5. **Investigate patent-general's minimal protection** — Verify whether it intentionally has fewer required checks or if checks are misconfigured.

## Batch Operation Summary

| Metric | Value |
|--------|-------|
| Repos processed | 5 (1 manual + 4 batch) |
| Total batch wall time | 4m 50s |
| Time in blocked/unstable polling | ~4m 10s (86% of batch time) |
| API calls (estimated) | ~80 (10 per repo + polling) |
| Issues created | 5 |
| PRs created and merged | 5 |
| Failures | 0 |
