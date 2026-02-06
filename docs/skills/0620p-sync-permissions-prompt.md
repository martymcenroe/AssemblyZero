# /sync-permissions - Prompt Usage

**File:** `docs/skills/0620p-sync-permissions-prompt.md`
**CLI Guide:** [0620c-sync-permissions-cli.md](0620c-sync-permissions-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/sync-permissions                      # Audit current project
/sync-permissions --clean              # Clean (dry-run first, then confirm)
/sync-permissions --audit PROJECT      # Audit specific project
/sync-permissions --merge-up           # Merge patterns to master
/sync-permissions --repair             # Fix invalid JSON (deletes broken files)
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| Routine cleanup after sessions | **CLI** - saves tokens |
| Settings file is corrupted/broken | **Skill** - Claude can diagnose |
| Want to understand what's being removed | **Skill** - Claude explains |
| Integrating with other cleanup tasks | **Skill** - Claude orchestrates |
| Quick check before starting work | **CLI** - `--quick-check` |

---

## Usage

### Audit (Default)

```
/sync-permissions
```

Claude will:
1. Detect the current project from working directory
2. Run `assemblyzero-permissions.py --audit --project PROJECT`
3. Explain the findings (session vends, reusable patterns, unclear)
4. Recommend whether cleaning is needed

### Clean

```
/sync-permissions --clean
```

Claude will:
1. Run dry-run first: `--clean --all-projects --dry-run`
2. Show what would be removed
3. Ask for confirmation: "Remove N one-time permissions? (y/n)"
4. If confirmed, run actual clean
5. Report results

### Audit Specific Project

```
/sync-permissions --audit Aletheia
```

Claude will audit only the specified project.

### Merge Up

```
/sync-permissions --merge-up
```

Claude will:
1. Clean all projects first (locked step)
2. Merge unique patterns from projects into master
3. Sync master to Projects level
4. Report what was merged

---

## What Claude Does Behind the Scenes

The skill invokes:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py [OPTIONS]
```

### Detection Logic

Claude uses the tool's detection to identify:

| Detection | Description |
|-----------|-------------|
| **Giant** | Permissions >300 chars (e.g., Gemini prompts) |
| **Embedded** | Newlines, markdown, code in permissions |
| **Pattern** | Known one-time patterns (commits, PRs) |

### Safety Features

- Always dry-run before destructive operations
- Creates backup before modifying
- Validates JSON before and after writes
- Asks for confirmation before cleaning

---

## Example Session

```
User: /sync-permissions --clean

Claude: I'll clean accumulated one-time permissions. Let me run a dry-run first.

[Runs dry-run]

Found 3 permissions to remove:
- AssemblyZero: 1 giant permission (6230 chars)
- Talos: 1 giant permission (1975 chars)
- Projects: 1 embedded content permission

Remove these 3 one-time permissions? (y/n)

User: y

Claude: [Runs actual clean]

Done. Cleaned 3 permissions:
- AssemblyZero: Removed 1, kept 50
- Talos: Removed 1, kept 63
- Projects: Removed 1, kept 215

Backups created at *.local.json.bak
```

---

## Troubleshooting

### "Found 1 invalid settings file" (Claude Code /doctor)

If you see this error on Claude startup:
```
Found 1 invalid settings file · /doctor for details
```

**Use --repair:**
```
/sync-permissions --repair
```

Claude will:
1. Find the broken settings file(s)
2. Delete project-level files (inheritance kicks in from parent)
3. For master-level: restore from backup if available

**Why this works:** Project-level settings files are expendable. Deleting them lets the parent level take over. Claude recreates permissions as you work.

### "Invalid JSON" During --clean or --audit

If --clean or --audit fails with a JSON error, run --repair first:
```
/sync-permissions --repair
/sync-permissions --clean
```

### Claude Can't Find Project

If Claude can't detect the project:
```
/sync-permissions --audit PROJECT_NAME
```

Specify the project name explicitly.

---

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `/cleanup` | Often run together at session end |
| `/friction` | Analyzes permission prompts (different purpose) |
| `/zugzwang` | Logs permission events in real-time |

---

## Source of Truth

**Tool:** `AssemblyZero/tools/assemblyzero-permissions.py`
**Skill definition:** `~/.claude/commands/sync-permissions.md`

If the tool needs fixing, fix it in AssemblyZero - not locally.
