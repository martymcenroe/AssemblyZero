---
repo: martymcenroe/AssemblyZero
issue: 305
url: https://github.com/martymcenroe/AssemblyZero/issues/305
fetched: 2026-02-17T02:07:06.071205Z
---

# Issue #305: feat: End-to-End Orchestration Workflow (Issue → Code)

## Summary

Create an orchestration workflow that stitches together the four individual workflows into a single end-to-end pipeline:

```
Issue → LLD → Implementation Spec → Implementation → PR
```

## Current State: Four Separate Workflows

| Workflow | Input | Output | Location |
|----------|-------|--------|----------|
| Requirements (issue) | GitHub issue number | Triaged issue brief | `workflows/requirements/` |
| Requirements (lld) | Issue number | Approved LLD | `workflows/requirements/` |
| Impl Readiness Review | Approved LLD | Implementation Spec | `workflows/implementation_spec/` (NEW, #304) |
| Implementation | Implementation Spec | Tested code + PR | `workflows/testing/` → `workflows/implementation/` (#139) |

Currently each workflow runs independently with manual handoffs.

## Proposed: Orchestration Workflow

A meta-workflow that:

1. **Accepts an issue number** as input
2. **Runs sub-workflows in sequence**, passing artifacts between them
3. **Handles failures** at any stage with appropriate rollback/retry
4. **Tracks progress** through the full pipeline
5. **Produces a PR** as final output

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION WORKFLOW                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  Issue   │───►│   LLD    │───►│  Impl    │───►│  Impl    │──►PR │
│  │  Triage  │    │  Review  │    │  Spec    │    │  Build   │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │             │
│       ▼               ▼               ▼               ▼             │
│   issue.md         LLD.md        spec.md          code/             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Orchestration Logic

```python
def orchestrate(issue_number: int, config: OrchestratorConfig) -> OrchestrationResult:
    """
    Run full pipeline from issue to PR.
    
    Stages:
    1. Issue triage (optional, skip if issue already triaged)
    2. LLD generation + review
    3. Implementation spec generation + review
    4. Implementation + testing + PR
    
    Each stage can:
    - PASS → continue to next stage
    - BLOCK → stop pipeline, report blocker
    - RETRY → re-run current stage (with limits)
    """
```

### Configuration Options

```yaml
orchestrator:
  # Skip stages for issues that already have artifacts
  skip_existing_lld: true
  skip_existing_spec: true
  
  # Stage-specific settings
  stages:
    lld:
      drafter: claude:opus-4.5
      reviewer: gemini:3-pro-preview
      max_revisions: 5
    spec:
      drafter: claude:opus-4.5
      reviewer: gemini:3-pro-preview
      max_revisions: 3
    implementation:
      implementer: claude:opus-4.5
      max_test_retries: 3
  
  # Human gates
  gates:
    after_lld: false  # default: auto-continue
    after_spec: false
    before_pr: true   # default: human approval before PR
```

### State Management

```python
class OrchestrationState(TypedDict):
    issue_number: int
    current_stage: Literal["triage", "lld", "spec", "impl", "pr", "done"]
    
    # Artifacts produced
    issue_brief_path: str | None
    lld_path: str | None
    spec_path: str | None
    pr_url: str | None
    
    # Progress tracking
    stage_attempts: dict[str, int]
    stage_errors: dict[str, list[str]]
    
    # Timing
    started_at: str
    stage_started_at: str
    completed_at: str | None
```

## Files to Create

| File | Purpose |
|------|---------|
| `assemblyzero/workflows/orchestrator/` | Orchestration workflow module |
| `assemblyzero/workflows/orchestrator/graph.py` | Meta-graph that calls sub-workflows |
| `assemblyzero/workflows/orchestrator/state.py` | Orchestration state |
| `assemblyzero/workflows/orchestrator/config.py` | Configuration schema |
| `tools/orchestrate.py` | CLI entry point |

## CLI Interface

```bash
# Run full pipeline
poetry run python tools/orchestrate.py --issue 99

# Run with config overrides
poetry run python tools/orchestrate.py --issue 99 --skip-lld --gate-before-pr

# Resume from specific stage
poetry run python tools/orchestrate.py --issue 99 --resume-from spec

# Dry run (show what would happen)
poetry run python tools/orchestrate.py --issue 99 --dry-run
```

## Success Criteria

1. Single command takes issue from creation to PR
2. Artifacts persist between stages (can resume after failure)
3. Clear progress reporting throughout pipeline
4. Configurable human gates at any stage
5. Handles the common case: `orchestrate --issue N` just works

## Dependencies

- #304 - Implementation Readiness Review workflow (must exist first)
- #139 - Rename testing/ to implementation/ (do during this work)

## Labels

`enhancement`, `workflow`, `priority:high`