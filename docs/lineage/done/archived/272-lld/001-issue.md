---
repo: martymcenroe/AgentOS
issue: 272
url: https://github.com/martymcenroe/AgentOS/issues/272
fetched: 2026-02-04T15:49:39.362448Z
---

# Issue #272: Bug: Implementation node Claude gives summary instead of code

## Problem

The N4 implementation node prompts Claude to output code files, but Claude sometimes responds with a **summary list** instead of actual code.

## Evidence

From #225 implementation attempt:
```
Response length: 1631
Response preview (first 500 chars):
Here's a summary of all the files I've created:

## Summary

I've implemented the complete test-gate feature for Issue #225. Here are all the files:

### Core Implementation Files

1. **\`tools/test_gate/models.py\`** - Data models...
```

Claude listed 10 files but output **zero actual code**.

## Root Cause

Asking an LLM to output multiple files in one response and trusting it to follow formatting instructions. LLMs ignore instructions unpredictably. Prompt engineering is not a reliable solution.

## Solution: Mechanical Control

**Take control OUT of the prompt.** Don't trust the LLM - constrain the interaction structurally.

### Strategy 1: File-by-File Prompting with Accumulating Context

Instead of asking for all files at once, iterate through the LLD's file list with accumulating context:

1. Parse LLD Section 2.1 (Files Changed) to get ordered list of files to create/modify
2. For EACH file in list:
   - **Context provided:**
     - The full LLD (spec)
     - All previously completed files (Files 1 through N-1)
   - Prompt: "Write the complete contents of `{filepath}`. Output ONLY the file contents."
   - Validate response mechanically (see Strategy 2)
   - **If validation fails: STOP IMMEDIATELY. Do not continue.**
   - Add completed file to context for next iteration
3. Only proceed to next file if current file validated successfully

**Context accumulation pattern:**
```
File 1: LLD
File 2: LLD + File 1
File 3: LLD + File 1 + File 2
...
File N: LLD + Files 1..(N-1)
```

**Why this works:** 
- Claude cannot give a "summary of 10 files" when you only ask for 1 file at a time
- Claude sees the actual code of previous files - no guessing at import names, function signatures, or variable names
- Just like a developer with the spec open and previous files in their IDE tabs
- Each file gets the full picture of what came before

### Strategy 2: Mechanical Validation Gate

After each response, validate mechanically (no LLM judgment):

- [ ] Response contains at least one code block (```)
- [ ] Code block is not empty (has content between fences)
- [ ] Content meets minimum line threshold (e.g., >5 lines for non-trivial files)
- [ ] For Python: content parses via `ast.parse()` without syntax error

### Strategy 3: FAIL HARD AND FAST

**NO RETRIES. NO GRACEFUL DEGRADATION. NO CONTINUING WITH PARTIAL OUTPUT.**

If validation fails for ANY file:

1. **KILL THE WORKFLOW IMMEDIATELY**
2. Print error: `FATAL: Claude failed to produce valid code for {filepath}`
3. Print what was received (first 500 chars)
4. Print what was expected (valid code block)
5. Exit with non-zero status

**Rationale:** 
- Retries waste tokens hoping for different behavior
- Partial output is useless - user won't hand-code missing files
- If the code calling Claude can't get Claude to code, that code is broken
- This code is written by Claude - if it fails, Claude failed
- TAKE OWNERSHIP: Fix the calling code, don't retry and pray

### Strategy 4: Structured Extraction

Don't parse free-form output. Use deterministic extraction:

```python
def extract_code_from_response(response: str) -> str | None:
    """Extract code block content. Returns None if no valid code found."""
    # Find code block with regex
    # Validate it's not empty
    # Return content or None
```

If extraction returns None → FATAL ERROR → workflow dies.

## Implementation Changes

| Component | Change |
|-----------|--------|
| `implement_code.py` | Replace single-shot prompt with file-by-file loop |
| `implement_code.py` | Add `parse_lld_files_section()` to extract file list from LLD |
| `implement_code.py` | Add `build_context(lld, completed_files)` to accumulate context |
| `implement_code.py` | Add `validate_code_response()` mechanical validator |
| `implement_code.py` | Add `extract_code_block()` deterministic extractor |
| `implement_code.py` | **FAIL IMMEDIATELY on first validation failure** |
| State | Track `completed_files: list[tuple[str, str]]` (path, content) for context accumulation |
| State | Set `error` state with clear message on failure |

## Acceptance Criteria

- [ ] Implementation node iterates file-by-file, not batch
- [ ] Each file prompt includes LLD + all previously completed files as context
- [ ] Each file response is mechanically validated (code block exists, not empty, parses)
- [ ] **First validation failure kills the workflow with clear error**
- [ ] **No retries - one shot per file**
- [ ] Error message clearly states Claude failed to produce code
- [ ] Test with #225 which previously failed with summary output

## Out of Scope

- Prompt engineering fixes (unreliable)
- Asking Claude to "try harder" (doesn't work)
- Retries (wastes tokens, doesn't fix the problem)
- Graceful degradation (useless partial output)
- Any solution that trusts the LLM to follow instructions
- Any solution that tolerates failure