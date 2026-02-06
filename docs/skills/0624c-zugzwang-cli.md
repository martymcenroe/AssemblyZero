# /zugzwang - CLI Usage

**File:** `docs/skills/0624c-zugzwang-cli.md`
**Prompt Guide:** [0624p-zugzwang-prompt.md](0624p-zugzwang-prompt.md)
**Tool:** `AssemblyZero/tools/zugzwang.py`
**Version:** 2026-01-14

---

## Quick Start

```bash
# Show recent log entries
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/zugzwang.py --tail 10

# Log a single event
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/zugzwang.py --log "head -n 5 ~/.claude/file"

# Clear the log
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/zugzwang.py --clear

# Show help
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/zugzwang.py --help
```

---

## Command Reference

```
usage: zugzwang.py [-h] [--log EVENT] [--tail [N]] [--clear]
                   [--category {BASH,SPAWNED,DENIED,APPROVED}]

options:
  -h, --help            show this help message and exit
  --log, -l EVENT       Log a single event and exit
  --tail, -t [N]        Show last N log entries (default: 10)
  --clear               Clear the log file
  --category, -c {BASH,SPAWNED,DENIED,APPROVED}
                        Category for --log event
```

---

## Log Location

```
C:\Users\mcwiz\Projects\AssemblyZero\logs\zugzwang.log
```

---

## Event Types

| Event | Description |
|-------|-------------|
| `PATTERN_RISKY` | Commands with `\|`, `&&`, `;` |
| `TOOL_BLOCKED` | Tool calls blocked by hooks |
| `TOOL_DENIED` | User denied permission |
| `TOOL_APPROVED` | User approved permission |

---

## Log Entry Format

```
TIMESTAMP | EVENT_TYPE | agent:MODEL | tool:TOOL | context:"DESC" | status:STATUS
```

Example:
```
2026-01-14T10:30:45 | TOOL_BLOCKED | agent:sonnet | tool:Bash | context:"head -n 5 ~/.claude/file" | status:blocked
```

---

## Manual Log Review

```bash
# View entire log
cat /c/Users/mcwiz/Projects/AssemblyZero/logs/zugzwang.log

# Count events by type
grep -c "TOOL_BLOCKED" /c/Users/mcwiz/Projects/AssemblyZero/logs/zugzwang.log
grep -c "TOOL_DENIED" /c/Users/mcwiz/Projects/AssemblyZero/logs/zugzwang.log

# View recent entries
tail -20 /c/Users/mcwiz/Projects/AssemblyZero/logs/zugzwang.log
```

---

## When to Use CLI vs Prompt

| Scenario | Recommendation |
|----------|----------------|
| Quick log check | **CLI** - `--tail` |
| Live logging during work | Use `/zugzwang` prompt |
| Clear log before session | **CLI** - `--clear` |
| Post to GitHub | Use `/zugzwang --blast` prompt |
| Saving tokens | **CLI** |

---

## Related Files

- Log file: `AssemblyZero/logs/zugzwang.log`
- Tool: `AssemblyZero/tools/zugzwang.py`
- Skill definition: `~/.claude/commands/zugzwang.md`
