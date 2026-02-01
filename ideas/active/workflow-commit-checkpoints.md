# Workflow Commit Checkpoints

## Problem

On 2026-01-31, 6,114 lines of working code (the unified governance workflow) was written, tested, and run - but never committed. When the worktree was deleted, the code became dangling objects in git's lost-and-found. It was recovered only by accident through `git fsck --lost-found`.

**Root cause:** LLMs execute tasks but lack persistent memory. Without explicit commit gates, an LLM can complete work, report success, and move on - leaving uncommitted code that disappears when the session ends or the worktree is removed.

## Proposed Solution

Add explicit commit checkpoints to the governance workflow that:
1. Force commits at defined points (not optional, not "will do later")
2. Verify the commit succeeded before proceeding
3. Push to remote immediately (local commits can still be lost)

### Checkpoint Locations

| Checkpoint | Trigger | What Gets Committed |
|------------|---------|---------------------|
| CP1: Post-Scaffold | After creating new files/directories | Empty files with structure |
| CP2: Post-Implementation | After writing functional code | Working code (may not pass tests) |
| CP3: Post-Test-Pass | After tests pass | Tested code |
| CP4: Post-Review | After Gemini approval | Final reviewed code |

### Implementation

Add to `run_governance_workflow.py`:

```python
def commit_checkpoint(repo: Path, checkpoint: str, message: str) -> bool:
    """Force a commit at a workflow checkpoint.

    Returns False if nothing to commit (which is fine).
    Raises if commit fails.
    """
    # Check for uncommitted changes
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo, capture_output=True, text=True
    )

    if not result.stdout.strip():
        print(f"    [CP:{checkpoint}] No changes to commit")
        return False

    # Stage all changes in the repo
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    # Commit with checkpoint marker
    full_message = f"[{checkpoint}] {message}"
    subprocess.run(
        ["git", "commit", "-m", full_message],
        cwd=repo, check=True
    )

    # Push immediately - local commits can still be lost
    subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=repo, check=True
    )

    print(f"    [CP:{checkpoint}] Committed and pushed: {message}")
    return True
```

### Workflow Integration

```
N0: load_input
    |
N1: generate_draft
    |
    +-- CP1: commit_checkpoint("POST-SCAFFOLD", "scaffold created")
    |
N2: human_gate_draft (if enabled)
    |
N3: review
    |
    +-- CP2: commit_checkpoint("POST-DRAFT", "draft v{n} complete")
    |
N4: [loop back to N1 if BLOCKED]
    |
N5: finalize
    |
    +-- CP3: commit_checkpoint("POST-APPROVE", "approved by Gemini")
```

### CLI Flag

Add `--no-checkpoint` flag for testing/mock mode only:

```bash
# Normal usage - checkpoints enforced
python tools/run_governance_workflow.py --type lld --issue 42

# Testing only - skip checkpoints
python tools/run_governance_workflow.py --type lld --issue 42 --mock --no-checkpoint
```

## Acceptance Criteria

- [ ] Workflow refuses to proceed past checkpoint if commit fails
- [ ] Each checkpoint pushes to remote (not just local commit)
- [ ] Checkpoint commits have `[CP:NAME]` prefix for easy identification
- [ ] `--no-checkpoint` flag exists but only works with `--mock`
- [ ] Attempting `--no-checkpoint` without `--mock` prints warning and ignores flag

## Why This Matters

LLMs are like brilliant colleagues with amnesia. They can build incredible things, but without explicit save points, their work exists only in the moment. Commit checkpoints are the stone tablets - they make the work permanent regardless of what happens to the session, the worktree, or the LLM's context.

## Related

- Issue #101: Unified Governance Workflow
- Incident: 2026-01-31 lost code recovery via `git fsck`
