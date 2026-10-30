# Test Report: the requirements workflow's graph and nodes under standard 0034 (#3585 step 5)

Each fixed site has a test that fails before its fix and passes after, run first against the unchanged module. Filled in module by module on `3585-requirements-nodes`.

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
