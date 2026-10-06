# Test Report: the checkpoint carries no enum objects (#3708)

## Before the change

Every mock implementation run on 2026-10-06 printed, at N9 cleanup:

```
Deserializing unregistered type assemblyzero.workflows.testing.framework_detector.TestFramework from checkpoint. This will be blocked in a future version. ...
Deserializing unregistered type assemblyzero.workflows.testing.framework_detector.CoverageType from checkpoint. ...
```

## Tests added

`tests/unit/test_checkpoint_carries_no_enums.py`:

- `test_checkpoint_safe_config_holds_no_enum` (per framework): no Enum values; `framework` is the string; `coverage_type` converts back.
- `test_every_reader_still_resolves_the_string` (per framework): `_resolve_framework_enum` resolves the string, and still resolves the enum a pre-#3708 checkpoint carries.
- `test_the_registry_copy_is_not_mutated`.
- `test_the_strict_serializer_keeps_the_state_and_loses_the_old_shape`: under `JsonPlusSerializer(allowed_msgpack_modules=None)` the new state round-trips and the old shape comes back without its enums.
- `test_the_unit_tier_runs_the_serializer_strict`: `STRICT_MSGPACK_ENABLED` is true under the tier, proving the conftest setting took effect before LangGraph was imported.

## Runs

- `tests/unit/test_checkpoint_carries_no_enums.py tests/unit/test_impl_standalone_end_state.py tests/unit/test_resume_versus_residue.py`: see the closing comment on #3708.
- Under the strict conftest, `tests/unit/test_lld_mock_completes.py` and `tests/unit/test_testing_workflow.py` also passed (317 tests in the first combined run).
- Full unit tier in the worktree, strict: on the closing comment.
