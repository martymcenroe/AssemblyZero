# Test Report: the LLD workflow lands through the fleet merge driver (#3704)

## Before the change

The gh wrapper's own predicate on the exact argv `commit_and_pr` built, run from a process without the driver in its ancestry (2026-10-06): `refusal(argv) -> 'gh pr create'`, `caller_is_driver() -> False`. The guard also refused a script that merely contained the phrase.

## Tests added

`tests/unit/test_merge_driver.py`:

- configuration: unset is a reason naming the variable and the refused command; a path that is no file is a reason; a file is configured; `driver_path` raises with the reason.
- argv: the `--no-issue` form in full; the `--issue` form; exactly one of the two.
- output: the driver's lines are read back; a run without `[OK] stage=landed` is not a landing.
- `land`: a landing is reported with its PR number and squash SHA and no `gh` in the argv; a refusal is `MergeDriverError` with the driver's output and the runner was called once; exit 0 without the landed line is not a landing; an unconfigured driver never runs anything.

`tests/unit/test_issue_162.py`: `test_commit_and_pr_emits_no_issue_for_pr_body` and `test_commit_and_pr_targets_given_base_branch` now stand in for the driver and assert no `gh` call and no `git push` reach `run_command`; `test_commit_and_pr_reports_the_drivers_refusal_and_pushes_nothing` is new.

`tests/unit/test_requirements_cli.py`: the pre-generation-check tests set `AZ_MERGE_DRIVER`; a new test asserts the refusal when it is unset, before the check runs.

## Runs

- The files above with `test_requirements_nodes.py`, `test_issue_2684.py` and `test_github_writes_inert.py`: on the closing comment.
- Full unit tier in the worktree: on the closing comment.
