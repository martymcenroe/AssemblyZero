# Requirements Workflow Should Commit LLD After Creation

## Problem

On 2026-02-02, the implementation workflow failed because the LLD it needed was not in git. The sequence:

1. Run `run_requirements_workflow.py --type lld --issue 141` - creates LLD in `docs/lld/active/`
2. Run `run_implement_from_lld.py --issue 141` - creates worktree from main
3. **FAIL**: Worktree doesn't have the LLD because it was never committed

The requirements workflow creates artifacts (LLD, lineage files) but does not commit them. The implementation workflow creates a worktree expecting those artifacts to be in git history.

**Root cause:** The requirements workflow's finalize node saves files but doesn't commit them. This creates a chicken-and-egg problem when the next workflow in the pipeline expects those files in git.

## Proposed Solution

Add a commit step to the requirements workflow's finalize node (N5) that:

1. Stages the created LLD and lineage files
2. Commits with a standard message
3. Pushes to remote

### Implementation Location

`assemblyzero/workflows/requirements/nodes/finalize.py` (or wherever N5 lives)

### Commit Message Format

```
docs: add LLD-{issue} via requirements workflow

Auto-committed by requirements workflow finalize node.
```

### Files to Commit

| Workflow Type | Files |
|---------------|-------|
| `--type lld` | `docs/lld/active/LLD-{issue}.md`, `docs/lineage/active/{issue}-lld/**` |
| `--type issue` | `docs/lineage/active/{slug}/**` (issue filed to GitHub, not local) |

## Acceptance Criteria

- [ ] LLD workflow commits LLD and lineage files in finalize node
- [ ] Commit is pushed to remote (not just local)
- [ ] Issue workflow commits lineage files (if any local artifacts created)
- [ ] Commit uses consistent message format
- [ ] Implementation workflow can find LLD in worktree without manual intervention

## Relationship to Other Issues

- **Issue #141**: Archives files from `active/` to `done/` on implementation workflow completion (downstream)
- **This issue**: Commits files to git on requirements workflow completion (upstream)

Together they form the complete lifecycle:
```
requirements workflow → commit to git → implementation workflow → archive to done/
```

## Why This Matters

Without this fix, every LLD creation requires manual intervention:
1. User runs requirements workflow
2. User manually commits LLD
3. User runs implementation workflow

The whole point of the pipeline is automation. A missing commit step breaks the chain.
