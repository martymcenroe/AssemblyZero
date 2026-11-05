# Implementation report: #4562

Runbook 0935's "No Review At All" section sent every PR that stayed unreviewed after one driver rerun to the operator's Worker log. Whether the Worker ran on the PR at all can be read without that log, so the section now reads it first.

## What changed

- R1, `docs/runbooks/0935-pr-stuck-recovery.md`, "No Review At All": after a second `poll_timeout`, count the check contexts on the PR's head commit against the workflow jobs on that commit. No more contexts than jobs means pr-sentinel's `issue-reference` and `driver-provenance` checks are missing, and the Worker never ran on the PR. More means it ran and did not approve. "Step that works" now says the driver's rerun replaces an earlier run's stamp, so the stamp is always an `edited` event, and records the two incidents that the old behaviour left stuck.
- R2, the same section: the line saying the cause is in the Worker's log, which only the operator can read, now sits only in the case where pr-sentinel's checks are present.
- R3, "Diagnostic Decision Tree": the "No Review At All" branch splits on the count.
- R4, the same section: the four commands read the head commit, the contexts' `totalCount`, the run list and each run's job count, all of which the agent token can read. Check-run names are not read, because that token gets a 403 for them.
- The symptom table's "If it fails" cell, and revision history row 1.4.

## Why it counts and does not name

The agent token can read a commit's `statusCheckRollup.contexts.totalCount` but gets a 403 listing the commit's check runs or reading the contexts' names. A pr-sentinel that ran adds exactly two contexts beyond the workflow jobs, so the count answers the question the names would.

## What did not change

Steps 1 to 7, the behind-state section and the banned table. No code changed.
