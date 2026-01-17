# Implementation Report: Add --no-tools flag to gemini-retry.py

**Issue:** Gemini's agentic mode searches files during reviews, ignoring prompt content
**Branch:** gemini-notools-flag
**Date:** 2026-01-17
**Author:** Claude Agent

## Summary

Added `--no-tools` flag to gemini-retry.py that passes `--sandbox false` to the gemini CLI, disabling agentic tool usage (file search, code execution) during reviews.

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tools/gemini-retry.py` | Modified | Added --no-tools argument and plumbing |

## Design Decisions

### Decision 1: Use `--sandbox false` flag
**Context:** Need to disable Gemini's agentic file searching during reviews
**Decision:** Pass `--sandbox false` to gemini CLI when `--no-tools` is specified
**Rationale:** Testing showed this prevents Gemini from using tools to search files

### Decision 2: Make flag optional (default: tools enabled)
**Context:** Some use cases may benefit from agentic behavior
**Decision:** `--no-tools` is opt-in, tools enabled by default
**Rationale:** Backward compatibility; only reviews need tools disabled

### Decision 3: Propagate through all functions
**Context:** Flag needs to reach invoke_gemini() from main()
**Decision:** Added `no_tools` parameter to retry_gemini() and invoke_gemini()
**Rationale:** Clean parameter passing through the call chain

## Implementation Details

### Changes to invoke_gemini()
- Added `no_tools: bool = False` parameter
- When True, appends `["--sandbox", "false"]` to command

### Changes to retry_gemini()
- Added `no_tools: bool = False` parameter
- Passes to invoke_gemini()
- Logs no_tools status

### Changes to main()
- Added `--no-tools` argument with store_true action
- Passes `args.no_tools` to retry_gemini()
- Updated help text and examples

## Known Limitations

- `--sandbox false` may affect more than just tool usage
- Long prompts via `-p` flag may still have issues (separate from this fix)
- Credential rotation (gemini-rotate.py) does not support --no-tools yet

## Testing Summary

- Verified `--help` shows new flag
- Tested simple prompt with `--no-tools`: Direct response (no file search)
- Tested review prompt with `--no-tools`: No file searching observed

## Verification Checklist

- [x] Flag appears in --help output
- [x] Flag is passed through to invoke_gemini()
- [x] Testing shows reduced agentic behavior
- [x] Backward compatible (default is tools enabled)
