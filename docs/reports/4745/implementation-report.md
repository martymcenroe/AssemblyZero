# Implementation report: #4745

## The defect

Runbook 0911 told its reader to delete the audit branch with a force-delete, a banned command, in step 6f and in §Forensics on failure. The tool itself uses `git branch -d` (`tools/dependabot_review.py:1731`), which works because the audit branch is cut from `main` and never moves.

## R1: step 6f

`docs/runbooks/0911-dependabot-pr-audit.md:141` now reads `git branch -d` the audit branch, under the heading for the cleanup that runs on every path (#4744 moved it there).

## R2: the Forensics section

`docs/runbooks/0911-dependabot-pr-audit.md:216` says the tool deletes `dependabot-audit-<N>` with `git branch -d`, and a branch left behind once its worktree is gone goes to the fleet's landed-branch cleanup tool, never to a deletion by hand. The hand-run block that ended in the force-delete is gone. The block for a leftover worktree (`:211` to `:214`) has `poetry -C <path> env remove --all` and `git worktree remove <path>`, with no force flag. No private repository or path is named.

## Tests

Test 1: `grep -n "branch -D" docs/runbooks/0911-dependabot-pr-audit.md` returns nothing.
