# 0923 - Workflow Recovery and `--resume`

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-02-26

---

## Purpose

Recover interrupted workflows using checkpoint resume instead of starting from scratch. All LangGraph-based workflows persist state to SQLite via `SqliteSaver`, enabling recovery from the exact node where execution stopped.

**Use this when:** A workflow was interrupted (Ctrl+C, API timeout, credential exhaustion, crash) and you want to continue without re-running completed stages.

---

## When to Resume vs Clean Re-run

| Situation | Action | Why |
|-----------|--------|-----|
| Workflow interrupted mid-run (Ctrl+C, timeout) | `--resume` | State is valid, pick up where you left off |
| API credential exhaustion mid-workflow | `--resume` (after quota resets) | Completed nodes don't need re-running |
| LLD was revised after workflow started | Clean re-run | Checkpoint state references old LLD content |
| Code was manually modified during workflow | Clean re-run | Checkpoint state doesn't reflect manual changes |
| Max iterations reached, same failures | `--resume` (after manual fixes) | Fix the code, then let the workflow re-verify |
| Database locked error | Kill stale process, then `--resume` | Another process holds the lock |
| Workflow completed but output is wrong | Clean re-run | Checkpoint marks workflow as done |

**Rule of thumb:** Resume if the _inputs_ haven't changed. Clean re-run if the LLD, spec, or code was modified outside the workflow.

---

## Per-Tool Reference

| Tool | Flag | DB Path | Thread ID | Notes |
|------|------|---------|-----------|-------|
| `run_implement_from_lld.py` | `--resume` | `~/.assemblyzero/testing_{issue}.db` | `testing_workflow_{issue}` | Per-issue DB; fresh runs auto-clear stale DB |
| `run_implementation_spec_workflow.py` | `--resume` | `~/.assemblyzero/impl_spec_{issue}.db` | Per-issue | Per-issue DB partitioning |
| `run_requirements_workflow.py` (LLD) | `--resume` | `~/.assemblyzero/requirements_workflow.db` | Brief filename slug | Shared DB, thread-keyed by brief |
| `run_issue_workflow.py` | `--resume <file>` | `~/.assemblyzero/issue_workflow.db` | Brief filename slug | Interactive R/N/C prompt on conflict |
| `orchestrate.py` | `--resume-from <stage>` | N/A (stage-level) | N/A | Resumes from a named stage, not a checkpoint |

**DB directory:** All databases live in `~/.assemblyzero/` (resolved as `C:\Users\mcwiz\.assemblyzero\`). Override with `ASSEMBLYZERO_WORKFLOW_DB` env var for issue workflow.

---

## Inspecting Checkpoint State

### List All Checkpoints in a Database

```bash
sqlite3 ~/.assemblyzero/testing_381.db \
  "SELECT thread_id, checkpoint_id, created_at FROM checkpoints ORDER BY created_at DESC LIMIT 10;"
```

### Find Which Node the Workflow Stopped At

```bash
sqlite3 ~/.assemblyzero/testing_381.db \
  "SELECT thread_id, checkpoint_id, metadata FROM checkpoints ORDER BY created_at DESC LIMIT 1;" \
  | python -c "import sys,json; m=json.loads(sys.stdin.read().split('|')[-1]); print(f'Node: {m.get(\"source\",\"?\")}  Step: {m.get(\"step\",\"?\")}')"
```

### Quick: Does a Checkpoint Exist?

```bash
sqlite3 ~/.assemblyzero/testing_381.db \
  "SELECT COUNT(*) FROM checkpoints WHERE thread_id='testing_workflow_381';"
```

If the count is 0, `--resume` will start fresh automatically.

### List All Databases

```bash
ls -la ~/.assemblyzero/*.db
```

---

## Clearing Stale Checkpoints

### Delete a Single Issue's Checkpoint DB

```bash
# TDD workflow
rm ~/.assemblyzero/testing_381.db

# Impl spec workflow
rm ~/.assemblyzero/impl_spec_381.db
```

### Clear All Checkpoints for a Shared DB

```bash
# Requirements workflow (all threads)
rm ~/.assemblyzero/requirements_workflow.db

# Issue workflow (all threads)
rm ~/.assemblyzero/issue_workflow.db
```

### Selective: Delete One Thread from a Shared DB

```bash
sqlite3 ~/.assemblyzero/requirements_workflow.db \
  "DELETE FROM checkpoints WHERE thread_id='my-brief-slug';"
```

### Nuclear: Clear Everything

```bash
rm ~/.assemblyzero/*.db
```

**Note:** `run_implement_from_lld.py` automatically clears stale checkpoint DBs on fresh (non-resume) runs. The other tools do not — you must clear manually if needed.

---

## Troubleshooting

### "Database is locked"

**Cause:** Another workflow process holds the SQLite lock.

```bash
# Find the process
ps aux | grep "run_implement\|run_requirements\|run_issue\|run_implementation_spec"

# If no process is running, the lock is stale — just delete the DB
rm ~/.assemblyzero/testing_381.db
```

### "No checkpoint found for issue #N, starting fresh..."

**Cause:** `--resume` was used but no checkpoint exists. This is informational — the workflow starts from the beginning automatically. No action needed.

**If you expected a checkpoint:** Check you're targeting the right issue number and the DB file exists:
```bash
ls -la ~/.assemblyzero/testing_{issue}.db
```

### "Stale state after resume"

**Symptoms:** Tests reference code that no longer exists, or the workflow re-does work that was already committed.

**Fix:** The checkpoint state is stale. Delete the DB and start fresh:
```bash
rm ~/.assemblyzero/testing_{issue}.db
poetry run python tools/run_implement_from_lld.py --issue {issue}
```

### "Workflow completed but I need to re-run"

**Cause:** The checkpoint marks the workflow as finished. `--resume` sees "done" and exits.

**Fix:** Delete the checkpoint DB to force a fresh run:
```bash
rm ~/.assemblyzero/testing_{issue}.db
```

### Orchestrator Resume

`orchestrate.py` uses `--resume-from <stage>` (not `--resume`). Valid stages depend on the orchestrator pipeline. Example:

```bash
poetry run python tools/orchestrate.py --issue 305 --resume-from spec
```

This skips all stages before `spec` and begins from that stage.

---

## Examples

### Resume an Interrupted TDD Workflow

```bash
# Was running, got interrupted
poetry run python tools/run_implement_from_lld.py --issue 381
# ^C (interrupted at N4)

# Resume from where it stopped
poetry run python tools/run_implement_from_lld.py --issue 381 --resume
```

### Resume After Credential Exhaustion

```bash
# Workflow died with CredentialPoolExhausted at N1
# Wait for quota to reset, then:
poetry run python tools/run_implement_from_lld.py --issue 102 --resume
```

### Fresh Re-run After LLD Revision

```bash
# LLD was updated — checkpoint is stale
rm ~/.assemblyzero/testing_102.db
poetry run python tools/run_implement_from_lld.py --issue 102
```

---

## Related Documents

- [0909 - TDD Implementation Workflow](0909-tdd-implementation-workflow.md) — Primary workflow using `--resume`
- [0907 - Unified Requirements Workflow](0907-unified-requirements-workflow.md) — LLD/issue workflow with checkpoints
- [Issue #440](https://github.com/martymcenroe/AssemblyZero/issues/440) — Tracking issue for this documentation
- [Issue #333](https://github.com/martymcenroe/AssemblyZero/issues/333) — Recovery scenario that motivated this runbook

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-26 | Initial version documenting --resume across all workflow tools |
