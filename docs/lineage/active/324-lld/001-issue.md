---
repo: martymcenroe/AgentOS
issue: 324
url: https://github.com/martymcenroe/AgentOS/issues/324
fetched: 2026-02-05T06:03:09.735787Z
---

# Issue #324: bug: Implementation workflow fails on large file modifications (needs diff-based generation)

## Summary

The implementation workflow fails to generate complete files when the target file is large (800+ lines) because Claude's response is truncated by the `max_tokens=8192` limit.

## Observed Behavior

Running implementation for issue #309 (modify `implement_code.py`, 804 lines):

```
[N4] Implementing code file-by-file (iteration 0)...
    [1/1] agentos/workflows/testing/nodes/implement_code.py (Modify)...
        Calling Claude...
        Written: agentos/workflows/testing/nodes/implement_code.py

[N5] Verifying green phase (all tests should fail)...
    Results: 0 passed, 15 failed
    Coverage: 0.0%
```

The generated file was only **79 lines** instead of the expected **~900 lines**.

## Root Cause

In `implement_code.py` line 334:
```python
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=8192,
    messages=[{"role": "user", "content": prompt}]
)
```

- Original file: 804 lines (~25,000 chars)
- Prompt includes: LLD + existing file + test content = ~50,000 chars
- Response needed: ~25,000 chars (complete file)
- `max_tokens=8192` ≈ 32,000 chars max output

When Claude tries to regenerate the entire file, it runs out of tokens and the response is truncated mid-file.

## Impact

- Workflow iterates endlessly (tests always fail on truncated code)
- User must manually implement changes to large files
- No error message indicates the truncation

## Chosen Solution: Diff-based Generation

For "Modify" change type on large files, ask Claude to output only the changes in a structured diff format instead of regenerating the entire file.

### Approach

1. **Detect large files**: If existing file > threshold (e.g., 500 lines or 15KB), use diff mode
2. **Modified prompt**: Ask Claude to output changes as structured edits, not the full file
3. **Apply changes**: Parse the diff/edit instructions and apply them to the existing file
4. **Fallback**: For small files or "Add" type, continue using full file generation

### Output Format for Diff Mode

```
## Output Format (for Modify - Large Files)

Output ONLY the changes needed. Use this format for each change:

### CHANGE 1: [brief description]
FIND:
```python
[exact lines to find in the file]
```

REPLACE WITH:
```python
[new lines to replace them with]
```

### CHANGE 2: [brief description]
...

IMPORTANT:
- Include enough context in FIND to uniquely identify the location
- Output ALL changes needed, in order from top to bottom of file
- Do NOT output the entire file
```

### Benefits

- Response size proportional to change size, not file size
- Works for files of any size
- Existing file content is preserved (no accidental deletions)
- Each change is atomic and verifiable

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `agentos/workflows/testing/nodes/implement_code.py` | Modify | Add diff-based prompt for large Modify files |
| `agentos/workflows/testing/nodes/implement_code.py` | Modify | Add `apply_diff_changes()` function to parse and apply edits |
| `agentos/workflows/testing/nodes/implement_code.py` | Modify | Add file size threshold detection |
| `tests/unit/test_implement_code_diff.py` | Add | Tests for diff-based generation |

## Acceptance Criteria

1. Files > 500 lines use diff-based generation for "Modify" operations
2. Diff changes are applied correctly to the original file
3. Validation still runs on the final merged result
4. Small files continue to use full-file generation (no regression)
5. "Add" files continue to use full-file generation
6. Truncation is detected and causes retry (not silent failure)

## Related Issues

- #309 - Retry on validation failure (was affected by this bug)
- #321 - API timeout (different failure mode)

## Labels

`bug`, `workflow`