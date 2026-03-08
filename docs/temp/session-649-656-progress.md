# Session Progress Report — Cost Optimization Issues

Date: 2026-03-06
Clock: ~50m | Issues attempted: 4 | Issues completed: 0

## Infrastructure Fixes Shipped

Three blocking bugs discovered and fixed before any workflow could run:

| PR | Issue | Fix |
|----|-------|-----|
| #650 | #649 | Claude model IDs: `claude-4.6-sonnet` -> `claude-sonnet-4-6` (all variants) |
| #652 | #651 | Gemini reviewer ID: `gemini:3-pro-preview` -> `gemini:3.1-pro-preview` |
| #654 | #653 | Unicode `->` arrow in print() crashed on Windows cp1252 |

All three merged to main.

## Issue #641 — Route Scaffolding/Boilerplate to Haiku

**Status: LLD + Impl Spec done. TDD blocked.**

| Phase | Status | Artifact | Cost |
|-------|--------|----------|------|
| LLD | APPROVED | `docs/lld/active/LLD-641.md` | $0.72 |
| Impl Spec | APPROVED | `docs/lld/drafts/spec-0641-implementation-readiness.md` | $0.00 |
| TDD | FAILED x2 | — | wasted |

**Why TDD failed:** `implement_code.py` is 1814 lines. The workflow must output the entire modified file in one Claude response. Claude truncated it (1898 -> 705 lines), tripping the 50% size gate. Prompt was 113K+ chars and pruning didn't actually reduce it.

**To restart:** Do NOT re-run TDD. This issue is blocked by #655 (refactor implement_code.py). After #655, re-run:
```bash
CLAUDECODE= PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 641 --repo /c/Users/mcwiz/Projects/AssemblyZero --no-worktree
```

**Lineage artifacts exist** in `docs/lineage/active/641-testing/` and `docs/lineage/active/641-lld-n1/` — don't delete these.

## Issue #642 — Tiered Retry Context Pruning

**Status: LLD + Impl Spec done. TDD failed (different reason).**

| Phase | Status | Artifact | Cost |
|-------|--------|----------|------|
| LLD | APPROVED | `docs/lld/active/LLD-642.md` | $0.47 |
| Impl Spec | APPROVED | `docs/lld/drafts/spec-0642-implementation-readiness.md` | $0.67 |
| TDD | FAILED | — | minimal |

**Why TDD failed:** The LLD's Section 10 (test scenarios) was malformed or missing, causing the TDD workflow to find 0 test scenarios and GUARD-block. This is an LLD quality issue, not a file-size issue. The LLD has 20 requirements but the test plan section didn't parse.

**To restart:** Fix the LLD's Section 10 test plan format, then re-run TDD:
```bash
CLAUDECODE= PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue 642 --repo /c/Users/mcwiz/Projects/AssemblyZero --no-worktree
```

**This issue does NOT touch implement_code.py** — it creates new files only. Not blocked by #655.

## Issue #643 — Fix Cache Busting Across Per-File Calls

**Status: Not started.**

**Warning:** This issue modifies `implement_code.py` (restructures system prompt for cache reuse). Blocked by #655.

## Issue #647 — Batch Small File Generation

**Status: Not started.**

**Warning:** This issue modifies `implement_code.py` (groups small files into single prompts). Blocked by #655.

## Dependency Graph

```
#655 (refactor implement_code.py)
  |
  +-- unblocks #641 TDD
  +-- unblocks #643 (entire pipeline)
  +-- unblocks #647 (entire pipeline)

#642 is independent — fix LLD Section 10, re-run TDD
```

---

# implement_code.py Refactor Recommendations (Issue #655)

## Current State

- **File:** `assemblyzero/workflows/testing/nodes/implement_code.py`
- **Size:** 1814 lines, 30+ functions, 1 class
- **Problem:** Too large for the TDD workflow to modify (ironic — the code gen tool can't modify itself)

## Function Inventory

### Group 1: Prompt Building (~400 lines)
- `build_single_file_prompt()` (L708-871) — main per-file prompt
- `build_diff_prompt()` (L452-535) — diff-mode prompt
- `build_system_prompt()` (L890-915) — system prompt per file
- `build_retry_prompt()` (L1014-1048) — error feedback prompt
- `build_implementation_prompt()` (L1578-1683) — legacy batch prompt

### Group 2: Response Parsing (~250 lines)
- `extract_code_block()` (L150-198) — extract ```code``` from response
- `validate_code_response()` (L199-241) — AST parse, size checks
- `detect_summary_response()` (L242-268) — detect when Claude summarizes instead of coding
- `detect_truncation()` (L689-707) — detect truncated responses
- `parse_diff_response()` (L536-613) — parse diff-format responses
- `parse_implementation_response()` (L1684-1762) — parse batch responses

### Group 3: Context Management (~200 lines)
- `estimate_context_tokens()` (L269-280)
- `summarize_file_for_context()` (L281-339)
- `_summarize_function()` (L340-366)
- `_summarize_class()` (L367-400)
- `is_large_file()` (L401-428)

### Group 4: Diff/Strategy (~150 lines)
- `select_generation_strategy()` (L429-451)
- `apply_diff_changes()` (L614-671)
- `_normalize_whitespace()` (L672-688)

### Group 5: Claude Interaction (~250 lines)
- `call_claude_for_file()` (L916-1013) — main Claude call with fallback
- `call_claude_headless()` (L1800-1814) — legacy headless call
- `_find_claude_cli()` (L126-149)
- `compute_dynamic_timeout()` (L872-889)
- `ProgressReporter` class (L72-113)

### Group 6: Orchestration (~500 lines)
- `implement_code()` (L1239-1545) — THE langgraph node entry point
- `generate_file_with_retry()` (L1049-1195) — per-file retry loop
- `validate_files_to_modify()` (L1196-1238) — path validation
- `write_implementation_files()` (L1763-1799) — file writer
- `_mock_implement_code()` (L1546-1553)
- `example_function()` (L1554-1577) — dead code, delete

## Recommended Split

```
assemblyzero/workflows/testing/nodes/
    implement_code.py          -> becomes thin re-export shim (~20 lines)
    implementation/
        __init__.py            -> re-exports implement_code for backwards compat
        prompts.py             -> Group 1 (prompt building)
        parsers.py             -> Group 2 (response parsing)
        context.py             -> Group 3 + Group 4 (context mgmt + diff/strategy)
        claude_client.py       -> Group 5 (Claude interaction)
        orchestrator.py        -> Group 6 (orchestration, the langgraph node)
```

## Migration Strategy

1. Create the package directory
2. Move functions mechanically — no behavior changes
3. Update internal imports between the new modules
4. Keep `implement_code.py` as a re-export shim:
   ```python
   """Backwards-compatible re-export. See implementation/ package."""
   from assemblyzero.workflows.testing.nodes.implementation.orchestrator import implement_code
   from assemblyzero.workflows.testing.nodes.implementation.orchestrator import generate_file_with_retry
   # ... etc for any externally-imported names
   ```
5. Run existing tests — they should pass without changes
6. Delete `example_function()` — it's dead code

## Import Dependencies Between Modules

```
orchestrator.py imports from: prompts, parsers, context, claude_client
claude_client.py imports from: parsers (extract_code_block, validate_code_response)
prompts.py imports from: context (summarize_file_for_context, is_large_file)
parsers.py: standalone (only stdlib + ast)
context.py: standalone (only stdlib + ast)
```

No circular dependencies. Clean DAG.

## Constraints

- `implement_code` function signature and return type must not change (LangGraph node)
- All existing `from assemblyzero.workflows.testing.nodes.implement_code import X` must keep working
- Pure mechanical refactor — zero behavior changes
- Each resulting module should be <500 lines
