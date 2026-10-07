# Implementation report: #3762, #3763

## #3763: the implementation worktree is cut from origin/<base>

`assemblyzero/workflows/orchestrator/stages.py` (implementation worktree setup): the base is fetched with `git fetch origin <base>`, which updates the remote-tracking ref and is never refused, and the worktree is cut from `origin/<base>`. The old `fetch origin <base>:<base>` was refused whenever the branch was checked out in any worktree — boostgauge's `boostgauge-seed` always holds `hardening-run-20` — and the stage then only warned and cut from the stale local ref. A failed fetch now fails the stage (`could not fetch origin/<base> to cut the implementation worktree from: ...`). The PR base is unchanged. A base resolved from the target's current branch (no base in state) keeps the local ref, as before.

Found on boostgauge #2, run `run-issue2-052813` (2026-10-07 05:28 Central): the local ref predated the LLD the run had just landed (PR #491), the worktree had no LLD, and the loader rebuilt one from `graveyard/2-lld-salvage-20260809`. The graveyard fallback itself is #3764, filed.

Six tests pinned the bare base name as the worktree's commit-ish and now expect `origin/<base>`: `test_impl_worktree_base.py` (2), `test_impl_resume_from_preserved_attempt.py` (3), `test_impl_resume_prefers_best_measured.py` (1).

## An unsettled design artifact on the base is redrawn on the same base

`tools/speedrun_roll.py::ensure_base`: when every unsettled committed finding for the issue is a design artifact (`settlement.stage_of_artifact_path` names a stage: an LLD or a spec), the base is kept. The roll logs `BASE keeping '<base>': unsettled design artifact(s) will be redrawn and re-landed: <findings>`, records a `base-kept-redraw` heal, and continues with the remaining debris, if any. It no longer establishes a new attempt branch for them. A committed finding that is not a design artifact keeps today's path (`establishing a fresh attempt`).

Why it is safe: the scan behind these findings reads `docs/lld` only (#2609's own docstring), so it never sees merged implementation, #1959's founding case. The orchestrator already refuses to reuse a design artifact whose settlement does not verify (`should_skip_stage`: `unsettled -- redrawing`), and the merge driver's next landing overwrites the stale file in place.

Requirement 2 of the issue (the lld stage redraws an unsettled LLD rather than reusing it) was already true in `should_skip_stage`; no change.

`tests/unit/test_speedrun_roll.py::test_base_holding_this_issues_work_triggers_a_fresh_attempt` encoded the old behaviour for a committed LLD and is rewritten as `test_base_holding_this_issues_unsettled_lld_is_kept_for_a_redraw`.

Found on boostgauge #421 (2026-10-07): an unsettled `LLD-002.md` on `hardening-run-20` made run 51 try to cut `hardening-run-21`, and it was cleared by hand three times (boostgauge #479, #486, #489) to keep the seed carrying #7, #41, #4 and #332.
