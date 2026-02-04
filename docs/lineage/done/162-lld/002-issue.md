# Issue #162: fix: Requirements workflow should commit LLD after creation

## User Story
As a developer using the AgentOS pipeline,
I want the requirements workflow to automatically commit and push LLD artifacts,
So that the implementation workflow can find them in the git worktree without manual intervention.

## Objective
Add an automatic commit-and-push step to the requirements workflow's finalize node so that downstream workflows can access created artifacts.

## UX Flow

### Scenario 1: Happy Path - LLD Creation
1. User runs `run_requirements_workflow.py --type lld --issue 141`
2. Workflow generates LLD and lineage files in `docs/lld/active/` and `docs/lineage/active/`
3. Finalize node stages, commits, and pushes these files automatically
4. User runs `run_implement_from_lld.py --issue 141`
5. Implementation workflow creates worktree from main
6. Result: Worktree contains the LLD and lineage files; implementation proceeds

### Scenario 2: Issue Creation Workflow
1. User runs `run_requirements_workflow.py --type issue --slug my-feature`
2. Workflow generates lineage files locally and files issue to GitHub
3. Finalize node stages, commits, and pushes lineage files
4. Result: Lineage artifacts are preserved in git for audit trail

### Scenario 3: Push Failure
1. User runs `run_requirements_workflow.py --type lld --issue 142`
2. Workflow generates LLD successfully
3. Finalize node commits locally but push fails (network error, auth issue)
4. Result: Workflow exits with clear error message indicating local commit succeeded but push failed; user can retry push manually

## Requirements

### Commit Behavior
1. Finalize node MUST stage all artifacts created by the workflow run
2. Finalize node MUST commit with a standardized message format
3. Finalize node MUST push to remote origin
4. Commit MUST only include files created by the current workflow run (not unrelated changes)

### Message Format
1. LLD workflow commits MUST use format: `docs: add LLD-{issue} via requirements workflow`
2. Issue workflow commits MUST use format: `docs: add lineage for {slug} via requirements workflow`
3. All commits MUST include footer: `Auto-committed by requirements workflow finalize node.`

### File Staging
1. LLD workflow MUST stage: `docs/lld/active/LLD-{issue}.md`, `docs/lineage/active/{issue}-lld/**`
2. Issue workflow MUST stage: `docs/lineage/active/{slug}/**`
3. Staging MUST NOT include files outside the workflow's output directories

## Technical Approach
- **Finalize Node (N5):** Add git operations after file save; use subprocess for git commands
- **File Tracking:** Finalize node receives list of created files from prior nodes via workflow state
- **Error Handling:** Distinguish between commit failure and push failure; local commit is recoverable

## Files to Create/Modify
- `agentos/workflows/requirements/nodes/finalize.py` - Add commit/push logic after file save
- `agentos/workflows/requirements/state.py` - Add `created_files: list[Path]` to workflow state (if not present)
- `tests/workflows/requirements/test_finalize.py` - Add tests for commit behavior

## Acceptance Criteria
- [ ] Running `run_requirements_workflow.py --type lld --issue {N}` results in a new commit on main containing `docs/lld/active/LLD-{N}.md`
- [ ] The commit message matches format `docs: add LLD-{N} via requirements workflow`
- [ ] The commit is pushed to origin/main (verified by `git log origin/main`)
- [ ] Running `run_implement_from_lld.py --issue {N}` immediately after creates a worktree that contains the LLD file
- [ ] If push fails, workflow exits with non-zero code and error message contains "push failed"
- [ ] Commit includes only files in `docs/lld/active/` and `docs/lineage/active/` (no unrelated working directory changes)

## Related
- Issue #141: Archives files from `active/` to `done/` on implementation workflow completion (downstream)
- This issue: Commits files to git on requirements workflow completion (upstream)