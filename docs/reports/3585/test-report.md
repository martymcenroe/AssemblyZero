# Test Report: the requirements workflow under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on two branches and assembled on `3585-requirements-landing`: the graph and nodes on `3585-requirements-nodes`, then the support modules on `3585-requirements-support`, each keeping its own sections below.

## nodes/finalize.py

**New: `tests/unit/test_finalize_loud_failure.py` (39).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against HEAD's `finalize.py`: 30 failed, 9 passed. Every site test failed except two:
- 487, which #3864's router already halts;
- the whitespace-only case of the empty-LLD test, which the core batch's question scan already refuses.

The other seven pin a well-formed issue URL, an idea that is present and one never declared, a numeric `max_iterations`, a clean LLD, a file outside the repo passing through (297) and a failed filing logging nothing complete.

**Changed tests, each asserting the new behaviour:**
- `test_failopen_tags_3767.py`, `test_first_pass_tracking.py` and `test_lld_writes_only_worktree.py`: each state now carries an audit_dir that exists, because finalize halts without one. The worktree file's no-audit-dir test asserts the halt.
- `test_finalize_repair_routing.py`: the no-issue-number message names the repo.
- `test_orchestrator_lands_through_driver.py`: a failed landing is read from stderr, and `error_message` carries it.
- `test_requirements_nodes.py`:
  - three save tests keep the landing out of scope, because their targets are not git repos;
  - a REVISE LLD halts;
  - a nonexistent audit_dir halts;
  - a URL with no issue number halts.
- `test_requirements_validation.py`: an empty LLD fails validation.

**Neighbouring suites:** 562 passed across 29 files: every file that imports finalize, the mock runs, the graph tests and the gate registry. After the last edits, the 10 affected files ran again: 274 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 1 stale, the deleted tag. `audit_fail_open.py --check` reports no new fail-open. Ruff on `finalize.py` finds the same 17 issues as at HEAD.

**The mock issue run (its own commit):** three tests in `TestAMockRunFilesNothing`.
- **Against the finalize then on the branch:** 2 failed, 1 passed. The failures are that `gh` and `subprocess.run` were called under mock mode, and that a full mock `finalize()` called them. The one that passed is that a real run still files.
- **After the change:** the 15 files that run the issue workflow, its CLI, the mock runs and the gate registry gave 481 passed.

## graph.py

**New: `tests/unit/test_requirements_graph_loud_failure.py` (30).** One test per ledger line, then:
- every router given an error, which must halt;
- every node of the compiled graph, which must have a HALT edge.

**Before the fix, measured:** 8 failed, 22 passed.
- The 8 failures are the two human-gate routers, which went on to `next_node` with an error set.
- The 22 that passed are the ledger rows: #3864 had already routed seven of them, and two were compliant.

**Changed tests:** none.

**Neighbouring suites:** 424 passed and 1 skipped across 18 files that build or route the requirements graph.

## nodes/generate_draft.py

**New: `tests/unit/test_generate_draft_loud_failure.py` (20).**

**Before the fix, measured:** 15 failed, 5 passed. Every site test failed. The 5 that passed pin kept behaviour:
- a present audit_dir records the draft;
- a prompt at the cap is sent whole;
- a readable prior draft rides in the system prompt;
- a draft naming no Python files uses the N0b map;
- a draft with no open-questions section passes.

**Changed tests, each asserting the new behaviour:**
- `test_prompt_size_awareness.py`: its truncator tests became halt tests.
- `test_interface_surface.py`: one truncation test became a test that nothing is cut.
- `test_requirements_validation.py`: an empty draft blocks.
- `test_requirements_nodes.py`: a missing audit_dir halts. Two other tests gained an audit_dir.
- `test_lld_edit_script_revision.py`, `test_lld_mock_completes.py` and `test_diff_aware_review.py`: each state now has a target directory or an audit_dir that exists.

**Neighbouring suites (generate_draft):** the first run across 45 files gave 22 failures. Each was a test asserting retired behaviour: a missing audit_dir or target repository tolerated. After those tests were changed, and after the seat-handling change, the run across 47 files gave 987 passed and 1 skipped.

## nodes/analyze_codebase.py

**New: `tests/unit/test_analyze_codebase_loud_failure.py` (19).**

**Before the fix, measured:** 14 failed, 5 passed. Every site test failed except 153, which #3864's router already halts. The other four that passed pin kept behaviour:
- an empty key file is skipped quietly;
- a related binary file is skipped quietly;
- a repo with no Python has an empty surface;
- a file outside the repo is skipped (460).

**Changed tests:** `test_analyze_codebase.py`. The no-repo-path and missing-repo classes now expect the halt and an ERROR in the log, where they expected an empty context and a warning.

**Neighbouring suites:** 494 passed across 21 files: the analysis tests, the interface surface, the requirements graph, the mock runs, the CLI and the gate registry.

## nodes/analyze_requirements.py

**New: `tests/unit/test_analyze_requirements_loud_failure.py` (19).**

**Before the fix, measured:** 15 failed, 4 passed. Every site test failed. The 4 that passed pin kept behaviour:
- an empty findings list is a clean verdict;
- a calm storm probe reads False;
- a mock run reads nothing;
- a conflict that does not reproduce proceeds (779, #3767).

**Changed tests, each asserting the new behaviour:**
- `test_n0c_unarticulated_conflict.py`: an all-unarticulated verdict halts unverified, names the pairing, files nothing and writes no proceeded record.
- `test_requirements_gate_timeout.py`: the last fail-open path halts and records nothing.
- `test_requirements_conflict.py`: an empty body halts unverified.
- `test_requirements_gate_escalation.py`: a broken escalation target halts, naming it, with no re-ask.

**Neighbouring suites:** the first run across 28 files gave 603 passed, 1 skipped and 3 failed.
- Two of the failures were tests of the retired behaviour, changed above.
- The third, `test_check_requirements.py::TestConflict::test_report_says_filing_failed_when_it_did`, showed that the standalone pre-check reads "must-resolve filing failed" from the gate's captured stdout. The gate prints that line again, beside the alert.

The 6 files involved then gave 154 passed.

## nodes/review.py

**New: `tests/unit/test_review_loud_failure.py` (18).**

**Before the fix, measured** against the unchanged module, on its first 17 tests: 13 failed, 4 passed. Every site test failed. The 4 that passed pin kept behaviour: a tiered REVISE with no Tier 1 issue is APPROVED, one with an issue is BLOCKED, a self-build needs no target block, and a clean approval goes forward with its verdict saved. The eighteenth, a Tier 1 section without a Tier 2 section read as BLOCKED, was added after the fix to pin the narrowed contract.

**Changed tests, each asserting the new behaviour:**
- `test_requirements_nodes.py`:
  - three REVISE responses carry their Tier sections;
  - two states gain an audit_dir;
  - `test_reviewer_failure_is_llm_format_error` became `test_reviewer_failure_halts_with_the_providers_cause`.
- `test_validate_test_plan_node.py::test_review_resets_counter`: a real target and audit_dir.
- `test_lld_review_reads_template.py`: its scripted provider says its calls succeeded.
- `test_structured_verdicts.py`: the verdict guesser is read from the parser module, and review's copy is gone.

**Neighbouring suites:** 28 files gave 553 passed, 1 skipped, 4 deselected (e2e) and 2 failed. The 2 are `test_extract_and_discard.py::TestBlockedVerdictExtraction::test_blocked_verdict_stores_summary_not_prose` and `::TestApprovedVerdictExtraction::test_approved_verdict_stores_summary_not_prose`. Both fail identically with HEAD's `review.py` swapped back in, and both test the testing workflow's `review_test_plan`, so they are pre-existing.

## nodes/human_gate.py

**New: `tests/unit/test_human_gate_loud_failure.py` (17).**

**Before the fix, measured:** 12 failed, 5 passed. Every site test failed in both modes. The 5 that passed pin kept behaviour: BLOCKED under the cap revises and APPROVED finalizes, in both modes, and a human who chooses to revise is not capped.

**Changed tests:** none.

**Neighbouring suites:** 18 files gave 447 passed and 1 skipped. They cover the interactive gates, the graph, the open-questions loop, the mock runs and the gate registry.

## nodes/load_input.py

**New: `tests/unit/test_load_input_loud_failure.py` (9).**

**Before the fix, measured:** 7 failed, 2 passed. Every site test failed, and so did the mock-run test, since the mock looked up the remote. The 2 that passed pin kept behaviour: an issue with a body loads, and a GitHub remote names the repo.

**Changed tests:** in `test_requirements_nodes.py`, `TestLoadInputRetryLogic`'s two retry tests script the provenance lookup's answer. Their call lists ran out there, and the swallowed StopIteration had read as "unknown/unknown".

**Neighbouring suites:** the first run across 17 files gave 430 passed and 2 failed: the two tests above. After the change, the two affected files gave 107 passed.

## nodes/validate_test_plan.py

**New: `tests/unit/test_validate_test_plan_loud_failure.py` (5).**

**Before the fix, measured:** 4 failed, 1 passed. Every site test failed. The one that passed pins kept behaviour: a failing draft is preserved and loops back.

**Changed tests:** `test_validate_test_plan_node.py::TestNodeRoutesToDraftOnFail::test_node_routes_to_draft_on_fail` gives its failing draft an audit_dir.

**Neighbouring suites:** 17 files gave 316 passed, 1 skipped and 1 failed: the test above. After the change, its file and the new one gave 19 passed.

## nodes/ponder.py

**New: `tests/unit/test_ponder_loud_failure.py` (6).**

**Before the fix, measured:** 3 failed, 3 passed. Every site test failed. The 3 that passed pin kept behaviour: no draft skips to N1.5 (35, compliant), a fixed draft is written back, and a fix record is written.

**Changed tests:** none.

**Neighbouring suites:** 14 files gave 321 passed and 1 skipped.

## nodes/validate_mechanical.py

**New: `tests/unit/test_validate_mechanical_loud_failure.py` (24).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against the unchanged module: 15 failed, 9 passed. Every site test failed. The nine that passed pin a good draft passing, an empty similar-file search, a path the base ships and one it does not, no base branch asking git nothing, a lineage record landing, no lineage folder staying quiet, the compliant blocked route (1775) and a passing draft recording nothing.

**Changed tests, each asserting the new behaviour:**
- `test_validate_mechanical.py`: `test_missing_number_returns_block_error` and `test_no_h1_returns_block_error` expect ERROR; they expected WARNING.
- `test_prompt_telemetry.py`: `test_telemetry_failure_alerts_and_stops_the_run` expects the raise and one alert; it expected the verdict to come back.

**Neighbouring suites:** 442 passed and 1 skipped across 21 files that run mechanical validation, with only the three tests above failing before they were changed; the three changed files and the new one then gave 136 passed.

**Known failures from the mock drafter's title** (each passes at the base commit; the run prints "Could not extract issue number from title"; the remedy is the mock's title in `llm_provider.py`):
- `test_lld_mock_completes.py::TestMockFinishesAnLLDRun::test_a_mock_lld_run_reaches_finalize_and_writes_the_lld`;
- `test_lld_writes_only_worktree.py::TestAMockRunLeavesTheCheckoutClean`, five tests;
- `test_lld_mock_is_offline.py::TestMockIsOffline`, three tests.

**The mock title, on the landing branch:** with the title above, the three files gave 9 failed and 7 passed, the nine being these. With the mock titled `# 42 - Feature: Mock rehearsal LLD`, they gave 16 passed. The provider, CLI, seat, mechanical-validation and finalize suites that read the mock (11 files) then gave 509 passed.

## audit.py

**New: `tests/unit/test_requirements_audit_loud_failure.py` (25).**

**Before the fix, measured** against the unchanged module: 15 failed, 10 passed. Every site test failed; the ten pin kept behaviour and the compliant row (816).

**Changed tests, each asserting the new behaviour:**
- `test_lld_cache_pruning.py`: seven tests key a deleted repo's slice by its path (`_dead_key`), since `_repo_key` now raises for a path with no repository behind it.
- `test_lld_cache_repo_isolation.py`, `test_lld_tracking.py`, `test_requirements_audit.py`: a corrupt, empty, non-object or unreadable cache raises and alerts; a missing or outside context file raises; a nonexistent repo raises from `get_repo_structure`.
- `test_move_lineage.py`: a missing lineage dir and a failed move alert and raise.
- `test_lld_edit_script_revision.py`: the fixture creates the target repo it names.

**Neighbouring suites:** 158 passed across the six changed files; 1473 passed across 58 files whose nodes call these functions, with three of the mock-title failures above and two pre-existing failures in `test_extract_and_discard.py` (KeyError 'test_plan_status'), which fail identically with the base `audit.py` and `validate_mechanical.py` swapped in.

## contract_fidelity.py

**New: `tests/unit/test_contract_fidelity_loud_failure.py` (16).**

**Before the fix, measured** with the base module swapped in: 12 failed, 4 passed. The four pin a repo with no contract, an issue the declaration does not cover, an empty findings list, and findings that report without refusing.

**Changed tests, each asserting the new behaviour (`test_contract_fidelity.py`):** an unparseable answer and a missing findings list raise; a fetch failure refuses with an alert; the "never refuses" test is renamed for what it asserts, an audit that reached a verdict.

**Neighbouring suites:** 102 passed across `test_contract_fidelity.py`, the new file and `test_seats.py`.

## precheck.py (fixed in `tools/check_requirements.py`)

**New: `tests/unit/test_precheck_loud_failure.py` (12).** Each test drives the tool's `main` through one failure.

**Before the fix, measured** with the base tool swapped in: 10 failed, 2 passed (a conflict and a clean verdict, which alert nobody).

**Changed tests:** none; exit codes and output are unchanged.

**Neighbouring suites:** 123 passed across `test_check_requirements.py`, `test_check_requirements_form.py` and the new file.

## form_gate.py

**New: `tests/unit/test_form_gate_loud_failure.py` (8).**

**Before the fix, measured** against the unchanged module: 7 failed, 1 passed (a good issue proceeds without an alert).

**Changed tests:** `test_form_gate.py`'s unreadable-issue test expects the refusal and an alert; `test_scope_coverage.py`'s scope-crash test expects the refusal; `tests/unit/conftest.py` gains the offline-preflight fixture.

**Neighbouring suites:** 117 passed across the form-gate, scope and discrimination files; 349 passed and 3 skipped across the 13 launcher files that the refusal had broken (53 failures without the fixture) and five related files.

## best_of_n.py

**New: `tests/unit/test_best_of_n_loud_failure.py` (12, with parameters).** Before the fix: 6 failed, 6 passed (the kept and compliant rows).

**Changed tests (`test_best_of_n.py`):** a crashing gate raises and alerts; a non-numeric count raises.

**Neighbouring suites:** 34 passed (`test_best_of_n.py` and the new file); 28 passed across the draft node's tests.

## parsers/draft_updater.py

**New: `tests/unit/test_draft_updater_loud_failure.py` (6).** Before the fix: 4 failed, 2 passed.

**Changed tests (`test_issue_257.py`):** five tests that expected warnings expect the ValueError.

**Neighbouring suites:** 149 passed across `test_issue_257.py`, the new file and `test_requirements_nodes.py`.

## verdict_summarizer.py

**New: `tests/unit/test_verdict_summarizer_loud_failure.py` (10).** Before the fix: 7 failed, 3 passed (a JSON verdict with its issues, feedback with no verdict line, an empty entry).

**Changed tests:** `test_verdict_summarizer.py`'s malformed-JSON test expects the ValueError and an ERROR line.

**Neighbouring suites:** 44 passed with `test_feedback_window.py`.

## git_operations.py

**New: `tests/unit/test_git_operations_loud_failure.py` (11).** Before the fix: 6 failed, 5 passed (no origin, an origin without the branch, an origin with it, a reused branch on the arc, and the compliant 330).

**Changed tests:** `test_requirements_git_operations.py` and `test_issue_162.py` answer the new `git rev-parse` call; the no-SHA test expects the raise.

**Neighbouring suites:** 225 passed across ten files.

## ownership_check.py and the form verdict

**New: `tests/unit/test_ownership_check_loud_failure.py` (4).** Before the fix: 3 failed, 1 passed (a fully tagged table).

**Changed tests:** seven assertions of `RESULT: PASS` on vacuous runs, in `test_ownership_check.py`, `test_check_requirements_form.py` and `test_scope_coverage.py`, now assert `RESULT: NOT CHECKED` and the parts it names.

**Neighbouring suites:** 309 passed across ten files.

## form_check.py, scope_coverage.py, step_budget.py, parsers/verdict_parser.py

**New:** `test_form_check_loud_failure.py` (3), `test_scope_coverage_loud_failure.py` (4), `test_step_budget_loud_failure.py` (6), `test_verdict_parser_loud_failure.py` (3). Before the fix every site test failed and every kept test passed, except form_check's kept test, which asserts the new `not_checked` attribute and so fails against the base module.

**Changed tests:** two vacuous-scope assertions in `test_scope_coverage.py`, the junk-cap test in `test_step_budget.py`, and two parser tests in `test_issue_257.py`.

**Neighbouring suites:** 220 passed across the module tests; 278 passed across the step budget's callers.

## config.py, discrimination_check.py, table_injection.py

**New:** `test_requirements_config_loud_failure.py` (5), `test_discrimination_check_loud_failure.py` (2), `test_table_injection_loud_failure.py` (4). Before the fix: every site test failed; the kept and compliant tests passed.

**Changed tests:** three invalid-config tests in `test_requirements_config.py` expect the raise at construction.

**Neighbouring suites:** 207 passed.

## The landing branch

The 11 commits of `3585-requirements-nodes` and the 12 of `3585-requirements-support` were picked onto `origin/main` at `21e32f12`, oldest first.

**Conflicts, two:**
- The first support commit met the nodes half's copy of this report and its sibling, each a whole-file add. Both are kept: one title and preamble for the package, the nodes sections, then the support sections, each unchanged.
- The audit commit and the drafter commit each wrote a comment over the target-repo `mkdir` in `test_lld_edit_script_revision.py`'s `lld_state` fixture. The one comment now gives both reasons.

**Baselines and audits:**
- `audit_loud_failure.py --check`: 0 new and 33 stale. `--write-baseline` removed the 33 and nothing else, so the count went from 258 to 225, and `BASELINE_CEILING` is 225.
- `audit_fail_open.py --check`: no new fail-open. `--strict` reported a moved denominator, so `--write-baseline` ran: 49 entries removed, all in `assemblyzero/workflows/requirements/`, and the counts moved (sites examined 10,022 to 10,081; findings 468 to 408).
- `audit_halt_sites.py --check --strict`: every site registered; the denominator moved from 162 halt sites to 188, and `--write-baseline` changed only that count. It then passed.

**The full unit tier,** run once, alone on the machine: 12,161 passed, 66 skipped, 7 deselected and 6 xfailed in 637 s, with no failures. Run again at landing on 2026-10-31, on the merge of `main` at `5a979824`, beside other sessions' work: 12,165 passed, 66 skipped, 7 deselected and 6 xfailed in 1,662 s, with no failures.

---

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

## `nodes/review_spec.py`

- **Added:** `tests/unit/test_review_spec_loud_failure.py`, 18 tests. Before the fix: 11 failed, 7 passed; the 7 pin compliant rows and kept behaviour. After: 18 passed.
- **Changed:**
  - `test_implementation_spec_workflow.py`: three `TestReviewSpec` tests get a lineage directory, and `test_empty_response_blocked` is now `test_empty_response_raises`;
  - `test_spec_conflict_filing.py`: a failed filing is asserted to alert the operator, not to print a WARNING.
- **Neighbouring suites:** 18 files, 511 passed after the changes.
- **Audits:** `audit_loud_failure.py --check` 0 new, 3 stale (two of them this module's); `audit_fail_open.py --check` PASS.

## `criteria_coverage.py`

- **Added:** `tests/unit/test_criteria_coverage_loud_failure.py`, 8 tests. Before the fix: 5 failed, 3 passed. After: 8 passed.
- **Changed:** two `test_criteria_coverage.py` tests that read "not applicable" now read "cannot be checked" and assert the report is not ok; `test_call_recording_roll.py` tags its one criterion and cites it in the scripted spec.
- **Neighbouring suites:** all 103 unit test files that import the spec workflow, in one run: 2,163 passed and 2 failed, the two roll tests fixed above (6 passed on rerun).
- **Audits:** `audit_loud_failure.py --check` 0 new; `audit_fail_open.py --check` PASS.

## `assertion_manifest.py`

- **Added:** `tests/unit/test_assertion_manifest_loud_failure.py`, 6 tests, including a pin of the abstention left unchanged. Before the fix: 2 failed, 4 passed. After: 6 passed.
- **Neighbouring suites:** 9 files, 271 passed.
- **Audits:** `audit_loud_failure.py --check` 0 new; `audit_fail_open.py --check` PASS.

## `lineage_seed.py`

- **Added:** `tests/unit/test_lineage_seed_loud_failure.py`, 7 tests. Before the fix: 4 failed, 3 passed. After: 7 passed.
- **Neighbouring suites:** 4 files, 59 passed.
- **Audits:** `audit_loud_failure.py --check` 0 new; `audit_fail_open.py --check` PASS.

## `revision_pinning.py`

- **Added:** `tests/unit/test_revision_pinning_loud_failure.py`, 5 tests, one of them through N2. Before the fix, with both changed modules put back: 3 failed, 2 passed. After: 5 passed.
- **Changed:** the two `test_pinning_conservation.py` tests that expected the revision emitted unenforced now expect `PinningMergeError`.
- **Neighbouring suites:** 14 files, 251 passed after the change.
- **Audits:** `audit_loud_failure.py --check` 0 new; `audit_fail_open.py --check` PASS.

## `nodes/retry_prompt_builder.py`

- **Added:** `tests/unit/test_retry_prompt_builder_loud_failure.py`, 5 tests. Before the fix: 1 failed, 4 passed. After: 5 passed.
- **Changed:** `test_retry_prompt_builder.py`'s sentinel test now expects the raise.
- **Neighbouring suites:** 3 files, 65 passed.
- **Audits:** `audit_loud_failure.py --check` 0 new; `audit_fail_open.py --check` PASS.

## Four one-site modules: `error_path_coverage.py`, `review_progress.py`, `nodes/human_gate.py`, `table_injection.py`

- **Added:** four test files, 19 tests in all. Before the fix, with the four modules and `generate_spec.py` put back: 9 failed, 10 passed. After: 19 passed. The table-injection file is named `test_spec_...` because the requirements workflow has a module of the same name.
- **Changed:**
  - `test_spec_stage_pair.py`: a spec with no implementation fence cannot be checked, and is not ok;
  - `test_implementation_spec_workflow.py`: `test_t050` gains one implementation fence so the error-path check runs, and the disabled-gate test now expects a halt;
  - `test_call_recording_roll.py`: the scripted spec gains an implementation fence;
  - `test_review_convergence.py`: a garbage cap now raises.
- **Neighbouring suites:** all 116 unit test files that import the spec workflow, with the error-path change: 2,402 passed. With all four changes, the 26 closest files: 725 passed.
- **Audits:** `audit_loud_failure.py --check` 0 new, 4 stale (the earlier modules'); `audit_fail_open.py --check` PASS.

## The landing tier

Run on 2026-10-31 on the merge of `main` at `5ebba1ad` (the requirements package): 12,430 passed, 66 skipped, 7 deselected and 6 xfailed in 813 s, with no failures. The merge's only conflict beyond the reports and baselines was a test file both packages named `test_human_gate_loud_failure.py`; the spec's is now `tests/unit/test_spec_human_gate_loud_failure.py`. After the tier, `main`'s one further commit changed only ledger rows.

---

# Test Reports: the testing workflow under standard 0034 (#3585 step 5)

The package was swept in five batches from `fc1b2b0f` and merged on one branch. Each batch's report follows whole, under its own title, in merge order: C, B, D, E, A.

---

# Test Report: the testing graph and three of its nodes under standard 0034 (#3585 step 5, batch C)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-graph`. No test makes a model call, and no workflow is run against a repository; routers and nodes are called directly with built state, the one graph roll stubs every node it passes through, and alerts are asserted through the `operator_alerts` fixture.

## graph.py

**New: `tests/unit/test_testing_graph_loud_failure.py` (37).** Each site test is named for its ledger line; the rest pin kept behaviour and the stop wrapper's identity.

**Before the fix, measured** against HEAD's `graph.py`: 32 failed, 5 passed. The five that passed pin a working checkpoint, an N1 error without auto_mode, a BLOCKED plan under the revision cap, the augment path under budget, and N7.5's halt (557).

**Changed tests:** in `test_testing_workflow.py`, eight router tests that asserted `end` (or N2 under auto) now assert HALT or a revision; in `test_revise_test_plan.py`, the cap and strict tests assert HALT and the two auto tests assert a revision; `test_test_plan_revision_budget.py::test_what_the_defect_actually_was` now finds a halt with the budget reason and a bundle; `test_impl_verdict_integrity.py::test_the_cap_still_stops_the_loop`, two tests in `test_coverage_routes_to_tests.py`, `test_red_phase_retry_semantics.py::test_existing_routes_are_unchanged[END-HALT]` and `test_spec_stage_pair.py::test_an_exhausted_scaffold_no_longer_reaches_implementation` assert HALT.

**Neighbouring suites:** 28 files that import the graph, its routers, the atlas, the gate registry or the halt node: 434 passed, 1 skipped, and the two stale-baseline tests failed as expected. 18 impl, mock-roll, CLI and orchestrator files that build or invoke the graph: 306 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 1 stale, the checkpoint wrapper's handler. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes with every site registered. Ruff finds no issue in the module that is not at HEAD; the new test file is clean.

## nodes/load_lld.py

**New: `tests/unit/test_load_lld_loud_failure.py` (27).** Each site test is named for its ledger line; the eight compliant rows are pinned, and a control spec carries everything the halting tests remove.

**Before the fix, measured** against HEAD's `load_lld.py` with the first 26 tests: 15 failed, 11 passed. The eleven that passed are the control, the quiet "no functions" answer, a clean rebuild miss, and the eight compliant pins. The 27th test, added with the fix, checks that `validate_spec_structure` raises exactly the reason `spec_structure_error` gives.

**Changed tests:** each a fixture that relied on a missing files table or test plan being accepted, or an assertion of the old empty list: `test_extract_files_fencing.py::test_table_inside_code_fence_is_skipped` and `test_testing_workflow.py::test_extract_files_to_modify_no_table` expect the raise; the specs in `test_testing_workflow.py` (two tests), `test_implement_from_lld_cli.py`, `test_per_framework_coverage_target.py` and `test_two_frameworks_one_run.py` gain a files table; `test_ts_path_resolves_to_its_runner.py`'s helpers write a three-column table and a Section 10 test plan, and `test_two_frameworks_one_run.py`'s issue-only body carries both.

**Neighbouring suites:** 27 files that import the module or its functions, the spec workflow's three checks that call the extractor, the answer key and `tests/integration/test_lld_parsing_chain.py`: 670 passed after the fixture updates. The first pass, before them, failed 11, each one of those fixtures.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 more stale, the rebuild handler and its tag. `audit_fail_open.py --check` reports no new fail-open, and none is left in the module. `audit_halt_sites.py --check` passes. Ruff finds the module's same three issues as at HEAD; the new test file is clean.

## nodes/augment_tests.py

**New: `tests/unit/test_augment_tests_loud_failure.py` (32).** Each site test is named for its ledger line. The node runs with the model call and the vetting pytest run patched, in a temporary worktree with a small package, a test file and an audit dir; no model is called.

**Before the fix, measured** against HEAD's `augment_tests.py`: 29 failed, 3 passed. The three that passed pin the compliant fallback to bare lines (142), the quiet "nothing to remove" answers of `_without_named_tests`, and the clean success path.

**Changed tests:** in `test_n4c_keeps_the_suite_and_bounds_output.py`, the no-audit-dir test is now `test_no_audit_dir_halts_before_any_call`; the timed-out generation, the vetting run that collects nothing, and no addition passing expect the halt with the file as it was; the dropped-tests tests read the drops at ERROR on stderr, and the one whose repair call fails expects that halt. In `test_coverage_routes_to_tests.py`, the two node tests that returned to N5 are now `test_node_halts_when_nothing_to_target` and `test_node_halts_with_no_test_file`.

**Neighbouring suites:** 12 files that import the module, with the gate registry, the graph halts and the new file: 250 passed and 8 failed on the first pass, each one of the tests above; the three changed files then passed (78).

**Audits:** `audit_loud_failure.py --check` reports 0 new and 3 more stale, the three deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's same nine issues as at HEAD; the new test file is clean.

## nodes/e2e_validation.py

**New: `tests/unit/test_e2e_validation_loud_failure.py` (23).** Each site test is named for its ledger line; the three compliant rows and the no-E2E-test finalize are pinned. pytest is patched at `run_command`, so no test runs a suite.

**Before the fix, measured** against HEAD's `e2e_validation.py` with the first 22 tests: 16 failed, 6 passed. The six that passed pin the advisory count (45), the finalize for a run with no E2E test (313, 337), the circuit breaker (394), the cap (417) and the exit-1 loop to N4. The 23rd, added with the fix, checks that a file is judged by its path inside the repository.

**Changed tests:** in `test_testing_workflow.py`, `test_run_e2e_tests_timeout` and `test_run_e2e_tests_not_found` expect `E2ERunFailed`, `test_cleanup_sandbox` and `test_verify_safety_limits` expect `NotImplementedError`, and `test_e2e_validation_with_sandbox` expects the halt before any test runs.

**Neighbouring suites:** 15 files that name the node or N6, with the mock rolls and the gate registry: 532 passed after the updates. The first pass failed 5, the tests above.

**Audits:** `audit_loud_failure.py --check` reports 0 new; the module had no baseline entry. `audit_fail_open.py --check` reports no new fail-open, and the module's two baseline entries are stale. `audit_halt_sites.py --check` passes. Ruff finds the module's one issue at HEAD; the new test file is clean.


---

# Test Report: the testing workflow's implementation subpackage under standard 0034 (#3585 step 5, batch B)

Each module's new test file was run against the unchanged module first; every site test failed there, and every test that pins kept behaviour passed. No test makes a model call: `call_claude_for_file` and the provider gate behind it are replaced.

## orchestrator.py

- New: `tests/unit/test_orchestrator_loud_failure.py`, 32 tests (26 site tests, 6 that pin kept behaviour).
- Before the fix: 26 failed, 6 passed. After: 32 passed.
- Changed existing tests: five files ran `implement_code` in a temporary directory that was not a git repository and relied on `came_from_base` reading that as "untracked". Each now initialises a repository, as N4's worktree always is: `test_implement_code_timeout.py` (1 test), `test_modify_on_missing_is_an_add.py` (fixture), `test_n4_registers_every_framework.py` (helper, 4 tests), `test_planned_imports_resolve.py` (fixture), `test_testing_workflow.py` (3 tests).
- Neighbouring suites: the 56 unit test files that import the implementation package, the `implement_code` shim or the nodes package, plus `test_run_implement_from_lld_loud_failure.py`: 1031 passed and 10 failed, all ten the case above; after the change, the ten pass.
- Audits: `audit_loud_failure.py --check` 0 new, 7 stale (the baseline entries this fix removed); `audit_fail_open.py --check` no new fail-open; `audit_halt_sites.py --check` PASS, 162 sites registered.

## keep_passing_tests.py

- New: `tests/unit/test_keep_passing_tests_loud_failure.py`, 11 tests. Before the fix: 7 failed, 4 passed (the kept-behaviour pins). After: 11 passed.
- Changed existing tests in `test_n4_keeps_passing_tests.py`: five tests that asserted a quiet pass-through now assert the raise; two source-text tests search for the keep and release calls without their closing parenthesis, since the calls now pass the path.
- Neighbouring suites (the module's importers, the orchestrator's, and the green-phase contract tests): 114 passed and 2 failed, the two source-text tests; after the change, 80 passed in the three files they touch.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## parsers.py

- New: `tests/unit/test_parsers_loud_failure.py`, 7 tests. Before the fix: 4 failed, 3 passed. After: 7 passed.
- Changed existing test: `test_zero_needs_denominator.py::TestConftestOptionValidation::test_unparseable_new_code_abstains_here` becomes `test_unparseable_new_code_stops_here` and asserts the SyntaxError.
- Neighbouring suites (the ten unit files that import the parsers): 150 passed and 1 failed, the test above; after the change, 20 passed in the two files it touches.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## edit_script_fix.py

- New: `tests/unit/test_edit_script_fix_loud_failure.py`, 9 tests. Before the fix: 5 failed, 4 passed. After: 9 passed. Rows 497, 503 and 507 are tested in `test_orchestrator_loud_failure.py`.
- Changed existing test: `test_failure_attribution_by_test_body.py::test_an_unparseable_planned_file_attributes_nothing` becomes `test_an_unparseable_planned_file_stops_attribution` and asserts the SyntaxError.
- Neighbouring suites (the 13 unit files that import the module or its functions): 192 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## deprecated.py

- New: `tests/unit/test_deprecated_loud_failure.py`, 8 tests. Before the fix: 5 failed, 3 passed. After: 8 passed.
- Changed existing tests in `test_testing_workflow.py`: two `parse_implementation_response` tests that relied on an invented `implementation_N.py` now assert the ValueError.
- Neighbouring suites (`test_testing_workflow.py`, `test_implement_code_shim_exports.py` and the new file): 294 passed and 2 failed, the two tests above; after the change they pass.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## claude_client.py

- New: `tests/unit/test_claude_client_loud_failure.py`, 5 tests. Before the fix: 3 failed, 2 passed. After: 5 passed.
- Changed existing test: `test_llm_idle_timeout.py::test_a_bad_override_falls_back_rather_than_failing_the_call` becomes `test_a_bad_override_raises_naming_the_variable`, and an empty value is pinned as the default in `test_an_empty_override_is_the_default`.
- Neighbouring suites (the 21 unit files that import the module or its functions): 578 passed and 3 failed, the three parametrised cases above; after the change, 27 passed in the two files.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## import_validator.py

- New: `tests/unit/test_import_validator_loud_failure.py`, 7 tests. Before the fix: 4 failed, 3 passed. After: 7 passed.
- Changed existing tests: none.
- Neighbouring suites (the unit files that import the module, and `test_validate_code_short.py`): 60 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## routing.py

- New: `tests/unit/test_routing_loud_failure.py`, 2 tests that pin the compliant site; both pass before and after.
- Neighbouring suite `test_implement_code_routing.py` with the new file: 31 passed.

## prompts.py

- New: `tests/unit/test_prompts_loud_failure.py`, 3 tests. Before the fix: 1 failed, 2 passed. After: 3 passed.
- Changed existing tests: none.
- Neighbouring suites (the nine unit files that import the prompt builders, and the orchestrator's new tests): 480 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.

## context.py

- New: `tests/unit/test_context_loud_failure.py`, 3 tests. Before the fix: 2 failed (both on the new `filepath` keyword), 1 passed. After: 3 passed.
- Changed existing tests: none.
- Neighbouring suites (the module's importers and the prompt and context tests): 78 passed.
- Audits: 0 new loud-failure sites; no new fail-open; halt sites PASS.


---

# Test Report: the testing workflow's remaining nodes under standard 0034 (#3585 step 5, batch D)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-nodes`. No test makes a model call, and no workflow is run; nodes are called directly with built state in temporary directories, and alerts are asserted through the `operator_alerts` fixture.

## nodes/validate_tests_mechanical.py

**New: `tests/unit/test_validate_tests_mechanical_loud_failure.py` (18).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against HEAD's `validate_tests_mechanical.py`: 10 failed, 8 passed. The ten site tests failed (500, 523, three for 522, two for 676, three for 1043). The eight that passed pin the parse answers (101, 418, 499, 557), the two budget halts (963, 975), an absent neighbour, and a carried escalate with its reason.

**Changed tests:** `test_assertion_reading.py::test_an_unparseable_neighbour_costs_a_helper_not_the_run` is now `test_an_unparseable_neighbour_is_named_not_dropped` and expects `HelperSourceUnreadable`; `test_scaffold_gates_see_stubs.py::test_validator_reports_but_allows_a_hollow_suite_with_no_spec_bodies` reads the hollow line from stderr; `test_spec_stage_pair.py::test_an_exhausted_scaffold_no_longer_reaches_implementation` and `test_validate_tests_mechanical.py::test_escalate_after_max_attempts` expect the raise without a reason and "escalate" with one; `test_wave1_token_savings.py::test_identical_output_triggers_escalation` and `test_max_attempts_still_escalates` carry the node's `error_message` in state.

**Neighbouring suites:** 338 passed, 1 skipped, across the 20 files that import the module or `route_after_validate`, with `test_gate_registry.py`, `test_answer_key.py` and the new file.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 stale, the two deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the same two issues in the module as at HEAD; the new test file is clean.

## nodes/scaffold_tests.py

**New: `tests/unit/test_scaffold_tests_loud_failure.py` (18).** Generated test code is compiled and its test function called, so "fails until replaced" is measured rather than read off the text. The finder error is a stand-in `find_spec` that raises for one name.

**Before the fix, measured** against HEAD's `scaffold_tests.py`: 11 failed, 7 passed. The eleven site tests failed (105, 325, 342, two for 787, 788, 833, 834, 1069, two for 1199). The seven that passed pin a Section 10 that still parses, a derivable assertion, an unsupported framework raising (435), an unknown name read as a symbol, both scaffolds' audit copies when the directory exists, and the no-scenarios halt (1153).

**Changed tests:** `test_scaffold_tests.py::TestParseLLDTestSection::test_parse_missing_section_10` expects the ValueError; `test_spec_test_missing_imports.py::test_unparseable_source_reports_nothing` is now `test_unparseable_source_raises` and expects `ScaffoldImportError`.

**Neighbouring suites:** the 31 files that import the module or its changed functions, `tests/integration/test_lld_parsing_chain.py` among them: 720 passed and 2 failed before the two changes above, which were those two tests; both files pass after (37).

**Audits:** `audit_loud_failure.py --check` reports 0 new and 2 more stale, the two deleted tags. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes: no new halt site, since the halts go through the registered `_halt_scaffold_framework` and the existing returns. Ruff finds the module's same 8 issues as at HEAD; the new test file is clean.

## nodes/review_test_plan.py

**New: `tests/unit/test_review_test_plan_loud_failure.py` (11).** The provider and `with_retry` are stand-ins: no model is called. The router half of five rows is `graph.py`'s, so these tests pin the node half: an `error_message` and an ERROR line on stderr.

**Before the fix, measured** against HEAD's `review_test_plan.py`: 10 failed, 1 passed. Every site test failed (two for 156, 428, 489, 553, 579, 609, three for 710). The one that passed pins blocking issues as the feedback.

**Changed tests:** in `test_testing_workflow.py`, `test_load_review_prompt_file_missing` expects FileNotFoundError; `test_default_review_prompt` loads AssemblyZero's own prompt with no root; `test_extract_feedback_numbered_list`, `test_extract_feedback_fallback` and `test_extract_feedback_default_message` expect "" where they accepted the placeholder.

**Neighbouring suites:** the 23 files that import the module or `route_after_review`: 798 passed, 1 skipped and 5 failed before the changes above, which were those five tests; their classes pass after (14).

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's same 2 issues as at HEAD; the new test file is clean.

## nodes/document.py

**New: `tests/unit/test_document_loud_failure.py` (11).** The lessons template and the execution log are stand-ins; the wiki page, README and sidebar are real files, and each failure is injected at the step it names.

**Before the fix, measured** against HEAD's `document.py`: 9 failed, 2 passed. Every site test failed (two for 182, 215, two for 289, 292, 308, 338, 350); the first tests for 215 and 289 failed on the new wording only, since the kept behaviour, no raise and no change, held. The two that passed pin a README entry added under Features and a README that already names the feature.

**Changed tests:** `test_testing_workflow.py::TestDocumentModule::test_update_readme_no_readme` expects FileNotFoundError.

**Neighbouring suites:** `test_adversarial_review_halts.py`, `test_cleanup.py`, `test_doc_step_handling.py`, `test_document_assembler.py`, `test_testing_workflow.py` and `test_gate_registry.py`: 392 passed and 1 failed before the change above, which was that test; its class passes after (10).

**Audits:** `audit_loud_failure.py --check` reports 0 new and 4 more stale, the module's four broad handlers, which now re-raise. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff's four findings on the module at HEAD are gone; the new test file is clean.

## nodes/mechanical_hooks.py

**New: `tests/unit/test_mechanical_hooks_loud_failure.py` (9).** The hooks are real shell commands in a temporary directory, and `git` is the real one: the failed staging is git's own exit 128 outside a repository.

**Before the fix, measured** against HEAD's `mechanical_hooks.py`: 5 failed, 4 passed. The two 108 tests failed on the unread return code; 74, 91 and 98 failed only on the new stderr line, since their halts held. The four that passed pin no config, a config naming no command (two cases) and a successful hook's output staged.

**Changed tests:** none.

**Neighbouring suites:** the six files that import the module, with `test_gate_registry.py`: 158 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's one issue as at HEAD; the new test file is clean.

## nodes/revise_test_plan.py

**New: `tests/unit/test_revise_test_plan_loud_failure.py` (6).** The provider and `with_retry` are stand-ins: no model is called. Each site test drives the node into its failure and routes the result through `route_after_revision`.

**Before the fix, measured** against HEAD's `revise_test_plan.py`: 4 failed, 2 passed. The four site tests failed only on the new stderr line; their halts held. The two that passed pin a short plan under the cap asking again with no reason, and a complete revision going back to N1.

**Changed tests:** none.

**Neighbouring suites:** the six files that import the module or `route_after_revision`, with `test_gate_registry.py`: 381 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff is clean on the module and the new test file.

## nodes/finalize.py

**New: `tests/unit/test_finalize_loud_failure.py` (10).** Files are real, in a temporary repository; the failed move is a stand-in `rename`. The test report generator is a stand-in where N7 runs whole.

**Before the fix, measured** against HEAD's `finalize.py`: 8 failed, 2 passed. Every site test failed (46, the done/ lookup, 74, two cases of 152, two of 216, and the skipped-list print on its new wording). The two that passed pin a file outside active/ left alone and a green output with counts completing.

**Changed tests:** in `test_issue_141.py`, `test_100` expects `FinalizeError`, and `test_030` and `test_080` expect FileNotFoundError; `test_testing_workflow.py::TestFinalizeFullCoverage::test_finalize_archives_lld` carries a green output with counts.

**Neighbouring suites:** the 21 files that import the module or `route_after_finalize`, with `test_gate_registry.py`: 608 passed, 1 skipped and 4 failed before the changes above, which were those four tests; after, 25 passed in `test_issue_141.py` with the new file, and 18 in the Finalize classes of `test_testing_workflow.py`.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the module's same 2 issues as at HEAD; the new test file is clean.

## nodes/adversarial_validator.py

**New: `tests/unit/test_adversarial_validator_loud_failure.py` (4).** All four pin kept behaviour: a file that does not compile is an error, reported once, and the scans still find a mock and a test without assertions in code that compiles.

**Before the change, measured** against HEAD's `adversarial_validator.py`: 4 passed, as pins should.

**Changed tests:** none.

**Neighbouring suites:** `test_adversarial_validator.py`, `test_adversarial_review_halts.py`, `test_adversarial_node.py` and the new file: 115 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff is clean, as at HEAD.

## nodes/completeness_gate.py

**New: `tests/unit/test_completeness_gate_loud_failure.py` (2).** Both drive N4b with an empty requirement set and route the result through `route_after_completeness_gate`.

**Before the change, measured** against HEAD's `completeness_gate.py`: 1 failed, 1 passed. The first test failed only on the new stderr line, since the halt held; the second, with no recorded reason, passed.

**Changed tests:** none.

**Neighbouring suites:** the seven files that import the module, with `test_gate_registry.py`: 169 passed.

**Audits:** `audit_loud_failure.py --check` reports 0 new. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff is clean, as at HEAD.


---

# Test Report: the testing workflow's runners, templates and top-level modules under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-testing-runners`. Every runner test stands in for `npx` and the subprocess: nothing real is run.

## runners/jest_runner.py

**New: `tests/unit/test_jest_runner_loud_failure.py` (12).** Each site test is named for its ledger line; the rest pin kept behaviour.

**Before the fix, measured** against HEAD's `jest_runner.py`: 9 failed, 3 passed. The nine site tests failed. The three that passed pin a project with no package.json (quiet), a failing typecheck returned as a failing result (72), and a readable report read quietly.

**Changed tests:** `test_jest_runner.py::test_parse_invalid_json` now expects `RunnerError` where it expected a fallback result.

**Neighbouring suites:** 132 passed across the 13 files that import the runner modules.

**Audits:** `audit_loud_failure.py --check` reports 0 new and 1 stale, the deleted tag. `audit_fail_open.py --check` reports no new fail-open. `audit_halt_sites.py --check` passes. Ruff finds the same issue in each of `jest_runner.py` and `base_runner.py` as at HEAD.

## runners/base_runner.py

**New: `tests/unit/test_base_runner_loud_failure.py` (7).**

**Before the fix, measured:** 5 failed, 2 passed. The five site tests failed. The two that passed pin scenario coverage as passed over total, and a command that ran returning its streams and exit code.

**Changed tests:** none.

**Neighbouring suites:** 194 passed across 18 files: the runner files, the framework integration tests, the full-suite gate, the zero-collected route and the path-to-runner tests.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issue as at HEAD.

## runners/pytest_runner.py

**New: `tests/unit/test_pytest_runner_loud_failure.py` (9).**

**Before the fix, measured:** 6 failed, 3 passed. The six site tests failed: exit codes 2 to 5, a collection error, and the missing coverage table. The three that passed pin exit 0 and exit 1 read from the summary line, and a TOTAL row read.

**Changed tests:** `test_pytest_runner.py::test_parse_no_coverage` now expects None where it expected 0.0.

**Neighbouring suites:** 41 passed across the 5 files that use the pytest runner.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## runners/playwright_runner.py

**New: `tests/unit/test_playwright_runner_loud_failure.py` (9).**

**Before the fix, measured** against HEAD's module: 8 failed, 1 passed. The eight site tests failed; the one that passed pins a readable report.

**Changed tests:** `test_playwright_runner.py::test_parse_invalid_json` now expects `RunnerError` where it expected a fallback result.

**Neighbouring suites:** 52 passed across the 5 files that use the Playwright runner.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issue as at HEAD.

## runner_registry.py

**New: `tests/unit/test_runner_registry_loud_failure.py` (10).**

**Before the fix, measured:** 3 failed, 7 passed. The three site tests failed: an unknown string, a value of another type, and a one-framework run read as pytest. The seven that passed pin three ways of naming no framework and the four frameworks resolving from enum and string.

**Changed tests:**
- `test_scaffold_resolves_framework_string.py`: the "nonsense" case leaves the None test, and a new test expects the raise.
- `test_framework_integration.py`: `test_invalid_string_returns_none` is now `test_invalid_string_raises`.

**Neighbouring suites:** 197 passed across 18 files that resolve a framework, scaffold, or run several frameworks.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## exit_code_router.py

**New: `tests/unit/test_exit_code_router_loud_failure.py` (13).** Four site tests, and nine that pin the descriptions verify_phases prints.

**Before the fix, measured:** 4 failed, 9 passed. The four site tests failed, since the function was there; the nine description tests passed.

**Changed tests:** `test_exit_code_router.py` loses its 16 tests of the deleted function and their import. Its description and constant tests are unchanged.

**Neighbouring suites:** 68 passed and 1 skipped across 5 files: the router's two test files, the verify_phases lint test, the exit-code verify_phases tests and the honest-coverage tests. The skip is the lint test's own: ruff is not importable in the environment.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issue as at HEAD.

## framework_detector.py

**New: `tests/unit/test_framework_detector_loud_failure.py` (8).**

**Before the fix, measured:** 6 failed, 2 passed. The six site tests failed. The two that passed pin an existing empty project, read quietly as pytest at the root, and a detected config.

**Changed tests:** `test_framework_detector.py::test_nonexistent_directory` now expects `FrameworkResolutionError` naming the path, where it expected an empty list.

**Found later, fixed in a test-only commit:** the commit left 22 tests failing in 6 orchestrator files it had not run. Each drives the implementation stage with git stubbed, so the worktree is never cut, and the stage's provisioning now refuses a worktree that is not there. None of them is about provisioning, so each helper stands `provision_worktree` in, with a comment saying why. The 13 files that reach the stage or provisioning: 215 passed.

**Neighbouring suites:** 576 passed across 21 files: the detector's tests, N0's, provisioning's, the multi-framework and mock runs, and the LLD parsing chain.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## coverage_report.py

**New: `tests/unit/test_coverage_report_loud_failure.py` (6).** Every test pins the kept contract.

**Against HEAD's module:** 6 passed. There is no fix.

**Changed tests:** none.

**Neighbouring suites:** 51 passed across the 3 files that read the coverage report.

## audit.py, the testing workflow's

**New: `tests/unit/test_testing_audit_loud_failure.py` (8).** One is a strict xfail recording the open site 320.

**Before the fix, measured:** 3 failed, 4 passed, 1 xfailed. The three site tests failed. The four that passed pin an empty directory as file 1, numbering after the highest file, a working append, and a TOTAL row read.

**Changed tests:** none.

**Neighbouring suites:** 616 passed and 1 xfailed across 17 files: the module's importers, and the node tests that number and log audit records.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## path_validator.py

**New: `tests/unit/test_path_validator_loud_failure.py` (7).**

**Before the fix, measured:** 4 failed, 3 passed. The four site tests failed. The three that passed pin the stat rejection (65), files that all load, and no files.

**Changed tests:** `test_path_validator.py::test_skips_invalid_files` is now `test_one_invalid_file_leaves_no_partial_context` and expects empty content.

**Neighbouring suites:** 75 passed across 4 files, among them the entry point's loud-failure tests and the context-injection tests.

**Audits:** 0 new loud-failure sites, and this module's swallowed handler is now stale in the baseline; no new fail-open; halt sites pass. Ruff finds one fewer issue than at HEAD.

## symbol_validator.py

**New: `tests/unit/test_symbol_validator_loud_failure.py` (7).**

**Before the fix, measured:** 4 failed, 3 passed. The four site tests failed. The three that passed pin a module that is not the repository's own, a good name, and a missing name with its near match.

**Changed tests:**
- `test_generated_test_symbols.py`: the unparseable source and the unreadable module now expect `SymbolCheckError`.
- `test_symbol_validator_sees_conditional_bindings.py`: `test_an_unparseable_module_is_still_none` is now `test_an_unparseable_module_raises`.

**Neighbouring suites:** 129 passed across 8 files: the validator's tests and N4c's.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## knowledge/patterns.py

**New: `tests/unit/test_knowledge_patterns_loud_failure.py` (10).**

**Before the fix, measured:** 8 failed, 2 passed. The eight site tests failed. The two that passed pin the shipped file, loaded quietly, and detection reading it.

**Changed tests:** `test_testing_workflow.py::test_load_test_types_yaml_missing` now expects FileNotFoundError, where it called the deleted inline copy.

**Neighbouring suites:** 325 passed across 5 files: the workflow tests, N0's and N1's.

**Audits:** 0 new loud-failure sites, and this module's swallowed handler is now stale in the baseline; no new fail-open; halt sites pass. Ruff finds one fewer issue than at HEAD in the module and in the workflow tests.

## templates/runbook.py

**New: `tests/unit/test_runbook_template_loud_failure.py` (5).**

**Before the fix, measured:** 4 failed, 1 passed. The four site tests failed. The one that passed pins a runbook written from the LLD alone, with none of the invented strings.

**Changed tests,** all in `test_testing_workflow.py`:
- two runbook tests gain a verification section in their LLDs;
- the prerequisites test gains a procedure and a verification section, and now asserts the LLD's own row;
- the minimal-LLD test now expects the ValueError naming all three sections.

**Neighbouring suites:** 288 passed across the runbook and workflow tests.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds the same issues as at HEAD.

## templates/wiki_page.py

**New: `tests/unit/test_wiki_page_template_loud_failure.py` (5).**

**Before the fix, measured:** 2 failed, 3 passed. The two site tests failed. The three that passed pin a page written from the LLD's own overview, an already-linked page as False, and a new page linked.

**Changed tests:** `test_testing_workflow.py::test_generate_wiki_page_with_long_feature_name` gains an overview in its LLD and asserts the page, where it accepted None or the placeholder.

**Neighbouring suites:** 301 passed across 4 files: the wiki tests, the workflow tests and N8's.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds nothing in the module or the new test file.

## templates/cp_docs.py

**New: `tests/unit/test_cp_docs_template_loud_failure.py` (3).**

**Before the fix, measured:** 2 failed, 1 passed. The two site tests failed. The one that passed pins the LLD's own commands as the reference, with none of the invented ones.

**Changed tests:** `test_doc_step_handling.py::test_document_emits_cp_docs_when_not_skipped` gives its LLD a command, so the c/p docs it expects are written from the LLD.

**Neighbouring suites:** 299 passed across 4 files: the c/p doc tests, the workflow tests and N8's.

**Audits:** 0 new loud-failure sites; no new fail-open; halt sites pass. Ruff finds nothing in the module or the new test file.


---

# 3585 - Test Report: loud failure in the testing workflow, batch A

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #3585 (step 5); module issue #3810 for `checkpoints.py` |
| **Implementation Report** | `docs/reports/3585/implementation-report.md` |
| **Date** | 2026-10-31 |

## 2. Method

For each module the new test file was written first and run against the unchanged module with `-rA`: every site test had to fail, and every test pinning kept behaviour had to pass. The module was then fixed until all passed, and every test file that imports the module or a changed function was run.

## 3. `assemblyzero/workflows/testing/checkpoints.py`

| Run | Result |
|---|---|
| `tests/unit/test_checkpoints_loud_failure.py` against the unchanged module (26 tests) | 20 failed, 6 passed: every site test failed; the 6 kept-behaviour tests passed |
| The same file after the fix (30 tests, with N5's halt) | 30 passed |
| `test_tdd_checkpoints`, `test_impl_resume_prefers_best_measured`, `test_impl_lands_through_driver`, `test_doc_step_handling`, `test_post_finalize_checkpoint`, `test_gate_registry` with the new file | 140 passed |
| The 23 files that reach N5 and failed before the conftest stand-in and the registry row | 631 passed |
| The 17 files reaching `run_impl_stage`, `_best_measured_attempt` or `finish_standalone_run` | 302 passed |
| `tools/audit_loud_failure.py --check` | 0 new, 3 stale (the fixed `fail_open_tag` entries) |
| `tools/audit_fail_open.py --check` | no new fail-open |
| `tools/audit_halt_sites.py --check` | PASS, 163 halt sites, every one registered |

## 4. `verify_phases.py`, `cleanup_helpers.py`, `cleanup.py`

| Run | Result |
|---|---|
| `test_verify_phases_loud_failure.py` against the unchanged module (69 tests) | 42 failed, 27 passed (9 kept-behaviour pins, 18 compliant-row pins) |
| The same file after the fix | 69 passed |
| Every file naming verify_phases, its entry points, the testing graph, augment_tests or run_pytest | first 80 failures from the change (minimal states with no coverage target, full-suite gates outside a git repository, retired behaviour); after updating those tests, 593 and then 55 passed in the affected files |
| `test_cleanup_helpers_loud_failure.py` against HEAD's module (10 tests) | 5 failed, 5 passed |
| It and `test_cleanup_helpers.py` after the fix | 35 passed |
| `test_cleanup_loud_failure.py` against HEAD's module (12 tests) | 10 failed, 2 passed |
| It, `test_cleanup.py`, `test_cleanup_stage.py`, `test_node_modules_supply_nodes.py` | 45 passed |
| `test_adversarial_review_halts`, `test_doc_step_handling`, `test_testing_workflow`, `test_orchestrator_stages`, `test_post_finalize_checkpoint` | 377 passed |
| The three audits after the last commit | loud-failure 0 new (13 stale); fail-open no new; halt sites PASS, 164 sites |

For `checkpoints.py` (section 3): before the conftest stand-in, 92 unit tests in 23 files halted at N5: they stub the test run and point `repo_root` at a plain directory, so the measurement note git cannot write became their halt.

---

# Joining the batches

- **The full unit tier on the merged branch** (`64c051bc`, after the three baselines were regenerated): 14 failed, 5 errors, 12323 passed. Each batch had passed alone; every failure was where two met.
- **Fixed, each with its test:** `test_framework_ownership_unknown.py` (4 tests; 3 fail without the wrap); `test_checkpoint_ignored_exclusions.py` (2 tests; the first fails before the fix); `test_wiki_page_template_loud_failure.py::test_169` now pins None for a wiki with no sidebar. The N8 tests (25), the checkpoint and mock-run tests (40) and the loop-cap rolls (27) pass.
- **The full unit tier again** (`9899db9f`): 1 failed, 12347 passed. The one, `test_tdd_checkpoints.py::test_excludes_workflow_internal_dirs_from_staging`, had a fake git that answered `check-ignore` as "ignored"; corrected in `8e800226`, and the three checkpoint test files pass (44). The full tier runs once more when the package lands, after `origin/main` is merged.
- **Audits after the last code change:** loud-failure PASS (208 sites); fail-open PASS --strict (10116 sites); halt sites PASS --strict (182 sites, 113 gates, impl rows 50).

## The landing tier

Run on 2026-10-31 on the merge of the requirements and implementation_spec packages (`e8dc5d0f`): 12,955 passed, 66 skipped, 7 deselected and 7 xfailed in 926 s, with no failures. The merge's conflicts beyond the reports and baselines were `tests/unit/conftest.py`, where both sides were kept, and a test file both packages named `test_finalize_loud_failure.py`; testing's is now `tests/unit/test_testing_finalize_loud_failure.py`. Merging `main` afterwards left the tree unchanged, because `main`'s spec squash has no difference from the head already merged. After the merge: loud-failure PASS (154 sites); fail-open PASS --strict (10,194 sites); halt sites PASS --strict (214 sites, 114 gates, impl rows 50).

---

# Test Report: run-path modules outside the workflow packages under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, measured by running the new test file against the unchanged module first. Filled in module by module.

## speedrun/requirements_status.py

**New: `tests/unit/test_requirements_status_loud_failure.py` (7).** Each site test is named for its ledger line, plus tests that pin the kept behaviour: a written record reads back, an absent ledger is `[]`, blank lines are not corruption.

**Before the fix, measured** against the unchanged module: 4 failed, 3 passed. The three are the kept-behaviour tests.

**Changed test:** `test_requirements_gate_timeout.py::test_recording_never_raises` is now `test_a_record_that_cannot_be_written_alerts_and_raises`.

**Neighbouring suites:** 67 passed across `test_requirements_gate_timeout.py` and `test_n0c_unarticulated_conflict.py`.

## utils/ast_sentinel.py

**New: `tests/unit/test_ast_sentinel_loud_failure.py` (6).** Four site tests, plus an undefined name that is still a finding and a clean file that is ok.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** `test_ast_sentinel.py::test_analyze_file_io_error` and `::test_syntax_error` expect `SentinelCannotRun`; they read an `<io>` and a `<syntax>` finding.

**Neighbouring suites:** 24 passed across `test_ast_sentinel.py` and the new file; `test_validate_mechanical.py` 79 passed; `test_mechanical_gates.py` 18 passed.

## utils/lld_verification.py

**New: `tests/unit/test_lld_verification_loud_failure.py` (3).** The site test (a path outside the current directory with no project root is refused), plus a path inside the current directory and an explicit root, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 1 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 23 passed across `test_issue_177.py` and the new file.

## utils/lld_path_enforcer.py

**New: `tests/unit/test_lld_path_enforcer_loud_failure.py` (3).** It pins the kept behaviour: a spec with no Section 2.1 yields no paths and no alert, an LLD with Section 2.1 yields its paths, and the docstring says why the absence is quiet.

**Before the change, measured** against the unchanged module: 1 failed (the docstring test), 2 passed (the behaviour, which is kept).

**Changed tests:** none.

**Neighbouring suites:** 57 passed across `test_lld_path_enforcer.py`, `test_file_write_validator.py`, `test_freeze_tests_symmetry_break.py`, `test_path_advisory.py` and the new file.

## utils/codebase_reader.py

**New: `tests/unit/test_codebase_reader_loud_failure.py` (11).** Eight site tests, plus three that pin the quiet answers: a missing file, a binary or sensitive file, and a repo with no config file. The site tests match the exception by name, so against the old module they fail on "did not raise".

**Before the fix, measured** against the unchanged module: 8 failed ("did not raise CodebaseReadError"), 3 passed (the kept-behaviour tests).

**Changed tests, each asserting the raise in place of the empty result:** in `test_codebase_reader.py`, `test_corrupted_pyproject`, `test_corrupted_package_json`, `test_symlink_outside_repo_returns_empty`, `test_symlink_outside_repo_in_batch`, `test_non_utf8_file_returns_empty` (now `test_non_utf8_file_raises`), `test_oserror_on_exists_returns_empty` (now `..._raises`), `test_file_outside_repo_root_returns_empty` (now `..._raises`), `test_oserror_on_read_text_returns_empty` (now `..._raises`), `test_oserror_on_resolve_returns_empty` (now `..._raises`); in `test_analyze_codebase.py`, `TestSymlinkOutsideRepoBlocked::test_symlink_outside_repo_returns_empty`.

**Neighbouring suites:** 184 passed across `test_codebase_reader.py`, `test_analyze_codebase.py` and the new file; 80 passed across `test_issue_2684.py`, `test_requirements_graph_halts.py`, `test_cache_semi_static.py`, `test_base_api_surface.py`, `test_base_symbols_in_api_check.py`, `test_interface_surface.py` and `test_symbol_gather_reports_unreadable.py`.

## speedrun/convergence.py

**New: `tests/unit/test_convergence_loud_failure.py` (13).** Site tests for 90 (three event kinds, and a root the store path cannot be built from), 91, 185, 186 and 195 (two shapes), the `802` consumer test, and three kept-behaviour tests: a clean store, an absent store and a written record. The store-path test came with the follow-up commit; it failed against the first version (the path was built outside the alerted region) and passes after.

**Before the fix, measured** by putting HEAD's `convergence.py` and `factory_report.py` back: 11 failed, 1 passed (`test_a_written_record_returns_true`). Two of the eleven, `test_a_clean_store_reads_with_no_alert` and `test_a_missing_store_is_a_quiet_empty_answer`, fail only on the return shape: the old reader returned `(records, count)`.

**Changed tests:** `test_convergence_record.py::test_a_corrupt_line_is_counted_rather_than_dropped` is now `test_a_corrupt_line_stops_the_read`. The return shape changed every other read in `test_convergence_record.py` (12 lines), `test_testing_atlas.py` (2), `test_mock_roll.py` (1) and `test_call_recording_roll.py` (1); each dropped an `unreadable == 0` assertion that the raise now carries.

**Neighbouring suites (convergence):** 195 passed across the new file, `test_convergence_record.py`, `test_testing_atlas.py`, `test_factory_report.py`, `test_call_recording_roll.py`, `test_mock_roll.py`, `test_checkout_telemetry_isolation.py`, `test_profile_bench.py`, `test_model_record.py`, `test_narration.py`, `test_narration_gates_off.py` and `test_halt_node.py`.

## workflows/narration.py

**New: `tests/unit/test_narration_loud_failure.py` (9).** Site tests for 55 (kept), 64, 114 (two shapes), 160 (two) and 181, plus a healthy node and a state with no `repo_root`, which pin kept behaviour.

**Before the fix, measured** against the unchanged module (with the convergence fix already in): 6 failed, 3 passed (the three kept-behaviour tests).

**Changed tests, each asserting the new behaviour in place of the retired one:**
- `test_narration.py::test_an_unknown_node_warns_once_then_stays_silent` is now `test_an_unknown_node_fails_the_graph_build`;
- `test_narration.py::test_a_broken_atlas_entry_never_costs_the_node` is now `test_a_broken_atlas_entry_stops_the_node`;
- `test_narration_gates_off.py::TestNarrationStillNeverCostsARun::test_a_node_still_runs_when_narration_explodes` is now `TestNarrationFailureIsLoud::test_a_node_does_not_run_when_narration_explodes`;
- `test_convergence_record.py::test_a_node_still_runs_when_the_record_cannot_be_written` is now `test_a_node_does_not_run_when_the_record_cannot_be_written`;
- `test_node_modules_supply_nodes.py::test_narrated_names_the_wrapped_module` wrapped a node with an empty atlas; it now gives the node an entry.

**Neighbouring suites (narration):** 131 passed across the new file, `test_narration.py`, `test_narration_gates_off.py`, `test_node_modules_supply_nodes.py`, `test_convergence_record.py`, `test_testing_atlas.py`, `test_graph_atlas.py`, `test_tutorial_mode.py`, `test_quiz_mode.py` and `test_halt_legibility.py`; 249 passed across `test_implementation_spec_workflow.py`, `test_requirements_graph_halts.py` and `test_finalize_repair_routing.py`, which build the graphs.

## speedrun/prompt_telemetry.py

**New: `tests/unit/test_prompt_telemetry_loud_failure.py` (7).** Site tests for 130, 152, 180 and 188 (two shapes), plus an absent store and a written failure, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 5 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** in `test_prompt_telemetry.py`, `test_empty_details_are_not_recorded` is now `test_empty_details_are_recorded_under_their_own_fingerprint`, `test_a_malformed_line_does_not_break_the_report` is now `test_a_malformed_line_stops_the_report`, and `test_a_write_failure_is_logged_and_swallowed` is now `test_a_write_failure_alerts_and_raises`.

**Neighbouring suites:** 180 passed across `test_prompt_telemetry.py`, `test_checkout_telemetry_isolation.py`, `test_check_requirements.py`, `test_factory_report.py`, `test_n0c_unarticulated_conflict.py`, `test_requirements_gate_reproduces.py` and `test_spec_convergence_telemetry.py` before the three changes (the three were the only failures); 66 passed across the new file, `test_prompt_telemetry.py`, `test_spec_convergence_telemetry.py` and `test_checkout_telemetry_isolation.py` after.

## workflows/telemetry/hallucination_log.py

**New: `tests/unit/test_hallucination_log_loud_failure.py` (6).** Site tests for 105, 114 and 123, both sinks failing, and two kept-behaviour tests: a sink given as None, and both sinks written.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the kept-behaviour tests).

**Changed tests:** in `test_hallucination_telemetry.py`, `test_missing_audit_dir_skips_that_sink_without_error` is now `test_missing_audit_dir_alerts_and_raises_after_the_other_sink`, and `test_sink_failure_is_swallowed` is now `test_sink_failure_alerts_and_raises`.

**Neighbouring suites:** 235 passed across the new file, `test_hallucination_telemetry.py`, `test_checkout_telemetry_isolation.py` and `test_implementation_spec_workflow.py`.

## visual_gate/config.py

**New: `tests/unit/test_visual_gate_config_loud_failure.py` (6).** Site tests for 77 (absent and empty) and 79, plus an explicit zero floor, a full declaration and no declaration, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 3 failed, 3 passed (the kept-behaviour tests).

**Changed tests:** none; every existing declaration already carries both keys.

**Neighbouring suites:** 127 passed across the new file, `test_contract_fidelity.py`, `test_gate_opens_browser.py`, `test_visual_gate_decompose.py`, `test_visual_gate_loop.py`, `test_visual_gate_guardrails.py`, `test_visual_gate_stage.py` and `test_visual_gate_live_resume.py`; `test_assertion_manifest.py` 29 passed.

## utils/retry.py

**New: `tests/unit/test_utils_retry_loud_failure.py` (5).** Two site tests (a failure not worth retrying, and retries exhausted), plus a quiet success and the failed result still returned, not raised (two cases), which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 2 failed, 3 passed (the kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 85 passed across the new file, `test_utils_retry.py`, `test_retry_gate_wiring.py` and `test_retry_gate.py`; 23 passed across `test_gemini_retry_boundary.py`, `test_json_verdict_review_test_plan.py` and `test_review_test_plan_structured_output.py`.

## utils/process.py

**New: `tests/unit/test_process_loud_failure.py` (6).** Site tests for 33 (a failing `taskkill`) and 41 (a `taskkill` timeout, an OS refusal), plus three that pin the quiet answers: `taskkill` exit 0, `taskkill` exit 128 ("not found"), and `ProcessLookupError`.

**Before the fix, measured** against the unchanged module: 3 failed, 3 passed (the kept-behaviour tests).

**Changed tests:** none.

**Neighbouring suites:** 97 passed across the new file, `test_gemini_call_bounds.py`, `test_gemini_client.py`, `test_gemini_client_loud_failure.py`, `test_llm_idle_timeout.py` and `test_one_claude_cli_transport.py`.

## utils/workflow_timeout.py

**New: `tests/unit/test_workflow_timeout_loud_failure.py` (3).** Two site tests (the alert precedes the exit; the exit happens when the alert cannot be delivered), plus a disabled timeout that arms nothing. `os._exit` is replaced for the test.

**Before the fix, measured** against the unchanged module: 2 failed, 1 passed (the kept-behaviour test).

**Changed tests:** none.

**Neighbouring suites:** 15 passed across the new file and `test_workflow_timeout.py`.

## telemetry/cost.py

**New: `tests/unit/test_telemetry_cost_loud_failure.py` (6).** Site tests for 73 (two unpriced models, a sum that meets one, the instrumented record carrying None), plus a priced model and a priced model with no tokens, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 4 failed, 2 passed (the kept-behaviour tests).

**Changed tests:** in `test_cost_estimator.py`, `TestUnknownModel`'s four tests (0.0 and a WARNING) are three that expect None: `test_unknown_model_has_no_estimate`, `test_gemini_model_has_no_estimate`, `test_gpt_model_has_no_estimate`. The warning test is gone with the warning.

**Neighbouring suites:** 50 passed across the new file, `test_cost_estimator.py` and `test_llm_instrumentation.py`.

## utils/speedrun.py

**New: `tests/unit/test_utils_speedrun_loud_failure.py` (5).** Site tests for 144, 320 and 335, plus an absent run log and a written attempt, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 3 failed, 2 passed (the kept-behaviour tests).

**Changed test:** `test_speedrun.py::test_run_logger_skips_malformed_lines` is now `test_run_logger_refuses_malformed_lines`.

**Neighbouring suites:** 35 passed across the new file, `test_speedrun.py` and `test_model_record.py`.

## telemetry/store.py

**New: `tests/unit/test_telemetry_store_loud_failure.py` (7).** Site tests for 71, 88, 114 and 127, plus a disabled store, a day with no file, and written records read back and queried, which pin kept behaviour.

**Before the fix, measured** by putting HEAD's `store.py` back: 4 failed, 3 passed (the kept-behaviour tests).

**Changed test:** `test_llm_instrumentation.py::TestWriteFailure::test_oserror_does_not_propagate` is now `test_oserror_alerts_and_propagates`; the file's now-unused `import logging` is removed.

**Neighbouring suites:** 31 passed across the new file, `test_llm_instrumentation.py` and `test_telemetry_cost_loud_failure.py`.

## telemetry/emitter.py

**New: `tests/unit/test_telemetry_emitter_loud_failure.py` (10).** Site tests for 68, 84, 151, 156, 192, 200 and 203; tests for 54 and 171 that pin the two kept answers; and a healthy emit and flush.

**Before the fix, measured** by putting HEAD's `emitter.py` back: 7 failed, 3 passed (the two won't-do pins and the healthy path).

**Changed tests:** in `test_telemetry_emitter.py`, `TestWriteToBuffer::test_never_raises` is now `test_a_buffer_write_failure_alerts_and_raises`, and `TestEmit::test_never_raises_on_any_error` is now `test_an_event_that_cannot_be_built_alerts_and_raises`; the now-unused `Path` import is removed.

**Neighbouring suites:** 120 passed across the new file, `test_telemetry_emitter.py`, `test_factory_report.py`, `test_red_phase_import_is_named.py`, `test_spec_test_missing_imports.py` and `test_requirements_graph_halts.py`.

## telemetry/actor.py

**New: `tests/unit/test_telemetry_actor_loud_failure.py` (5).** Site tests for 34 (a failing `gh`; the token never requested) and 48 (`gh` missing, `gh` timing out), plus a logged-in `gh` that names the user quietly.

**Before the fix, measured** against the unchanged module: 4 failed, 1 passed (the kept-behaviour test).

**Changed tests:** none; `test_telemetry_actor.py::test_fallback_on_error` still holds ("unknown" on `FileNotFoundError`).

**Neighbouring suites:** 45 passed across the new file, `test_telemetry_actor.py`, `test_telemetry_emitter.py` and `test_telemetry_emitter_loud_failure.py`.

## speedrun/restore.py

**New: `tests/unit/test_restore_loud_failure.py` (7).** Site tests for 46, 83, 140 (two) and 150 against a real temporary git repository, plus the quiet "not restorable" (no ref, no path) and a file restored from `HEAD`, which pin kept behaviour.

**Before the fix, measured** against the unchanged module: 5 failed, 2 passed (the kept-behaviour tests).

**Changed tests:** `test_restore_from_graveyard.py::test_a_path_outside_the_repo_declines` is now `test_a_path_outside_the_repo_is_refused`, and `test_resume_after_failure.py::test_restore_artifact_outside_repo_refuses` expects the `ValueError`; both returned False.

**Neighbouring suites:** 136 passed across the new file, `test_input_rebuild_from_refs.py`, `test_restore_from_graveyard.py`, `test_restore_prefers_durable_and_base.py`, `test_resume_after_ceiling_halt.py`, `test_resume_from_pr_stage.py`, `test_spec_handoff_survives_janitor.py`, `test_speedrun_roll_kill.py`, `test_resume_after_failure.py` and `test_leavings_janitor.py`.

## speedrun/must_resolve.py

**New: `tests/unit/test_must_resolve_loud_failure.py` (29).** Site tests for 355, 359 (two), 372, 411, 443, 451, 465, 473, 498, 503, 509, 527, 535 (two: the alert, and the launcher refusing with 91), 539 (two), 613 (two), 630, 639 (two) and 721, plus tests that pin kept behaviour: 176's exit 127, a healthy filing and a healthy gate alerting nobody, a label failure the retry proves harmless, an absent ledger, and a suppressed line with no number.

**Before the fix, measured** against the unchanged module: 23 failed, 6 passed (the six kept-behaviour tests).

**Changed tests:** `test_filed_questions_ledger.py::test_recording_never_raises` is now `test_a_record_that_cannot_be_written_raises`; `::test_a_corrupt_line_costs_one_entry_not_the_file` is now `test_a_corrupt_line_alerts_and_stops_the_read`; `test_must_resolve_preflight.py::test_gh_failure_warns_and_proceeds` is now `test_gh_failure_refuses_the_launch`. `tests/unit/conftest.py` gains the autouse `_must_resolve_gate_answers_offline`.

**Neighbouring suites:** before the test changes, 433 passed and 3 failed (exactly those three) across `test_assertion_manifest.py`, `test_check_requirements.py`, `test_filed_questions_ledger.py`, `test_form_gate.py`, `test_github_writes_inert.py`, `test_healing_ledger.py`, `test_leavings_janitor.py`, `test_must_resolve_filing.py`, `test_must_resolve_preflight.py`, `test_n0c_unarticulated_conflict.py`, `test_provider_storm.py`, `test_requirements_gate_accepts_shapes.py`, `test_requirements_gate_reproduces.py`, `test_roll_blocker_preflight.py`, `test_solo_runbook.py`, `test_spec_conflict_filing.py`, `test_speedrun_roll_follow.py`, `test_speedrun_roll_verdict.py` and the new file; after, 436 passed. The suites that drive `speedrun_roll.main()` without patching the gate (`test_box_health.py`, `test_claude_spend_lock_refusal.py`, `test_narration_levels.py`, `test_no_console_windows.py`, `test_no_retries.py`, `test_profile_bench.py`, `test_speedrun_roll.py`, `test_speedrun_roll_attempts.py`, `test_speedrun_roll_detach.py`, `test_speedrun_roll_kill.py`, `test_speedrun_roll_lifecycle.py`, `test_speedrun_tests_are_host_independent.py`): 23 failed before the conftest fixture, 218 passed and 3 skipped after.

## speedrun/factory_report.py

**New: `tests/unit/test_factory_report_loud_failure.py` (23).** Site tests for 496, 511, 529, 630, 631, 646 (two: the log, and the report over it), 647, 764, 851, 852, 928 (two), 971 (two), 972 and 976, plus tests that pin kept behaviour: an unparseable window still raises, both window formats still parse, a record needs no date when no window is asked for, a repo never rolled has no runs, a path outside the root is not under it, and a readable bundle reads with no alert.

**Before the fix, measured** against the unchanged module: 17 failed, 6 passed (the six kept-behaviour tests).

**Changed tests:** `test_factory_report.py::TestHaltBundles::test_reads_bundles_and_skips_corrupt_ones` is now `test_reads_bundles_and_a_corrupt_one_stops_the_read`; `::test_stray_bytes_do_not_suppress_events` no longer reads the deleted `unreadable` field.

**Neighbouring suites:** before the test changes, 250 passed and 2 failed (exactly those two) across `test_cap_bundles.py`, `test_convergence_loud_failure.py`, `test_convergence_record.py`, `test_factory_report.py`, `test_gate_registry.py`, `test_non_pytest_red_is_deterministic.py`, `test_survived_infrastructure.py`, `test_alert_channel_at_start.py`, `test_github_writes_inert.py`, `test_halt_evidence.py` and the new file; after, 252 passed.

## speedrun/preserved.py

**New: `tests/unit/test_preserved_loud_failure.py` (9).** Site tests for 97 (two), 115, 124 (two) and 127, plus tests that pin kept behaviour: a written record returns True and reads back, an absent ledger is a quiet `[]`, and a clean ledger with a blank line reads with no alert.

**Before the fix, measured** against the unchanged module: 6 failed, 3 passed (the three kept-behaviour tests).

**Changed tests:** in `test_archive_bundles_graveyard.py::TestTheLedger`, `test_recording_never_raises_on_a_caller_saving_work` is now `test_a_record_that_cannot_be_written_raises_naming_the_ledger`, `test_a_malformed_line_does_not_hide_the_others` is now `test_a_malformed_line_alerts_and_stops_the_read`, and `test_a_record_without_a_branch_is_not_a_record` is now `test_a_record_without_a_branch_is_refused`.

**Neighbouring suites:** before the test changes, 308 passed, 3 failed (exactly those three) and 6 skipped across `test_archive_bundles_graveyard.py`, `test_factory_report.py`, `test_healing_ledger.py`, `test_input_rebuild_from_refs.py`, `test_interaction_matrix.py`, `test_leavings_janitor.py`, `test_mock_roll.py`, `test_spec_handoff_survives_janitor.py`, `test_speedrun_worktrees.py`, `test_worktree_readonly_retry.py`, `test_archive_readonly.py`, `test_archive_verify_completeness.py`, `test_rmtree_sites_are_gated.py`, `test_roll_archives_itself.py`, `test_runbook_0952_flags.py`, `test_solo_runbook.py`, `test_speedrun_archive.py` and the new file; after, 311 passed and 6 skipped.

## speedrun/worktrees.py

**New: `tests/unit/test_worktrees_loud_failure.py` (16).** Site tests for 97, 136, 223, 229, 236, 274, 286, 295, 300, 315, 330, 344 and 351, against real temporary git repositories (with a bare origin where a push must succeed), with `os` replaced by a stand-in carrying `st_file_attributes` for the ReadOnly sites so they run off Windows. Kept behaviour pinned: a healthy sweep alerts nobody, there is no attribute to clear off Windows, and every ReadOnly path is cleared.

**Before the fix, measured** against the unchanged module (with `preserved.py` already raising): 13 failed, 3 passed (the three kept-behaviour tests). The 295 test failed on the raise leaving `_preserve_dirty` unhandled.

**Changed tests:** `test_speedrun_worktrees.py::test_dirty_worktree_content_survives_a_failed_push` now asserts the worktree is kept, the entry is a problem and one alert; `::test_dirty_worktree_is_preserved_on_a_graveyard_branch` gains a bare origin so its push succeeds; `test_worktree_readonly_retry.py::TestClearingTheAttribute::test_it_never_raises_on_an_unreadable_corner` is now `test_a_chmod_that_fails_raises` (Windows-only, skipped on this Ubuntu machine, so not run).

**Neighbouring suites:** across `test_archive_bundles_graveyard.py`, `test_healing_ledger.py`, `test_input_rebuild_from_refs.py`, `test_interaction_matrix.py`, `test_leavings_janitor.py`, `test_mock_roll.py`, `test_spec_handoff_survives_janitor.py`, `test_speedrun_worktrees.py`, `test_worktree_readonly_retry.py`, `test_roll_archives_itself.py`, `test_solo_runbook.py`, `test_speedrun_archive.py`, the new file, and the twelve launcher suites listed under must_resolve: 439 passed, 1 failed (`test_dirty_worktree_is_preserved_on_a_graveyard_branch`, which had no origin), 8 skipped. After giving it an origin, the three worktree files: 40 passed, 5 skipped.

## speedrun/leavings.py

**New: `tests/unit/test_leavings_loud_failure.py` (8).** Site tests for 180, 213, 247, 263, 312 and 321 against a real repository with a bare origin, plus tests that pin kept behaviour: a healthy janitor alerts nobody, and pruning stops at a directory that still holds something (349).

**Before the fix, measured** against the unchanged module (with `preserved.py` already raising): 6 failed, 2 passed (the two kept-behaviour tests).

**Changed tests:** `test_speedrun_roll_attempts.py` (`_main` and `test_default_is_a_single_attempt`) and `test_speedrun_roll_detach.py` (`test_the_rebuilt_argv_actually_parses`, `test_a_roll_records_its_pid_so_it_can_be_stopped`, `test_a_finished_roll_leaves_no_pid_behind`) drive `main()` on a fake `.git` directory with the git-touching checks patched; they now also patch the baseline `untracked_files` read, which raises on a status that fails.

**Neighbouring suites:** across `test_archive_bundles_graveyard.py`, `test_healing_ledger.py`, `test_input_rebuild_from_refs.py`, `test_interaction_matrix.py`, `test_leavings_janitor.py`, `test_mock_roll.py`, `test_pass_criteria_carry_values.py`, `test_restore_from_graveyard.py`, `test_restore_loud_failure.py`, `test_restore_prefers_durable_and_base.py`, `test_resume_after_ceiling_halt.py`, `test_spec_handoff_survives_janitor.py`, `test_speedrun_new_attempt.py`, `test_zero_requirements_denominator.py`, the new file and the twelve launcher suites: before the test changes, 442 passed, 8 failed (exactly the eight above) and 3 skipped; after, 450 passed and 3 skipped.

## telemetry/cascade_events.py

**New: `tests/unit/test_cascade_events_loud_failure.py` (9).** Site tests for 72, 152 (two), 161 (two: an unparseable and a naive timestamp) and 170, plus tests that pin kept behaviour: with no window no timestamp is read, an absent log is zero stats, and a clean log counts every event in the window.

**Before the fix, measured** against the unchanged module: 6 failed, 3 passed (the three kept-behaviour tests).

**Changed tests:** `test_cascade_events.py::TestGetCascadeStats::test_corrupt_lines_skipped` is now `test_a_corrupt_line_stops_the_count`.

**Neighbouring suites:** before the test change, 129 passed and 1 failed (exactly that test) across `test_cascade_events.py`, `test_cascade_action.py`, `test_cascade_detector.py`, `test_circular_imports.py`, `tests/integration/test_cascade_hook_integration.py` and the new file; after, 130 passed.

## hooks/cascade_action.py, cascade_detector.py, cascade_patterns.py

**New:** `tests/unit/test_cascade_action_loud_failure.py` (4): site tests for 64 (a write that fails, an event that cannot be built), and pins that a recorded block and an allowed output alert nobody. `tests/unit/test_cascade_detector_loud_failure.py` (2): a site test for 81 and a pin that valid patterns still match. `tests/unit/test_cascade_patterns_loud_failure.py` (10): site tests for 221 (two), 228, 237, 245, 247 and 252, and pins for 214 (an absent config), a disabled config, and a valid config. Patterns and config paths are passed explicitly, so the default path and per-call read (open issues of their own) are not exercised.

**Before the fix, measured** against the unchanged modules: 10 failed, 6 passed (action 2 and 2, detector 1 and 1, patterns 7 and 3; the passes are the kept-behaviour tests).

**Changed tests:** `test_cascade_detector.py::TestCorruptConfigFallback::test_corrupt_config_fallback` is now `test_corrupt_config_raises_naming_it`.

**Neighbouring suites:** before the test change, 145 passed and 1 failed (exactly that test) across `test_cascade_events.py`, `test_cascade_action.py`, `test_cascade_detector.py`, `test_circular_imports.py`, `tests/integration/test_cascade_hook_integration.py`, the cascade-events loud-failure file and the three new files; after, 146 passed.
