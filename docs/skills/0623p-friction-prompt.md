# /friction - Prompt Usage

**File:** `docs/skills/0623p-friction-prompt.md`
**CLI Guide:** [0623c-friction-cli.md](0623c-friction-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/friction                     # Analyze last 3 sessions
/friction --sessions 5        # Analyze last 5 sessions
/friction --since 2026-01-05  # Analyze since date
/friction --help              # Show help
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| Comprehensive friction analysis | **Skill** - thorough |
| Quick search for one error | **CLI** - grep |
| Generate remediation plan | **Skill** - Claude generates |
| Periodic maintenance | **Skill** - scheduled |

---

## What It Does

1. Searches Claude Code's verbatim session transcripts
2. Finds tool calls that resulted in errors or permission prompts
3. Categorizes findings (MISSING, MSYS, PATTERN, ENV_PREFIX, DENIED)
4. Generates remediation plan with specific settings.local.json changes

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--help` | Show help and exit |
| `--sessions N` | Analyze last N session files (default: 3) |
| `--since YYYY-MM-DD` | Analyze sessions since date |

---

## Friction Categories

| Category | Description | Remediation |
|----------|-------------|-------------|
| **MISSING** | Command not in allowlist | Add `Bash(cmd:*)` to allow |
| **MSYS** | Windows path conversion | Add `MSYS_NO_PATHCONV=1` prefix |
| **PATTERN** | Command structure blocked | Change to allowed pattern |
| **ENV_PREFIX** | Env var prefix not allowed | Add `Bash(VAR=val cmd:*)` |
| **DENIED** | Intentionally blocked | Document why, no action |

---

## Example Session

```
User: /friction --sessions 5

Claude: Analyzing last 5 session transcripts...

## Permission Friction Analysis - 2026-01-14

**Project:** AssemblyZero
**Scope:** Analyzed 5 sessions from 2026-01-10 to 2026-01-14

### Findings Summary

| Category | Count | Priority |
|----------|-------|----------|
| MISSING | 3 | HIGH |
| MSYS | 1 | MEDIUM |
| PATTERN | 0 | - |

### Remediation Actions

Add to settings.local.json allow list:
```json
"Bash(new-tool:*)",
"Bash(MSYS_NO_PATHCONV=1 aws:*)"
```

### Details

1. **MISSING:** `new-tool --flag` (3 occurrences)
   - Sessions: session-abc, session-def
   - Add: `Bash(new-tool:*)`

2. **MSYS:** `aws logs tail /aws/lambda/...`
   - Path converted incorrectly
   - Add: `Bash(MSYS_NO_PATHCONV=1 aws:*)`
```

---

## Permission-Safe Execution

This skill uses ONLY these tools (no permission prompts):

| Tool | Why Safe |
|------|----------|
| Glob | No path restrictions |
| Grep | No path restrictions |
| Read | System allows .claude paths |

---

## Output Format

```markdown
## Permission Friction Analysis - YYYY-MM-DD

**Project:** {PROJECT}
**Scope:** Analyzed N sessions from [date range]

### Findings Summary
| Category | Count | Priority |

### Remediation Actions
[JSON to add to settings]

### Details
[Per-finding breakdown]
```

---

## Relationship to /zugzwang

| Skill | Purpose |
|-------|---------|
| `/zugzwang` | Live capture during work |
| `/friction` | Forensic analysis after sessions |

They are complementary. Use `/zugzwang` while working, `/friction` periodically.

---

## Source of Truth

**Skill definition:** `~/.claude/commands/friction.md`
