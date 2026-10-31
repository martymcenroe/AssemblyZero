# Implementation Report: delete the spent one-shots (#3154, #3170)

The 2026-10-31 open-issue review found that one-shot landing scripts whose work was finished were still executable in `tools/`, and each still carried open issues. This deletes 26 of them.

## What was deleted

- 26 scripts in `tools/`, and the four test files that existed only for them.
- The scripts' six sites in `tests/fixtures/loud_failure_baseline.json`, so `BASELINE_CEILING` drops from 124 to 118.
- Nothing in the fail-open baseline changed.

## How each was checked

Every issue named in a script's opening docstring was read from GitHub. All are closed or merged, except one reference to an issue that no longer resolves; that script's other target is closed.

One candidate failed the check and **stays**: `tools/fix_gemini_ack.py` names no issue, so the change itself was looked for, and two top-level `GEMINI.md` files still carry the section it removes. Its job is not finished, so it and its issue #4051 are left alone. The plan on #3154 said 27 scripts; 26 went.

`tools/land_staged_workflow.py`, `tools/new_repo.py`, `tools/upgrade_auto_reviewer_caller.py` and `tools/deploy_auto_reviewer_workflow.py` are reusable and stay.

## What had to change around them

No surviving code imports a deleted script. The references that remained were prose:

- `tools/require_status_check.py` and `tools/upgrade_auto_reviewer_caller.py` named scripts they generalize.
- Standard 0016 listed `deploy_auto_reviewer_fleet.py` as the caller's deployer; it now names `deploy_auto_reviewer_workflow.py`, which is the deployer that stands, and the two deleted rows are gone.
- Standard 0017 and runbook 0926 use two deleted scripts as reference examples, so each now gives the `git show` command for the last version instead of a path that no longer exists.
- ADR 0216's list of tools marks the deleted one. ADR 0237 and `docs/lessons-learned.md` record past events and are left as written.

In `docs/audits/0908-loud-failure-sweep-ledger.md`, the 185 rows for these scripts now read as won't-do with the reason, so every finding is still fixed or accounted for.

## What this does not do

Deleting a file from `HEAD` does not remove its name from git history.
