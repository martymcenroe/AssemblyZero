# Test Report: a halt's files belong to one repository and one run (#4292)

## New tests: `tests/unit/test_halt_files_by_repository.py` (28)

Each builds its halts by running the real HALT node into the per-test state directory that `tests/conftest.py` redirects every binding to; nothing touches the operator's home.

- T1 (requirement 1, `TestAContractIsOnlyItsRepositorys`): a halt on repository A's #42 leaves a contract that a run on repository B's #42 neither verifies, consumes nor is refused by (B passes as a fresh run, A's file is untouched, no alert). A's own run still verifies and consumes it. A contract naming another repository found in this run's own place is refused by name. A worktree and its primary checkout are one repository, on a real throwaway git repository.
- Contracts from before the change (`TestAContractFromBeforeTheChange`): attributed from `audit_dir`. Another repository's is left byte-identical and named; this repository's, through its primary or one of its worktrees, is verified and consumed; one with no attributable repository, one whose repository git cannot read and one whose root is gone each refuse by name with an alert and stay in place. One test shows a run that reads a legacy contract for another repository leaves every file in the shared directory unchanged.
- T2 (requirement 2, `TestHaltFilesDoNotCollideAcrossRepositories`): two repositories both named `app` write distinct state, recovery-plan and contract paths, each in a directory of its own. The directory name carries no character unsafe on Windows. A halt whose state names no repository stops, alerts and writes nothing.
- T3 (requirement 3, `TestBriefRunsHaveKeysOfTheirOwn`): two briefs write distinct state, plan and contract files, none named for issue 0; one brief name in two directories differs; one brief rerun has one key; no issue and no brief raises.
- Mock (the comment on #4292, `TestAMocksHaltNeverReachesARealRun`): all three spellings of mock halt into the `mock` directory; a real run does not read or consume a mock's contract; a mock run resumes its own; a mock's contract in a real run's place is refused.
- The factory report still finds a halt bundle in the per-repository layout.

Each test fails without the change. On `main` the new API does not exist, so every test errors on `halt_paths` or on `check_and_consume`'s new `repo_root`. The behaviour was also checked by two mutations of this branch, each run and reverted: with `halt_directory` returning the shared directory, 7 of the 28 failed (T1, T2, the legacy-other case and all four mock cases); with `run_key` returning `"0"` for a brief, 4 failed (all of T3).

## Existing tests changed

These called the old API or built a halting state with no repository, which now stops. Each state now carries `repo_root`, and each path now goes through the repository's directory: `test_resume_contract.py`, `test_resume_contract_loud_failure.py`, `test_halt_node.py` (the alert test uses a real directory for `target_repo`), `test_halt_evidence.py`, `test_halt_evidence_loud_failure.py`, `test_halt_legibility.py`, `test_state_persistence.py`, `test_state_persistence_loud_failure.py`, `test_home_state_guard.py`, `test_impl_lands_through_driver.py`, `test_spec_graph_loud_failure.py`, `test_testing_graph_loud_failure.py`.

## Full runs, 2026-10-31

Unit tier, `poetry run pytest tests/unit -q --tb=short -p no:cacheprovider`:

    13238 passed, 66 skipped, 7 deselected, 7 xfailed, 26 warnings in 980.74s (0:16:20)

Integration, `ASSEMBLYZERO_MOCK_MODE=1`, `tools/test-gate.py tests/ -m integration`:

    64 passed, 7 skipped, 13870 deselected, 26 warnings in 73.36s (0:01:13)

E2E, same environment, `-m e2e`:

    19 passed, 13922 deselected, 26 warnings in 34.56s

An earlier unit run found five failures: a new fail-open site in the attribution helper (now a handler that alerts and refuses), and four tests with states that name no repository (corrected above). `tests/unit/test_loud_failure_check.py` passes with no new baseline site and no new halt row.

`ruff check` on the changed files shows only findings already present on `main` (import order, `datetime.UTC`, a `subprocess.run` without `check`).
