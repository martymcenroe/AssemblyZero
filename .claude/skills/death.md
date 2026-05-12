---
description: Reconcile documentation with reality
scope: project
---

# /death — The Hourglass Protocol

DEATH arrives when the documentation no longer describes reality.
Two modes. One purpose: reconciliation.

## Usage

/death [report|reaper] [--force]

- **report** (default): Walk the field. Produce a reconciliation report. Change nothing.
- **reaper**: Walk the field. Fix everything. Requires confirmation before writes.
- **--force**: Skip confirmation gate (reaper mode only, for scripted usage).

## What DEATH Does

1. **Walk the Field** — Spelunk the codebase. Compare docs against code reality.
2. **Harvest** — Write the ADRs that capture what was decided (produces 0015-age-transition-protocol.md).
3. **Archive** — Move old age artifacts to legacy.
4. **Chronicle** — Update README and wiki to describe the civilization as it now exists.
5. **Rest** — DEATH departs. The new age begins with clean documentation.

## Example

```
/death report    # See what's stale
/death reaper    # Fix it all (with confirmation)
/death reaper --force  # Fix it all (no confirmation, scripted)
```

> WHAT CAN THE HARVEST HOPE FOR, IF NOT FOR THE CARE OF THE REAPER MAN?