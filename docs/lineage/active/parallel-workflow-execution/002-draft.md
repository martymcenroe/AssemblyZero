# Parallel Workflow Execution for LLD and Issue Processing

## User Story
As a developer using AgentOS workflows,
I want to process multiple LLDs or issues in parallel,
So that I can dramatically reduce the total time required for batch operations.

## Objective
Enable concurrent execution of LLD and Issue workflows with the `--all` flag, solving SQLite contention, credential pool management, and output coordination challenges.

## UX Flow

### Scenario 1: Happy Path - Parallel LLD Processing
1. User runs `lld-workflow --all --parallel 3`
2. System identifies 10 pending LLDs to process
3. System spawns 3 worker processes, each with isolated checkpoint databases
4. Console shows prefixed output: `[LLD-42] >>> Executing: N1_design`
5. As each LLD completes, next pending LLD starts automatically
6. All 10 LLDs complete in ~3x faster than sequential
7. Summary report shows: 8 approved, 2 need revision

### Scenario 2: Credential Pool Exhaustion During Parallel Run
1. User runs `issue-workflow --all --parallel 5`
2. System starts processing 5 issues concurrently
3. Gemini credential pool becomes exhausted mid-run
4. System pauses ALL workers gracefully (not abruptly)
5. Console displays: `[COORDINATOR] Credential pool exhausted. Pausing all workflows...`
6. System waits for credential refresh or user intervention
7. On resume, workflows continue from their checkpointed state

### Scenario 3: Single Workflow Failure
1. User runs `lld-workflow --all --parallel 3`
2. LLD-42 encounters unrecoverable error (invalid spec)
3. System logs error: `[LLD-42] FAILED: Invalid spec format`
4. Other workflows continue unaffected
5. Summary report shows: 9 completed, 1 failed (LLD-42)

### Scenario 4: Graceful Shutdown (Ctrl+C)
1. User runs `lld-workflow --all --parallel 3`
2. User presses Ctrl+C during execution
3. System signals all workers to checkpoint and stop
4. Console shows: `[COORDINATOR] Shutting down... waiting for workers to checkpoint`
5. All workers save state within 5 seconds
6. User can resume later with same command

## Requirements

### Parallelism Control
1. New `--parallel N` flag to enable concurrent execution (default N=3)
2. `--parallel` without N uses sensible default (3)
3. Maximum parallelism capped at 10 to prevent resource exhaustion
4. `--parallel 1` is equivalent to current sequential behavior

### Database Isolation
1. Each workflow subprocess uses isolated checkpoint database
2. Database path pattern: `~/.agentos/checkpoints/lld_workflow_{issue_number}.db`
3. Cleanup of completed workflow databases after successful run
4. Retain failed workflow databases for debugging/resume

### Credential Pool Coordination
1. Credential pool shared across all workers with thread-safe access
2. Workers request credentials through coordinator, not directly
3. When pool low (< 2 credentials), reduce parallelism automatically
4. When pool exhausted, pause all workers and await replenishment

### Console Output Management
1. All output prefixed with workflow identifier: `[LLD-42]` or `[ISSUE-17]`
2. Coordinator messages prefixed: `[COORDINATOR]`
3. Per-workflow log files in `~/.agentos/logs/parallel/{timestamp}/`
4. Summary progress bar showing: `[=====>    ] 5/10 workflows complete`

### Audit and Logging
1. Per-workflow audit files: `workflow-audit-{issue_number}.jsonl`
2. Consolidated summary audit after all complete
3. Lineage directories remain per-workflow (already isolated)

## Technical Approach
- **Process Isolation:** Use `ProcessPoolExecutor` for subprocess management; each worker is fully isolated
- **Checkpoint Databases:** Environment variable `AGENTOS_WORKFLOW_DB` passed to each subprocess for isolated DB path
- **Credential Coordinator:** New `CredentialCoordinator` class wraps existing pool with reservation/release semantics
- **Output Prefixer:** Wrapper that intercepts stdout/stderr and adds `[{id}]` prefix before writing
- **Progress Tracker:** Shared memory or file-based progress tracking for coordinator awareness

## Security Considerations
- No new permissions required; uses existing Gemini credentials
- Subprocess isolation prevents one workflow from affecting another's state
- Checkpoint databases contain workflow state only, no secrets
- Log files may contain LLD/issue content; same visibility as current logs

## Files to Create/Modify
- `src/agentos/workflows/parallel_coordinator.py` — New coordinator managing worker pool and progress
- `src/agentos/workflows/credential_coordinator.py` — Thread-safe credential reservation system
- `src/agentos/workflows/output_prefixer.py` — Stdout/stderr wrapper with prefix injection
- `src/agentos/workflows/lld_workflow.py` — Add `--parallel` flag, integrate with coordinator
- `src/agentos/workflows/issue_workflow.py` — Add `--parallel` flag, integrate with coordinator
- `src/agentos/workflows/checkpoint_manager.py` — Support dynamic database path via env var
- `tests/test_parallel_coordinator.py` — Unit tests for coordinator logic
- `tests/test_credential_coordinator.py` — Unit tests for credential reservation

## Dependencies
- None — builds on existing `--all` implementation and credential pool

## Out of Scope (Future)
- **PostgreSQL/Redis backend** — SQLite with isolation is sufficient for MVP
- **Rich/curses split-pane display** — Prefixed output is sufficient for MVP
- **Distributed execution across machines** — Single-machine parallelism only
- **Auto-scaling parallelism based on system resources** — Fixed N for MVP
- **Web UI for monitoring parallel runs** — CLI only for MVP

## Acceptance Criteria
- [ ] `lld-workflow --all --parallel 3` processes 3 LLDs concurrently
- [ ] `issue-workflow --all --parallel` uses default parallelism of 3
- [ ] Each workflow uses isolated checkpoint database
- [ ] Console output is prefixed with workflow identifier, no interleaving of partial lines
- [ ] Credential exhaustion pauses all workflows gracefully
- [ ] Ctrl+C triggers graceful shutdown with checkpointing
- [ ] Failed workflows don't affect other parallel workflows
- [ ] Summary report shows status of all workflows at completion
- [ ] Per-workflow log files created in `~/.agentos/logs/parallel/{timestamp}/`
- [ ] Total execution time for N items with parallelism P is ~N/P times sequential (accounting for overhead)

## Definition of Done

### Implementation
- [ ] Core parallel coordinator implemented
- [ ] Credential coordinator with reservation semantics implemented
- [ ] Output prefixer working for both stdout and stderr
- [ ] Both lld-workflow and issue-workflow support `--parallel` flag
- [ ] Unit tests written and passing
- [ ] Integration test with 3+ mock workflows running in parallel

### Tools
- [ ] No new CLI tools required (flags added to existing commands)
- [ ] Document `--parallel` usage in tool help text

### Documentation
- [ ] Update wiki pages for lld-workflow and issue-workflow
- [ ] Update README.md with parallel execution examples
- [ ] Create ADR for parallel execution architecture decision
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0809 Security Audit - PASS
- [ ] Run 0817 Wiki Alignment Audit - PASS

## Testing Notes

### Manual Testing
1. Create 5+ pending LLDs, run `lld-workflow --all --parallel 3`
2. Observe prefixed output, verify no interleaving
3. Check `~/.agentos/checkpoints/` for per-workflow databases during run
4. Verify databases cleaned up after successful completion

### Forcing Error States
- **Credential exhaustion:** Set `AGENTOS_CREDENTIAL_LIMIT=2` env var to artificially limit pool
- **Workflow failure:** Create LLD with intentionally invalid spec format
- **Graceful shutdown:** Press Ctrl+C during parallel run, verify checkpoint files exist

### Performance Benchmarking
- Compare time for 6 LLDs: sequential vs `--parallel 2` vs `--parallel 3`
- Expected improvement: ~linear speedup minus coordination overhead (~10%)