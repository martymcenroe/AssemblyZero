---
repo: martymcenroe/AssemblyZero
issue: 611
url: https://github.com/martymcenroe/AssemblyZero/issues/611
fetched: 2026-03-06T05:55:13.239100Z
---

# Issue #611: fix: shell.py command middleware is dead code — no workflow nodes use it (#598/#601 follow-up)

## Problem

PRs #604 (#598) and #602 (#601) created `assemblyzero/utils/shell.py` with:
- `validate_command()` — blocks dangerous flags (`--admin`, `--force`, `-D`, `--hard`)
- `run_command()` — wraps `subprocess.run()` with bash detection + command validation
- `wrap_bash_if_needed()` — auto-wraps commands in `bash -c` on Windows

**None of these are used by any workflow node.** There are ~50 direct `subprocess.run()` calls across the codebase that bypass the middleware entirely. The security firewall exists but has no walls.

## Acceptance Criteria

- All `subprocess.run()` calls in workflow nodes (`assemblyzero/workflows/`) are migrated to use `run_command()` from `shell.py`
- Or: a clear architectural decision is made about which calls should and shouldn't go through the middleware, documented in the module

## Additional Issues in shell.py

- `validate_command()` raises `ValueError` but #598 spec requires `SecurityException`
- Unused `shlex` import on line 7
- Naive substring matching for flags (e.g., `-D` matches inside `-Docs`, `--hard` matches `--hard-wrap`)

## Origin

Discovered during post-merge review of Gemini's last 10 closed issues.