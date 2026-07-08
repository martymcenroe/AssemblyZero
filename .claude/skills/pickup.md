---
description: Import the last handoff context (thin alias for /onboard --pickup)
argument-hint: "[--help]"
scope: global
---

# Pickup

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

## Help

```
/pickup - Import context from the last /handoff into this session

Usage: `/pickup`

Thin alias for `/onboard --pickup`: skips pickup detection and imports the
last handoff from data/handoff-log.md in the current repo.

Pair with /handoff: the old session runs /handoff, the new session runs
/pickup (or /onboard, which adds smart pickup detection).
```

## This command is a thin alias for `/onboard --pickup`

All pickup logic — reading `data/handoff-log.md`, honoring the
`<!-- picked-up -->` marker, the event-ordered pickup decision (#575), the
per-file read log, the wrapped `pickup_marker.py` call, and the drift check —
lives in ONE place: the `/onboard` skill's **Step 1D — Pickup import**.
`/pickup` reimplements none of it.

Earlier, `/pickup` carried its own fork of that logic: activity-based staleness
counting from `session-index.jsonl` (one doctrine behind onboard's event-ordered
model), no `<!-- picked-up -->` check (so it could re-import a handoff a prior
session had already consumed), and an unwrapped `pickup_marker.py` call that
failed silently on non-Python repos. Collapsing to the alias removes that whole
drift class (#1696).

## Execution

Execute the `/onboard --pickup` flow: follow the **onboard** skill's
**Step 1D — Pickup import** exactly. `--pickup` means "skip detection, import the
last handoff now." That single routine:

1. Extracts the body between the last `<!-- handoff-start -->` /
   `<!-- handoff-end -->`, honoring any `<!-- picked-up -->` marker.
2. Parses the plan-state block.
3. Reads every "Files to Read First" entry and persists the per-file read log.
4. Writes the pickup marker via the
   `(cd …/unleashed && poetry run python src/pickup_marker.py --repo {repo_root})`
   wrapper.
5. Runs the drift check and reports.

Do not duplicate or paraphrase those steps here — run onboard's.

## Rules

- `/pickup` owns no pickup logic of its own. If pickup behavior must change,
  change it in `/onboard` (and `pickup_decide.py` / `pickup_marker.py`), never
  here — this file must stay a thin alias.
- `data/handoff-log.md` is append-only; the pickup marker is written by
  `pickup_marker.py`, not by the agent directly.
