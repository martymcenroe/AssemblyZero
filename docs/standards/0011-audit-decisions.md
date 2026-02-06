# 0011 - Audit Decisions

**Status:** Active
**Created:** 2026-01-29
**Applies to:** Structure audits via `new-repo-setup.py --audit`

---

## Purpose

This document records decisions that affect how structure audits interpret compliance with the canonical project structure defined in `0009-canonical-project-structure.md`.

Not every project needs every directory. This file codifies which exceptions are acceptable and why.

---

## Allowed Empty Directories

These directories may be empty (with `.gitkeep`) without triggering audit warnings:

- `tests/*` - Empty test category scaffolding is intentional; tests are added as features mature
- `docs/templates/` - May not have project-specific templates initially
- `docs/adrs/` - New projects may not have ADRs yet
- `docs/standards/` - New projects typically inherit from AssemblyZero
- `docs/runbooks/` - Operational procedures added as needed
- `docs/session-logs/` - Populated during agent sessions
- `docs/audit-results/` - Populated when audits run
- `docs/lld/active/` - Populated when implementation starts
- `docs/lld/done/` - Populated when implementations complete
- `docs/reports/active/` - Populated during implementation
- `docs/reports/done/` - Populated after merges
- `docs/media/` - Media files added as needed (4xxxx range)
- `docs/legal/` - Legal docs added for consumer-facing apps
- `docs/design/` - Design artifacts added for UI/visual projects
- `data/` - App data added as needed (examples, templates, seeds)

---

## Allowed Missing Directories

These directories are optional and may be entirely absent:

- `extensions/` - Only required for browser extension projects
- `wiki/` - Only if GitHub wiki integration is used
- `ideas/` - Optional encrypted ideation folder (see AssemblyZero CLAUDE.md for setup)
- `.claude/gemini-prompts/` - Only if project uses Gemini reviews
- `.claude/commands/` - Only if project has custom slash commands
- `.claude/hooks/` - Only if project uses pre/post tool hooks
- `src/` - Extension-only or tools-only projects may not need src/
- `tools/` - Not every project needs custom tools

---

## Required Regardless of Project Type

These items are ALWAYS required and cannot be exempted:

### Files
- `CLAUDE.md` - Agent instructions (required for AssemblyZero governance)
- `GEMINI.md` - Gemini agent instructions
- `README.md` - Project overview
- `.gitignore` - Git ignore rules
- `.claude/project.json` - Project variables
- `.claude/settings.json` - Hook configuration
- `docs/00003-file-inventory.md` - Project file inventory

### Directories
- `docs/` - Documentation root
- `tests/` - Test root (even if empty subdirectories)
- `.claude/` - Claude Code configuration

---

## Adding New Exceptions

When a legitimate exception is needed:

1. **Create an issue** explaining why the exception is needed
2. **Get orchestrator approval**
3. **Update this file** with the exception and rationale
4. **Add tests** to verify the audit correctly handles the exception

---

## Audit Failure Remediation

When an audit fails:

1. **Check this file** - Is the missing item actually required?
2. **Create the directory** with `.gitkeep` if it should exist
3. **Add to exceptions** if the item is legitimately optional
4. **Re-run audit** to verify compliance

---

## Related Standards

- `0009-canonical-project-structure.md` - Defines the required structure
- `AssemblyZero/CLAUDE.md` - Ideas folder setup with git-crypt
