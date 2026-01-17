# Sync Permissions User Guide

**File:** `docs/skills/0620-sync-permissions.md`
**Tool:** `AgentOS/tools/agentos-permissions.py`
**Slash Command:** `/sync-permissions`
**Version:** 2026-01-14

---

## Purpose

Clean accumulated one-time permissions from Claude Code settings files. Every time you approve a permission prompt, that exact command gets saved:

```json
"Bash(git -C /c/Users/mcwiz/Projects/Aletheia commit -m \"docs: cleanup 2026-01-10\")"
```

These are useless clutter. This tool removes them while keeping useful patterns like `Bash(git -C:*)`.

---

## Quick Start

```bash
# Show help
poetry run python tools/agentos-permissions.py --help

# Audit a project (read-only)
poetry run python tools/agentos-permissions.py --audit --project Aletheia

# Clean a project (dry-run first)
poetry run python tools/agentos-permissions.py --clean --project Aletheia --dry-run

# Clean all projects
poetry run python tools/agentos-permissions.py --clean --all-projects
```

---

## Command Reference

```
usage: agentos-permissions.py [-h] (--audit | --clean | --quick-check |
                              --merge-up | --restore | --repair) [--project PROJECT]
                              [--all-projects] [--dry-run]

options:
  -h, --help            show this help message and exit
  --audit               Read-only analysis of permissions
  --clean               Remove session vends (keeps reusable patterns)
  --quick-check         Fast check for cleanup integration
  --merge-up            Collect unique patterns from projects into master
  --restore             Restore from backup
  --repair              Fix invalid JSON by deleting broken files (inheritance kicks in)
  --project, -p PROJECT Project name (e.g., Aletheia)
  --all-projects        Apply to all projects
  --dry-run, -n         Show what would be done without modifying files
```

---

## Modes

### --audit (Read-Only)

Analyzes permissions and categorizes them. Does not modify files.

```bash
poetry run python tools/agentos-permissions.py --audit --project Aletheia
```

**Output:**
- Total permissions count
- Session vends (REMOVE): One-time permissions to clean
- Reusable patterns (KEEP): Wildcards, skills, web tools
- Unclear (KEEP): Permissions that don't clearly fit either category

### --clean

Removes session vends from project settings. Always creates a backup first.

```bash
# Always dry-run first
poetry run python tools/agentos-permissions.py --clean --project Aletheia --dry-run

# Then clean for real
poetry run python tools/agentos-permissions.py --clean --project Aletheia
```

**Safety features:**
- Creates `.bak` backup before modifying
- Validates JSON before and after writing
- Atomic write (temp file + rename)

### --quick-check

Fast check for cleanup script integration. Returns exit code:
- `0` = OK (5 or fewer session vends)
- `1` = Needs cleaning (more than 5 session vends)
- `2` = Error

```bash
poetry run python tools/agentos-permissions.py --quick-check --project Aletheia
echo $?  # Check exit code
```

### --merge-up

Collects unique reusable patterns from all projects and merges into master (`~/.claude/settings.local.json`).

```bash
# Dry-run first
poetry run python tools/agentos-permissions.py --merge-up --all-projects --dry-run

# Then merge
poetry run python tools/agentos-permissions.py --merge-up --all-projects
```

**Locked steps:**
1. Clean all projects first (remove session vends)
2. Merge unique patterns to master
3. Sync master to Projects level (`~/Projects/.claude/settings.local.json`)

### --restore

Restores from backup created by --clean or --merge-up.

```bash
poetry run python tools/agentos-permissions.py --restore --project Aletheia
```

### --repair

**Fixes invalid JSON settings files.** Use this when Claude Code shows:
```
Found 1 invalid settings file · /doctor for details
```

```bash
# Dry-run first (see what would be fixed)
poetry run python tools/agentos-permissions.py --repair --dry-run

# Actually repair
poetry run python tools/agentos-permissions.py --repair
```

**How it works:**

The tool leverages Claude Code's permission inheritance hierarchy:
```
~/.claude/settings.local.json          ← Master (protected)
~/Projects/.claude/settings.local.json ← Projects level (can delete)
~/Projects/{Project}/.claude/...       ← Project level (can delete)
```

| Level | Repair Strategy |
|-------|-----------------|
| Project-level | DELETE file → inherits from Projects-level or master |
| Projects-level | DELETE file → inherits from master |
| Master | RESTORE from backup (if valid) or manual fix required |

**Why delete instead of repair?**
- JSON repair is fragile and error-prone
- Deleting lets the parent level take over immediately
- Claude will recreate permissions as you work
- No data loss that matters (it's just accumulated junk anyway)

---

## Detection Logic

The tool detects one-time "session vends" that should be removed using three methods:

### 1. Giant Permission Detection (NEW)

Permissions longer than 300 characters are almost certainly one-time garbage (e.g., Gemini prompts saved as permissions).

**Threshold:** `MAX_PERMISSION_LENGTH = 300`

**Example caught:**
```
Bash(gemini-model-check.sh "You are reviewing an issue draft for the AgentOS project...")
[6230 chars - REMOVED]
```

### 2. Embedded Content Detection (NEW)

Permissions containing embedded prompts, scripts, or content markers:

| Marker | Description |
|--------|-------------|
| `\n` | Actual newlines (not escaped) |
| ` ``` ` | Markdown code blocks |
| `## ` | Markdown headers |
| `\\n\\n` | Double escaped newlines |
| `[BLOCKING]` | Review markers |
| `[HIGH]` | Review markers |
| `[SUGGESTION]` | Review markers |
| `QUESTION:` | Prompt markers |
| `CRITICAL INSTRUCTIONS:` | Prompt markers |
| `OUTPUT FORMAT:` | Prompt markers |
| `def ` | Python function definitions |
| `function ` | JS function definitions |
| `import ` | Import statements |

### 3. Pattern-Based Detection (Original)

| Pattern | Reason |
|---------|--------|
| Git commits with heredocs | `git commit -m "$(cat <<EOF...` |
| Git commits with inline messages | `git -C /path commit -m "specific"` |
| PR creations with long bodies | `gh pr create --body "..."` |
| Worktree-specific commands | `git -C /path/Project-123 status` |
| Push with tracking | `git push -u origin specific-branch` |
| PR merge commands | `gh pr merge` |
| Specific file opens | `start "" "C:\path\file.html"` |

---

## What Gets Kept

### Reusable Patterns

| Category | Example |
|----------|---------|
| Bash wildcards | `Bash(git -C:*)`, `Bash(poetry:*)` |
| Path wildcards | `Bash(/c/Users/mcwiz/Projects/**:*)` |
| Env var wildcards | `Bash(MSYS_NO_PATHCONV=1 aws:*)` |
| Skills | `Skill(cleanup)`, `Skill(onboard)` |
| Web tools | `WebFetch`, `WebSearch` |
| File wildcards | `Read(C:\Users\mcwiz\Projects\**)` |
| gh commands | `Bash(gh pr create:*)` |

### Protected Permissions

These are NEVER allowed in deny lists:
- `Bash(python:*)`
- `Bash(python3:*)`

If found in deny, they are automatically removed.

---

## JSON Validation (NEW)

The tool now validates JSON at multiple points to prevent corruption:

1. **Before serialization:** Ensures settings dict can be converted to JSON
2. **After serialization:** Validates the JSON string
3. **After writing:** Validates the written file before renaming

**Atomic write pattern:**
1. Write to `.json.tmp` file
2. Validate the temp file
3. Rename temp to final (atomic on most systems)

If validation fails at any step, the operation is aborted and the original file is preserved.

---

## File Locations

| File | Purpose |
|------|---------|
| `~/.claude/settings.local.json` | Master (user-level) settings |
| `~/Projects/.claude/settings.local.json` | Projects-level settings |
| `~/Projects/{Project}/.claude/settings.local.json` | Project-specific settings |
| `*.local.json.bak` | Backup files (created before modifications) |

---

## Slash Command Usage

The `/sync-permissions` slash command wraps this tool:

```
/sync-permissions                      # Audit current project
/sync-permissions --audit Aletheia     # Audit specific project
/sync-permissions --clean              # Remove one-time permissions (dry-run first)
/sync-permissions --quick              # Fast check (for cleanup integration)
/sync-permissions --merge-up           # Pull unique patterns from all projects into master
```

The slash command always:
1. Detects project from working directory
2. Runs dry-run first for destructive operations
3. Asks for confirmation before actual clean

---

## Troubleshooting

### "Found 1 invalid settings file" (Claude Code /doctor)

This means a settings.local.json file has corrupted JSON. **Use --repair:**

```bash
# See which file is broken
poetry run python tools/agentos-permissions.py --repair --dry-run

# Fix it (deletes broken file, inheritance kicks in)
poetry run python tools/agentos-permissions.py --repair
```

**Common causes:**
- Claude saved a giant Gemini prompt as a permission
- Multi-line strings or special characters in permissions
- Truncated write during a crash

**Why --repair works:** Project-level files are expendable. Deleting them lets the parent level (Projects or master) take over. Claude will recreate permissions as needed.

### "Invalid JSON" Error (during --audit or --clean)

If --audit or --clean fails with invalid JSON, use --repair first:

```bash
poetry run python tools/agentos-permissions.py --repair
# Then retry your original command
poetry run python tools/agentos-permissions.py --clean --project Aletheia
```

### Restore from Backup

```bash
# Find the backup
ls ~/.claude/settings.local.json.bak

# Restore
cp ~/.claude/settings.local.json.bak ~/.claude/settings.local.json
```

Or use the tool:
```bash
poetry run python tools/agentos-permissions.py --restore --project Aletheia
```

### Settings Not Taking Effect

Claude Code permissions DO NOT INHERIT - they REPLACE. When a project has its own permissions block, it completely overrides the parent.

Check the inheritance chain:
1. `~/.claude/settings.local.json` (master)
2. `~/Projects/.claude/settings.local.json` (projects level)
3. `~/Projects/{Project}/.claude/settings.local.json` (project specific)

---

## History

| Date | Change |
|------|--------|
| 2026-01-14 | Added giant permission detection (>300 chars) |
| 2026-01-14 | Added embedded content detection (newlines, markdown, code) |
| 2026-01-14 | Added JSON validation with atomic writes |
| 2026-01-14 | Created this user guide |

---

## Source of Truth

**Canonical location:** `AgentOS/tools/agentos-permissions.py`

If the tool needs fixing, fix it in AgentOS - not locally.
