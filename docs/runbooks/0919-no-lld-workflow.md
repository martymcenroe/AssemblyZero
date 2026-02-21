# 0919 - No-LLD Lightweight Workflow

**Status:** Active
**Created:** 2026-02-21
**Issue:** #287

---

## Purpose

Document the manual lightweight process for issues that don't need a full Low-Level Design (LLD). Provides a fast path from issue to implementation for small, well-understood changes.

---

## When to Use

| Scenario | Use No-LLD? |
|----------|:-----------:|
| Bug fix with clear reproduction | YES |
| Config/environment change | YES |
| Simple refactor (rename, move) | YES |
| Documentation-only change | YES |
| Single-file feature (<100 lines) | YES |
| Dependency update | YES |
| Multi-component feature | NO — use LLD |
| Architectural change | NO — use LLD |
| New workflow or system | NO — use LLD |
| Cross-repo coordination | NO — use LLD |
| Security-sensitive change | NO — use LLD |

**Rule of thumb:** If you can explain the entire change in the issue body and it touches ≤3 files, skip the LLD.

---

## Manual Process

### Step 1: Read the Issue

Read the GitHub issue body. It should contain:
- Clear problem statement
- Expected behavior
- Acceptance criteria (or enough context to derive them)

### Step 2: Create Worktree

```bash
cd /c/Users/mcwiz/Projects/{REPO}
git worktree add ../{REPO}-{ISSUE_NUMBER} -b {ISSUE_NUMBER}-short-description
cd ../{REPO}-{ISSUE_NUMBER}
```

### Step 3: Implement

Write code directly. Follow existing patterns in the codebase.

### Step 4: Test

```bash
poetry run pytest tests/ -q
```

Ensure no regressions. Add tests for new behavior.

### Step 5: Commit, Push, PR

```bash
git add <specific files>
git commit -m "feat: description (#ISSUE)"
git push -u origin {BRANCH}
gh pr create --title "..." --body "..."
```

### Step 6: Merge & Cleanup

Follow standard post-merge cleanup from WORKFLOW.md.

---

## Automated Path: `--issue-only` Flag

For issues that fit the no-LLD criteria, the TDD workflow supports an `--issue-only` flag that fetches the issue body and uses it directly as the implementation spec:

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
CLAUDECODE= PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue NUMBER --repo /c/Users/mcwiz/Projects/TARGET_REPO \
    --issue-only --no-worktree
```

This skips the LLD/spec file search and constructs a synthetic spec from the issue title and body. All downstream TDD nodes (N1-N8) run normally.

---

## Governance

- No-LLD changes still require PR review
- No-LLD changes still need tests (no exceptions)
- If scope grows during implementation, stop and create an LLD
- Track time in closing comment: `Clock: Xm Ys`
