# /friction - CLI Usage (Manual Steps)

**File:** `docs/skills/0623c-friction-cli.md`
**Prompt Guide:** [0623p-friction-prompt.md](0623p-friction-prompt.md)
**Version:** 2026-01-14

---

## Overview

The `/friction` skill analyzes Claude Code session transcripts for permission friction. There's no standalone CLI tool, but you can manually search transcripts.

---

## Manual Analysis

### Find Session Transcripts

```bash
# List recent transcripts
ls -la ~/.claude/projects/C--Users-mcwiz-Projects-PROJECT/

# Each folder is a session with transcript files
```

### Search for Permission Errors

```bash
# Find "permission" mentions
grep -r "permission" ~/.claude/projects/C--Users-mcwiz-Projects-PROJECT/

# Find blocked tool calls
grep -r "blocked" ~/.claude/projects/C--Users-mcwiz-Projects-PROJECT/

# Find error patterns
grep -r "error\|Error\|ERROR" ~/.claude/projects/C--Users-mcwiz-Projects-PROJECT/
```

### Common Friction Patterns

| Pattern | Indicates |
|---------|-----------|
| `permission denied` | Missing allowlist entry |
| `MSYS_NO_PATHCONV` | Windows path conversion issue |
| `not found` | Command not in PATH or allowlist |
| `blocked by hook` | Hook rejected the command |

---

## Manual Remediation

Once you identify friction, add patterns to settings:

```json
// ~/.claude/settings.local.json or PROJECT/.claude/settings.local.json
{
  "permissions": {
    "allow": [
      "Bash(new-command:*)"
    ]
  }
}
```

---

## When to Use Manual vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Quick search for specific error | Manual grep |
| Comprehensive friction analysis | Use `/friction` |
| Generate remediation plan | Use `/friction` |
| Saving tokens | Manual |

---

## Friction Categories

| Category | Description | Remediation |
|----------|-------------|-------------|
| MISSING | Command not in allowlist | Add `Bash(cmd:*)` |
| MSYS | Path conversion issue | Add `MSYS_NO_PATHCONV=1` prefix |
| PATTERN | Command structure blocked | Change to allowed pattern |
| ENV_PREFIX | Env var prefix not allowed | Add `Bash(VAR=val cmd:*)` |
| DENIED | Intentionally blocked | Document why |

---

## Related Files

- Session transcripts: `~/.claude/projects/C--Users-mcwiz-Projects-PROJECT/`
- Permission settings: `~/.claude/settings.local.json`
- Skill definition: `~/.claude/commands/friction.md`
