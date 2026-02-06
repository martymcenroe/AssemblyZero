# Parallel Workflow Execution

## Problem Statement

The current `--all` option for both LLD and Issue workflows processes items **sequentially**. This is safe but slow - processing 10 LLDs could take hours if each requires multiple Gemini review cycles.

Parallel execution would dramatically improve throughput, but requires solving several concurrency challenges.

## Current Constraints Preventing Parallel Execution

### 1. SQLite Single-Writer Limitation (CRITICAL)

Both workflows use SQLite for LangGraph checkpointing:
- `~/.assemblyzero/lld_workflow.db`
- `~/.assemblyzero/issue_workflow.db`

SQLite allows only ONE writer at a time. Concurrent workflows would cause "database is locked" errors.

**Possible Solutions:**
- Per-workflow isolated databases: `lld_workflow_{issue_number}.db`
- Switch to PostgreSQL/Redis for concurrent access
- Use SQLite WAL mode with write queue coordination

### 2. Credential Pool Contention (HIGH)

Multiple parallel workflows would compete for the same Gemini credential pool:
- Faster exhaustion of quotas
- Need fair scheduling across workflows
- Need to propagate `CredentialPoolExhaustedException` cleanly

**Possible Solutions:**
- Per-workflow credential reservation
- Global coordinator that allocates credentials to workflows
- Reduce parallelism when pool runs low

### 3. Console Output Collision (MEDIUM)

Multiple workflows printing to stdout simultaneously creates chaos.

**Possible Solutions:**
- Prefix each line with workflow ID: `[LLD-42] >>> Executing: N1_design`
- Write to separate log files, show only summary on console
- Use curses/rich for split-pane display

### 4. JSONL Audit Log Interleaving (LOW)

`workflow-audit.jsonl` could have interleaved entries if two workflows write simultaneously.

**Possible Solutions:**
- Per-workflow audit files (already done for lineage dirs)
- File locking around appends
- Use a logging queue

## Proposed Architecture

### Option A: Process-Level Isolation

Each workflow runs as a separate subprocess with:
- Its own checkpoint database
- Its own log file
- Prefixed console output
- Shared credential pool with reservation system

```python
# Parent process coordinates
pool = ProcessPoolExecutor(max_workers=3)
futures = [pool.submit(run_workflow, issue) for issue in issues]
```

### Option B: Thread-Level with Database Isolation

Single process, multiple threads, each with isolated resources:
- Per-thread checkpoint database
- Thread-local logging
- Shared credential manager with thread-safe access

### Option C: Worker Queue Architecture

More sophisticated:
- Worker processes pull from a queue
- Central coordinator manages checkpoint storage
- Results written to shared output directory

## Recommendation

Start with **Option A (Process Isolation)** as it's simplest:
1. Each subprocess uses `AGENTOS_WORKFLOW_DB` env var for isolated DB
2. Console output prefixed with `[{issue}]`
3. Credential pool already has thread-safe rotation
4. Easy to limit parallelism (e.g., max 3 concurrent)

## Success Criteria

1. `--all --parallel` or `--parallel N` flag to enable
2. N workflows run concurrently (default N=3)
3. Clear per-workflow progress indication
4. Graceful handling of credential exhaustion (pause all, provide resume)
5. Summary report at end with all results

## Related Issues

- This brief extends the sequential `--all` implementation
- Builds on existing `CredentialPoolExhaustedException` handling
