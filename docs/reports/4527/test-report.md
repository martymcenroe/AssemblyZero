# Test Report: Codex is back (#4527)

Before the change, a one-line `codex exec --model gpt-6.1-sol` from an empty folder answered, using 18,689 tokens, so the plan works and not only the saved login.

`python assemblyzero/fleet_models.py --check` against the changed file lists every role as live. `tests/unit/test_fleet_models.py` passes, including the test that the file still says how to go back.

The full suite against the worktree gave 14,257 passed, 66 skipped, 7 xfailed and 19 failed, and none of the 19 comes from this change:

- 16 in `tests/test_auto_reviewer_wait_loop.py`, the same on main without this change (#4528).
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`, the same on main (#4529).
- `tests/test_universal_claude_md.py::test_adr_references_resolve`, the same on main (#3730).
- `tests/unit/test_checkpoint_carries_no_enums.py::test_the_unit_tier_runs_the_serializer_strict`, which passes alone and failed only because the whole `tests/` tree was run together, so langgraph was imported before that tier's conftest set its flag.
