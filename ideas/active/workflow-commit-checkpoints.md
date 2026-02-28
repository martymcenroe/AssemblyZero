# Brief: Workflow Commit Checkpoints

**Status:** Active
**Created:** 2026-02-01
**Updated:** 2026-02-28
**Effort:** Medium
**Priority:** High
**Tracking Issue:** None

---

## Problem

On 2026-01-31, 6,114 lines of working code were lost when a worktree was deleted before code had been committed. The code existed only in the working tree — LangGraph's SqliteSaver checkpoints preserve *graph state* (which node ran, what the LLM returned), not uncommitted file changes. When the worktree was removed, the code vanished with it.

This remains an open risk. The TDD workflow (`workflows/testing/graph.py`) generates code across multiple nodes — scaffold tests in N2, implement code in N4, verify green in N5 — and none of these nodes commit to git. A crash, timeout, or premature cleanup at any point loses everything since the last human commit.

## What Already Exists

- **SqliteSaver checkpoints** — save LangGraph state (node outputs, routing decisions), enabling `--resume`. Do NOT save uncommitted file changes.
- **`workflows/testing/graph.py`** — TDD workflow with nodes N0–N9 plus HALT. Code generation happens in N2 (scaffold), N4 (implement), N5 (verify green).
- **`tools/run_implement_from_lld.py`** — entry point for implementation workflows; supports `--no-worktree`.
- **`tools/orchestrate.py`** — end-to-end pipeline (Issue → LLD → Spec → Impl → PR) via `stages.py`.
- **3,788 tests** across unit, integration, adversarial, e2e, and other categories.

## The Gap

No workflow node commits code to git. The only commits happen when a human (or the orchestrator's PR stage) explicitly runs `git commit`. Between those points, all generated code is ephemeral.

## Proposed Solution

Add explicit `git commit` checkpoints at three points in the TDD workflow:

| Checkpoint | After Node | What It Saves |
|-----------|-----------|--------------|
| CP1: post-scaffold | N2 (scaffold_tests) | Generated test files |
| CP2: post-implementation | N4 (implement_code) | Implementation code |
| CP3: post-green | N5 (verify_green_phase) | Green state (tests + code passing) |

Each checkpoint:
1. `git add` only files in the repo's working tree (not `.assemblyzero/` or temp files)
2. `git commit` with a `[CP:NAME]` prefix (e.g., `[CP:post-scaffold] issue #123: scaffold tests`)
3. `git push` to the remote branch immediately (protects against local disk loss)

Checkpoints are commits on the feature branch — they get squashed on merge and leave no trace in `main`.

## Integration Points

- **TDD workflow graph** (`workflows/testing/graph.py`) — checkpoints are new nodes inserted after N2, N4, N5
- **Orchestrator** (`tools/orchestrate.py`) — no changes needed; orchestrator calls the TDD workflow which handles its own checkpoints
- **Worktree cleanup** — with checkpoints, `git worktree remove` is safe even mid-workflow

## Acceptance Criteria

- [ ] Code generated in N2 survives a simulated crash (kill process, verify code recoverable from git)
- [ ] Code generated in N4 survives a simulated crash
- [ ] Checkpoint commits use `[CP:NAME]` prefix and are squash-mergeable
- [ ] Checkpoint commits push to remote immediately
- [ ] No checkpoint touches files outside the repo working tree
- [ ] Existing `--resume` behavior (SqliteSaver) is unaffected

## Dependencies & Cross-References

- **Issue #247** — two-tier commit validation with hourly orphan detection. Complementary: #247 validates commits exist; this brief creates them.
- **Brief: `city-watch-regression-guardian.md`** — Watch verifies test health; checkpoints ensure code exists to test.
