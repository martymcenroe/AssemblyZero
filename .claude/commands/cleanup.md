---
description: Session cleanup with quick/normal/full modes
argument-hint: "[--help] [--quick|--normal|--full] [--no-auto-delete]"
aliases: ["/closeout", "/goodbye"]
scope: global
---

# Cleanup

**Aliases:** `/closeout` (same as `/cleanup`), `/goodbye` (same as `/cleanup --quick`)

**Model hints:**
- `--quick`: Can use **Haiku** (simple git commands, session log append)
- `--normal`: Use **Sonnet** (branch analysis, conditional fixes)
- `--full`: Use **Sonnet** (comprehensive verification)

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

---

## Help

Usage: `/cleanup [--help] [--quick|--normal|--full] [--no-auto-delete]`

| Argument | Description |
|----------|-------------|
| `--help` | Show this help message and exit |
| `--quick` | Minimal cleanup (~2 min) - appends session log, does NOT commit |
| `--normal` | Standard cleanup (~5 min) - typical session end (default) |
| `--full` | Comprehensive cleanup (~12 min) - after features, before breaks |
| `--no-auto-delete` | Skip automatic deletion of orphaned branches |

**What each mode does:**
| Check | Quick | Normal | Full |
|-------|:-----:|:------:|:----:|
| Git status | YES | YES | YES |
| Branch list | YES | YES | YES |
| Open PRs | YES | YES | YES |
| **Session log append** | YES | YES | YES |
| **Commit & push** | | YES | YES |
| Stash list | | YES | YES |
| Worktree list | | YES | YES |
| **Auto-delete orphans** | | YES | YES |
| **Purge tmpclaude files** | YES | YES | YES |
| Inventory audit | | | YES |

**Quick mode philosophy:** Record what happened (session log), but don't commit. Changes accumulate until a normal/full cleanup commits them.

---

## Project Detection

Detect the current project from working directory:
- Extract project name from path (e.g., `/c/Users/mcwiz/Projects/Aletheia` → `Aletheia`)
- Handle worktree paths (e.g., `Aletheia-123` → project is `Aletheia`)
- Look up GitHub repo from known registry or `gh repo view`

**Known Projects:**
| Project | GitHub Repo |
|---------|-------------|
| Aletheia | martymcenroe/Aletheia |
| AssemblyZero | martymcenroe/AssemblyZero |
| Talos | martymcenroe/Talos |
| claude-code | anthropics/claude-code |
| maintenance | (none) |

---

## Execution

**Mode:** Parse `$ARGUMENTS` for flags. Default is `--normal` if no flag provided.

**Session Name:** Determine the session identifier:
1. If `/rename` was used, extract the name
2. Look for session ID in visible transcript path
3. Otherwise use "unnamed"

---

## Quick Mode — Execute Inline (no subagent)

**Quick mode runs directly in the parent agent.** No Task tool, no subagent spawn.
This saves ~$0.05-0.10 per invocation since quick mode is just a few git commands + session log.

### Step 1: Information Gathering (3 parallel Bash calls)

```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} status
```
```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch --list
```
```bash
gh pr list --state open --repo {GITHUB_REPO}
```

(Skip `gh` call if no GitHub repo.)

### Step 2: Purge tmpclaude Files

```bash
find /c/Users/mcwiz/Projects/{PROJECT_NAME} -name "tmpclaude-*-cwd" -type f -delete
```

### Step 3: Session Log

1. `mkdir -p /c/Users/mcwiz/Projects/{PROJECT_NAME}/docs/session-logs`
2. Get date: `powershell.exe -Command "Get-Date -Format 'yyyy-MM-dd'"`
3. Read existing log file if it exists, then use Write/Edit tool to append:

```
## Session: {SESSION_NAME}
- **Mode:** quick cleanup
- **Summary:** [brief description of what happened this session]
- **Next:** Per user direction
```

### Step 4: Report

Display a brief summary:

```
Quick cleanup: {PROJECT_NAME}
• Git: {clean/N uncommitted}
• Branches: {list}
• Open PRs: {count}
• tmpclaude purged: {count}
• Session log: appended
(No commit — use /cleanup --normal to commit)
```

**DONE. Do not proceed to normal/full phases.**

---

## Normal & Full Modes — Delegate to Subagent

**For `--normal` and `--full`:** Use the **Task tool** with `model: sonnet` to execute the cleanup.

Spawn a Task with `subagent_type: general-purpose` and `model: sonnet` with this prompt:

---

### Task Prompt for Sonnet Agent

```
You are executing a cleanup procedure.
Project: {PROJECT_NAME}
GitHub Repo: {GITHUB_REPO} (if known, skip gh commands if none)
Project Root: /c/Users/mcwiz/Projects/{PROJECT_NAME}
Mode: {MODE: normal|full}
Session: {SESSION_NAME}

## Rules
- Use absolute paths with git -C /c/Users/mcwiz/Projects/{PROJECT_NAME}
- Use --repo {GITHUB_REPO} for all gh commands (skip if no repo)
- Run independent commands in PARALLEL (multiple Bash calls in one message)
- ONE commit at the end - stage files as you go, commit once
- NEVER touch files in worktree directories (e.g., `../Project-123/`)

## Phase 1: Information Gathering (ALL PARALLEL)

**Normal mode (7 parallel calls):**
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} status
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch --list
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} stash list
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} fetch --prune
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} worktree list
- gh pr list --state open --repo {GITHUB_REPO} (skip if no repo)
- gh issue list --state open --repo {GITHUB_REPO} (skip if no repo)

**Full mode adds (9 parallel calls total):**
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -vv
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -r

## Phase 2: Conditional Fixes

1. **Branches vs Worktrees** - Cross-reference:
   - Branch HAS worktree: OK (active work)
   - Branch has NO worktree + remote gone: Orphan candidate

2. **Auto-Delete Orphaned LOCAL Branches** (unless --no-auto-delete):
   - Safety: Not main, remote shows `gone`, no worktree
   - Action: `git -C ... branch -D {branch-name}`

3. **CRITICAL: Delete Stale REMOTE Branches for Merged PRs:**
   - Get merged PRs: `gh pr list --repo {GITHUB_REPO} --state merged --limit 50 --json headRefName`
   - Get remote branches: `git -C ... branch -r` (exclude origin/main, origin/HEAD)
   - For each remote branch (e.g., `origin/57-foo`):
     - If branch name appears in merged PR list → DELETE IT
     - Action: `git -C ... push origin --delete {branch-name}`
   - This is NON-NEGOTIABLE. Merged PR branches MUST be deleted.

4. **Verify No Orphaned Worktrees:**
   - List worktrees: `git -C ... worktree list`
   - For each worktree (not main):
     - Check if corresponding branch has an OPEN PR
     - If PR is MERGED or CLOSED: worktree is orphaned → REPORT AS ERROR
   - Worktrees for merged work MUST be removed manually (safety)
   - **Pre-removal poetry venv eviction (Windows file-lock mitigation):** Before calling `git worktree remove` on any worktree, run the following inside that worktree so its cached poetry virtualenv doesn't hold file locks:
     ```bash
     poetry env remove --all  # run from inside the worktree
     ```
     Without this, `git worktree remove` will succeed in deregistration but leave the on-disk directory locked by the venv's Python process handles. (#944)

5. **Delete Empty Orphaned Worktree Directories:**
   - After `git -C ... worktree prune`, scan for leftover orphan directories:
     ```bash
     ls -d /c/Users/mcwiz/Projects/{PROJECT_NAME}-*/ 2>/dev/null
     ```
   - For each matching directory:
     - Skip if it appears in `git worktree list` (still active)
     - **Evict cached poetry venv first** (releases Windows file locks):
       ```bash
       cd /c/Users/mcwiz/Projects/{DIR_NAME}
       poetry env remove --all 2>/dev/null || true
       cd -
       ```
     - Check if empty: `ls -A /c/Users/mcwiz/Projects/{DIR_NAME}/`
     - If empty: `rmdir /c/Users/mcwiz/Projects/{DIR_NAME}` (safe — fails if not empty)
     - If contains only `.git` file: remove it first, then rmdir
     - If still not empty after venv eviction: report as warning with contents listing (do NOT `rm -rf` from the skill — user decides)
   - Report count of deleted directories and any residue

6. **Open PRs** - Flag if any exist

7. **Stashes** - Document any found

8. **Purge tmpclaude Files:**
   - `find /c/Users/mcwiz/Projects/{PROJECT_NAME} -name "tmpclaude-*-cwd" -type f -delete`
   - Report count in results

9. **Filesystem Hygiene Report** (counts only — no auto-delete):
   ```bash
   find /c/Users/mcwiz/.claude/todos/ -name "*.json" -size -20c 2>/dev/null | wc -l
   ls /c/Users/mcwiz/.claude/plans/*.md 2>/dev/null | wc -l
   ls /c/Users/mcwiz/.claude/security_warnings_state_*.json 2>/dev/null | wc -l
   ```
   - Report: "Filesystem: {N} empty todos, {N} plan files, {N} stale state files"
   - If empty todos > 100 or plan files > 20: suggest purge

## Phase 3: Session Log

Create/append session log:
1. mkdir -p /c/Users/mcwiz/Projects/{PROJECT_NAME}/docs/session-logs
2. Get date: powershell.exe -Command "Get-Date -Format 'yyyy-MM-dd'"
3. Use Write tool: C:\Users\mcwiz\Projects\{PROJECT_NAME}\docs\session-logs\{DATE}.md

If file exists, read first and append new section.

Content:
```
## Session: {SESSION_NAME}
- **Mode:** {MODE} cleanup
- **Summary:** [brief description]
- **Next:** Per user direction
```

## Phase 4: Commit Session Artifacts via Tracked PR

**Scope (critical — do NOT expand without addressing #920 risks):** this phase is INTENTIONALLY NARROW. It stages only session artifacts, never user code, binaries, or drafts. Expanding scope (auto-committing user work) requires the secret-scan, size-gate, and policy-file mitigations tracked in #920 Phase 2+.

**ALLOWED paths** (auto-staged):
- `docs/session-logs/*.md`
- `docs/lessons-learned.md`
- `data/session-index.jsonl`
- `data/pickup-status.json`
- `.claude/commands/*.md` (AssemblyZero only — skill sync)
- `.claude/hooks/*.sh` (AssemblyZero only — hook sync)

**DENIED patterns** (NEVER staged, even if changed — report only so user handles separately):
- Credentials: `*.env*`, `*.dev.vars*`, `*.pem`, `*.key`, anything matching `*secret*`, `*credential*`, `*token*` in filename
- Binaries/opaque: `*.zip`, `*.pptx`, `*.mp4`, `*.wav`, `*.mov`, `*.ipynb`, any file `>10MB`
- Content: `drafts/**`, anything outside the ALLOWED list

### 4.1 — Detect ALLOWED-scope changes

```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} status --porcelain
```

- If no ALLOWED-scope files are modified/untracked: skip to Phase 5.
- If NON-ALLOWED files are ALSO modified: stage only the ALLOWED ones; REPORT the non-allowed list to the user so they can handle it separately. Do NOT block cleanup.

### 4.2 — Detect branch protection

```bash
gh api repos/{GITHUB_REPO}/branches/main/protection --jq 'has("required_status_checks")' 2>/dev/null
```

- Output `true`: main is protected → use tracked-PR flow (4.3).
- Output `false` / error / 404: main is unprotected → use direct-push fallback (4.9).

### 4.3 — Tracked-PR flow (protected main)

**a) Create tracking issue:**
```bash
gh issue create --repo {GITHUB_REPO} \
  --title "chore: session cleanup {DATE} — {SESSION_NAME}" \
  --body "Auto-created by /cleanup to track session-artifact commit.

Files:
{LIST_OF_ALLOWED_FILES}

Session: {SESSION_NAME}"
```
Capture issue number from the URL → `ISSUE_N`.

**b) Branch + stage ALLOWED paths + commit:**
```bash
BRANCH="cleanup-{DATE}-{session-slug}"
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} checkout -b $BRANCH
# Stage only ALLOWED paths (ignore errors for paths that don't apply to this project):
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add docs/session-logs/ 2>/dev/null
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add docs/lessons-learned.md 2>/dev/null
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add data/session-index.jsonl 2>/dev/null
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add data/pickup-status.json 2>/dev/null
# AssemblyZero only (skill + hook sync):
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add .claude/commands/ 2>/dev/null
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add .claude/hooks/ 2>/dev/null
# Review what's staged:
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} diff --cached --stat
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} commit -m "chore: session cleanup {DATE} (Closes #${ISSUE_N})

Session: {SESSION_NAME}

Co-Authored-By: Claude [model] <noreply@anthropic.com>"
```

**c) Push and open PR:**
```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} push -u origin $BRANCH
gh pr create --repo {GITHUB_REPO} --head $BRANCH --base main \
  --title "chore: session cleanup {DATE} (Closes #${ISSUE_N})" \
  --body "## Summary

Session cleanup artifacts from \`{SESSION_NAME}\`.

{git diff --cached --stat output}

Closes #${ISSUE_N}"
```
Capture PR number → `PR_N`.

**d) Wait for checks, merge, clean up branch:**
```bash
until [ "$(gh api repos/{GITHUB_REPO}/pulls/$PR_N --jq '.mergeable_state')" = "clean" ]; do sleep 10; done
gh pr merge $PR_N --squash --repo {GITHUB_REPO}
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} checkout main
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} pull --rebase
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -D $BRANCH
```

### 4.9 — Direct-push fallback (unprotected main only)

If 4.2 detected no protection:
```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add docs/session-logs/ docs/lessons-learned.md data/session-index.jsonl data/pickup-status.json 2>/dev/null
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} commit -m "chore: session cleanup {DATE} — {SESSION_NAME}"
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} push
```

### 4.10 — Failure handling

If ANY step in 4.3 fails: STOP and REPORT. Do NOT use `--admin`, `--no-verify`, or bypass branch protection. Report:
- Tracking issue number (may need manual closure)
- Branch name (may need manual push/merge)
- Files still uncommitted

Let the user decide the next step.

## Phase 5: Verification (PARALLEL)

```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} status
gh pr list --state open --repo {GITHUB_REPO}
```

Full mode adds:
```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} worktree list
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -r
```

## Return Results

| Check | Status |
|-------|--------|
| Project | {PROJECT_NAME} |
| Git Status | Clean / {details} |
| Open PRs | 0 / {count} open |
| Open Issues | {count} |
| Local Branches | Only main / {list} |
| Remote Branches | Only main / {list} |
| Worktrees | Only main / {list} |
| Local Orphans Deleted | {count} branches / 0 |
| **Remote Stale Deleted** | {count} branches / 0 |
| **Orphan Worktrees** | None / **ERROR: {list}** |
| Empty Worktree Dirs Deleted | {count} / 0 |
| Stashes | None / {count} |
| tmpclaude Purged | {count} files / 0 |
| Empty Todos | {count} (purge if >100) |
| Plan Files | {count} (archive if >20) |
| Stale State Files | {count} (purge if >0) |
| Commit | Pushed |

**BLOCKING CONDITIONS (must be resolved):**
- Orphan worktrees (worktree exists but PR merged/closed)
- Stale remote branches (remote branch exists but PR merged)

Flag any unexpected conditions.
```

---

## After Task Completes

Display the results summary to the user. Highlight any warnings.
