# Per-Repo Workflow Database

## User Story
As a developer running issue workflows,
I want checkpoint databases stored per-repository instead of globally,
So that I can run concurrent workflows across multiple repos and worktrees without conflicts.

## Objective
Change the default workflow checkpoint database location from global (`~/.agentos/issue_workflow.db`) to per-repo (`.agentos/issue_workflow.db` in repo root) to enable safe concurrent workflow execution.

## UX Flow

### Scenario 1: Default Per-Repo Workflow (Happy Path)
1. User runs `poetry run python tools/run_issue_workflow.py --brief notes.md` in a repo
2. System detects repo root and creates `.agentos/` directory if needed
3. System stores checkpoints in `{repo_root}/.agentos/issue_workflow.db`
4. Result: Workflow runs isolated from other repos/worktrees

### Scenario 2: Environment Variable Override
1. User sets `AGENTOS_WORKFLOW_DB=/custom/path/workflow.db`
2. User runs workflow command
3. System uses the specified path, ignoring per-repo default
4. Result: Custom database location used

### Scenario 3: Resuming Legacy Global Workflow
1. User has existing checkpoints in `~/.agentos/issue_workflow.db`
2. User runs workflow in a repo (new per-repo default)
3. System creates new per-repo database, doesn't find old checkpoints
4. User sets `AGENTOS_WORKFLOW_DB=~/.agentos/issue_workflow.db` to resume
5. Result: Legacy workflow resumed successfully

### Scenario 4: Multiple Worktrees
1. User has main repo at `~/code/project`
2. User creates worktree at `~/code/project-feature`
3. User runs workflows in both simultaneously
4. Each worktree has its own `.agentos/issue_workflow.db`
5. Result: No checkpoint collision between worktrees

## Requirements

### Database Location Logic
1. Environment variable `AGENTOS_WORKFLOW_DB` takes highest priority
2. Default location is `{repo_root}/.agentos/issue_workflow.db`
3. `.agentos/` directory created automatically with appropriate permissions
4. Graceful error if repo root cannot be determined (fall back to global?)

### Git Integration
1. Add `.agentos/` to recommended `.gitignore` patterns
2. Document that workflow state is local, not shared via git
3. Ensure `.agentos/` works correctly in worktree scenarios

### Backward Compatibility
1. Existing global database remains untouched at `~/.agentos/`
2. No automatic migration of existing checkpoints
3. Clear documentation for resuming legacy workflows

## Technical Approach
- **Path Resolution:** Update `get_checkpoint_db_path()` to detect repo root first, fall back to global only if outside a repo
- **Directory Creation:** Use `mkdir(parents=True, exist_ok=True)` for `.agentos/` directory
- **Repo Detection:** Use existing `get_repo_root()` utility or git command to find repo root
- **Worktree Handling:** Use actual worktree path, not shared `.git` location

## Security Considerations
- Database files contain workflow state, not secrets
- Local `.agentos/` directory inherits repo permissions
- No network or cross-user access implications

## Files to Create/Modify
- `src/agentos/workflow/checkpoint.py` — Update `get_checkpoint_db_path()` with new logic
- `.gitignore` — Add `.agentos/` pattern
- `docs/workflow.md` — Document new default behavior and migration path
- `tools/migrate_workflow_db.py` — Optional migration script for active checkpoints

## Dependencies
- None - this is a standalone improvement

## Out of Scope (Future)
- Automatic migration of existing checkpoints — users can manually set env var
- `--global` flag for CLI — env var override is sufficient
- Other per-repo state beyond workflow checkpoints — future consideration
- Shared workflow state across team members — intentionally local-only

## Acceptance Criteria
- [ ] Running workflow in repo creates `.agentos/issue_workflow.db` in repo root
- [ ] Running workflow in different repo creates separate database
- [ ] Setting `AGENTOS_WORKFLOW_DB` overrides per-repo default
- [ ] Worktrees get independent `.agentos/` directories
- [ ] Existing global database at `~/.agentos/` is not modified or deleted
- [ ] `.agentos/` is added to `.gitignore`
- [ ] Running 150 concurrent workflows across repos causes no conflicts

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing
- [ ] Integration test for worktree isolation

### Tools
- [ ] Update `run_issue_workflow.py` if needed
- [ ] Create optional `migrate_workflow_db.py` script
- [ ] Document tool usage

### Documentation
- [ ] Update wiki pages affected by this change
- [ ] Update README.md if user-facing
- [ ] Update relevant ADRs or create new ones
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0817 Wiki Alignment Audit - PASS (if wiki updated)

## Testing Notes

**Test per-repo isolation:**
```bash
cd /tmp && mkdir repo1 repo2
cd repo1 && git init && poetry run python tools/run_issue_workflow.py --brief test.md
cd ../repo2 && git init && poetry run python tools/run_issue_workflow.py --brief test.md
# Verify: repo1/.agentos/issue_workflow.db and repo2/.agentos/issue_workflow.db exist independently
```

**Test env var override:**
```bash
AGENTOS_WORKFLOW_DB=/tmp/custom.db poetry run python tools/run_issue_workflow.py --brief test.md
# Verify: /tmp/custom.db is used, not per-repo location
```

**Test worktree isolation:**
```bash
cd ~/code/myrepo
git worktree add ../myrepo-feature feature-branch
cd ../myrepo-feature
poetry run python tools/run_issue_workflow.py --brief test.md
# Verify: ../myrepo-feature/.agentos/issue_workflow.db exists, separate from main repo
```