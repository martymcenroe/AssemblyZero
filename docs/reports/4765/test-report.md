# Test report: #4765, #4778, #4791

## Command

```
poetry run pytest tests/unit/test_new_repo.py tests/unit/test_new_repo_post_create_hooks.py tests/unit/test_new_repo_ubuntu_run.py tests/unit/test_cerberus_after_auto_review.py tests/unit/test_new_repo_no_auto_review_caller.py tests/unit/test_new_repo_safety.py tests/unit/test_new_repo_guidance.py tests/unit/test_projects_roots.py tests/unit/test_store_pr_sentinel_app_key.py tests/unit/test_loud_failure_check.py -q
```

## Result

```
338 passed, 1 warning in 621.30s (0:10:21)
```

Run on 2026-11-15 in the worktree, after the test-isolation change below. The full unit tier is run separately before landing.

## New tests

- `test_new_repo_ubuntu_run.py::TestProjectsRoots`: #4765 T1 (refused outside the roots, proceeds at the second root), T2 (a name under another root, with and without a pointer), T3 (no pointer: unchanged), a broken pointer, #4778 T1, T2, T3.
- `test_new_repo.py::TestRunPrSentinelCheck::test_T325_new_repo_keeps_no_jwt_code_of_its_own` (#4791).
- `test_new_repo.py::TestMainReadsTemporaryProjectsRoots::test_a_pointer_set_on_this_machine_never_decides_a_test_of_main` (#4765): the tests of `main()` read temporary Projects roots through the fixture `temporary_projects_roots` (`tests/unit/conftest.py`), opted into by a module-level autouse fixture in each module that runs `main()`. With a pointer that leaves `tmp_path` out, `main()` is refused; with the fixture's config, the same run proceeds.

## Lint

`ruff check` on the changed files: no finding on a changed line after the fixes in this commit (the remaining findings are on lines this change did not touch).

## Unit tier, 2026-11-15

Run on Ubuntu with pytest directly, after replaying the branch onto main: `15433 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 3126.86s (0:52:06)`. No test failed.
