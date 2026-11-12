# Implementation report: #4712, #4713

One branch for two issues of one concern. The operator, 2026-11-11: "shut it off fleet-wide. i simply do NOT understand why i ever did it. and even AZ. why take the extra time and tokens." He wants the GitHub test jobs off across the fleet with one command, and wants no new repository to get them back.

## #4713: `tools/land_workflow_plan.py`

A new operator-run tool. It reads a JSON plan of staged workflow copies and lands them across many repositories inside one `classic_pat_session()`, so the operator types one passphrase for the whole fleet.

- **Per target:** one branch, one commit per file, one pull request whose body closes the target's issue, a wait for each changed workflow's run against the conclusion the plan expects (`skipped` or `success`), then a squash merge and the branch's deletion.
- **Refusals:** a staged copy holding a carriage return; a file whose live blob on `main` moved since the copy was made; a target whose default branch is not `main`; a reason naming a private target when any target is public. Every target's repository is read before any write.
- **Reruns:** a target already landed is skipped without a write.
- **Failure:** the first failure stops the whole run, which prints how many targets landed and how many did not.
- **No repository name is written in the tool.** The plan is the only source of them, and it lives outside this repository.
- Every GitHub call goes through `tools/land_staged_workflow.py`'s functions, so the two landers share one Contents API path.
- Dry run by default; `--apply` lands. `--only` limits a run to named targets and refuses a name not in the plan.

## #4712: no test workflow from the scaffolder

`create_github_workflows()` in `tools/new_repo.py` has never written a test workflow; it writes `auto-reviewer.yml` and `release.yml`. Nothing held that. `tests/unit/test_new_repo_no_test_workflow.py` now does, and the function's docstring and runbook 0901 say why a new repository gets no GitHub test job.
