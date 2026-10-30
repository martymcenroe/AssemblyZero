# Test Report: the implementation-spec workflow under standard 0034 (#3585 step 5, first half)

Each fixed site has a test that fails before its fix and passes after, run against the unchanged module first. Filled in module by module.

## graph.py

**New: `tests/unit/test_spec_graph_loud_failure.py` (11).** Five tests are named for the N3 unrouted-error entry: three router states that carry an `error_message` (below the cap, beside a pass, beside a grace), the loud-failure scan of the spec graph, and a graph built from the real router and the real HALT node, with the edge map read from the compiled graph, asserting one alert. Four pin kept routes: a failure with no error revises, a grace with no error revises, the cap with no grace halts, and a revision does not alert. Two pin the rows #3887 fixed (265 and 513).

**Before the fix, measured:** 5 failed, 6 passed. The three router tests got `N2_generate_spec`, `N5_review_spec` and `N2_generate_spec`; the scan still found the N3 entry; the graph test visited N2 and sent no alert. The six that passed pin kept behaviour.

**Changed tests:** none.

**Neighbouring suites:** 427 passed and 1 skipped across `test_cap_grace_for_untried_check.py`, `test_ceiling_one_authority.py`, `test_check_classification.py`, `test_failopen_tags_3767.py`, `test_implementation_spec_workflow.py`, `test_graph_atlas.py`, `test_spec_finalize_halts.py`, `test_review_convergence.py`, `test_issue_248.py`, `test_node_modules_supply_nodes.py`, `test_stage_verdict_is_explicit.py` and `test_cap_bundles.py`; 127 passed across `test_gate_registry.py`, `test_call_recording_roll.py`, `test_commit_message_guard_retired.py`, `test_mock_roll.py`, `test_orchestrator_lineage.py`, `test_orchestrator_repo_targeting.py`, `test_profile_bench.py` and `test_spec_rides_lld_pr.py`.

**Audits:** `audit_loud_failure.py --check`: 0 new, 1 stale (the entry above). `audit_fail_open.py --check`: no new fail-open.

## nodes/validate_completeness.py

**New: `tests/unit/test_validate_completeness_loud_failure.py` (57).** Each test is named for its ledger line, one or more per site, plus tests that pin what is kept: an empty draft below the cap revises, a complete state reaches a verdict, no pattern references and no pyproject are answers, tagged criteria still gate, a probe that answers is read, no repo root owns no packages, an untagged fence that does not parse is counted and passed over, a resolvable stdlib base still lends its methods, and the two rows #3767 fixed (1725, 1746).

**Before the fix, measured** against the unchanged module: 45 failed, 12 passed. The 12 are the kept-behaviour pins. The 45 failed on their sites: 28 did not raise, 4 still passed, 3 had no `completeness_cannot_check`, 6 found a tag, and one each found no unresolved base in the details, "skipped" in the details, `api_symbols_exist` where `python_fences_parse` belongs, no extractor refusal, and an empty cap message.

**Changed tests, each asserting the new behaviour in place of the retired one:**
- `test_assertion_manifest.py`: a python fence that does not parse fails the diff and names lines 9-11, and a new test keeps the untagged abstention.
- `test_criteria_coverage.py`: an absent LLD raises; `test_the_node_runs_the_check` reads `_run_checks`.
- `test_first_party_mid_build.py` and `test_implementation_spec_workflow.py`: a malformed pyproject raises.
- `test_hallucination_telemetry.py`: a telemetry failure halts N3 with its cause.
- `test_implementation_spec_workflow.py`: empty symbols raise for a call that needs them.
- `test_import_checker_env.py`: an environment that cannot answer stops the import check.
- `test_section_ten_carries_tests.py`: no Section 10 fails, and the complaint reads as a demand to add.
- `test_spec_test_suite_checks.py`: a block that does not parse fails; text that is not TOML raises; a broken pyproject stops the check; a missing one is reported as "the checkout has no pyproject.toml".

**Changed tests that used an empty repo root or LLD as a shortcut** now get a temporary repo and an LLD with one REQ-tagged criterion, with assertions unchanged: `test_halt_legibility.py`, `test_density_heuristic_advisory.py`, `test_ceiling_one_authority.py`, `test_completeness_pinning_deadlock.py`, `test_pinning_conservation.py`, `test_builtin_methods_and_opaque_receivers.py`, `test_hallucination_telemetry.py` (and a probe that answers "imports none"), and `test_implementation_spec_workflow.py`, whose complete spec gains a Section 10. Four tests that had become vacuous on the halt now assert that the checks ran, or that the pass happened.

**Before the test changes, measured:** the 44 files naming the module gave 45 failed, 958 passed. All 45 passed with HEAD's module, so none was pre-existing.

**Neighbouring suites:** 1004 passed across the 44 test files that name the module (1003 in the full run, plus the one corrected line range); 150 passed across `test_assertion_manifest.py`, `test_gate_registry.py`, `test_check_classification.py` and `test_completeness_message_addressability.py`; 131 passed across `test_golden_disasters.py`, `test_factory_report.py`, `test_interaction_matrix.py` and `test_cap_bundles.py`.

**Audits:** `audit_loud_failure.py --check`: 0 new, 10 stale (the graph entry and nine here). `audit_fail_open.py --check`: no new fail-open.
