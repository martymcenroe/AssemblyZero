---
description: Agent onboarding (quick/full mode, smart pickup detection)
argument-hint: "[--help] [--refresh | --quick | --full] [--pickup]"
---

# Agent Onboarding

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP. Do not execute onboarding.

Onboard yourself to the current project. Detects whether a recent handoff exists and offers pickup automatically.

## Help

```
/onboard - Agent onboarding for current project

Usage: `/onboard [--help] [--refresh | --quick | --full] [--pickup]`

Options:
| Flag | Effect |
|------|--------|
| `--help` | Show this help message and exit |
| `--refresh` | Reload rules only — for post-compact/resumed sessions |
| `--quick` | Config + session log + issues — for simple tasks |
| `--full` | Full onboarding with pickup detection (default) |
| `--pickup` | Skip detection, go straight to pickup import |

Examples:
- `/onboard` - full onboard with smart pickup detection
- `/onboard --pickup` - skip detection, import last handoff immediately
- `/onboard --refresh` - reload rules after context compaction
- `/onboard --quick` - quick onboard for status check
```

## Important: What Is Already In Context

CLAUDE.md (root + repo) and MEMORY.md (index) are auto-injected by Claude Code at session start. **Do NOT re-read them.** Individual memory files are loaded on demand when relevant — do not bulk-read them during onboard.

## Step 0: Project Detection and Config

1. Get working directory and extract project name from path
2. Project root (Windows): `C:\Users\mcwiz\Projects\{PROJECT}`
3. Project root (Unix): `/c/Users/mcwiz/Projects/{PROJECT}`
4. Read `{repo_root}/.unleashed.json` (if exists). Extract:
   - `assemblyZero` (bool, default false) — whether to read AssemblyZero rules
   - `onboard.pickupThresholdMinutes` (int, default 10) — age below which auto-pickup fires
   - `onboard.guide` (string or null) — path to project guide doc
   - `onboard.plan` (string or null) — path to immediate plan doc
5. Get GitHub repo: `git -C {unix_root} remote get-url origin` and extract `{owner}/{repo}`

## Modes

| Mode | Use Case |
|------|----------|
| `--refresh` | Post-compact, resumed sessions, rule reload |
| `--quick` | Simple tasks, status checks |
| `--full` (default) | Complex work, session start, pickup detection |

---

## Refresh Mode (`--refresh`)

**Purpose:** Reload rules after context compaction. Does NOT re-read project state or session logs.

**Steps (parallel reads):**

1. Read project config (Step 0 above)
2. IF `assemblyZero == true`:
   - Read `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md`
   - Read `C:\Users\mcwiz\Projects\AssemblyZero\docs\prompts\gemini-rotation-instructions.md`

**Report:**
```
Rules refreshed for {PROJECT}
Model: {model} | Effort: {effort} | Window: {window}
Ready to continue.
```

---

## Quick Mode (`--quick`)

Read config + most recent session log + open issues. No pickup detection.

1. Read project config (Step 0)
2. IF `onboard.guide` is set: read `{repo_root}/{guide}`
3. Glob `docs/session-logs/*.md`, read the most recent file
4. `gh issue list --state open --limit 10 --repo {owner}/{repo}`
5. Report (same format as full mode, abbreviated)

---

## Full Mode (`--full` or no argument)

### Step 1: Pickup Detection

**IF `--pickup` flag is set:** Skip detection. Go directly to Step 1C (import).

**OTHERWISE:**

**A) Check handoff log:**
1. Check if `{repo_root}/data/handoff-log.md` exists
2. If exists, find the LAST `<!-- handoff-start -->` / `<!-- handoff-end -->` pair
3. Extract timestamp from `## Handoff — YYYY-MM-DD HH:MM:SS` header above start marker
4. Calculate age: current LOCAL time minus handoff timestamp (no UTC — use `date +"%Y-%m-%d %H:%M:%S"`)

**B) Check session index (if exists):**
1. Read `{repo_root}/data/session-index.jsonl`
2. Parse last 5 entries (each is one JSON object per line)
3. Check for thrashing and crash patterns (see below)
4. Count sessions that started AFTER the handoff timestamp (post-handoff activity)

**C) Apply decision logic:**

| Condition | Action |
|-----------|--------|
| `--pickup` flag set | Auto-pickup, no confirmation |
| Handoff age < threshold (default 10 min) | Auto-pickup, no confirmation |
| Handoff age 10 min - 48h | Show timestamp + age + post-handoff sessions, ask user to confirm |
| Handoff age > 48h or no handoff | Skip pickup, proceed to Step 2 |
| THRASHING detected | Skip pickup, report thrashing, find last substantive session |
| CRASH detected | Report crash, offer session log as partial context |

**Post-handoff activity display (10 min - 48h case):**
Always show the absolute timestamp: "Handoff from YYYY-MM-DD HH:MM:SS ({age})".
If post-handoff sessions exist, show: "Note: {N} session(s) ran after this handoff ({total_lines} lines, {total_hours}h)."

**Thrashing detection:**
- From session-index.jsonl, check if 3+ entries have start timestamps within a 30-minute window AND each has `line_count < 50`
- If detected: "Detected {N} brief sessions in last 30 min — resume thrashing or recovery. Last substantive session: {timestamp} ({duration}). Skipping pickup."
- Find the most recent entry with `line_count >= 50` for context reference

**Crash detection:**
- Last session-index entry has `line_count >= 50` (substantive work happened)
- No handoff-log entry exists with a timestamp after that session's start time
- If detected: "Last session ({start}, {duration}) ended without handoff — possible crash or manual close. Session log may have partial context."

**Pickup import (when triggered):**
1. Extract full content between `<!-- handoff-start -->` and `<!-- handoff-end -->`
2. Internalize as working context
3. Read every file listed in the "Files to Read First" section
4. Report: "Picked up handoff from {age}. {N} files read."

### Step 2: Project Context

**IF pickup was imported:** Skip session log reads (handoff has the context). Still read open issues.

**IF `assemblyZero == true` (from config):**
- Read `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md`
- Read `C:\Users\mcwiz\Projects\AssemblyZero\docs\prompts\gemini-rotation-instructions.md`

**IF `onboard.guide` is set:** Read `{repo_root}/{onboard.guide}`

**IF `onboard.plan` is set:** Read `{repo_root}/{onboard.plan}`

**IF pickup was NOT imported:**
- Glob `docs/session-logs/*.md`, read the most recent file

**Always:** `gh issue list --state open --limit 10 --repo {owner}/{repo}`

### Step 3: Report

```
Project: {name}
Type: {from CLAUDE.md description — already in context}
Focus: {from plan doc, handoff, or session log}
Top 3 issues: {from gh issue list}
Model: {from system prompt} | Effort: {from config or "default"} | Window: {model window}
```

IF pickup was imported:
  "Picked up handoff from {age}. Ready to continue."
ELSE:
  "Onboarded fresh. Ready."

Then ask: "What do you want to work on next?"

---

## Rules

- Use absolute paths and `git -C` patterns (no cd && chaining)
- Use `--repo {owner}/{repo}` for all gh commands
- CLAUDE.md and MEMORY.md are already in context — never re-read them
- `data/handoff-log.md` is append-only -- never delete or rewrite entries. Pickup markers (`<!-- picked-up ... -->`) may be appended after `<!-- handoff-end -->`
- `data/session-index.jsonl` is read-only — never modify it
- If no `.unleashed.json` exists, use defaults: `assemblyZero=false`, `pickupThreshold=10`, no guide, no plan
