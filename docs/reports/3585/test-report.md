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
