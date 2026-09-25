# Implementation Report — The LLD workflow writes only into its worktree and names how it ends (#3510)

Backfilled 2026-09-25 after the merge, from PR #3537 (merge `bf5b060c`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

- N5 wrote `docs/lld/active/LLD-{NNN}.md` into the operator's checkout, then copied it into the LLD worktree; the original stayed behind as an uncommitted change.
- Regeneration (`audit.shift_lineage_versions`) deleted the checkout's tracked LLD and rewrote its `lld-status.json` entry.
- A mock run wrote its lineage into the checkout's `docs/lineage/active/{issue}-lld/`, beside a real run's, and the pre-generation check shifted that real lineage to `-n1`.
- A mock run recorded its mock APPROVED verdict in the target's real approval cache (`audit.lld_status_path` resolves to the main worktree whatever path it is given, #1970).
- With no `audit_dir` in state, `Path("")` is the current directory; finalize wrote `NNN-final.md` wherever the process was running.
- Nothing said how the `-lld` worktree and branch end.

## What changed

- `git_operations.lld_write_root(state)`: a real run writes into the LLD worktree; a mock run writes under `git_operations.mock_output_root()`, `{target}/data/mock-runs/{issue}-lld/`, gitignored. If a real run's worktree cannot be cut, N5 halts rather than write into the checkout.
- A mock run creates its lineage under the mock output root, moves it to done there, skips the approval cache, and skips the regeneration pre-check.
- `shift_lineage_versions` only shifts lineage; the checkout's LLD and status stay as the base has them.
- `_mirror_to_worktree` passes through files already inside the worktree. An empty `audit_dir` no longer means the current directory, at all three sites.
- `run_record.finishing_commands()` turns the "left in place" list into the exact commands that finish the job, printed as `[run] to finish:` and written to the events log: worktrees before branches, `fetch --prune` before `branch -d`, the ADR-0217 graft named for the squash-merge case, no `-D` or `--force`. The implementation tool shares `RunRecord` and gets the same report (#3509).
- The dry-run plan names the new locations.

Real-run lineage stays in the checkout's `docs/lineage/` by design (#1458); a target that does not ignore `docs/lineage/` and `data/` sees those files in the "left in place" list.

## Files

`assemblyzero/core/run_record.py`, `assemblyzero/workflows/requirements/audit.py`, `assemblyzero/workflows/requirements/git_operations.py`, `assemblyzero/workflows/requirements/nodes/finalize.py`, `assemblyzero/workflows/requirements/nodes/load_input.py`, `tools/run_requirements_workflow.py`, and ten test files.
