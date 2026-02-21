---
description: Save operational state to survive context compaction
argument-hint: ""
---

# Checkpoint

**Model hints:** Can use **Haiku** — purely mechanical state gathering.

Save current operational state to `.claude/checkpoint.json` so it survives context compaction.

## When to Use

- Before a long operation that might trigger compaction
- When context is getting large (many tool calls, large file reads)
- Before switching tasks within the same session

## Execution

### Step 1: Gather State

Analyze the current conversation and determine:

1. **Task** — What are you currently working on? (1-2 sentences)
2. **Approach** — What strategy are you following? (1-2 sentences)
3. **Pending decisions** — Any open questions or choices not yet made? (list)
4. **Files in progress** — Which files have you been reading or editing? (list of paths)
5. **Context notes** — Any other relevant state (branch name, issue number, error encountered, etc.)

### Step 2: Write Checkpoint

Use the Write tool to save `.claude/checkpoint.json` at the project root:

```json
{
  "timestamp": "ISO 8601 timestamp",
  "task": "description of current work",
  "approach": "current strategy",
  "pending_decisions": ["list of open questions"],
  "files_in_progress": ["list of file paths"],
  "context_notes": "any other relevant state"
}
```

**Path:** Write to the project root, e.g., `C:\Users\mcwiz\Projects\{PROJECT}\. claude\checkpoint.json`

### Step 3: Confirm

Report to the user:

```
Checkpoint saved. If context compaction occurs, I'll recover from .claude/checkpoint.json.
```

## Recovery

Recovery is automatic — MEMORY.md (always loaded) instructs the agent to check for
`.claude/checkpoint.json` on startup. When found:

1. Read the checkpoint file
2. Resume with the saved context
3. Delete the checkpoint file (one-shot, prevents stale state)
