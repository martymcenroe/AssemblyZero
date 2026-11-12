# Implementation report: #4719, #4720, #4721

One branch for three issues of one concern. The reusable Auto Review workflow is retired (#3663: every job `if: false`), and the pr-sentinel Worker approves as Cerberus once `issue-reference` passes, so the per-repository caller `.github/workflows/auto-reviewer.yml` only ever runs a skipped job. The fleet is removing the caller from about 86 repositories. This branch stops it coming back, makes the audits accept its absence, and gives the plan lander the delete action that removal needs.

## #4719: the scaffolder and the two caller tools

- `tools/new_repo.py` no longer writes `auto-reviewer.yml`. `_CANONICAL_AUTO_REVIEWER_CALLER` and `verify_workflow_content_on_origin()` are gone, and so are the `Created auto-reviewer.yml ...` step lines and the `[PASS]`/`[FAIL] auto-reviewer.yml` GitHub-side check.
- `create_github_workflows()` writes only `release.yml`, and only with `--pypi`. With PyPI off (the default) it writes no workflow and creates no `.github/workflows/`.
- The local-only path (`--no-github`) used to `git add .github/workflows` unconditionally. With no workflow file that command would fail the run, so it now runs only when the directory holds a file.
- The Dependabot comments that said "every repo ships at least the auto-reviewer workflow" now give the true reason `github-actions` is always listed.
- **The two retired tools are removed, not made to refuse.** `tools/deploy_auto_reviewer_workflow.py` and `tools/upgrade_auto_reviewer_caller.py` had no caller in code: only their own tests (`tests/unit/test_deploy_auto_reviewer_workflow.py`, `tests/unit/test_upgrade_auto_reviewer_caller.py`, the deploy half of `tests/unit/test_fleet_readiness.py`, and the caller-template class of `tests/unit/test_new_repo_guidance.py`) and docs. A stub that refuses would be dead code that the loud-failure baseline and every grep for the caller keep finding. Both are deleted with their tests. The loud-failure baseline drops their two entries, and its ceiling goes from 118 to 115 with T09's entry (below).
- Docs: standard 0016 (the caller row, and the classic-PAT script table now names `land_workflow_plan.py`), runbooks 0901, 0927, 0933 and 0934, and a comment in `tools/audit_fleet_rulesets.py`. Historical audit ledgers and reports are left as written. The reusable `.github/workflows/auto-reviewer.yml` and `.github/workflows/auto-reviewer-caller.yml` here are untouched.

## #4720: the audits

- `tools/audit_fleet_auto_merge_readiness.py`: the caller no longer counts toward readiness. `workflow_present` stays in the TSV for visibility, and an error reading it leaves the column blank instead of turning the repository UNKNOWN.
- `tools/test_governance_system.py`: T09 is retired. It required `pr-sentinel.yml` and `auto-reviewer.yml`, and both are retired per repository: the Worker posts the pr-sentinel check, and the scaffolder writes neither file.
- `tools/audit_cerberus_health.py` already treated a repository without the caller as NOT_DEPLOYED, skipped it and exited 0. A test now pins that, and its guidance line says the caller is retired and its absence expected.

## #4721: `tools/land_workflow_plan.py`

- **Plan:** a file entry may be `{"workflow": ..., "action": "delete", "base_blob": ...}`. A delete entry carrying `staged` or `expect`, or an `action` other than `delete` or `replace`, is refused. `source` is required only while some entry replaces a workflow.
- **A delete entry:**
  - `already` when the file is absent on `main`;
  - a stop before any write when the live blob is not `base_blob`;
  - otherwise a Contents-API DELETE of that blob on the target's one branch, one pull request closing the target's issue, no wait for a run, the mergeable wait, the squash merge and the branch deletion;
  - then a read of `main`, and a file still there stops the run.
- **Reruns:** a branch already lacking the file takes no second DELETE.
- **Mixed targets:** replace and delete entries land in one pull request, and only the replaced workflows are waited for. The replace path is unchanged, and its tests pass as they were.
- **`--max-targets N`:** lands at most N targets not already done, then stops with a summary and exit 0. Targets already done do not count, so a rerun goes on from there.
- **Before the passphrase:** `--apply` prints how many targets it will land at most and the contributions that adds (2 per landed target: the pull request and its squash commit). The dry run prints the same, plus a `delete <path> base <sha10>` line per delete entry, and says the plan has no source.
- `run()` now resolves `classic_pat_session` when it is called rather than when it is defined, so a test can replace the session through `main()`.
