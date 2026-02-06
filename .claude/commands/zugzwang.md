---
description: Real-time permission friction logger - track every permission prompt
argument-hint: "[--help] [--tail N] [--clear] [--review] [--blast]"
aliases: ["/zz"]
---

# Zugzwang - Permission Friction Logger

**Aliases:** `/zz` (same as `/zugzwang`)

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

---

## Help

Usage: `/zugzwang [--help] [--tail N] [--clear] [--review] [--blast]`

| Argument | Description |
|----------|-------------|
| `--help` | Show this help message and exit |
| `--tail N` | Show last N log entries (default: 10) |
| `--clear` | Clear the log file and start fresh |
| `--review` | Show full log with analysis, do NOT clear |
| `--blast` | Post to GitHub #17637, then clear log |

**Examples:**
- `/zugzwang --help` - show this help
- `/zugzwang` or `/zz` - activate logger, show recent entries
- `/zugzwang --tail 20` - show last 20 entries
- `/zugzwang --clear` - clear log file
- `/zugzwang --review` - review all entries without clearing
- `/zugzwang --blast` - post to GitHub and clear

**What it does:**
1. Activates real-time logging of all permission-related events
2. Logs risky command patterns BEFORE execution
3. Logs blocked/denied tool calls AFTER they fail
4. Propagates logging to spawned agents

**Log location:**
`C:\Users\mcwiz\Projects\AssemblyZero\logs\zugzwang.log`

**Why "zugzwang"?**
Chess term: a position where any move worsens your situation. Perfect metaphor for permission friction - you're stuck waiting for approval, unable to proceed.

---

## Execution

### Step 1: Determine Mode

Parse `$ARGUMENTS`:
- `--blast` flag present → Blast mode (post to GitHub, then clear)
- `--review` flag present → Review mode (show full log, no clear)
- `--clear` flag present → Clear mode
- `--tail N` present → Show N entries (extract number)
- No flags → Default mode (activate + show last 10)

### Step 2: Log File Path

```
LOG_PATH = C:\Users\mcwiz\Projects\AssemblyZero\logs\zugzwang.log
(Bash path: /c/Users/mcwiz/Projects/AssemblyZero/logs/zugzwang.log)
```

### Step 3: Execute Based on Mode

**If `--blast`:**
1. Read full log from LOG_PATH
2. If empty: Output "No friction events to blast." and STOP
3. Count unique patterns and total events
4. Post to GitHub:
   ```bash
   gh issue comment 17637 --repo anthropics/claude-code --body "## Friction Batch

   [List each unique pattern with:
   - The prompt/command that triggered it
   - The pattern that SHOULD have matched]

   Total events: [count]"
   ```
5. Clear the log file
6. Output: "Blasted [N] events to GitHub #17637. Log cleared."
7. STOP

**If `--review`:**
1. Read full log from LOG_PATH
2. If empty: Output "No friction events logged yet." and STOP
3. Display ALL entries with analysis:
   - Group by event type (PATTERN_RISKY, TOOL_BLOCKED, etc.)
   - Count occurrences of each pattern
   - Identify most frequent friction points
4. Output summary table
5. Do NOT clear the log
6. STOP

**If `--clear`:**
1. Use Write tool to create empty file at LOG_PATH
2. Output: "Zugzwang log cleared. Fresh start."
3. STOP

**If `--tail N` or default:**
1. Use Read tool to check if LOG_PATH exists
2. If file doesn't exist or is empty:
   - Output: "No friction events logged yet."
3. If file has content:
   - Read last N lines (default 10) using Read with offset
   - Display entries in formatted table

### Step 4: Activate Logging Protocol

Output to user:
```
**Zugzwang Active**

From this point forward, I will log all permission-related events to:
`C:\Users\mcwiz\Projects\AssemblyZero\logs\zugzwang.log`

Events logged:
- PATTERN_RISKY: Commands with |, &&, ; before execution
- TOOL_BLOCKED: Tool calls blocked by hooks/permissions
- TOOL_DENIED: User denied permission prompts
- TOOL_APPROVED: User approved permission prompts

When spawning agents, logging instructions will be included automatically.
```

---

## Logging Protocol (ACTIVE FOR REMAINDER OF SESSION)

### Pre-Tool Logging (BEFORE Bash calls)

**Risky patterns that MUST be logged before execution:**
- Command contains `|` (pipe)
- Command contains `&&` (chain)
- Command contains `;` (separator)
- Command uses `head -n` or `tail -n` with flags on `.claude/` paths
- Command not in common safe allowlist

**If risky pattern detected:**
1. Get current timestamp: Use PowerShell `Get-Date -Format "yyyy-MM-ddTHH:mm:ss"`
2. Append to log file using Write tool (read, append, write back):

```
Entry format:
TIMESTAMP | PATTERN_RISKY | agent:opus | tool:Bash | context:"COMMAND_HERE" | status:pre-execution
```

3. Then execute the command

### Post-Tool Logging (AFTER tool results)

**Scan every tool result for these indicators:**
- "blocked"
- "denied"
- "not allowed"
- "requires approval"
- "permission"
- Exit code non-zero with permission-related context

**If indicator found:**
```
TIMESTAMP | TOOL_BLOCKED | agent:opus | tool:TOOL_NAME | context:"ERROR_MSG" | status:blocked
```

---

## Spawned Agent Instructions (MANDATORY)

**When spawning ANY Task agent while zugzwang is active, APPEND this to the prompt:**

```
**ZUGZWANG LOGGING ACTIVE:**

You MUST log permission-related events to:
C:\Users\mcwiz\Projects\AssemblyZero\logs\zugzwang.log

**Before ANY Bash command that:**
- Contains | (pipe), && (chain), or ; (separator)
- Uses flags like `head -n` or `tail -n` on .claude/ paths
- Might trigger a permission prompt

**Do this:**
1. Read the current log file content
2. Append a new line: `TIMESTAMP | PATTERN_RISKY | agent:sonnet | tool:Bash | context:"YOUR_COMMAND" | status:pre-execution`
3. Write the updated content back
4. Then execute your command

**After ANY tool result containing:**
"blocked", "denied", "not allowed", "requires approval"

**Do this:**
1. Read → Append → Write: `TIMESTAMP | TOOL_BLOCKED | agent:sonnet | tool:TOOL | context:"ERROR" | status:blocked`

Use PowerShell for timestamp: `powershell.exe -Command "Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'"`
```

---

## Log Entry Format Reference

```
TIMESTAMP | EVENT_TYPE | agent:MODEL | tool:TOOL | context:"DESCRIPTION" | status:STATUS
```

| Field | Values |
|-------|--------|
| TIMESTAMP | `yyyy-MM-ddTHH:mm:ss` |
| EVENT_TYPE | `PATTERN_RISKY`, `TOOL_BLOCKED`, `TOOL_DENIED`, `TOOL_APPROVED` |
| agent | `opus`, `sonnet`, `haiku` |
| tool | `Bash`, `Edit`, `Write`, `unknown` |
| context | Brief description or command snippet |
| status | `pre-execution`, `blocked`, `denied`, `confirmed` |

---

## Integration with /friction

- `/zugzwang` = live capture during work
- `/friction` = forensic analysis after sessions

They are complementary. Future enhancement: `/friction` could read zugzwang.log to correlate.
