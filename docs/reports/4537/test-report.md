# Test Report: a runtime requirement lands where the target runs it (#4537)

`tests/unit/test_lld_runtime_homes_4537.py` has 32 tests, and all of them pass. The fixture `tests/fixtures/lld_runtime_homes/lld-runtime-mechanic-in-offline-module.md` holds the approved LLD's requirements and file list, with the target's identity removed.

- T1 (AC1): `test_t1_refused_naming_the_observation_generator_and_the_engine_file`. The test fails on `main`, where the module does not exist. Its control, `test_t1_the_same_plan_with_the_engine_listed_passes`, clears validation with no errors.
- T2 (AC2): `test_t2_an_issue_naming_the_observation_returns_the_engine_file`. Further tests cover a type declared in one file and built in another, Python read with `ast`, the drafter's first prompt, and a revision that sees the homes and their signatures.
- T3 (AC3): `test_t3_the_prompt_asks_of_every_requirement_which_listed_file_implements_it`. Further tests cover the reviewer seeing the homes and the Tier 1 row in the standing instructions.

Two smoke runs read the real tree and wrote nothing.

- **The private target.** Run on the issue text as the original run read it, the finder homes `Observation` in the engine file in 0.4 s. It refuses requirements 3, 5, 7, 8, 9 and 10 of the approved LLD.
- **AssemblyZero.** Across 45 recent issues it homes only camel-case code names, in 2 to 5 s per run. The first version also homed `Section` (from "Section 6") and `Coverage` (a table cell). The tokenizer rules for number labels, table cells and fenced blocks now exclude them.

The full suite against the worktree gave 14,425 passed, 66 skipped, 7 xfailed and 19 failed. None of the 19 comes from this change, and each fails the same way on `main` in the primary checkout:

- 16 in `tests/test_auto_reviewer_wait_loop.py` (#4528).
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (#4529).
- `tests/test_universal_claude_md.py::test_adr_references_resolve` (#3730).
- `tests/unit/test_checkpoint_carries_no_enums.py::test_the_unit_tier_runs_the_serializer_strict`, which fails only in a whole-tree run and passes when `tests/unit` is collected alone. It is now filed as #4540.

The audit ratchets (gate registry, halt-site renumbering, fail-open, loud failure) pass. Ruff reports no new findings in the changed files.
