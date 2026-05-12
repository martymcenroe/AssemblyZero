---
description: Park the session for deliberate pickup later (alias for /handoff --park)
argument-hint: "[--help]"
scope: global
---

# Park

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP.

## Help

```
/park - Generate a handoff AND mark this session as deliberately parked

Usage: `/park`

What it does:
- Runs the full /handoff machinery (state capture, lessons, hygiene, log append).
- Writes a `<!-- park YYYY-MM-DD HH:MM:SS -->` close-state marker after the
  handoff entry in data/handoff-log.md.
- DOES NOT spawn a new wt window. /park is for "I'm done for now, will resume
  later" — distinct from plain /handoff which spawns a fresh session for
  "context window filling up" mid-work.
- Surfaces in panopticon's Exit column as `park` (distinct from `exit`,
  `handoff`, `reboot-parked`, `away`, `null`) so future-you can see at a
  glance "I deliberately parked this one — pick it up next time."

Equivalent to: `/handoff --park`. /park exists as a shorter, more
intention-revealing alias.

After /park, run `/exit` to close the session. `/onboard` against this
repo next time will detect the unconsumed handoff and pick it up.
```

## Execution

Invoke the `/handoff` skill with the `--park` argument. All of /handoff's
behavior applies — state gathering, lessons-learned capture, hygiene
report, log persistence, plan archive — plus the park marker written in
Step 5.8 by `handoff_marker.py`. Step 6 (spawn) is skipped per the
`--park` clause; the user closes via `/exit` when ready.

The user's intent here is unambiguous: they typed /park because they're
done for now and want this session to surface as the resume target next
time. Don't second-guess that intent. Don't suggest /handoff (without
--park) as an alternative — they already chose the parking variant.
