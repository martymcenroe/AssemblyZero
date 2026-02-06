# /onboard - CLI Usage (Manual Steps)

**File:** `docs/skills/0622c-onboard-cli.md`
**Prompt Guide:** [0622p-onboard-prompt.md](0622p-onboard-prompt.md)
**Version:** 2026-01-14

---

## Overview

The `/onboard` skill is Claude-orchestrated. For manual onboarding, read these files directly.

---

## Refresh Mode (Manual)

For post-compact or resumed sessions - just reload rules:

```bash
# 1. AssemblyZero core rules
cat /c/Users/mcwiz/Projects/AssemblyZero/CLAUDE.md

# 2. Projects root rules
cat /c/Users/mcwiz/Projects/CLAUDE.md

# 3. Current project rules
cat PROJECT/CLAUDE.md

# 4. Current permissions (optional)
cat /c/Users/mcwiz/Projects/.claude/settings.local.json | jq '.allow'
```

---

## Quick Mode (Manual)

Read these files:

```bash
# 1. Project rules
cat PROJECT/CLAUDE.md

# 2. System guide (if exists)
cat PROJECT/docs/0000-GUIDE.md

# 3. Recent session log
cat PROJECT/docs/session-logs/$(date +%Y-%m-%d).md
# or most recent file in that directory
```

---

## Full Mode (Manual)

All of Quick mode, plus:

```bash
# 4. Architecture docs
cat PROJECT/docs/0001-*.md

# 5. Open issues
gh issue list --state open --repo OWNER/REPO --limit 10

# 6. Sprint focus (if exists)
cat PROJECT/docs/SPRINT-*.md

# 7. Onboard digest (if exists)
cat PROJECT/docs/0000b-ONBOARD-DIGEST.md
```

---

## Key Files to Read

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules and constraints |
| `docs/0000-GUIDE.md` | System philosophy and patterns |
| `docs/0001-*.md` | Architecture documentation |
| `docs/session-logs/*.md` | Recent session history |
| `docs/0000b-ONBOARD-DIGEST.md` | Auto-generated project summary |

---

## When to Use Manual vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Post-compact / resumed session | Use `/onboard --refresh` |
| Quick status check | Manual - read CLAUDE.md |
| Full context loading | Use `/onboard` - Claude synthesizes |
| New to project | Use `/onboard --full` |
| Just need rules | Manual - read CLAUDE.md |
| Saving tokens | Manual |

---

## Related Files

- Project rules: `PROJECT/CLAUDE.md`
- Session logs: `PROJECT/docs/session-logs/`
- Skill definition: `AssemblyZero/.claude/commands/onboard.md`
