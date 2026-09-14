# ADR 0229: The "Fully Landed" State

## Context

Git terminology relies on the word "clean" to describe the state of the local working directory (i.e. `git status` reports no modified tracked files and no untracked files). However, a "clean" local directory does not mean the project as a whole is finished or free of dangling architectural state. Agents and operators frequently miscommunicate because "clean" can exist simultaneously with open PRs, dormant stashes, and dangling worktrees.

When auditing a repository's lifecycle state across the fleet, we need a precise vocabulary term that describes a project at absolute rest.

## Decision

We define the term **"Fully Landed"** to describe a repository that meets five strict criteria:

1. **Working Directory Clean:** `git status` shows no modified tracked files and no untracked files (excluding properly gitignored artifacts).
2. **No Dangling Worktrees:** `git worktree list` shows only the `main` branch worktree. There are no active feature worktrees. (This implicitly guarantees that the operator's local `~/Projects/` directory remains free of orphaned worktree subdirectories.)
3. **No Local Stashes:** `git stash list` is empty.
4. **No Open Pull Requests:** `gh pr list` returns 0 open pull requests. All in-flight work has been merged or explicitly closed.
5. **Main Branch Synced:** The local `main` branch is exactly up to date with `origin/main` (`git fetch origin && git status` confirms parity). **Crucially: the agent (not the operator) is responsible for executing the final `git pull` on `main` to achieve this state.**

If all five conditions are met, the repo is **Fully Landed**.

## Consequences

- When an operator or agent performs a fleet-wide inspection and asks "Is this repo fully landed?", the agent must explicitly evaluate all five criteria (status, worktrees, stashes, PRs, and sync) rather than just looking at the local directory.
- This term gives us a binary, non-ambiguous diagnostic target for repository hygiene.
