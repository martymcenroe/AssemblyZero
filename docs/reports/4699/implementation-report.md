# Implementation report: #4699

`tools/land_staged_workflow.py` and its test file. No other file changes.

## The wait (R1, R2)

`wait_for_workflow` had one budget, `CHECK_POLL_ATTEMPTS = 40` polls `CHECK_POLL_SLEEP_S = 15` seconds apart, for a run both to appear and to finish. A run still going after ten minutes fell out of the loop as `"no_run"`, and `main` printed that the run did not START.

It now has two waits. Until a run appears, the forty-poll budget holds, and exhausting it returns `"no_run"`, which is then true. Once a run is seen, no poll count ends the wait: the interval starts at `RUN_POLL_START_S = 15`, grows by `RUN_POLL_FACTOR = 1.5` to `RUN_POLL_CAP_S = 60`, and the last sleep is clamped to `RUN_WAIT_CEILING_S`, six hours, GitHub's own limit for a job on a hosted runner. A run that finishes twelve minutes after it is seen costs 14 polls.

It returns a `WaitResult(conclusion, url)`. When the ceiling passes, or the operator presses Ctrl-C after a run was seen, the conclusion is `"in_progress"` and the URL is the run's page. A Ctrl-C before any run appears propagates as before.

The report moved out of `main` into `report_wait`, which returns whether the merge may go ahead. `"in_progress"` prints that the workflow is STILL RUNNING, its URL, that nothing is merged, and that a rerun of the same command waits on it again; it never merges, `--merge-on-red` included, since there is no result to override. The other branches print what they printed before. The dry run gains a line saying how long the wait lasts.

`latest_run` holds the one `/actions/runs` request both waits make.

## The rerun (R3)

`put_workflow` decodes the branch's copy of the destination and returns `False` without a PUT when it equals the staged text, so a rerun after a stopped wait adds no commit and starts no second run. It returns `True` after a PUT. `delete_staged`, `ensure_branch` and `open_pr` already skipped work that was done, so the whole rerun lands on the same head commit and waits on the same run.

## Lint

`ruff check` on the tool reports one finding, RUF100 on the `# noqa: E402` of the `_pat_session` import, which `main` already reports. The new code and the test file are clean.
