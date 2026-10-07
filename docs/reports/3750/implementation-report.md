# Implementation report: #3750

## The approved LLD outlives its landing; the lld stage never fails blank

Found on boostgauge #2, run `run-issue2-013743` (2026-10-07 01:37 Central), the first roll after #3717: the merge driver landed the approved LLD and removed the LLD worktree, `final_lld_path` still named the file inside it, `run_lld_stage` found nothing there and failed with an empty reason, and the orchestrator's retries landed two more LLD PRs (boostgauge #476, #477, #478, all merged into `hardening-run-20`).

- `assemblyzero/workflows/requirements/nodes/finalize.py`:
  - `durable_lld_path(target, N)` = `<target>/docs/lineage/active/<N>-lld-handoff/LLD-NNN.md`, gitignored lineage beside the spec's `<N>-implspec/` handoff (#2311).
  - `_save_lld_file` writes the approved LLD there right after saving it into the worktree, before any landing, and prints its path. Not on a mock run. A failed write warns and carries on (ruled `# fail-open:` in the code: the LLD itself is saved and about to land).
  - `_commit_and_push_files`, after the driver reports the landing, points `final_lld_path` at the durable copy when it exists.
- `assemblyzero/workflows/orchestrator/stages.py::run_lld_stage`: the failure branch uses `error_message or <default>`; the sub-workflow carries `""` when it did not fail, so `.get(key, default)` never applied. A reported `final_lld_path` with no file behind it is named: `LLD workflow reported <path> but no file is there`.

## Fail-open baseline

Regenerated; only the totals move (9552 to 9556 sites, 557 to 558 findings), the new handler being ruled on in the code.
