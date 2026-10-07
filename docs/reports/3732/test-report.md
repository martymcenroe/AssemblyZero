# Test report: #3732

## New tests: `tests/unit/test_scaffold_resolves_framework_string.py`

- `test_a_checkpointed_pytest_config_takes_the_pytest_path`: `scaffold_tests` with `checkpoint_safe(get_framework_config(PYTEST))` takes the pytest path. This is the boostgauge #2 failure as a unit test.
- `test_an_enum_pytest_config_takes_the_pytest_path`: a checkpoint written before #3708 still carries the enum.
- `test_no_framework_config_takes_the_pytest_path`.
- `test_a_checkpointed_ts_config_reaches_the_ts_path_with_the_enum` (Playwright, Jest, Vitest): the non-Python path is taken and receives `framework_config["framework"] is <the enum>`.
- `test_resolve_framework_reads_the_enum_and_its_string` (all four frameworks), and `test_resolve_framework_is_none_for_anything_else` (`"nonsense"`, `None`, no key, no config).
- `test_no_node_compares_the_raw_framework_to_the_enum`: an AST walk of every module under `nodes/` for a comparison between `x.get("framework")` or `x["framework"]` and a `TestFramework` member.

The path is observed by patching `_scaffold_non_python_tests` to record its argument, and `get_repo_root`, which only the pytest path calls, to raise a sentinel. The module is imported with `importlib` because `nodes/__init__.py` re-exports the `scaffold_tests` function under the module's name.

## Runs, 2026-10-06 and 2026-10-07, Ubuntu (WSL)

- **The tests catch the bug.** With only the `scaffold_tests.py` change stashed (named path), the new file gives 5 failed, 10 passed: the checkpointed pytest config, the three TypeScript frameworks, and the AST guard naming the raw comparison. With it, 15 passed.
- The new file with the related files `test_checkpoint_carries_no_enums.py`, `test_framework_integration.py`, `test_scaffold_tests_multifw.py`, `test_edit_blocks_never_write_markers.py` and `test_runner_registry.py`: 92 passed.
- Full `tests/unit`: 10839 passed, 68 skipped, 7 deselected, 6 xfailed in 12m 17s.
- Full suite (`pytest -q`, every tier): 11336 passed, 20 failed, 74 skipped. Nineteen of the twenty fail identically on `main` (`6098e1f7`) in the same environment: `tests/test_auto_reviewer_wait_loop.py` (16), `tests/tools/test_dependabot_review.py::TestRunJsGate` (2) and `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (1). The twentieth, `test_checkpoint_carries_no_enums.py::test_the_unit_tier_runs_the_serializer_strict`, asserts that `tests/unit/conftest.py` set strict msgpack before LangGraph was imported; it passes alone and in the full unit tier on this branch, and fails only when an earlier tier has already imported LangGraph during whole-suite collection. This change adds no LangGraph import outside `tests/unit`.
- `ruff check`: the three edited node files carry the same findings on this branch and on `main` (9, 3 and 13). `runner_registry.py` carries one, the `I001` on the inline import inside `get_runner`, which `main` carries at line 123; it moved to 144.
