---
description: Session cleanup with quick/normal/full modes
argument-hint: "[--help] [--quick|--normal|--full] [--no-auto-delete]"
aliases: ["/closeout", "/goodbye"]
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

5. **Delete Empty Orphaned Worktree Directories:**
   - After `git -C ... worktree prune`, scan for leftover empty directories:
     ```bash
     ls -d /c/Users/mcwiz/Projects/{PROJECT_NAME}-*/ 2>/dev/null
     ```
   - For each matching directory:
     - Skip if it appears in `git worktree list` (still active)
     - Check if empty: `ls -A /c/Users/mcwiz/Projects/{DIR_NAME}/`
     - If empty: `rmdir /c/Users/mcwiz/Projects/{DIR_NAME}` (safe — fails if not empty)
     - If contains only `.git` file: remove it first, then rmdir
     - If not empty: report as warning (do NOT rm -rf)
   - Report count of deleted directories

6. **Open PRs** - Flag if any exist

7. **Stashes** - Document any found

8. **Purge tmpclaude Files:**
   - `find /c/Users/mcwiz/Projects/{PROJECT_NAME} -name "tmpclaude-*-cwd" -type f -delete`
   - Report count in results

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

## Phase 4: Single Commit & Push

Stage ALL pending doc changes:
```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} add docs/ CLAUDE.md .github/workflows/ .claude/
```

Review and commit:
```bash
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} status
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} commit -m "docs: {MODE} cleanup $(powershell.exe -Command "Get-Date -Format 'yyyy-MM-dd'")"
git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} push
```

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
| Commit | Pushed |

**BLOCKING CONDITIONS (must be resolved):**
- Orphan worktrees (worktree exists but PR merged/closed)
- Stale remote branches (remote branch exists but PR merged)

Flag any unexpected conditions.
```

---

## After Task Completes

Display the results summary to the user. Highlight any warnings.
