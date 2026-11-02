# Implementation Report: the strict checkpoint serializer in a whole-tree run (#4540)

## What was wrong

#3708 set `LANGGRAPH_STRICT_MSGPACK=true` in `tests/unit/conftest.py`. LangGraph reads the variable once, at import (`langgraph/checkpoint/serde/_msgpack.py`, copied by value into `langgraph/_internal/_serde.py`). A `tests/unit`-only run loads that conftest before anything imports LangGraph. A whole-tree run (`poetry run pytest`, `testpaths = ["tests"]`) loads it only when collection reaches `tests/unit`, and by then a test module in an earlier directory has imported LangGraph, so the serializer was lenient for every tier, the unit tier included. `test_the_unit_tier_runs_the_serializer_strict` caught it in every whole-tree run.

## Changes made

1. `tests/conftest.py`: sets `LANGGRAPH_STRICT_MSGPACK=true` with `os.environ.setdefault`, at module level, before anything else in the file runs. pytest loads this conftest before any test module under `tests/`, in every kind of run.
2. `tests/unit/conftest.py`: the setting and its now-unused `os` import are removed.
3. `tests/unit/test_checkpoint_carries_no_enums.py`: the existing test's message points at `tests/conftest.py`; a new test proves the top conftest sets the variable before LangGraph loads; the import block is sorted.

## Why every tier, not only the unit tier

LangGraph's flag is a module constant read at import, so within one process every tier shares one setting; a whole-tree run cannot be strict for `tests/unit` and lenient elsewhere through the variable. No tier needs lenient: no test outside `tests/unit` reads a checkpoint written before #3708, and the integration and e2e tiers pass strict when run as CI runs them. Production is unchanged and stays lenient, so checkpoints written before #3708 still load.
