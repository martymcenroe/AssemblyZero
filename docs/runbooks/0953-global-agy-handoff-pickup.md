# Runbook: Global AGY Handoff & Pickup

## Purpose
This runbook documents the global machine-local skill pattern used across the fleet of 89 repositories to standardize session wrap-up and resumption in Antigravity (AGY).

By implementing these two skills in `~/.gemini/config/skills/`, every single repository on the machine instantly inherits the ability to close out state gracefully, and catch up seamlessly. This replaces the complex and brittle `/cleanup` template command and ensures that Claude Code can still read the repository state if the operator switches agent clients.

## The Skills

### 1. The Global Handoff Skill
**Location:** `~/.gemini/config/skills/handoff/SKILL.md`

**Trigger:** The operator says "handoff", "wrap up", "cleanup", or "close out".

**Execution Steps:**
1. Append to `data/handoff-log.md` with an `<!-- handoff-start -->` block detailing accomplishments, current state, and next steps.
2. Append a session summary to `docs/session-logs/YYYY-MM-DD.md`.
3. Capture new rules or patterns to `docs/lessons-learned.md`.
4. Stage only these specific tracking files.
5. Commit with `chore: session cleanup (logs)` and branch/push the cleanup artifacts.

### 2. The Global Pickup Skill
**Location:** `~/.gemini/config/skills/pickup/SKILL.md`

**Trigger:** The operator says "pickup", "catch up", "what did I miss", or "reorient".

**Execution Steps:**
1. Read the most recent entry in `data/handoff-log.md` to see the intended next steps.
2. Run `git status`, `git log -n 5`, and `gh pr list` to determine what actually occurred while the agent was inactive.
3. Reconcile the discrepancy between the handoff state and the current git reality.
4. Output a summary to the operator and propose the next logical action.

## Deployment
These skills do not need to be duplicated per-repository. Simply ensure they are present in the global config directory on the operator's machine.
