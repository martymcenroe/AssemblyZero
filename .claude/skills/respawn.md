---
description: Same-window relaunch — capture handoff state, signal wrapper to re-spawn this slot
argument-hint: "[--help]"
scope: global
---

# Respawn

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

## Help

```
/respawn - Same-window relaunch (vs. /handoff which opens a new window)

Usage: `/respawn`

Captures session state via the /handoff mechanism, then signals the
running unleashed wrapper to relaunch fresh in the SAME window slot.
The new wrapper auto-onboards and picks up the just-written handoff.

Use when:
- You need a fresh Claude Code process (cached skill, weird state, new
  wrapper version, etc.) but can't afford a new window
- /handoff would open a new tab that obscures this one
- Companion tabs (Mirror/Friction/Console) get reset along with Claude

If you want a new window instead: use /handoff.
If you want to end the session without relaunch: use /handoff --park or /exit.
```

## Execution

**Do NOT delegate to a subagent.** The handoff state-capture needs the current
session's context (memory, lessons, decisions).

### Step 1: Run the handoff state capture

Execute `/handoff`'s Steps 0 through 5C, with TWO overrides:

1. **Close-state marker** (Step 5.8 in `handoff.md`): pass `--marker respawn`
   instead of `handoff`/`park`/`reboot-parked`. This is what panopticon and
   `pickup_decide.py` use to distinguish a respawn from a normal handoff.

   ```bash
   poetry run python /c/Users/mcwiz/Projects/unleashed/src/handoff_marker.py --repo-root {REPO_ROOT} --marker respawn
   ```

2. **Skip Step 6 (spawn).** Do NOT call `handoff_spawn.py`. The wrapper handles
   the relaunch itself when it sees the respawn sentinel (next step).

All other handoff steps — git status gather, plan archive, lessons-learned
append, session log append, skill_sync (if AZ) — run normally. The persisted
handoff is what the new session's auto-onboard will pick up.

### Step 2: Write the respawn sentinel

```bash
poetry run python /c/Users/mcwiz/Projects/unleashed/src/respawn_request.py --cwd {REPO_ROOT}
```

This writes `~/.unleashed/respawn-pending-{slug}` where the slug is derived from
the cwd. The running wrapper's `_respawn_watcher` thread polls every 2s and will
detect this sentinel within ~2s of it appearing.

The sentinel has a 5-minute TTL on the wrapper side, so if the user never types
`/exit` after this skill runs, the sentinel ages out and is removed without
firing — no surprise respawn hours later.

### Step 3: Tell the user to exit

Output to the user:

```
Respawn requested. Type /exit (or Ctrl+D) when ready.

The wrapper will detect the sentinel within 2s of Claude exiting, close
companion tabs, and launch a new wt.exe window with fresh unleashed-alpha.
New session will auto-onboard from this handoff.

Sentinel TTL: 5 minutes. If you don't /exit within 5 min the sentinel
ages out and the next /exit becomes a normal session-end.
```

### Step 4: STOP

Do not call /handoff's Step 6 spawn under any circumstances. Do not call any
companion-tab cleanup script (the wrapper handles companions on exit). Do not
prompt the user further — the next user action is `/exit`.

## Rules

- The respawn marker (Step 1 override) must be exactly `respawn`. Other values
  break panopticon's intent classification.
- If `respawn_request.py` exits non-zero, surface the error and DO NOT instruct
  the user to /exit — without a sentinel the wrapper won't relaunch, and the
  user would just be ending their session.
- Don't bundle other work into a /respawn. The user invoked it to fast-cycle;
  side work belongs in /handoff.
