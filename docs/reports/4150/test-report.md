# Test Report: #4150

## New tests: `tests/unit/test_impl_lands_through_driver.py` (24)

- **T1, the landing** (`TestARealRunLandsThroughTheDriver`): the driver is called once with the branch, the worktree, a title ending `(Closes #42)`, the issue and the base; the body file sits under `data/assemblyzero/pr-bodies/` with `Closes #42` on its own line; a spy on `subprocess.run` sees no `push` and no `gh`, and the origin's heads are unchanged; the late work is on the branch the driver gets; ignored lineage is kept and caches are not; no `gh pr create` line.
- **T3, the stops** (`TestAnUnfinishedRunKeepsItsWork`): a driver refusal keeps the worktree and the branch and carries `stage=checks_failed`; a broken `.git` stops at `git status` before anything moves (ledger 296); work the final checkpoint missed is never moved aside or landed; the checkpoint's own exclusions do not stop the finish; a detached HEAD is a stop (ledger 353).
- **T2, the start-up refusal** (`TestTheDriverIsCheckedAtStart`): a real run needs the driver; dry, mock, scaffold-only and `--no-worktree` runs do not; `main` exits non-zero with one alert, and builds no graph, consumes no resume contract and cuts no worktree.
- **The outcome, through `main` with a stand-in graph** (`TestTheRunsOutcome`): a completed run lands and exits 0 with no alert; a driver refusal reaches the HALT alert with the driver's output, keeps the worktree and branch, writes FAILED, exits 1; an end short of N7 lands nothing and alerts naming N7; no final state alerts (ledger 1484); a crash alerts with its type (ledger 1458); an error that bypassed HALT is on stderr and alerts (ledgers 1344, 1377); an error that went through HALT is not alerted twice.

**Before the fix, measured.** I stashed the three source files by named path in the worktree and ran the file against the original code: **22 failed and 2 passed**. The two that pass pin behaviour the change keeps: `test_ignored_lineage_is_kept_and_caches_are_not` and `test_an_error_that_went_through_halt_is_not_alerted_twice`. The stash was reapplied, its three paths checked, the file rerun (24 passed), and the stash dropped.

## Changed tests

- `test_impl_standalone_end_state.py`: the four real-run tests asserted the retired push, removal and `gh pr create` line. Each has its replacement above: `test_only_the_remote_branch_remains` by the driver-call and no-push tests, `test_the_late_work_is_on_the_pushed_branch` by the late-work test, `test_ignored_lineage_is_kept_and_caches_are_not` by its namesake (content check kept), `test_a_failed_push_keeps_the_worktree_and_the_branch` by the driver-refusal test. The help test now asserts the new end state and that `gh pr create` is gone.
- **T4:** `TestAMockRunLeavesNothing` is unchanged and passes.
- `test_loud_failure_check.py`: `BASELINE_CEILING` 318 to 317.

## Tiers (no other test run on the machine)

```
pytest tests -q                                   22 failed, 11634 passed, 66 skipped, 90 deselected, 6 xfailed (13m 52s)
pytest -m "integration or e2e or adversarial"     83 passed, 7 skipped
```

Twenty-one of the 22 also fail on unchanged `main` on this machine, as recorded for PRs #4138, #4147 and #4149:
- `test_auto_reviewer_wait_loop.py` (16);
- `TestRunJsGate` (2);
- `test_adr_references_resolve`;
- `test_full_pipeline_success`;
- `test_checkpoint_carries_no_enums::test_the_unit_tier_runs_the_serializer_strict`, which passes alone.

The 22nd is `test_cascade_detector.py::TestDetectionLatency::test_max_input_latency` (6.3 to 7.2 ms against a 5 ms limit). It fails alone in this worktree **with the source changes stashed**, and passes alone in the main checkout. So it is the environment, not this change: the load-sensitive test of #3731, where the measurement is recorded.

## Audits

```
audit_loud_failure.py --check            PASS -- 317 site(s), all in the baseline (#3581)
audit_fail_open.py --check --strict      PASS -- 312 files, 9708 sites examined, no new fail-open
audit_halt_sites.py --check              PASS -- 152 halt sites, every one registered
```

## Lint

The five changed Python files carry 21 ruff findings, the same count as on `main`; the new test file has none.
