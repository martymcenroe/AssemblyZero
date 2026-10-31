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
