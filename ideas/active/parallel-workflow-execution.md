# Brief: Parallel Workflow Execution

**Status:** Active
**Created:** 2026-02-01
**Updated:** 2026-02-28
**Effort:** Low (brief rewrite) | Medium (implementation — frozen)
**Priority:** Medium
**Tracking Issue:** #137

---

## Problem

The `--all` flag on workflow tools processes issues sequentially. With the credential pool limited to 4 Gemini credentials, running N workflows in parallel risks exhausting all credentials simultaneously, leaving the entire pool depleted with no fallback. Issue #137 is deep-frozen for this reason.

## What Already Exists — Infrastructure Is 80% Built

The parallel execution infrastructure is fully implemented:

| Module | Path | Purpose |
|--------|------|---------|
| `coordinator.py` | `workflows/parallel/coordinator.py` | Main parallel coordination — process pooling, result aggregation |
| `credential_coordinator.py` | `workflows/parallel/credential_coordinator.py` | Credential lease/release across parallel workers |
| `input_sanitizer.py` | `workflows/parallel/input_sanitizer.py` | Sanitize inputs for parallel execution |
| `output_prefixer.py` | `workflows/parallel/output_prefixer.py` | Prefix console output per worker (avoid interleaving) |

Additionally:
- **`tools/batch-workflow.sh`** — shell script for batch processing (sequential)
- **`gemini-rotate.py`** — credential rotation with exhaustion tracking
- **Per-repo workflow databases** — SQLite isolation already implemented (Issue #78)

## The Gap

The infrastructure modules exist but aren't wired into the CLI entry points:

1. **No `--parallel N` flag** on `run_requirements_workflow.py` or `run_implement_from_lld.py`
2. **No per-workflow SQLite DB isolation** at the process level (the modules support it, but the CLI doesn't create isolated DBs per worker)
3. **`batch-workflow.sh` doesn't use the parallel coordinator** — it loops sequentially
4. **Credential exhaustion risk is unmitigated** — with 4 credentials and N parallel workers, all credentials can exhaust simultaneously. No backpressure mechanism exists.

## Why #137 Is Frozen

The credential pool is the bottleneck. With 4 credentials:
- **N=2:** survivable — 2 credentials per worker, rotation can absorb spikes
- **N=3:** risky — credential contention likely
- **N=4+:** guaranteed exhaustion — each worker grabs a credential, all hit quota, no fallback

Unfreezing requires one of:
- More credentials (costly, limited by Google's free tier)
- Smarter backpressure (worker pauses when credential pool is thin)
- Workflow-level credential budgeting (each workflow gets a quota slice, not unlimited)

## Proposed Solution (When Unfrozen)

1. Add `--parallel N` flag to `run_requirements_workflow.py` and `run_implement_from_lld.py`
2. Wire CLI to `parallel/coordinator.py` for process management
3. Create isolated SQLite DB per worker process (temp directory, merge results on completion)
4. Implement backpressure: if available credentials < N, reduce parallelism dynamically
5. Update `batch-workflow.sh` to call the Python coordinator instead of looping

## Integration Points

- **`tools/run_requirements_workflow.py`** — add `--parallel N` flag
- **`tools/run_implement_from_lld.py`** — add `--parallel N` flag
- **`tools/batch-workflow.sh`** — replace sequential loop with coordinator call
- **`gemini-rotate.py`** — credential pool size determines max safe parallelism

## Acceptance Criteria

- [ ] `--parallel N` flag on both workflow CLI tools
- [ ] Each parallel worker uses an isolated SQLite database
- [ ] Console output is prefixed per worker (no interleaving)
- [ ] Credential coordinator prevents all-credential exhaustion
- [ ] Backpressure reduces parallelism when credential pool is thin
- [ ] Results are aggregated after all workers complete

## Dependencies & Cross-References

- **Issue #137** — tracking issue (deep-frozen)
- **Issue #78** — per-repo workflow databases (done — foundation for per-worker isolation)
- **`workflows/parallel/`** — existing infrastructure modules
- **`gemini-rotate.py`** — credential pool management
