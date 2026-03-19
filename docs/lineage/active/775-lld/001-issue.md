---
repo: martymcenroe/AssemblyZero
issue: 775
url: https://github.com/martymcenroe/AssemblyZero/issues/775
fetched: 2026-03-19T16:25:48.155111Z
---

# Issue #775: refactor: eliminate regex LLM output parsing — use response_schema/--json-schema everywhere

## Problem

6 files parse LLM reviewer output using regex patterns like `r"\[X\]\s*\**APPROVED\**"` instead of using structured JSON output. This is fragile, hallucination-prone, and unnecessary — both Gemini (`response_schema`) and Claude (`--json-schema`) support structured output natively.

The infrastructure already exists: `verdict_schema.py` has `VERDICT_SCHEMA` and `parse_structured_verdict()`. It's just not wired into the review nodes.

## Audit Results

### SHOULD BE JSON (P1 — 6 files, ~15 regex patterns)

**Verdict checkbox parsing:**
- `workflows/requirements/nodes/review.py` lines 306-312: `r"\[X\]\s*\**APPROVED\**"`, REVISE, DISCUSS
- `workflows/implementation_spec/nodes/review_spec.py` lines 497-515: APPROVED, REVISE, BLOCKED checkboxes
- `workflows/testing/nodes/review_test_plan.py` line 614+: `_parse_verdict()` regex fallback

**Section extraction from reviewer markdown:**
- `workflows/requirements/nodes/review.py` lines 456, 512, 570: feedback, open questions, resolved issues
- `workflows/requirements/nodes/generate_draft.py` line 582: open questions section
- `workflows/implementation_spec/nodes/review_spec.py` line 599: feedback extraction

**Question/issue list parsing:**
- `workflows/requirements/nodes/review.py` lines 521, 527: `r"^- \[ \]"` unchecked items
- `workflows/requirements/nodes/finalize.py` lines 219, 223: question detection
- `workflows/requirements/nodes/generate_draft.py` line 591: unchecked questions

### LEGITIMATE (38 files — no change needed)
- Markdown structure parsing (headings, tables, code blocks)
- Error message parsing (HTTP status, module names)
- Security cascade detection
- File path extraction
- Configuration validation
- Emoji stripping

### QUESTIONABLE (4 files — lower priority)
- `validate_completeness.py`, `validate_mechanical.py`: function/class detection via regex — could use Python `ast` module
- `analyze_codebase.py`: docstring extraction via regex — `ast.get_docstring()` exists
- `metrics/collector.py`: verdict parsing from saved files

## Fix

For every LLM call that currently relies on regex to parse the response:
1. Define a `response_schema` (JSON schema) for the expected output format
2. Pass it to the provider: Gemini via `response_schema=`, Claude via `--json-schema`
3. Parse the response as JSON — no regex
4. Keep regex fallback ONLY as a last-resort safety net, log a warning when it triggers

The `VERDICT_SCHEMA` in `verdict_schema.py` is the template. Extend it to cover feedback sections, open questions, and issue lists.

## Gemini Review Prompt

Use this prompt with Gemini to get a detailed refactoring plan:

```
You are reviewing a Python codebase that uses regex to parse LLM reviewer output. This is fragile and unnecessary because both Gemini (via response_schema) and Claude CLI (via --json-schema) support structured JSON output natively.

Here is the current architecture:
- `assemblyzero/core/verdict_schema.py` defines VERDICT_SCHEMA and parse_structured_verdict()
- `assemblyzero/core/llm_provider.py` has get_provider() factory returning LLMProvider instances
- GeminiProvider.invoke() accepts response_schema kwarg
- ClaudeCLIProvider.invoke() will be extended to accept response_schema (maps to --json-schema flag)
- Review nodes in workflows/ call provider.invoke() and parse the response

Here are the 6 files that need refactoring (regex → structured JSON):
1. assemblyzero/workflows/requirements/nodes/review.py — verdict checkboxes, feedback sections, open questions
2. assemblyzero/workflows/implementation_spec/nodes/review_spec.py — verdict checkboxes, feedback extraction
3. assemblyzero/workflows/testing/nodes/review_test_plan.py — verdict regex fallback
4. assemblyzero/workflows/requirements/nodes/generate_draft.py — open questions section extraction
5. assemblyzero/workflows/requirements/nodes/finalize.py — question/TODO detection
6. assemblyzero/core/verdict_schema.py — currently only handles verdict; needs schemas for feedback, questions, issues

For each file:
1. Show the current regex patterns and what they parse
2. Design a JSON schema that replaces the regex
3. Show how the code changes to use response_schema instead of regex
4. Identify any edge cases where structured output might fail

Design principles:
- One schema per logical output type (verdict, feedback, questions)
- Schemas should be minimal — only the fields the code actually reads
- response_schema is passed to provider.invoke(), not stored on the provider instance
- Both Gemini and Claude must produce valid output against the same schema
```

## Refs
- #773 (--no-api default + claude:opus reviewer)
- #774 (full LLM call instrumentation)
- #492 (original structured verdict work — partial)