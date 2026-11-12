# Implementation report: #4723

One branch with #4724, because both are loose ends of the same retirement. The reusable Auto Review workflow is retired (#3663: its only job is `if: false`), the fleet is removing its caller (#4719, #4721), and the pr-sentinel Worker approves each PR as Cerberus with its own copy of the App key.

## R1: is there evidence of key health left?

`tools/audit_cerberus_health.py` judged each repository's Cerberus key by that repository's most recent Auto Review run. That evidence is gone: a repository still carrying the caller gets runs that end `skipped`, and one without the caller has no run at all.

The search recorded on #4724 found that nothing reads the per-repository key any more (`REVIEWER_APP_PRIVATE_KEY`, in either scope). A key nothing reads has no health to observe, and revoking it breaks nothing, so a per-repository key audit has nothing left to judge.

One key still signs: the Worker's `CERBERUS_PRIVATE_KEY_B64`. Its evidence is a Cerberus approval on a PR. That is one key and one observation, not one per repository, and every landing by the merge driver already waits on it, so a broken Worker key stops every landing loudly. It belongs in the rotation procedure as a step, not in a fleet scan.

So the audit is retired the way #4719 retired the deploy and upgrade tools: removed, not made to refuse.

## What changed

- `tools/audit_cerberus_health.py` and `tests/tools/test_audit_cerberus_health.py` are removed. No code imported the tool; only its tests and three runbooks named it.
- Runbook 0939 (key rotation) is rewritten around the Worker. Its copies of the key are the App's public half, the encrypted blob and the Worker's secret. Step 2 puts the new key in the Worker with `tools/cerberus_worker_key.py`, and steps 3 and 5 replace the audit with one `gh api .../reviews` read showing a Cerberus approval later than the deploy, then later than the revoke. Failure recovery and the tool reference follow. A lingering per-repository secret is described as dead bytes once its key is revoked.
- Runbook 0927's two "audit via `tools/audit_cerberus_health.py`" sentences now give the Worker procedure. The other 0927 changes belong to #4724.
- `tools/new_repo.py`'s two "deploy new, audit, THEN revoke old" lines now say "put the new key in the Worker, see Cerberus approve a PR, THEN revoke the old key".
- Historical records keep their wording: the loud-failure sweep ledger and the #4719 reports. The loud-failure baseline held no entry for the audit, so it is unchanged at 115 sites.

## R2

With the audit gone, no repository is classed UNCERTAIN and no run exits non-zero for want of an Auto Review run.
