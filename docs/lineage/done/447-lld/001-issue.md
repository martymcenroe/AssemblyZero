---
repo: martymcenroe/AssemblyZero
issue: 447
url: https://github.com/martymcenroe/AssemblyZero/issues/447
fetched: 2026-02-25T05:16:55.766790Z
---

# Issue #447: bug: TDD workflow N4 fails on non-Python files (.md skill definitions)

## Problem

Issue #444's TDD implementation workflow failed because the file to modify is `.claude/commands/test-gaps.md` — a Markdown skill definition, not Python code.

The N4 `implement_code` node:
1. Sends a prompt asking Claude to output code in a ` ```python ` block
2. Validates the response has a code block
3. All 3 retries failed because Claude's response for a `.md` file was conversational, not a code block

The system prompt says "Output ONLY code" and expects ` ```python ` blocks — this is hard-coded for Python files.

## Root Cause

`build_single_file_prompt()` and the system prompt in `call_claude_for_file()` both assume Python:
- System prompt: "Just the code in a ```python block"
- Prompt: "Output ONLY the file contents" but framed as code generation
- `extract_code_from_response()` looks for code blocks with language tags

## Suggested Fix

1. Detect file type from extension (`.py` vs `.md` vs `.yaml` etc.)
2. Adjust code block language tag in prompt and system prompt accordingly
3. For `.md` files, use ` ```markdown ` or just ` ``` ` fencing
4. `extract_code_from_response()` should accept any fenced block, not just `python`

## Workaround

For issue #444, implement the file manually since it's a single Markdown file.