# Implementation Report: LLD Governance Workflow

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #86 |
| **LLD** | `docs/LLDs/active/LLD-086-lld-governance-workflow.md` |
| **Branch** | `86-lld-governance-workflow` |
| **Date** | 2026-01-29 |

## 2. Summary

Implemented a LangGraph-based workflow that orchestrates LLD creation from GitHub issues with human review gates and Gemini governance approval.

## 3. Files Changed

| File | Change Type | Lines | Description |
|------|-------------|-------|-------------|
| `agentos/workflows/lld/__init__.py` | Add | 24 | Package exports |
| `agentos/workflows/lld/state.py` | Add | 97 | LLDWorkflowState TypedDict and HumanDecision enum |
| `agentos/workflows/lld/audit.py` | Add | 265 | Audit trail utilities, context assembly, path validation |
| `agentos/workflows/lld/nodes.py` | Add | 543 | N0-N4 node implementations with mock mode |
| `agentos/workflows/lld/graph.py` | Add | 195 | StateGraph with conditional routing |
| `tools/run_lld_workflow.py` | Add | 261 | CLI runner with --auto, --mock, --context, --resume |
| `tests/test_lld_workflow.py` | Add | 413 | 30 unit tests |

**Total:** 1,798 lines added

## 4. Design Decisions

### 4.0 Shared Audit Helpers (Refactoring)

Extracted duplicate audit saving logic into shared helper functions:
- `_save_draft_to_audit()`: Saves draft files, updates counters
- `_save_verdict_to_audit()`: Saves verdict files, updates counters

Both production and mock implementations now use these helpers, ensuring consistency and reducing code duplication.

### 4.1 LangGraph StateGraph Pattern

Used LangGraph's StateGraph for workflow orchestration because:
- Built-in checkpoint/resume via SqliteSaver
- Conditional routing with type-safe edges
- Natural fit for human-in-the-loop workflows

### 4.2 Mock Mode Architecture

Created separate `_mock_*` functions for each node:
- `_mock_fetch_issue`: Returns canned issue data
- `_mock_design`: Generates minimal valid LLD
- `_mock_review`: Rejects first iteration, approves second

This allows full E2E testing without API calls while maintaining the same control flow.

### 4.3 Context Injection (DN-001)

Implemented `--context` flag per Design Note DN-001:
```bash
python tools/run_lld_workflow.py --issue 86 --context docs/standards/0702c.md
```

Context files are:
1. Validated to be inside project root
2. Assembled into a single content block
3. Saved to audit trail alongside the issue

### 4.4 Audit Trail Numbering

Sequential numbering (001-issue.md, 002-draft.md, etc.) chosen over timestamps because:
- Easier to follow review history
- Natural ordering in file listings
- Gaps allowed (e.g., 001, 005 means files 002-004 were deleted)

### 4.5 Max Iterations Enforcement

Hard limit of 5 iterations prevents infinite loops:
- Checked in both real `review` node and mock
- Returns clear error message for manual intervention
- Does not create additional audit files after max

## 5. Node Flow

```
N0_fetch_issue → N1_design → N2_human_edit → N3_review
                     ↑              |              |
                     |              v              v
                     +←←←←←←←←←←←←←+         N4_finalize → END
                     |                            |
                     +←←←←←←←←←←(revision loop)←←+
```

| Node | Responsibility |
|------|----------------|
| N0_fetch_issue | Fetch from GitHub, assemble context, create audit dir |
| N1_design | Generate LLD draft, save to audit trail |
| N2_human_edit | Human decision gate: Send/Revise/Manual exit |
| N3_review | Submit to Gemini, parse verdict, enforce max iterations |
| N4_finalize | Save approved LLD to `docs/LLDs/active/` |

## 6. Known Limitations

1. **No nested context files**: `validate_context_path` only accepts direct paths, not globs
2. **Single-repo only**: Context files must be in same repo as issue
3. **VS Code opening deferred**: Auto-open in N1_design not yet implemented (marked TODO in LLD)
4. **No partial resume**: Checkpoint saves full state, cannot resume mid-node

## 7. Deferred to Future Issues

| Item | Reason | Reference |
|------|--------|-----------|
| LangSmith tracing | Awaiting Issue #54 completion | LLD Section 7 |
| Cross-repo context | Scope creep | DN-001 |

## 8. Commit

```
349ec7d feat: implement LLD governance workflow (issue #86)
```
