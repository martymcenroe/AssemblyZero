# Implementation Report — The babysit protocol stops prescribing echo and /tmp (#3514)

Backfilled 2026-09-25 after the merge, from PR #3524 (merge `2aff6442`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502, stage 2. Docs only; no code.

## What was wrong

`docs/babysit-protocol.md` told the agent to launch with `echo "PID: $!"` and to redirect under `/tmp`, both of which the fleet's shell guard denies and the universal rules ban.

## What changed

The two hard rules say what the guard accepts: redirect to the target repo's `data/` directory, launch with the Bash tool's `run_in_background`, and monitor by reading the run's own record (the `[run] <tag> -> <path>` first line and the `-events.log` beside it, from #3503). The three pipeline commands redirect to the target's `data/` instead of `/tmp`.

## Files

`docs/babysit-protocol.md`.
