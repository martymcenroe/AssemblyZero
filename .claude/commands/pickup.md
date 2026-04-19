---
description: Import the last handoff context from the previous session
argument-hint: "[--help]"
scope: global
---

# Pickup

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

## Help

```
/pickup - Import context from the last /handoff into this session

Usage: `/pickup`

Reads the most recent entry from data/handoff-log.md in the current repo,
shows a preview with age, and imports the context on confirmation.

Pair with /handoff: old session runs /handoff → new session runs /pickup.
```

## Why This Exists

`/handoff` persists a structured context transfer to `data/handoff-log.md`. This command reads it back so the new session starts with full context instead of cold-starting from CLAUDE.md alone.

**Prefer `/onboard`** which includes smart pickup detection (auto-pickup for fresh handoffs, thrashing detection, crash recovery). Direct `/pickup` skips detection and goes straight to import.

## Execution

**Note:** CLAUDE.md (root + repo) and MEMORY.md are auto-injected by Claude Code at session start. Do NOT re-read them.

### Step 1: Locate the Handoff Log

1. Run `git rev-parse --show-toplevel` to find the repo root.
2. Check if `{repo_root}/data/handoff-log.md` exists.
3. If not found, tell the user: "No handoff log found at `{repo_root}/data/handoff-log.md`. Run `/handoff` in the previous session first." and STOP.

### Step 2: Extract the Last Entry

1. Read `data/handoff-log.md`.
2. Find the LAST occurrence of `<!-- handoff-start -->` and its matching `<!-- handoff-end -->`.
3. Extract the content between these markers — this is the handoff prompt.
4. Extract the timestamp from the `## Handoff — YYYY-MM-DD HH:MM:SS` header immediately above the start marker.

### Step 3: Show Preview and Age

1. Calculate the age of the handoff (current LOCAL time minus the timestamp). Handoff timestamps are local time -- do NOT use UTC. Use `date +"%Y-%m-%d %H:%M:%S"` (no `-u` flag).
2. Format age as human-readable: "2 minutes ago", "3 hours ago", "2 days ago".
3. Check `data/session-index.jsonl` for sessions that started AFTER the handoff timestamp. For each, note the start time, line count, and duration. Sum the totals.
4. Show the user:

```
Handoff found -- {YYYY-MM-DD HH:MM:SS} ({age})

Preview (first 5 lines):
> {line 1}
> {line 2}
> {line 3}
> {line 4}
> {line 5}
```

5. If post-handoff sessions exist, show: "Note: {N} session(s) ran after this handoff ({total_lines} lines, {total_hours}h). This handoff may not reflect the latest state."
6. If the handoff is older than 48 hours, add a warning: "This handoff is {age} old. The codebase may have changed significantly since then."

### Step 4: Confirm Import

Ask the user: "Import this handoff? (Y/n)"

- If declined, say "Pickup cancelled." and STOP.
- If confirmed, proceed to Step 5.

### Step 5: Import Context

1. Internalize the full handoff prompt as your working context.
2. **Parse the plan-state block (deterministic).** If the handoff contains a `<!-- plan-state-start -->` / `<!-- plan-state-end -->` block, read the YAML inside. Apply this decision logic:
   - `plan_state: completed` → Tell user: "Previous plan `{plan_slug}` was completed (archived at `{archive_path}`). Starting fresh." Do NOT read the plan file.
   - `plan_state: active` with `remaining_steps > 0` → Tell user: "Resuming plan `{plan_slug}`: {completed_steps}/{total_steps} steps done." Read `{plan_path}` and treat it as the active plan for this session.
   - `plan_path` is set but the file is missing → Fall back to `{archive_path}`. Warn user: "Live plan missing, reading archived copy instead."
   - No plan-state block, or `plan_state: none` → Continue without a plan.
3. Read every file listed in the "Files to Read First" section of the handoff. Actually read them — don't just note the paths.
4. Summarize what you imported:
   - What was accomplished in the previous session
   - What the next steps are
   - How many files you read from the "Files to Read First" list
   - Whether a plan was resumed, started fresh, or absent
5. **Write the pickup marker** by running: `poetry run python C:/Users/mcwiz/Projects/unleashed/src/pickup_marker.py --repo {repo_root}`
   If it fails, report the error to the user. Do NOT proceed silently.

Tell the user: "Pickup complete. Ready to continue where the last session left off."

## Rules

- **Append-only** -- never delete or rewrite entries in `data/handoff-log.md`. The pickup marker is written by `pickup_marker.py` (Step 5.5), not by the agent directly.
- **Always show age** — the user needs to know how stale the context is.
- **Always ask before importing** — don't silently load context.
- **Actually read the files** — the "Files to Read First" section exists so the agent gets grounded in current code, not just the handoff narrative.
