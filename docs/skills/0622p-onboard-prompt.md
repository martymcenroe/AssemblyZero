# /onboard - Prompt Usage

**File:** `docs/skills/0622p-onboard-prompt.md`
**CLI Guide:** [0622c-onboard-cli.md](0622c-onboard-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/onboard              # Full onboarding (default)
/onboard --full       # Same as above
/onboard --quick      # Minimal - rules + recent context
/onboard --refresh    # Reload rules only (post-compact/resumed)
/onboard --help       # Show help
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| Post-compact / resumed session | **Skill --refresh** |
| Starting complex work | **Skill** - full context |
| Quick task | **Skill --quick** or **CLI** |
| Need project synthesis | **Skill** - Claude summarizes |
| Just need rules | **CLI** - read CLAUDE.md |

---

## Modes

### --refresh (~15s, ~$0.01)

Reload rules only - for post-compact or resumed sessions.

**What it reads:**
- `AssemblyZero/CLAUDE.md` - core rules (bash constraints, worktree isolation)
- `Projects/CLAUDE.md` - root rules
- Project `CLAUDE.md` - project-specific rules
- `settings.local.json` - current permissions (optional scan)

**Use when:** Context was compacted, resuming with `/resume`, or need to re-anchor on rules.

### --quick (~30s, ~$0.02)

Minimal onboarding for simple tasks.

**What it reads:**
- `CLAUDE.md` - project rules
- `docs/0000-GUIDE.md` - if exists
- Most recent session log entry

**Use when:** Status check, simple task, returning briefly.

### --full (~2min, ~$0.35) - Default

Comprehensive onboarding for complex work.

**What it reads:**
- Everything in quick mode
- `docs/0001-*.md` - architecture docs
- Sprint focus document (if exists)
- Open issues via `gh issue list`
- Onboard digest (if exists)

**Use when:** Feature work, audits, unfamiliar territory.

---

## Mode Comparison

| Check | Refresh | Quick | Full |
|-------|:-------:|:-----:|:----:|
| AssemblyZero CLAUDE.md | YES | | |
| Projects CLAUDE.md | YES | | |
| Project CLAUDE.md | YES | YES | YES |
| settings.local.json | optional | | |
| docs/0000-GUIDE.md | | YES | YES |
| Recent session log | | YES | YES |
| Architecture docs | | | YES |
| Sprint focus | | | YES |
| Open issues | | | YES |
| Onboard digest | | | YES |

---

## Example Session

```
User: /onboard --quick

Claude: Quick onboarding for AssemblyZero...

## Project: AssemblyZero
**Type:** Agent configuration system
**Status:** Active development

### Key Rules
- One command per Bash call (no &&)
- Worktree isolation for all code changes
- Visible self-check protocol required

### Recent Context
Last session (2026-01-14): Enhanced sync-permissions with giant detection

Ready to assist. What would you like to work on?
```

---

## Fallback for Unknown Projects

If project lacks AssemblyZero documentation:
1. Reads CLAUDE.md (if exists)
2. Reads README.md
3. Lists top-level directories
4. Reports: "Minimal onboarding - no AssemblyZero docs found"

---

## Troubleshooting

### "No CLAUDE.md found"

The project may not use AssemblyZero conventions. Claude will fall back to README.md.

### Onboard seems outdated

Check if `docs/0000b-ONBOARD-DIGEST.md` needs regeneration:
```bash
poetry run python tools/generate_onboard_digest.py
```

---

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `/cleanup` | Opposite operation (end vs start) |
| `/friction` | May run after onboard to check permissions |

---

## Source of Truth

**Skill definition:** `AssemblyZero/.claude/commands/onboard.md`
**User stub:** `~/.claude/commands/onboard.md`
