REVIEW THE FOLLOWING GITHUB ISSUE ONLY. DO NOT SEARCH FOR OTHER FILES.

# Issue #36: fix(sentinel): API key isolation causes silent hang

## Problem

When running `sentinel-test`, modifying the environment with `os.environ.pop("ANTHROPIC_API_KEY", None)` causes the script to hang silently before any output.

## Goal

- API key should be used by Haiku gating (litellm calls)
- API key should NOT be inherited by Claude CLI (so Claude uses subscription, not API)

## What Was Tried

1. **`dotenv_values()` instead of `load_dotenv()`** - Hangs silently
2. **`os.environ.pop()` after `load_dotenv()`** - Hangs silently
3. **Passing `env=` parameter to `winpty.PtyProcess.spawn()`** - Hangs silently

## Current State

- `sentinel` works (uses load_dotenv, keeps API key in env)
- `sentinel-test` reset to exact copy of `sentinel.py` (works)
- User selects "No" at Claude CLI API key prompt as workaround

## Acceptance Criteria

- [ ] `sentinel-test` launches without hanging
- [ ] Claude CLI does not inherit `ANTHROPIC_API_KEY`
- [ ] Haiku gating still works via litellm

## Notes

The hang occurs before any Python print statements execute, suggesting the issue is at import time or very early in module loading. Poetry with `--directory` flag may be relevant.

---

END OF ISSUE.

Please review this GitHub issue for:
1. Clarity - Is the problem statement clear?
2. Completeness - Is enough context provided to debug?
3. Accuracy - Are there any technical errors in the description?
4. Missing information - What else should be included?

Respond with JSON only:
{
  "verdict": "APPROVE" or "BLOCK",
  "issues": ["list of issues if BLOCK"],
  "suggestions": ["optional improvements"],
  "summary": "brief assessment"
}
