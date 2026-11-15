# Test report: #4765, #4778, #4791

## Command

```
poetry run pytest tests/unit/test_new_repo.py tests/unit/test_new_repo_post_create_hooks.py tests/unit/test_new_repo_ubuntu_run.py tests/unit/test_cerberus_after_auto_review.py tests/unit/test_new_repo_safety.py tests/unit/test_new_repo_guidance.py tests/unit/test_projects_roots.py tests/unit/test_store_pr_sentinel_app_key.py tests/unit/test_loud_failure_check.py -q
```

## Result

Pending when this was written: the run had not finished before the commit. Its log is `data/scratch-2026-11-15-4765/targeted.log` in the worktree. The coordinator records the result here before landing.

## New tests

- `test_new_repo_ubuntu_run.py::TestProjectsRoots`: #4765 T1 (refused outside the roots, proceeds at the second root), T2 (a name under another root, with and without a pointer), T3 (no pointer: unchanged), a broken pointer, #4778 T1, T2, T3.
- `test_new_repo.py::TestRunPrSentinelCheck::test_T325_new_repo_keeps_no_jwt_code_of_its_own` (#4791).

## Lint

`ruff check` on the changed files: no finding on a changed line after the fixes in this commit (the remaining findings are on lines this change did not touch).
