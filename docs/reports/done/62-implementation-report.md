# Implementation Report: #62 Governance Workflow StateGraph

**Issue:** [#62](https://github.com/martymcenroe/AssemblyZero/issues/62)
**Branch:** `62-governance-workflow-stategraph`
**Date:** 2026-01-26

## Summary

Implemented a LangGraph StateGraph that enforces the issue lifecycle via Inversion of Control. The workflow ensures no LLM output reaches another LLM without human review, and provides human gates at every critical juncture.

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/workflows/__init__.py` | Add | Package init for workflows |
| `assemblyzero/workflows/issue/__init__.py` | Add | Issue workflow package |
| `assemblyzero/workflows/issue/state.py` | Add | TypedDict state definition |
| `assemblyzero/workflows/issue/audit.py` | Add | Audit trail utilities |
| `assemblyzero/workflows/issue/graph.py` | Add | StateGraph with N0-N6 nodes |
| `assemblyzero/workflows/issue/nodes/__init__.py` | Add | Nodes package |
| `assemblyzero/workflows/issue/nodes/load_brief.py` | Add | N0: Load user's brief |
| `assemblyzero/workflows/issue/nodes/sandbox.py` | Add | N1: Pre-flight checks |
| `assemblyzero/workflows/issue/nodes/draft.py` | Add | N2: Claude drafting |
| `assemblyzero/workflows/issue/nodes/human_edit_draft.py` | Add | N3: VS Code post-Claude |
| `assemblyzero/workflows/issue/nodes/review.py` | Add | N4: Gemini review |
| `assemblyzero/workflows/issue/nodes/human_edit_verdict.py` | Add | N5: VS Code post-Gemini |
| `assemblyzero/workflows/issue/nodes/file_issue.py` | Add | N6: gh issue create |
| `tools/run_issue_workflow.py` | Add | CLI runner |
| `docs/audit/active/.gitkeep` | Add | Audit directory |
| `docs/audit/done/.gitkeep` | Add | Audit directory |
| `pyproject.toml` | Modify | Add langgraph-checkpoint-sqlite |
| `tests/test_issue_workflow.py` | Add | 42 unit tests |

## Design Decisions

### 1. Two Human Gates (N3, N5)

Implemented two separate human interrupts to ensure complete LLM isolation:
- **N3 (post-Claude):** User reviews draft before sending to Gemini
- **N5 (post-Gemini):** User can sanitize Gemini output before it reaches Claude or filing

This prevents any prompt injection or hallucinated instructions from propagating between models.

### 2. Hard-Coded 0701c Path

The Gemini review prompt path (`docs/skills/0701c-Issue-Review-Prompt.md`) is hard-coded in the review node. This cannot be changed by the agent, preventing prompt substitution attacks.

### 3. Slug Collision Handling

When a slug already exists in `active/`, the workflow prompts:
- **[R]esume** - Continue existing workflow from checkpoint
- **[N]ew name** - Enter a different slug
- **[A]bort** - Exit cleanly

This is more user-friendly than failing with an error.

### 4. Sequential Audit File Numbering

All audit files use three-digit sequential numbering (001, 002, 003...) across the entire workflow. This preserves exact event order even through multiple revision loops.

### 5. Iteration Display

At human prompts, the workflow displays:
- N3: `Iteration {n} | Draft #{n}`
- N5: `Iteration {n} | Draft #{n} | Verdict #{n}`

This helps users track where they are in the loop.

### 6. VS Code Only (MVP)

The MVP uses VS Code (`code -w`) as the only editor. This is because VS Code renders Mermaid diagrams in preview, which is essential for reviewing issue drafts. A note was added for future `--editor` flag support if productized.

## Known Limitations

1. **No worktree creation:** The sandbox node (N1) performs pre-flight checks but does not create a git worktree. This would need to be added for full implementation of the "jail" concept.

2. **No permission stripping:** Agent permission stripping is conceptual - the actual implementation would require integrating with Claude Code's permission system.

3. **SQLite in memory:** The current checkpointer uses in-memory SQLite. For true persistence across terminal restarts, this should use a file-based SQLite database.

4. **0701c prompt not included:** The review node expects `docs/skills/0701c-Issue-Review-Prompt.md` to exist. This file needs to be created separately.

## Dependencies Added

```toml
"langgraph-checkpoint-sqlite (>=1.0.0,<2.0.0)"
```

## Testing

See [62-test-report.md](62-test-report.md) for full test results.

- **Total tests:** 42
- **Passed:** 42
- **Failed:** 0
- **Coverage areas:** Slug generation, audit numbering, label parsing, graph routing, node behavior

## Deviation from LLD

| LLD Section | Deviation | Reason |
|-------------|-----------|--------|
| N1 worktree creation | Not implemented | Complex integration with git, deferred |
| N1 permission stripping | Not implemented | Requires Claude Code integration |
| SQLite persistence | In-memory only | File-based requires path configuration |

## Next Steps

1. Create `docs/skills/0701c-Issue-Review-Prompt.md` if it doesn't exist
2. Add file-based SQLite persistence
3. Implement worktree creation in N1
4. Integration testing with real Claude/Gemini APIs
