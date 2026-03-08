# Brief: The Patrician — GitHub Project Stage Automation

**Status:** Active
**Created:** 2026-02-02
**Updated:** 2026-02-28
**Effort:** Medium
**Priority:** Medium
**Tracking Issue:** None

---

## Problem

GitHub Projects tracks issues through lifecycle stages (Backlog → LLD Approved → Implementation → Done), but stage transitions are updated manually. The orchestrator and workflow tools already know when stages change — they just don't tell GitHub Projects about it. This means the project board drifts from reality: issues sit in "Backlog" long after their LLD is approved, or stay in "Implementation" after the PR is merged.

## What Already Exists

- **Runbook 0912** (`docs/runbooks/0912-github-projects.md`) — reference documentation for GitHub Projects field/stage IDs and `gh` CLI commands
- **`tools/orchestrate.py`** — end-to-end pipeline with stage awareness via `workflows/orchestrator/stages.py`
- **`stages.py`** (`workflows/orchestrator/stages.py`) — already has `git push` at stage boundaries; natural integration point for stage updates
- **`gh` CLI** — `gh project item-edit` supports setting stage fields programmatically

## The Gap

No code connects workflow stage transitions to GitHub Projects API calls. The orchestrator knows "LLD is approved, moving to implementation" but doesn't update the project board. The `gh project item-edit` commands exist in the runbook but aren't automated.

## Proposed Solution

A lightweight Python module (`assemblyzero/integrations/github_projects.py`) that:

1. **Reads project/field/stage mappings** from a config file (`~/.assemblyzero/project-mappings.json`) — not hardcoded, since IDs change per project
2. **Exposes a `update_stage(issue_number, stage_name, repo)` function** that translates stage names to project-specific field IDs and calls `gh project item-edit`
3. **Is fire-and-forget** — stage update failures are logged but never block the workflow. The GitHub Projects API is informational, not critical path.

### Integration Points in the Orchestrator

| Workflow Event | Stage Transition |
|---------------|-----------------|
| LLD workflow completes with APPROVED | Backlog → LLD Approved |
| Implementation workflow starts | LLD Approved → Implementation |
| PR merged | Implementation → Done |

### Config File Structure

```json
{
  "martymcenroe/AssemblyZero": {
    "project_id": "PVT_...",
    "stage_field_id": "PVTSSF_...",
    "stages": {
      "Backlog": "...",
      "LLD Approved": "...",
      "Implementation": "...",
      "Done": "..."
    }
  }
}
```

Config data lives in `~/.assemblyzero/project-mappings.json` and runbook 0912 — not in this brief or in source code.

## Integration Points

- **Orchestrator stages** (`workflows/orchestrator/stages.py`) — call `update_stage()` at each stage boundary
- **Runbook 0912** — config data source; runbook becomes the "how to set up" guide
- **`gh` CLI** — underlying API transport

## Acceptance Criteria

- [ ] Stage updates fire at LLD approval, implementation start, and PR merge
- [ ] Stage update failures are logged, never block workflow execution
- [ ] Config is external (`~/.assemblyzero/project-mappings.json`), not hardcoded
- [ ] Works across multiple repos/projects (config is per-repo)
- [ ] `update_stage()` is callable standalone for manual corrections

## Dependencies & Cross-References

- **Runbook 0912** — project/field/stage ID reference and setup instructions
- **`tools/orchestrate.py`** / `stages.py` — primary integration point
