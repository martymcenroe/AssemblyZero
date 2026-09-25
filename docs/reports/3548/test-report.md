# Test Report — The checkpoint database is keyed by repository and issue (#3548)

## What was run

From the main checkout's venv, against this worktree
(`PYTHONPATH=<worktree>`, `--rootdir <worktree>`, `-p no:cacheprovider`):

```
tests/unit/test_checkpoint_db_keyed_by_repo.py tests/unit/test_implement_from_lld_cli.py
tests/unit/test_impl_standalone_end_state.py tests/unit/test_checkpoint_db_cleanup.py
tests/unit/test_impl_dry_run_is_dry.py tests/unit/test_impl_no_push_before_work.py
85 passed, 2 warnings in 17.31s
```

Those six files are every test that calls the checkpoint-path functions or
drives the tool's run setup (dry run, mock run, end state, database
cleanup).

```
poetry run ruff check tools/run_implement_from_lld.py tests/unit/test_checkpoint_db_keyed_by_repo.py tests/unit/test_implement_from_lld_cli.py
All checks passed!
```

## The new tests fail on the old tool

`tools/run_implement_from_lld.py` was stashed by name, the tests run, and
the stash popped:

```
tests/unit/test_checkpoint_db_keyed_by_repo.py
1 error in 0.29s
E   ImportError: cannot import name 'legacy_checkpoint_db_path' from 'tools.run_implement_from_lld'

tests/unit/test_implement_from_lld_cli.py -k TestCheckpointDbPath
5 failed, 48 deselected
FAILED ...::TestCheckpointDbPath::test_default_per_issue_partitioning
FAILED ...::TestCheckpointDbPath::test_different_issues_get_different_dbs
FAILED ...::TestCheckpointDbPath::test_zero_issue_falls_back
FAILED ...::TestCheckpointDbPath::test_env_var_overrides
FAILED ...::TestCheckpointDbPath::test_env_var_takes_priority_over_issue
```

## What each new test shows

| Test | Shows |
|---|---|
| `test_two_repositories_running_issue_42_get_different_databases` | Requirement 1 and the issue's first test: two throwaway repositories, issue 42 each, distinct paths under each one's `data/speedrun/checkpoints/`. |
| `test_a_resume_in_one_repository_cannot_read_the_other` | Acceptance criterion: repo A's file is written; repo B's path for the same issue does not exist. |
| `test_the_directory_is_created_under_the_target` | The function creates `data/speedrun/checkpoints/` under the target. |
| `test_nothing_lands_in_the_home_directory` | With `Path.home` pointed at a temp directory, a real run's path resolution leaves `~/.assemblyzero/` empty. |
| `test_the_environment_variable_wins` | Requirement 2: `ASSEMBLYZERO_WORKFLOW_DB` over the repository path. |
| `test_db_path_wins_over_everything` | Requirement 2: `--db-path` over the variable and the repository path. |
| `test_a_mock_run_is_unchanged` | #3547's location, untouched. |
| `test_it_is_never_the_default_even_when_it_exists` | Requirement 3: with a legacy `~/.assemblyzero/testing_42.db` present, the run's path is not it. |
| `test_the_run_names_it_and_the_flag_that_would_use_it` | The notice carries the path, `Ignoring`, and `--db-path <path>`. |
| `test_no_notice_when_it_does_not_exist` / `..._when_the_run_chose_its_database` / `..._for_a_mock_run` | The notice is silent when there is nothing to say. |
| `test_issue_zero_names_the_generic_file` | `testing_workflow.db` for issue 0. |

`TestCheckpointDbPath` (#379, five tests) passes the repository and asserts
the path is under the target's `data/` and not under `.assemblyzero`.

## Not verified

- A real `--resume` across two repositories. The acceptance criterion is
  shown on the paths, not by running two implementation workflows.
- The notice line printed by `main`: `legacy_checkpoint_notice` is tested
  directly, and `main` prints its return value in one added `if`.
- The full unit tier was not run for this change: the touched function has
  one caller, `checkpoint_db_for_run`, whose callers are the six files above.
  CI runs the full tier on the PR.
