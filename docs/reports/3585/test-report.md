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

**Known failure:** `test_lld_mock_completes.py::TestMockFinishesAnLLDRun::test_a_mock_lld_run_reaches_finalize_and_writes_the_lld` fails: the mock drafter's LLD title carries no issue number, so N1.5 blocks it. It passes at the base commit. The remedy is the mock's title in `llm_provider.py`.
