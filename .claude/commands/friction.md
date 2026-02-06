---
description: Analyze session transcripts for permission friction (15-30 min)
argument-hint: "[--help] [--sessions N] [--since YYYY-MM-DD]"
---

# Permission Friction Analysis

**Model hint:** Use **Sonnet** - requires pattern recognition and analysis across multiple session files.

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

---

## Help

Usage: `/friction [--help] [--sessions N] [--since YYYY-MM-DD]`

| Argument | Description |
|----------|-------------|
| `--help` | Show this help message and exit |
| `--sessions N` | Analyze last N session files (default: 3) |
| `--since YYYY-MM-DD` | Analyze sessions since date |

**Examples:**
- `/friction --help` - show this help
- `/friction` - analyze last 3 session transcripts
- `/friction --sessions 5` - analyze last 5 sessions
- `/friction --since 2026-01-05` - analyze sessions since Jan 5

**What it does:**
1. Searches Claude Code's verbatim session transcripts (NOT agent-written summaries)
2. Finds tool calls that resulted in errors or permission prompts
3. Categorizes findings (MISSING, MSYS, PATTERN, ENV_PREFIX, DENIED)
4. Generates remediation plan with specific settings.local.json changes

**Time:** ~15-30 minutes depending on scope

---

## Project Detection

Detect the current project from working directory:
- Extract project name from path (e.g., `/c/Users/mcwiz/Projects/Aletheia` → `Aletheia`)
- Session transcripts are at: `~/.claude/projects/C--Users-mcwiz-Projects-{PROJECT}/*.jsonl`

---

## Execution

Analyze Claude Code session transcripts to find commands that caused friction.

**Ref:** `AssemblyZero:audits/permission-friction`

---

## CRITICAL: Permission-Safe Execution

This skill MUST NOT trigger permission prompts itself. Use ONLY these tools:

| Tool | Why Safe |
|------|----------|
| **Glob** | No path restrictions |
| **Grep** | No path restrictions, uses ripgrep |
| **Read** | System allows reading .claude paths |

**DO NOT USE:**
- Complex Bash pipelines with `|` or `&&`
- `python` or `python3` directly (use poetry run)
- `jq` with pipes

---

## Procedure

### Step 1: List Available Session Transcripts

Use Glob to find session files:
```
Glob pattern: *.jsonl
Path: C:\Users\mcwiz\.claude\projects\C--Users-mcwiz-Projects-{PROJECT}
```

This returns all session transcript files. Sort by modification time (most recent first).

### Step 2: Pre-Filter Sessions (COST OPTIMIZATION)

**Before reading full files, use Grep to identify which sessions have friction.**

Run these Grep patterns across all candidate session files:
```
Grep pattern: "Exit code [1-9]"
Grep pattern: "Permission denied"
Grep pattern: "not allowed"
```

This produces a list of files that contain friction. Only proceed with files that have matches.

**Why:** Session transcripts can be 100KB+. Pre-filtering with Grep (fast, no token cost) eliminates sessions with no friction before expensive file reads.

### Step 3: Identify Sessions to Analyze

Based on arguments AND pre-filter results:
- Default: Last 3 `.jsonl` files **with friction matches** by modification time (exclude `agent-*.jsonl`)
- `--sessions N`: Last N files **with friction matches**
- `--since YYYY-MM-DD`: Files modified after that date **with friction matches**

**Filter out subagent files:** Skip files matching `agent-*.jsonl` (these are subagent transcripts, not main sessions).

**If no sessions have friction matches:** Report "No friction found in recent sessions" and exit early.

### Step 4: Search for Friction Patterns

For each session file, use **Grep** to search for friction indicators:

**Error patterns (in tool results):**
```
Grep pattern: "error".*"Exit code
Grep pattern: "Permission denied"
Grep pattern: "not allowed"
Grep pattern: "requires approval"
```

**MSYS path issues:**
```
Grep pattern: MSYS_NO_PATHCONV
Grep pattern: C:/Program Files/Git
Grep pattern: path conversion
```

**Command structure issues:**
```
Grep pattern: "cd.*&&"
Grep pattern: "\\|"  (pipe in command)
```

**Permission blocks:**
```
Grep pattern: "deny"
Grep pattern: "blocked"
```

### Step 5: Read Current Permissions

Use Read tool on settings.local.json:
```
Read: C:\Users\mcwiz\Projects\{PROJECT}\.claude\settings.local.json
```

### Step 6: Analyze and Categorize

For each friction instance found, classify:

| Category | Description | Remediation |
|----------|-------------|-------------|
| **MISSING** | Command not in allowlist | Add `Bash(cmd:*)` to allow |
| **MSYS** | Windows path conversion | Add `MSYS_NO_PATHCONV=1` prefix |
| **PATTERN** | Command structure blocked | Change to allowed pattern (e.g., `git -C` instead of `cd && git`) |
| **ENV_PREFIX** | Env var prefix not allowed | Add `Bash(VAR=val cmd:*)` |
| **DENIED** | Intentionally blocked | Document why, no action needed |

### Step 7: Generate Report

Output format:

```markdown
## Permission Friction Analysis - YYYY-MM-DD

**Project:** {PROJECT}
**Scope:** Analyzed N session transcripts from [date range]
**Location:** ~/.claude/projects/C--Users-mcwiz-Projects-{PROJECT}/

### Findings Summary

| Category | Count | Priority |
|----------|-------|----------|
| MISSING | N | HIGH/MED/LOW |
| MSYS | N | ... |
| PATTERN | N | ... |
| DENIED | N | ... |

### Detailed Findings

#### [Category]: [Command Pattern]
- **Session:** [filename] @ [timestamp]
- **Context:** [what was being attempted]
- **Error:** [exact error message]
- **Remediation:** [specific fix]

### Remediation Actions

#### Add to settings.local.json allow list:
```json
"Bash(new-pattern:*)",
```

#### Update CLAUDE.md:
- [Any workflow changes needed]

#### No Action (Intentionally Blocked):
- [Patterns that should remain blocked]
```

---

## JSONL Structure Reference

Session transcripts are JSONL (one JSON object per line):

```jsonl
{"type":"user","message":{"content":"..."}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"..."}}]}}
{"type":"tool_result","result":"..."}  // <-- Look for errors here
```

**Key fields to examine:**
- `type: "tool_result"` - Contains command outcomes
- `message.content[].type: "tool_use"` - Contains the command attempted
- `error` or `Exit code 1` in results - Indicates friction

---

## Rules

- **Use allowed tools only** - See "Permission-Safe Execution" above
- **Evidence-based** - Only report friction actually found in transcripts
- **Actionable output** - Every finding must have a specific remediation
- **Ask before applying** - Do NOT modify settings.local.json without user approval
- **One command per Bash call** - No pipes or chains

---

## Quick Reference: Common Remediations

| Friction Type | Fix |
|--------------|-----|
| AWS path mangling | Prefix with `MSYS_NO_PATHCONV=1` |
| `cd /path && git` | Use `git -C /path` instead |
| Tool not allowed | Add `Bash(tool-name:*)` to allow |
| Env prefix blocked | Add `Bash(VAR=value cmd:*)` |
| Python blocked | Use `poetry run python` instead |
