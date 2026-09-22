# ADR 0231: PR Stuck Recovery Procedure

**Date:** 2026-09-13
**Status:** Accepted

> **Renumbered 0229 → 0231 on landing (#3461).** Written 2026-09-13 on a branch
> that could not see a sibling branch writing ADR 0229 at the same time. That one
> landed as `0229-fully-landed-state.md`, and `0230` followed it, so this took the
> next free number. Content is unchanged from the original.

## 1. Context

When a Pull Request is blocked by `pr-sentinel` (typically because the parasitic regex extracts an invalid `Closes #N` or the agent forgot to include it), agents historically resorted to violating strict rules to clear the block. Common evasion tactics included:
- Force-pushing amended commits to rewrite the commit message and re-trigger CI.
- Pushing empty or noise commits to re-trigger workflows (polluting git history).
- Attempting to bypass branch protection using `--admin` flags.

Because force-pushing and history pollution are permanently banned, we need a formalized, non-destructive procedure for recovering a stuck PR using only the GitHub API and without altering the git commit history.

## 2. Decision

We will use a purely metadata-driven recovery procedure utilizing the GitHub CLI. When a PR is stuck due to `pr-sentinel`:

1. **Fix the metadata without pushing commits:** The agent must run `gh pr edit {NUMBER} --title "... (Closes #N)" --body "... (Closes #N)"`. This corrects the parser input without touching git history.
2. **Re-trigger the CI without pushing commits:** Because the `edited` webhook does not trigger Cerberus Auto-Review, the agent must simulate a state change by running `gh pr close {NUMBER} && gh pr reopen {NUMBER}`. 
3. **Squash Merge:** Once Cerberus approves, the agent runs `gh pr merge {NUMBER} --squash`.

## 3. Consequences

### Positive
- **No Git History Pollution:** We eliminate the need for noise commits (`git commit --allow-empty`) just to trigger CI.
- **No Force Pushing:** We eliminate the need to amend commits and force push, strictly adhering to the global no-force-push policy.
- **Workflow Scope Bypass:** Because the recovery uses the GitHub Pull Request API (`gh pr`) rather than `git push`, it does not trigger the restrictive `.github/workflows` PAT block, eliminating the need to escalate to the Classic PAT (ADR-0216).

### Negative
- **Agent Friction:** The procedure is multi-step and requires specific CLI commands rather than standard git operations, introducing a learning curve and testing agent discipline.

## 4. Implementation

The procedure is documented in `CLAUDE.md` and the detailed decision tree is maintained in `docs/runbooks/0935-pr-stuck-recovery.md`. Agents must follow this exact sequence rather than improvising git commands.
