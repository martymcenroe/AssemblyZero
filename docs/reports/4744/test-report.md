# Test report: #4744

## Changed tests

- Test 1 (R1): `grep -n -i "retain" docs/runbooks/0911-dependabot-pr-audit.md` prints nothing. On `tools/dependabot_review.py` it prints only `:33`, "no local artifact retained", which says nothing is kept. Re-run on the committed tree, 2026-11-13.
- Test 2 (R2): `tests/unit/test_dependabot_outcomes.py::test_main_summary_deferred_heading_makes_no_worktree_claim` runs `main()` over one deferred PR and asserts the Summary's deferred line carries neither "retain" nor "worktree" and its label is exactly `Deferred`.
- The runbook change itself (`docs/runbooks/0911-dependabot-pr-audit.md`: the exit-code gate, the flow's step 6f, §Forensics on failure) has no test beyond Test 1.

## Full suite, 2026-11-13

Every tier finished after the last code edit, at 4:00 PM Central. Each exited 0.

- Unit tier, 4:27 PM Central: `= 14546 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1148.40s (0:19:08) =`
- Integration tier, 4:10 PM Central: `=== 65 passed, 7 skipped, 15246 deselected, 34 warnings in 135.05s (0:02:15) ===`
- E2E tier, 4:10 PM Central: `======== 19 passed, 15299 deselected, 34 warnings in 159.39s (0:02:39) =========`
- Adversarial tier, 4:09 PM Central: `======== 1 skipped, 15317 deselected, 34 warnings in 106.36s (0:01:46) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 4:08 PM Central: `559 passed, 1 warning in 19.68s`
- `ruff check`: `tools/dependabot_review.py` reports 16 findings, the same as at 6815f7be. `tests/unit/test_dependabot_outcomes.py` is clean.

No nightly was run.
