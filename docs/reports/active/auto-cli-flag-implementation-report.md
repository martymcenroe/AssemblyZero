# Implementation Report: --auto CLI Flag

**Branch:** `auto-cli-flag`
**Date:** 2026-01-28

## Summary

Added `--auto` CLI flag to `run_issue_workflow.py` that enables unattended workflow execution by:
- Skipping VS Code during draft review
- Auto-sending drafts to Gemini for review
- Opening the done/ folder at the end for batch review

## Files Changed

| File | Change |
|------|--------|
| `tools/run_issue_workflow.py` | Added `--auto` argument, sets `AGENTOS_AUTO_MODE=1` env var |
| `assemblyzero/workflows/issue/nodes/human_edit_draft.py` | Check `AGENTOS_AUTO_MODE` to skip VS Code (line 209) and auto-send to Gemini (line 144) |
| `assemblyzero/workflows/issue/nodes/human_edit_verdict.py` | Check `AGENTOS_AUTO_MODE` to skip VS Code preview (line 253) |
| `assemblyzero/workflows/issue/nodes/file_issue.py` | Check `AGENTOS_AUTO_MODE` to open done/ folder at end (line 375) |

## Design Decisions

1. **Environment variable approach**: Used `AGENTOS_AUTO_MODE` env var rather than passing flag through state, keeping the change minimal and consistent with existing `AGENTOS_TEST_MODE` pattern.

2. **TEST_MODE priority**: When both `AGENTOS_TEST_MODE` and `AGENTOS_AUTO_MODE` are set, TEST_MODE takes priority. This is intentional - test mode is for automated testing and should behave predictably.

3. **VS Code skip with done/ folder open**: Instead of opening VS Code for each draft iteration, the entire done/ folder is opened at the end. This allows batch review of all artifacts after the workflow completes.

## Usage

```bash
# Run with auto mode
poetry run python tools/run_issue_workflow.py --select --auto

# Combine with brief
poetry run python tools/run_issue_workflow.py --brief my-idea.md --auto
```

## Known Limitations

- Auto mode still requires interactive idea selection unless combined with `AGENTOS_TEST_MODE`
- No timeout mechanism if Gemini review takes too long
- Done folder only opens if workflow completes successfully (issue is filed)
