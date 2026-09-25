# Implementation Report — The checkpoint database is keyed by repository and issue (#3548)

Parent: #3502. Follow-up to #3547, found by the stage 6 rehearsal on
2026-09-24.

## What was wrong

`get_checkpoint_db_path` put a real run's LangGraph checkpoint database at
`~/.assemblyzero/testing_{issue}.db`. The key was the issue number alone, so
two target repositories that each had an issue 42 shared one database, and a
`--resume` in one could load the other's checkpoints. #3547 moved only the
`--mock` database, into the target's `data/mock-runs/`. The LLD approval
cache had the same shape (#1160) and #1970 moved it into each repository's
`data/`; this follows that reasoning.

## What changed

`tools/run_implement_from_lld.py`:

- `get_checkpoint_db_path(issue_number, target_repo)` returns
  `<target_repo>/data/speedrun/checkpoints/testing_{issue}.db`
  (`testing_workflow.db` for issue 0), creating the directory. The
  `ASSEMBLYZERO_WORKFLOW_DB` override is unchanged and still first.
  `target_repo` is required: nothing called the function without a
  repository except the old tests.
- `checkpoint_db_for_run` passes the target through for a real run.
  `--db-path` still wins; a `--mock` run's location is #3547's, untouched.
- `legacy_checkpoint_db_path(issue)` names the pre-#3548 location, and
  `legacy_checkpoint_notice(issue, db_path_arg, mock)` returns the line a
  real run prints when that file exists: `Ignoring <path>: keyed by the issue
  alone, it may hold another repository's checkpoints (#3548). To resume from
  it, pass --db-path <path>`. `main` prints it right after choosing the
  database. Requirement 3: the old file is named and ignored, never silently
  read, and the flag that would use it is on the same line. There is no
  notice for a run that chose its database or for a mock run, which never
  read that location.

The run banner's `Database:` line and the final report's
`Checkpoint database (resume state):` line print the new path as before.
The stale-database clearing on a non-resume run (`db_path.unlink()`) now
clears the repository-local file.

## What did not change

- `ASSEMBLYZERO_WORKFLOW_DB` and `--db-path` semantics.
- The mock database (#3547).
- The LLD and spec tools' `get_checkpoint_db_path`, which are separate
  functions with their own histories (#78's `checkpoint.py` is
  repository-rooted already).

## For the operator

A real run started before this change and halted keeps its checkpoints at
`~/.assemblyzero/testing_{issue}.db`. Resuming it means passing that path to
`--db-path`; the run prints the exact flag when it sees the file. Nothing
under `~/.assemblyzero/` is deleted by this change.
