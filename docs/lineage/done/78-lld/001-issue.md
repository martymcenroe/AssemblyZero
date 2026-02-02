# Issue #78: Per-Repo Workflow Database

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

### Scenario 3: Non-Repo Execution (Fail Closed)
1. User runs workflow outside of any git repository
2. System cannot determine repo root
3. System exits with error: "Cannot determine repository root. Set AGENTOS_WORKFLOW_DB environment variable to specify database location."
4. Result: No accidental corruption of global state; user must explicitly configure

### Scenario 4: Resuming Legacy Global Workflow
1. User has existing checkpoints in `~/.agentos/issue_workflow.db`
2. User runs workflow in a repo (new per-repo default)
3. System creates new per-repo database, doesn't find old checkpoints
4. User sets `AGENTOS_WORKFLOW_DB=~/.agentos/issue_workflow.db` to resume
5. Result: Legacy workflow resumed successfully

### Scenario 5: Multiple Worktrees
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
4. **Fail Closed:** If repo root cannot be determined and no environment variable is set, exit with error message instructing user to set `AGENTOS_WORKFLOW_DB`

### Git Integration
1. Add `.agentos/` to recommended `.gitignore` patterns
2. Document that workflow state is local, not shared via git
3. Ensure `.agentos/` works correctly in worktree scenarios

### Backward Compatibility
1. Existing global database remains untouched at `~/.agentos/`
2. No automatic migration of existing checkpoints
3. Clear documentation for resuming legacy workflows

## Technical Approach
- **Path Resolution:** Update `get_checkpoint_db_path()` to detect repo root first; if outside a repo and no env var set, raise descriptive error
- **Directory Creation:** Use `mkdir(parents=True, exist_ok=True)` for `.agentos/` directory
- **Repo Detection:** Use existing `get_repo_root()` utility or git command to find repo root
- **Worktree Handling:** Use actual worktree path, not shared `.git` location

## Security Considerations
- Database files contain workflow state, not secrets
- Local `.agentos/` directory inherits repo permissions
- No network or cross-user access implications

## Files to Create/Modify
- `src/agentos/workflow/checkpoint.py` â€” Update `get_checkpoint_db_path()` with new logic and fail-closed behavior
- `.gitignore` â€” Add `.agentos/` pattern
- `docs/workflow.md` â€” Document new default behavior, fail-closed behavior, and migration path

## Dependencies
- None - this is a standalone improvement

## Out of Scope (Future)
- Automatic migration of existing checkpoints â€” users can manually set env var
- Migration tooling (`migrate_workflow_db.py`) â€” deferred to future issue
- `--global` flag for CLI â€” env var override is sufficient
- Other per-repo state beyond workflow checkpoints â€” future consideration
- Shared workflow state across team members â€” intentionally local-only

## Acceptance Criteria
- [ ] Running workflow in repo creates `.agentos/issue_workflow.db` in repo root
- [ ] Running workflow in different repo creates separate database
- [ ] Setting `AGENTOS_WORKFLOW_DB` overrides per-repo default
- [ ] Running workflow outside a repo (without env var) exits with descriptive error
- [ ] Worktrees get independent `.agentos/` directories
- [ ] Existing global database at `~/.agentos/` is not modified or deleted
- [ ] `.agentos/` is added to `.gitignore`
- [ ] Running 3 concurrent workflows across different repos causes no conflicts (manual verification)

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing
- [ ] Integration test for worktree isolation

### Tools
- [ ] Update `run_issue_workflow.py` if needed
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

**Test fail-closed behavior (non-repo execution):**
```bash
cd /tmp && mkdir not-a-repo && cd not-a-repo
poetry run python tools/run_issue_workflow.py --brief test.md
# Verify: Command exits with error message about setting AGENTOS_WORKFLOW_DB
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

**Test concurrent execution (manual):**
```bash
# Open 3 terminal windows, each in a different repo
# Run workflow simultaneously in all 3
# Verify: No errors, each repo has independent .agentos/issue_workflow.db
```

---

**Labels:** `enhancement`, `workflow`, `dx`

**Effort:** Small