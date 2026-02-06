# /zugzwang - Prompt Usage

**File:** `docs/skills/0624p-zugzwang-prompt.md`
**CLI Guide:** [0624c-zugzwang-cli.md](0624c-zugzwang-cli.md)
**Version:** 2026-01-14

---

## Quick Reference

```
/zugzwang              # Activate logger, show recent
/zz                    # Alias
/zugzwang --tail 20    # Show last 20 entries
/zugzwang --clear      # Clear log file
/zugzwang --review     # Full log with analysis
/zugzwang --blast      # Post to GitHub, then clear
/zugzwang --help       # Show help
```

---

## When to Use This Skill

| Scenario | Use Skill? |
|----------|------------|
| Activate live logging | **Skill** - stays active |
| Quick log check | **CLI** - saves tokens |
| Review with analysis | **Skill --review** |
| Post findings to GitHub | **Skill --blast** |
| Just clear log | **CLI** - one command |

---

## What It Does

Real-time permission friction logger. Tracks:
- Commands with risky patterns (`&&`, `|`, `;`)
- Tool calls blocked by hooks
- User denials and approvals

---

## Arguments

| Argument | Description |
|----------|-------------|
| `--help` | Show help and exit |
| `--tail N` | Show last N entries (default: 10) |
| `--clear` | Clear the log file |
| `--review` | Full log with analysis, don't clear |
| `--blast` | Post to GitHub #17637, then clear |

---

## Event Types

| Event | Description |
|-------|-------------|
| `PATTERN_RISKY` | Commands with `\|`, `&&`, `;` before execution |
| `TOOL_BLOCKED` | Tool calls blocked by hooks/permissions |
| `TOOL_DENIED` | User denied permission prompts |
| `TOOL_APPROVED` | User approved permission prompts |

---

## Example Session

```
User: /zugzwang

Claude: Zugzwang logger activated. Recent entries:

2026-01-14T10:30:45 | TOOL_BLOCKED | agent:sonnet | tool:Bash | context:"head -n 5 ~/.claude/file" | status:blocked
2026-01-14T10:31:02 | TOOL_APPROVED | agent:opus | tool:Bash | context:"git status" | status:confirmed

2 events logged. Monitoring for new friction...
```

---

## Review Mode

```
User: /zugzwang --review

Claude: ## Zugzwang Log Analysis

**Period:** 2026-01-14 09:00 to 14:30
**Total Events:** 15

### Summary
| Event Type | Count |
|------------|-------|
| TOOL_BLOCKED | 8 |
| TOOL_DENIED | 2 |
| TOOL_APPROVED | 5 |

### Top Friction Points
1. `head -n` on .claude paths (5 blocks)
2. `grep` with pipe (2 blocks)
3. AWS command without MSYS prefix (1 block)

### Recommended Actions
- Use Read tool instead of head
- Use Grep tool instead of grep
- Add MSYS_NO_PATHCONV=1 prefix for AWS
```

---

## Blast Mode

Posts accumulated findings to GitHub issue #17637 (Claude Code permission friction tracking), then clears the log.

```
User: /zugzwang --blast

Claude: Posted 15 events to github.com/anthropics/claude-code/issues/17637
Log cleared.
```

---

## Why "zugzwang"?

Chess term: a position where any move worsens your situation. Perfect metaphor for permission friction - you're stuck waiting for approval, unable to proceed.

---

## Relationship to /friction

| Skill | Purpose |
|-------|---------|
| `/zugzwang` | Live capture during work |
| `/friction` | Forensic analysis after sessions |

Complementary. Use both for comprehensive friction tracking.

---

## Source of Truth

**Tool:** `AssemblyZero/tools/zugzwang.py`
**Log:** `AssemblyZero/logs/zugzwang.log`
**Skill definition:** `~/.claude/commands/zugzwang.md`
