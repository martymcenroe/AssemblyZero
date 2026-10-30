# Test Report: the implementation-spec workflow under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, run against the unchanged module first. The package was swept in two halves and assembled on one branch; each half's sections follow in its order.

## The first half

### graph.py

**New: `tests/unit/test_spec_graph_loud_failure.py` (11).** Five tests are named for the N3 unrouted-error entry: three router states that carry an `error_message` (below the cap, beside a pass, beside a grace), the loud-failure scan of the spec graph, and a graph built from the real router and the real HALT node, with the edge map read from the compiled graph, asserting one alert. Four pin kept routes: a failure with no error revises, a grace with no error revises, the cap with no grace halts, and a revision does not alert. Two pin the rows #3887 fixed (265 and 513).

**Before the fix, measured:** 5 failed, 6 passed. The three router tests got `N2_generate_spec`, `N5_review_spec` and `N2_generate_spec`; the scan still found the N3 entry; the graph test visited N2 and sent no alert. The six that passed pin kept behaviour.

**Changed tests:** none.

**Neighbouring suites:** 427 passed and 1 skipped across `test_cap_grace_for_untried_check.py`, `test_ceiling_one_authority.py`, `test_check_classification.py`, `test_failopen_tags_3767.py`, `test_implementation_spec_workflow.py`, `test_graph_atlas.py`, `test_spec_finalize_halts.py`, `test_review_convergence.py`, `test_issue_248.py`, `test_node_modules_supply_nodes.py`, `test_stage_verdict_is_explicit.py` and `test_cap_bundles.py`; 127 passed across `test_gate_registry.py`, `test_call_recording_roll.py`, `test_commit_message_guard_retired.py`, `test_mock_roll.py`, `test_orchestrator_lineage.py`, `test_orchestrator_repo_targeting.py`, `test_profile_bench.py` and `test_spec_rides_lld_pr.py`.

**Audits:** `audit_loud_failure.py --check`: 0 new, 1 stale (the entry above). `audit_fail_open.py --check`: no new fail-open.

### nodes/validate_completeness.py

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

**Changed later (found by the compile_manifest batch):** `test_call_recording_roll.py::TestARecordedRollReplaysExactly` (2 cases) failed after this module's commit. Its LLD's one criterion carried no REQ tag, and N3 now halts on that (1892) instead of passing it as "not applicable". The scenario now carries REQ-1, and the spec's test cites it in a docstring; 6 passed. The file does not name this module, which is why the sweep over files that do missed it.

### nodes/compile_manifest.py

**New: `tests/unit/test_compile_manifest_loud_failure.py` (24).** Each test is named for its ledger line, plus tests that pin what is kept: a repo with no gate declaration compiles, a compiled manifest is persisted, an ordinary LLD sits out and records why (89, WON'T DO), a mock run files nothing and still halts (186), a working filing files one per criterion, a recorded absence and a recorded abstain pass N1c (230, the abstain half WON'T DO), and rows with their criteria list pass.

**Before the fix, measured** against the unchanged module: 16 failed, 8 passed. The 8 are the kept-behaviour pins. Of the 16, six halts did not happen, five tags were present, one filing failure sent no alert, and two N1c findings were empty. The other two, 198 and 199, call `_file_failures` with its new signature, so before the fix they failed on its missing `mock_mode` argument rather than on the behaviour.

**Changed tests:** `test_assertion_manifest.py::TestTheCompileNode` and `test_decision_table_survives.py::TestTheNodeTravelsTheAbsenceForward` get a temporary repo root. The abstain-gate state in `test_decision_table_survives.py` carries the `assertion_manifest_absent` flag N1b always writes. `test_a_bare_pass_through_still_works` became `test_a_recorded_absence_passes_through` and `test_a_bare_state_with_no_recorded_absence_is_a_finding`. All 11 tests these fixed passed with HEAD's module, so none was pre-existing.

**Neighbouring suites:** 336 passed across `test_assertion_manifest.py`, `test_decision_table_survives.py`, `test_implementation_spec_workflow.py`, `test_spec_graph_loud_failure.py`, `test_gate_registry.py` and the new file. 446 passed across the 22 other test files that name the manifest or the spec graph, including the mock-roll, orchestrator and recorded-roll suites.

**Audits:** `audit_loud_failure.py --check`: 0 new, 17 stale (1 graph, 9 validate_completeness, 7 here). `audit_fail_open.py --check`: no new fail-open.

## The second half

Each new test file names its tests `test_<line>_...` after the ledger row they pin. Every file was first run against the unchanged module: each site test failed and each test of kept behaviour passed.

### `base_tree.py`

- **Added:** `tests/unit/test_base_tree_loud_failure.py`, 18 tests. Before the fix: 8 failed, 10 passed. After: 18 passed.
- **Changed**, each of which relied on the retired local-branch fallback:
  - `test_spec_base_aware.py`: `test_a_base_that_does_not_exist_is_not_fatal` is now `test_a_base_that_does_not_exist_raises`;
  - `test_import_checker_base.py`, `test_import_check_names_the_real_module.py` and `test_call_recording_roll.py`: their fixtures push the base branch to a bare origin.
- **Neighbouring suites:** `test_spec_base_aware`, `test_import_checker_base`, `test_import_check_names_the_real_module`, `test_spec_calls_existing_code`, `test_failopen_tags_3767`, `test_import_checker_env`, `test_base_api_surface`, `test_base_symbols_in_api_check`, `test_call_recording_roll`, `test_resume_after_ceiling_halt`, `test_stage_verdict_is_explicit`, `test_first_party_mid_build`, `test_mock_roll` and `test_implementation_spec_workflow` (207 passed): all pass.
- **Audits:** `audit_loud_failure.py --check` PASS at 280; `audit_fail_open.py --check` PASS, no new fail-open.

## `nodes/analyze_codebase.py`

- **Added:** `tests/unit/test_spec_analyze_codebase_loud_failure.py`, 40 tests, named `test_spec_...` because the requirements workflow has a module of the same name. Before the fix: 30 failed, 10 passed. Two of the 10, for lines 988 and 1044, had been fixed by the `base_tree.py` commit; with `base_tree.py` put back at `552149a1` both fail. After: 40 passed.
- **Changed**, each of which asserted retired behaviour:
  - `test_implementation_spec_workflow.py`: `test_040_file_not_found_graceful` is now `test_040_file_not_found_halts`, and `test_empty_files_list` is now `test_empty_files_list_halts`;
  - `test_cache_semi_static.py`: the plan carries one Add, since an empty plan halts;
  - `test_symbol_gather_reports_unreadable.py`: the line says the stage halts, not that the file was excluded, and the node test reads `_analyze`;
  - `test_base_api_surface.py` and `test_base_symbols_in_api_check.py`: a ref git cannot read raises `BaseTreeError`;
  - `test_call_recording_roll.py`: the LLD's Files Changed table parses, so the roll no longer runs with an empty plan.
- **Neighbouring suites:** every unit test file that imports the spec workflow ran: 1,014 passed and 8 failed, the 8 being the roll, gate-registry and section-ten tests changed or answered above. After the loop was restructured, the 17 files closest to the node ran again: 501 passed.
- **Audits:** `audit_loud_failure.py --check` PASS at 280; `audit_fail_open.py --check` PASS, no new fail-open. The fail-open baseline has 11 stale `analyze_codebase` entries, for the parent's regeneration.

## `nodes/finalize_spec.py`

- **Nothing to change.** Every row was settled by #3887 and #3891 (PR #3901).
- **Added:** `tests/unit/test_finalize_spec_loud_failure.py`, 4 tests, for the rows `test_spec_finalize_halts.py` does not reach: the short draft (137), the temp-file cleanup (219), a failed write (224) and a spec absent after the write (234). They pass before and after, since the module is unchanged.

## `nodes/generate_spec.py`

- **Added:** `tests/unit/test_generate_spec_loud_failure.py`, 20 tests. Before the fix: 14 failed, 6 passed; the 6 pin kept behaviour and the compliant preflight, drafter and budget halts. After: 20 passed.
- **Changed**, each of which relied on retired behaviour:
  - `test_generate_spec_pinning.py`: every state has a lineage directory, and `test_an_unextractable_verdict_abstains` is now `test_an_unextractable_verdict_halts`;
  - `test_spec_edit_script.py`: a lineage directory, and a complaint that backticks the functions the edits touch;
  - `test_diff_aware_review.py`: a lineage directory, and feedback that backticks a span;
  - `test_implementation_spec_workflow.py`: the `TestGenerateSpec` tests get a lineage directory, `TestTruncatePrompt` exercises `_fit_to_budget`, and `TestSplitIntoSections` is deleted with the function it tested;
  - `test_call_recording_roll.py`: the lineage directory exists before N2.
- **Neighbouring suites:** 17 files, 468 passed.
- **Audits:** `audit_loud_failure.py --check` reports 0 new and 1 stale, the withdrawn tag; `audit_fail_open.py --check` PASS.

## `nodes/load_lld.py`

- **Added:** `tests/unit/test_spec_load_lld_loud_failure.py`, 19 tests, named `test_spec_...` because the testing workflow has a module of the same name. Before the fix: 12 failed, 7 passed. After: 19 passed.
- **Changed** in `test_implementation_spec_workflow.py`: the two `TestParseLldTable` tests that expected `[]` for a missing table, and `test_unknown_defaults_to_add`, now expect `ValueError`.
- **Neighbouring suites:** 16 files, 514 passed after the three changes.
- **Audits:** `audit_loud_failure.py --check` 0 new; `audit_fail_open.py --check` PASS.
