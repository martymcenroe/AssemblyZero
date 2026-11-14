# Test report: #4272

## Changed tests

- `tests/unit/test_generate_spec_resume_4272.py` (new, 5 tests):
  - T1: `TestAnUnreadableDraftHalts::test_t1_a_draft_that_is_not_utf8_halts_n2_with_the_path_named` and `test_t1_a_draft_that_cannot_be_opened_halts_n2_with_the_path_named`.
  - The halt is loud: `TestAnUnreadableDraftHalts::test_the_halt_is_loud_on_stderr`.
  - T2: `TestAnEmptyDraftIsReported::test_t2_an_empty_draft_is_reported_then_n2_drafts`.
  - Unchanged behaviour: `TestAGoodDraftStillResumes::test_a_readable_draft_is_recovered_without_a_drafter_call`.

## Implementation runs, 2026-11-14

- The new file before the fix: `4 failed, 1 passed`, with `UnicodeDecodeError` and `PermissionError` raised out of the node.
- The new file with `test_generate_spec_loud_failure.py` and `test_generate_spec_pinning.py`, after the fix: `32 passed`.

## Full suite, 2026-11-14

Every tier ran in the worktree after the last edit, at 3:30 AM Central. Each exited 0.

- Unit tier, 3:59 AM Central: `= 14562 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1119.35s (0:18:39) =`
- Integration tier, 3:42 AM Central: `=== 65 passed, 7 skipped, 15262 deselected, 34 warnings in 76.48s (0:01:16) ====`
- E2E tier, 3:42 AM Central: `========= 19 passed, 15315 deselected, 34 warnings in 80.49s (0:01:20) =========`
- Adversarial tier, 3:42 AM Central: `========= 1 skipped, 15333 deselected, 34 warnings in 63.97s (0:01:03) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 3:41 AM Central: `559 passed, 1 warning in 15.81s`

No nightly was run.
