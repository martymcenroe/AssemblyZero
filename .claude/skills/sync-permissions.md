---
description: Clean accumulated one-time permissions from settings (AssemblyZero)
argument-hint: "[--audit | --clean | --quick | --merge-up] [PROJECT]"
scope: global
---

# Sync Permissions

**Cost:** Zero LLM cost - this skill orchestrates a Python tool, no model spawning.

Manage permissions across master (user-level) and project-level settings files.

## Background

Every time you approve a permission prompt, that exact command gets saved. Over time, hundreds of specific one-time commands accumulate:

```json
"Bash(git -C /c/Users/mcwiz/Projects/Aletheia commit -m \"docs: cleanup 2026-01-10\")"
```

These are useless clutter. The tool removes them while keeping useful patterns like `Bash(git -C:*)`.

---

## Usage

```
/sync-permissions                      # Audit current project
/sync-permissions --audit Aletheia     # Audit specific project
/sync-permissions --clean              # Remove one-time permissions (dry-run first)
/sync-permissions --quick              # Fast check (for cleanup integration)
/sync-permissions --merge-up           # Pull unique patterns from all projects into master
```

---

## Execution

### Step 1: Determine Project

Parse `$ARGUMENTS` for project name. If none specified, detect from working directory:
- `/c/Users/mcwiz/Projects/Aletheia` → `Aletheia`
- `/c/Users/mcwiz/Projects/AssemblyZero` → `AssemblyZero`

### Step 2: Parse Mode

| Argument | Mode |
|----------|------|
| (none) or `--audit` | Read-only analysis |
| `--clean` | Remove one-time permissions |
| `--quick` | Fast check (exit 0=OK, 1=needs cleaning) |
| `--merge-up` | Collect unique patterns from projects into master |

### Step 3: Execute

**Audit mode:**
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py --audit --project PROJECT_NAME
```

**Clean mode (always dry-run first):**
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py --clean --project PROJECT_NAME --dry-run
```

Show results and ask: "Remove N one-time permissions? (y/n)"

If yes:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py --clean --project PROJECT_NAME
```

**Quick mode:**
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py --quick-check --project PROJECT_NAME
```

**Merge-up mode (always dry-run first):**
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py --merge-up --all-projects --dry-run
```

Show results and ask: "Merge N patterns into master? (y/n)"

If yes:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py --merge-up --all-projects
```

### Step 4: Report

Display tool output with summary:
- Total permissions in file
- One-time permissions (removable)
- Reusable patterns (kept)
- Recommendation

---

## What Gets Removed vs Kept

**REMOVED (one-time, accumulated clutter):**
- Specific git commits: `git commit -m "specific message"`
- Specific PR creations with bodies
- Specific push commands: `git push -u origin specific-branch`
- Commands on worktrees: `git -C /path/Aletheia-123 ...`

**KEPT (reusable patterns):**
- Wildcards: `Bash(git -C:*)`, `Bash(poetry:*)`
- Skills: `Skill(cleanup)`, `Skill(onboard)`
- Web tools: `WebFetch`, `WebSearch`
- File patterns: `Read(C:\Users\mcwiz\Projects\**)`

---

## Source of Truth

This skill calls the tool at `AssemblyZero/tools/assemblyzero-permissions.py`.

**If the tool needs fixing, fix it in AssemblyZero - not locally.**
