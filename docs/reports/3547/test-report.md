# Test Report: a mock run's checkpoint DB stays in the target (#3547)

## New test

`tests/unit/test_impl_standalone_end_state.py::TestAMockRunLeavesNothing::test_the_checkpoint_db_stays_in_the_target_not_home` runs a full `--mock` run with no `--db-path`, against a throwaway repository with a bare origin, with `Path.home()` patched to a temporary directory. It asserts:

- no `testing_42.db` under the patched home;
- the database exists at `<target>/data/mock-runs/impl-42/checkpoints.db`;
- the report names that path.

It fails on the code before the change, which was checked by stashing `tools/run_implement_from_lld.py` and rerunning.

## Run

```
pytest tests/unit/test_impl_standalone_end_state.py tests/unit/test_impl_no_push_before_work.py
       tests/unit/test_impl_dry_run_is_dry.py tests/unit/test_implement_from_lld_cli.py
69 passed
```

## Rehearsal

The rehearsal that found this was rerun after the change, on a fresh throwaway. The result is recorded on #3502.
