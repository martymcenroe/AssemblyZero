# Implementation Report — Derive the Projects root from the checkout instead of spelling it (#3536)

Backfilled 2026-09-25 after the merge, from PR #3544 (merge `888d759d`) and its body (#3559). This PR was landed by a different session from the #3502 pass; it is on the same repository and the same gate missed it. No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

## What changed

- `tools/assemblyzero_config.py`: `DEFAULTS` is derived from where the checkout sits instead of spelled as `C:\Users\mcwiz\...` and `/c/Users/mcwiz/...`. `_spellings()` gives a real path in both formats: a Windows drive path gets its Git Bash twin, a `/mnt/<d>/` path gets its drive twin, and an ext4 path is the same POSIX path in both. Under WSL the old `unix` default pointed at a directory that does not exist. `~/.assemblyzero/config.json` still overrides every value, and on the Windows machine the derived values equal the old ones.
- Nine tools that spelled the Projects root or a file under it derive it from `Path(__file__)` (and `batch-workflow.sh` from `BASH_SOURCE`).
- The no-config fallbacks in `assemblyzero-permissions.py` and `assemblyzero-harvest.py` give the `/c/...` spelling for a drive path, matching `projects_root_unix()`, so their patterns keep matching.

## Files

`tests/unit/test_assemblyzero_config_derived.py`, `tools/append_session_log.py`, `tools/assemblyzero-harvest.py`, `tools/assemblyzero-permissions.py`, `tools/assemblyzero_config.py`, `tools/audit_fully_landed.py`, `tools/audit_gitignore_drift.py`, `tools/backfill_assemblyzero_flag.py`, `tools/banned_command_sweep.py`, `tools/batch-workflow.sh`, `tools/dependabot_morning_status.py`.
