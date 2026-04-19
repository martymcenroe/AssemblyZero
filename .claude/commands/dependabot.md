---
description: Run the dependabot PR review + merge tool (test-then-approve, author-gated)
argument-hint: "[--help] [--dry-run]"
scope: global
---

# Dependabot

Runs `tools/dependabot_review.py` — a deterministic, author-gated, exit-code-gated tool that processes open dependabot PRs. Tests each PR in an audit worktree, and on green: injects `No-Issue:` into the body so pr-sentinel passes, approves with the invoking user's credentials (creating a `PullRequestReview` event that accrues to the user's profile Code Review stat), and squash-merges.

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

---

## Help

Usage: `/dependabot [--help] [--dry-run]`

| Argument | Effect |
|---|---|
| `--help` | Show this help and exit |
| `--dry-run` | List dependabot PRs that would be processed; take no action |

The tool operates ONLY on PRs authored by `dependabot[bot]`. Any other author is refused at the author gate. Tests must exit 0; non-zero exit means the PR is commented on and left for human review (not approved, not merged). No LLM in the decision loop — decisions are pure exit-code / string-match.

Reference: runbook `docs/runbooks/0911-dependabot-pr-audit.md` v2.0.

---

## Execution

Runs inline in the main agent context. No subagent — the Python tool does all the orchestration; the skill is a thin wrapper.

### Step 1 — Verify there are dependabot PRs to process

```bash
gh pr list --repo martymcenroe/AssemblyZero --author "app/dependabot" --state open --json number,title --jq 'length'
```

If the result is `0`: print "No open dependabot PRs. Nothing to do." and STOP.

### Step 2 — Invoke the tool

Run from the AssemblyZero root (NOT a worktree):

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/dependabot_review.py
```

Pass `--dry-run` through if the user supplied it:

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/dependabot_review.py --dry-run
```

Stream the tool's output to the user as-is.

### Step 3 — Report the summary

When the tool finishes, it prints a summary line like:

```
=== Summary ===
  Merged:   [756, 741]
  Deferred: [479]
  Errored:  []
```

Relay that summary to the user. If any PRs are in `Deferred`, note:

- The worktree for each deferred PR has been retained at `C:/Users/mcwiz/Projects/AssemblyZero-dependabot-<N>` for forensics
- Multi-package PRs that failed tests will have an `@dependabot recreate` comment posted; dependabot will generate per-package PRs shortly, which can be processed with another `/dependabot` run

If any PRs are in `Errored`, flag them plainly — those are infrastructure failures, not test failures, and likely need manual attention.

---

## Rules

- NEVER modify the Python tool from this skill — the skill is a wrapper, not a logic layer.
- NEVER approve or merge dependabot PRs outside this tool. The tool enforces the author gate and exit-code gate; ad-hoc approvals bypass those guarantees.
- The tool uses the invoking user's `gh` credentials to create the approval event. That's intentional — the `PullRequestReview` event attributes to the user, which is how the Code Review profile stat accrues. This only applies to dependabot PRs (author-gated) and only after tests pass (exit-code-gated).
- Do NOT invoke from inside a worktree. The tool needs access to the main repo to create audit worktrees.
