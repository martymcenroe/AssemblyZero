# Implementation report: #4725

Some repositories have GitHub issues turned off and file their issues in another repository. The plan lander's pull request closed only the target's own issue (`Closes #<issue>`), so a target like that could not go into a plan. A target may now name the repository its issue lives in.

## `tools/land_workflow_plan.py`

- **Plan:** a target may carry `issue_repo`, the name (not `owner/name`) of the repository that holds its `issue`. Validation refuses an `issue_repo` holding a `/` ("is a name, not owner/name") and any value that is not a repository name: empty, not a string, or a character outside `A-Z a-z 0-9 . _ -` ("is not a repository name"). A target without the key is validated as before.
- **`closes_ref(owner, target)`** returns what the target's pull request closes: `#<issue>`, or `<owner>/<issue_repo>#<issue>` when the key is set. `target_cfg()` stores it as `cfg.closes`.
- **Pull request text:** `pr_title()` and `pr_body()` take the issue number, as before, or that reference. The body's first line is `Closes <reference>`, still its only directive, and the title ends `(Closes <reference>)`, also in the long-title fallback (`ci: <verb> N workflows (...)`).
- **Commits:** the removal commit (`ci: remove <file> (Closes <reference>)`) and a replaced workflow's commit carry the same reference. A one-commit pull request's squash can take that commit's subject, so a bare `#<issue>` there would point at the wrong repository's number.
- **Output:** the dry run prints `PR closes <reference>` per target, and `--apply` names the reference on each target's heading line.
- The branch stays `ci/staged-workflow-<issue>` in the target, and nothing else changes for a target without `issue_repo`.

## `tools/land_staged_workflow.py`

- `put_workflow()`'s commit message now reads `_closes(cfg)`: `cfg.closes` when a caller set it, otherwise `#<issue>`. This tool's own argparse namespace has no `closes`, so its messages are unchanged.

## Membrane

This repository is public, and no repository name is written here: `issue_repo` arrives in the plan at run time, like every other name. Whether a public target's pull request may name its issue's repository is for the plan's author to decide before the run.

## Loud-failure compliance

No handler, fallback or default was added. A malformed `issue_repo` raises `PlanError` before any credential is asked for, naming the target and the key, and the run exits non-zero as for any other plan fault.
