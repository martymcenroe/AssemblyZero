# Test Report: the implementation-spec workflow under standard 0034 (#3585 step 5, first half)

Each fixed site has a test that fails before its fix and passes after, run against the unchanged module first. Filled in module by module.

## graph.py

**New: `tests/unit/test_spec_graph_loud_failure.py` (11).** Five tests are named for the N3 unrouted-error entry: three router states that carry an `error_message` (below the cap, beside a pass, beside a grace), the loud-failure scan of the spec graph, and a graph built from the real router and the real HALT node, with the edge map read from the compiled graph, asserting one alert. Four pin kept routes: a failure with no error revises, a grace with no error revises, the cap with no grace halts, and a revision does not alert. Two pin the rows #3887 fixed (265 and 513).

**Before the fix, measured:** 5 failed, 6 passed. The three router tests got `N2_generate_spec`, `N5_review_spec` and `N2_generate_spec`; the scan still found the N3 entry; the graph test visited N2 and sent no alert. The six that passed pin kept behaviour.

**Changed tests:** none.

**Neighbouring suites:** 427 passed and 1 skipped across `test_cap_grace_for_untried_check.py`, `test_ceiling_one_authority.py`, `test_check_classification.py`, `test_failopen_tags_3767.py`, `test_implementation_spec_workflow.py`, `test_graph_atlas.py`, `test_spec_finalize_halts.py`, `test_review_convergence.py`, `test_issue_248.py`, `test_node_modules_supply_nodes.py`, `test_stage_verdict_is_explicit.py` and `test_cap_bundles.py`; 127 passed across `test_gate_registry.py`, `test_call_recording_roll.py`, `test_commit_message_guard_retired.py`, `test_mock_roll.py`, `test_orchestrator_lineage.py`, `test_orchestrator_repo_targeting.py`, `test_profile_bench.py` and `test_spec_rides_lld_pr.py`.

**Audits:** `audit_loud_failure.py --check`: 0 new, 1 stale (the entry above). `audit_fail_open.py --check`: no new fail-open.
