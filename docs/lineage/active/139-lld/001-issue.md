# Issue #139: chore: rename workflows/testing/ to workflows/implementation/

## Summary

The `agentos/workflows/testing/` directory is misnamed. It implements the **Implementation Workflow** (Issue #87), not a standalone testing workflow.

## Current State

- Directory: `agentos/workflows/testing/`
- Exports: `build_testing_workflow`, `TestingWorkflowState`
- Purpose: Transforms approved LLDs into tested, production-ready code (TDD)

## Proposed Change

Rename to align with the workflow's actual purpose:

| Current | Proposed |
|---------|----------|
| `workflows/testing/` | `workflows/implementation/` |
| `build_testing_workflow` | `build_implementation_workflow` |
| `TestingWorkflowState` | `ImplementationWorkflowState` |

## Files Affected

- `agentos/workflows/testing/` â†’ `agentos/workflows/implementation/`
- `agentos/workflows/testing/__init__.py`
- `agentos/workflows/testing/graph.py`
- `agentos/workflows/testing/state.py`
- `agentos/workflows/testing/nodes/*.py`
- `agentos/workflows/testing/audit.py`
- Any imports referencing `workflows.testing`

## Why

- The workflow is the "Implementation Workflow" per Issue #87
- "Testing" is what it *does* (TDD), not what it *is* (implementation stage)
- Naming should reflect the pipeline stage: issue â†’ lld â†’ **implementation**