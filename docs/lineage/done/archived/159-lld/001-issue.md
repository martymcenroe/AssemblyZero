# Issue #159: fix: Unicode encoding error in workflow output on Windows

## Problem

The requirements workflow crashes with a Unicode encoding error when outputting characters like `â†’` (arrow) to the Windows console.

**Error:**
```
ERROR: 'charmap' codec can't encode character '\u2192' in position 13: character maps to <undefined>
```

This happens frequently at the end of workflows, causing exit code 1 even when the actual work completed successfully.

## Context

- Occurs on Windows with Git Bash / MINGW
- The workflow completes its actual work (LLD generation, Gemini review) but crashes when trying to print results
- Characters like `â†’`, `âœ“`, `âœ—`, and other Unicode symbols trigger the error

## Likely Cause

Python's default stdout encoding on Windows uses `cp1252` (Windows-1252) which doesn't support many Unicode characters. When the workflow tries to print Unicode characters, the codec fails.

## Potential Fixes

1. **Force UTF-8 encoding** - Set `PYTHONIOENCODING=utf-8` environment variable
2. **Replace Unicode characters** - Use ASCII alternatives in output (`->` instead of `â†’`)
3. **Encode with replacement** - Use `errors='replace'` or `errors='ignore'` when writing to stdout
4. **Wrap stdout** - Replace `sys.stdout` with a UTF-8 encoded wrapper at startup

## Affected Areas

- `tools/run_requirements_workflow.py` - workflow runner output
- Any code that prints Unicode characters to console on Windows

## Workaround

Set environment variable before running:
```bash
export PYTHONIOENCODING=utf-8
```

## Labels
bug, windows