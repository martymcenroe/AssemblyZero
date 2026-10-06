# Implementation Report: the checkpoint carries no enum objects (#3708)

## What was wrong

`load_lld.py` put `get_framework_config(fw)` into state as `framework_config`, a dict whose `framework` and `coverage_type` values were `TestFramework` and `CoverageType` members. LangGraph's serializer stores an Enum as a Python object and, on every read, warned that it will refuse unregistered types in a future version. Measured: in strict mode the serializer does not raise; it logs `Blocked deserialization` and hands back something that is not the value, so the day the default flips, a resumed run loses its framework silently. Dependency bumps land on `main` without review (#3638).

## Changes made

1. `runner_registry.checkpoint_safe(config)`: a copy with every Enum value replaced by its string value.
2. `load_lld.py`: the three `"framework_config": dict(fw_config)` writes become `checkpoint_safe(fw_config)`. Every reader already accepted the string (`_resolve_framework_enum`; the `CoverageType(...)` conversion in `verify_phases.py:3596`).
3. `tests/unit/conftest.py`: `LANGGRAPH_STRICT_MSGPACK=true` is set before LangGraph is imported, so the unit tier runs the serializer in the mode LangGraph has announced; a new unregistered type in any checkpoint fails a test. Production stays lenient, so checkpoints written before this change still load (with the warning).

## Not changed

The production checkpointer in `tools/run_implement_from_lld.py` keeps LangGraph's default; an `allowed_msgpack_modules` list was not added, because the state no longer needs one.
