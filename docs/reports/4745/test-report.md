# Test report: #4745

## Changed tests

- Test 1 (R1, R2): `grep -n "branch -D" docs/runbooks/0911-dependabot-pr-audit.md` prints nothing. Re-run on the committed tree, 2026-11-13.
- The change is to the runbook only. Step 6f reads `git branch -d`, and §Forensics on failure sends a leftover branch to the fleet's landed-branch cleanup tool. No code and no test file changed for this issue.

## Full suite, 2026-11-13

The batch's full suite ran on the same tree. Every tier finished after the last code edit, at 4:00 PM Central. Each exited 0.

- Unit tier, 4:27 PM Central: `= 14546 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1148.40s (0:19:08) =`
- Integration tier, 4:10 PM Central: `=== 65 passed, 7 skipped, 15246 deselected, 34 warnings in 135.05s (0:02:15) ===`
- E2E tier, 4:10 PM Central: `======== 19 passed, 15299 deselected, 34 warnings in 159.39s (0:02:39) =========`
- Adversarial tier, 4:09 PM Central: `======== 1 skipped, 15317 deselected, 34 warnings in 106.36s (0:01:46) =========`. The tier's one test makes a live agy call and runs only with `AZ_LIVE_ADVERSARIAL_PROBE=1`.
- `tests/tools/`, 4:08 PM Central: `559 passed, 1 warning in 19.68s`

No nightly was run.
