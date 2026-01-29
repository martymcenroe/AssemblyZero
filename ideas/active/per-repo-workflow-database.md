# Per-Repo Workflow Database

## Problem

The issue workflow stores checkpoints in a single global database at `~/.agentos/issue_workflow.db`. This creates problems:

1. **Worktree collision** - Multiple worktrees of the same repo share the same database, causing checkpoint conflicts
2. **Multi-project chaos** - Running workflows on different projects pollutes the same database
3. **No isolation for testing** - Can't test workflow changes without risking production state
4. **Concurrent workflow limit** - Can't safely run 150 simultaneous workflows on one machine

## Current Workaround

Set `AGENTOS_WORKFLOW_DB` environment variable per-session:
```bash
AGENTOS_WORKFLOW_DB=./workflow.db poetry run python tools/run_issue_workflow.py --brief notes.md
```

This is manual and easy to forget.

## Proposed Solution

Change the default database location from global (`~/.agentos/`) to per-repo (`.agentos/` inside repo root).

### New default path logic:
```python
def get_checkpoint_db_path() -> Path:
    # 1. Environment variable override (highest priority)
    if db_path_env := os.environ.get("AGENTOS_WORKFLOW_DB"):
        return Path(db_path_env)

    # 2. Per-repo database (new default)
    repo_root = get_repo_root()
    db_dir = repo_root / ".agentos"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "issue_workflow.db"
```

### Gitignore addition:
```gitignore
# Local workflow state (per-repo, not shared)
.agentos/
```

## Benefits

- **Zero config** - Just works per-repo without setting env vars
- **Worktree safe** - Each worktree has its own `.agentos/` directory
- **Multi-project safe** - Different repos can't interfere
- **Concurrent safe** - Run as many workflows as you want across repos
- **Testable** - Worktrees get isolated databases automatically

## Migration

- Existing global database remains at `~/.agentos/issue_workflow.db`
- New workflows use per-repo by default
- Old workflows can be resumed by setting `AGENTOS_WORKFLOW_DB=~/.agentos/issue_workflow.db`
- Or: one-time migration script to move active checkpoints to per-repo locations

## Open Questions

1. Should `.agentos/` contain other per-repo state beyond workflow checkpoints?
2. Should we add a `--global` flag to explicitly use the old global database?
3. How to handle worktrees specifically - they share `.git` but should have separate `.agentos/`?
