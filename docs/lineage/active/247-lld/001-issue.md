---
repo: martymcenroe/AgentOS
issue: 247
url: https://github.com/martymcenroe/AgentOS/issues/247
fetched: 2026-02-04T19:47:42.688830Z
---

# Issue #247: feat: Two-tier commit validation with hourly orphan issue detection

## Problem

Not every commit should close an issue:
- LLD commits → `Ref #N` (design done, implementation needed)
- Artifact commits → `Ref #N`
- Implementation PRs → `fixes #N` (actually closes)

A simple "must have fixes #N" hook can't know the intent. LangGraph knows (it's in workflow state), but direct LLM prompts don't have that context.

## Solution: Two-Tier Validation

### Tier 1: Pre-commit Hook (Immediate)

Every commit MUST reference an issue:
```
Ref #N OR fixes #N OR closes #N OR resolves #N
```

If no reference found → BLOCK with message:
```
ERROR: Commit must reference an issue.
Use 'Ref #N' for artifacts or 'fixes #N' for implementation.
```

This catches completely orphaned commits.

### Tier 2: Orphan Issue Detection (Hourly)

Scheduled job that finds issues that SHOULD be closed but aren't:

```python
def detect_orphan_issues():
    """Find issues where implementation is merged but issue is open."""
    open_issues = gh_api.list_issues(state="open")

    for issue in open_issues:
        # Check if any merged PR references this issue
        prs = gh_api.list_prs(state="merged", search=f"#{issue.number}")

        for pr in prs:
            # If PR title/body suggests implementation (not just LLD)
            if is_implementation_pr(pr):
                report_orphan(issue, pr)
```

Heuristics for `is_implementation_pr()`:
- PR modifies `.py`, `.ts`, `.js` files (not just `.md`)
- Branch name matches issue number
- PR title starts with `fix:` or `feat:` (not `docs:`)

### Output

Weekly report or Slack notification:
```
Orphan Issues Detected:
- #173: PR #250 merged but issue still open (implementation PR)
- #188: PR #255 merged but issue still open (implementation PR)
```

## Files to Create

| File | Purpose |
|------|---------|
| `.githooks/commit-msg` | Tier 1 validation |
| `tools/orphan_issue_detector.py` | Tier 2 detection |
| `.github/workflows/orphan-detection.yml` | Hourly schedule |

## Acceptance Criteria

- [ ] Pre-commit hook rejects commits without issue reference
- [ ] Hook accepts both `Ref #N` and `fixes #N`
- [ ] Orphan detector runs hourly via GitHub Actions
- [ ] Detector distinguishes LLD PRs from implementation PRs
- [ ] Report generated for orphan issues

## Labels

`enhancement`, `governance`, `needs-lld`
