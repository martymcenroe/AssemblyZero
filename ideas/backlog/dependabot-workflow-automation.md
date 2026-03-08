# Brief: Dependabot Workflow Automation

**Status:** Active
**Created:** 2026-02-01
**Updated:** 2026-02-28
**Effort:** Medium
**Priority:** Medium
**Tracking Issue:** #351

---

## Problem

Dependabot creates PRs for dependency updates, but each PR requires manual review: check what changed, run tests, verify no regressions, merge or revert. With multiple repos and frequent updates, this is a recurring time sink. Runbook 0911 documents the current manual process, but it's tedious and easy to skip.

The core principle is simple: **exit codes are truth**. If `pytest` returns 0 after merging a dependency update, the update is safe. If it returns non-zero, revert. No LLM interpretation needed.

## What Already Exists

- **Runbook 0911** (`docs/runbooks/0911-dependabot-pr-audit.md`) — current manual Dependabot PR review process
- **Dependabot** — configured and creating PRs across repos
- **Parallel infrastructure** (`workflows/parallel/`) — coordinator, credential management, output prefixing — could batch-process multiple Dependabot PRs
- **`gh` CLI** — programmatic PR listing, checkout, merge, and revert

## The Gap

No automation connects Dependabot PRs to test execution and merge decisions. Each PR still requires a human to run the runbook manually. There is also no health gate — if `main` is already broken, merging a Dependabot PR on top makes diagnosis harder.

## Proposed Solution

A Python script (not a LangGraph workflow — no LLM in the critical path) that processes Dependabot PRs:

1. **Health gate** — query the Watch baseline (`run_watch.py --status`). If `main` is unhealthy, refuse to process Dependabot PRs until regressions are fixed.
2. **List pending PRs** — `gh pr list --author app/dependabot --json number,title,headRefName`
3. **For each PR:**
   a. Check out the PR branch
   b. Run `pytest` (full suite or configurable subset)
   c. If tests pass: merge (squash)
   d. If tests fail: add a comment with failure details, label `needs-review`, skip
4. **Report** — summary of merged/skipped/failed PRs

### Batch Processing

When multiple Dependabot PRs are pending, process them sequentially (not parallel — each merge changes `main` and subsequent PRs must rebase). Order by: patch updates first, then minor, then major.

### Safety Rails

- Never force-merge — if merge conflicts exist, label `needs-rebase` and skip
- Never process PRs that touch `pyproject.toml` lock file conflicts without human review
- Always run tests on the merged result, not just the PR branch

## Integration Points

- **Watch** (`city-watch-regression-guardian.md`) — health gate prerequisite. Watch must report healthy before automation proceeds.
- **Runbook 0911** — automation replaces the manual steps; runbook becomes the fallback for edge cases
- **Parallel infrastructure** (`workflows/parallel/`) — future enhancement: batch multiple repo scans in parallel (PR processing within a repo stays sequential)

## Acceptance Criteria

- [ ] Lists pending Dependabot PRs across configured repos
- [ ] Checks Watch health gate before processing
- [ ] Runs tests on each PR's merged result
- [ ] Auto-merges PRs where tests pass
- [ ] Labels and skips PRs where tests fail
- [ ] Produces a summary report (merged N, skipped N, failed N)
- [ ] Does not require an LLM or Gemini credentials
- [ ] Handles merge conflicts gracefully (skip, don't force)

## Dependencies & Cross-References

- **Issue #351** — tracking issue for automated dependency modernization
- **Brief: `city-watch-regression-guardian.md`** — Watch health gate is a hard dependency
- **Runbook 0911** — current manual process this replaces
- **Brief: `parallel-workflow-execution.md`** — parallel infrastructure for future multi-repo batch processing
