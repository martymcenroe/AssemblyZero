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

**IMPORTANT:** Use the **Task tool** with `model: sonnet` to execute the cleanup.

Spawn a Task with `subagent_type: general-purpose` and `model: sonnet` with this prompt:

---

### Task Prompt for Sonnet Agent

```
You are executing a cleanup procedure.
Project: {PROJECT_NAME}
GitHub Repo: {GITHUB_REPO} (if known, skip gh commands if none)
Project Root: /c/Users/mcwiz/Projects/{PROJECT_NAME}
Mode: {MODE: quick|normal|full}
Session: {SESSION_NAME}

## Rules
- Use absolute paths with git -C /c/Users/mcwiz/Projects/{PROJECT_NAME}
- Use --repo {GITHUB_REPO} for all gh commands (skip if no repo)
- NO pipes (|) or chain operators (&&) - one command per Bash call
- Run independent commands in PARALLEL (multiple Bash calls in one message)
- ONE commit at the end - stage files as you go, commit once

## CRITICAL: Contribution Budget & Worktree Safety

**PARSIMONIOUS COMMITS:** Batch ALL pending changes into ONE commit. Never make multiple small commits.

**WORKTREE ISOLATION:** NEVER touch files in worktree directories (e.g., `../Project-123/`). Only operate on the main worktree.

## Phase 1: Information Gathering (ALL PARALLEL)

**Quick mode (3 parallel calls):**
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} status
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch --list
- gh pr list --state open --repo {GITHUB_REPO} (skip if no repo)

**Normal mode adds (7 parallel calls total):**
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} stash list
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} fetch --prune
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} worktree list
- gh issue list --state open --repo {GITHUB_REPO} (skip if no repo)

**Full mode adds (9 parallel calls total):**
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -vv
- git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -r

## Phase 2: Conditional Fixes

1. **Branches vs Worktrees** - Cross-reference:
   - Branch HAS worktree: OK (active work)
   - Branch has NO worktree + remote gone: Orphan candidate

2. **Auto-Delete Orphaned LOCAL Branches** (Normal and Full, unless --no-auto-delete):
   - Safety: Not main, remote shows `gone`, no worktree
   - Action: `git -C ... branch -D {branch-name}`

3. **CRITICAL: Delete Stale REMOTE Branches for Merged PRs** (Normal and Full):
   - Get merged PRs: `gh pr list --repo {GITHUB_REPO} --state merged --limit 50 --json headRefName`
   - Get remote branches: `git -C ... branch -r` (exclude origin/main, origin/HEAD)
   - For each remote branch (e.g., `origin/57-foo`):
     - If branch name appears in merged PR list → DELETE IT
     - Action: `git -C ... push origin --delete {branch-name}`
   - This is NON-NEGOTIABLE. Merged PR branches MUST be deleted.

4. **Verify No Orphaned Worktrees** (Normal and Full):
   - List worktrees: `git -C ... worktree list`
   - For each worktree (not main):
     - Check if corresponding branch has an OPEN PR
     - If PR is MERGED or CLOSED: worktree is orphaned → REPORT AS ERROR
   - Worktrees for merged work MUST be removed manually (safety)

5. **Open PRs** - Flag if any exist

6. **Stashes** - Document any found

7. **Purge tmpclaude Files** (ALL modes):
   - Claude Code leaves orphaned `tmpclaude-*-cwd` files (temp CWD markers)
   - Delete them: `find /c/Users/mcwiz/Projects/{PROJECT_NAME} -name "tmpclaude-*-cwd" -type f -delete`
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
- **Model:** Claude Sonnet 4
- **Summary:** [brief description]
- **Next:** Per user direction
```

## Phase 4: Single Commit & Push (SKIP FOR QUICK MODE)

**If mode is `quick`: SKIP this phase entirely.**

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
| Stashes | None / {count} |
| tmpclaude Purged | {count} files / 0 |
| Commit | Pushed / Skipped (quick) |

**BLOCKING CONDITIONS (must be resolved):**
- Orphan worktrees (worktree exists but PR merged/closed)
- Stale remote branches (remote branch exists but PR merged)

Flag any unexpected conditions.
```

---

## After Task Completes

Display the results summary to the user. Highlight any warnings.
