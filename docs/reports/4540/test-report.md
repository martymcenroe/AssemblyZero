# Test Report: the strict checkpoint serializer in a whole-tree run (#4540)

All runs on Ubuntu, in the worktree, on 2026-11-02.

## Before the change

On `main` at `a360aa11`, the issue's reproduction:

```
poetry run pytest -q -p no:cacheprovider tests -k test_the_unit_tier_runs_the_serializer_strict
1 failed, 14647 deselected, 33 warnings in 49.66s
```

## Test added

`tests/unit/test_checkpoint_carries_no_enums.py::test_the_conftest_every_run_loads_first_sets_strict_before_langgraph`: a fresh interpreter, with `LANGGRAPH_STRICT_MSGPACK` removed from its environment, imports `tests.conftest` and then LangGraph's `_msgpack`, and exits 0 only if `STRICT_MSGPACK_ENABLED` is true. With the setting in `tests/conftest.py` commented out, this test and `test_the_unit_tier_runs_the_serializer_strict` both failed (`2 failed, 10 passed`); restored, both pass.

## Runs after the change

- T1, the same reproduction: `1 passed, 14648 deselected, 33 warnings in 32.65s`.
- T2, `poetry run pytest -q -p no:cacheprovider tests/unit/test_checkpoint_carries_no_enums.py`: `12 passed`.
- Full unit tier, `poetry run pytest -q -p no:cacheprovider tests/unit`: `13945 passed, 66 skipped, 7 deselected, 7 xfailed, 33 warnings in 708.53s`.
- Whole tree, `poetry run pytest -q -p no:cacheprovider`: `18 failed, 14465 passed, 66 skipped, 93 deselected, 7 xfailed, 33 warnings in 799.31s`. The 18 are already tracked: 16 in `tests/test_auto_reviewer_wait_loop.py` (#4528), `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (#4529) and `tests/test_universal_claude_md.py::test_adr_references_resolve` (#3730). The strict-serializer test is not among them.
- e2e tier as CI runs it, `ASSEMBLYZERO_MOCK_MODE=1 LANGSMITH_TRACING=false poetry run pytest -q -p no:cacheprovider tests/ -m e2e`, now strict: `19 passed, 14630 deselected`.
- Integration tier as CI runs it, same environment, `tests/ -m integration`, now strict: `65 passed, 7 skipped, 14577 deselected`. The two live probes skipped, as their opt-in variables were unset.
- `ruff check` on the three changed test files: clean.
