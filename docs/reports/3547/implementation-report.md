# Implementation Report: a mock run's checkpoint DB stays in the target (#3547)

## Found

The stage 6 rehearsal (#3502) ran `tools/run_implement_from_lld.py --mock` against a throwaway repository. The run left `~/.assemblyzero/testing_42.db` in the operator's home directory. `get_checkpoint_db_path` sends every run there, mock or real. A later real `--resume` for issue 42, in any repository, would have read the mock's checkpoints.

## Changed

| File | Change |
|---|---|
| `tools/run_implement_from_lld.py` | New `checkpoint_db_for_run()`: `--db-path` wins; a `--mock` run uses `<target>/data/mock-runs/impl-<issue>/checkpoints.db`; a real run is unchanged. Used by the dry run and by `main()`. The final report prints `Checkpoint database (resume state): <path>` on success and on failure. |
| `tests/unit/test_impl_standalone_end_state.py` | `test_the_checkpoint_db_stays_in_the_target_not_home` |

## Not changed

Real runs still use `~/.assemblyzero/testing_{issue}.db`, keyed by issue alone. That is #3548.
