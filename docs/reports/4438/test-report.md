# Test report: #4438, #4489

## Changed tests

- `tests/unit/test_mock_scaffolds_every_framework.py` (new):
  - `TestT1TheMockScaffoldsEveryFramework`: one Python and one TypeScript file, each in its framework's directory, and N2.5 accepts the pair (#4438 T1).
  - `TestAMocksPlaceholdersAlertNoOne`: `test_t1_a_mock_run_alerts_no_one_and_says_why` and `test_t2_a_real_runs_placeholders_still_alert` (#4489 T1, T2).
  - `TestARunOfOneFramework`: a pytest run writes the one file, and a Vitest run writes no Python.
  - `test_a_framework_the_run_cannot_scaffold_halts_by_name`.
  - `TestTheProvisionStepCannotPassOnNothing`: the `provision` step's verdict, which needs no network to hold: a suite that ran nothing fails, a failing suite fails, and pytest gets no `VIRTUAL_ENV`.
- `tests/integration/test_two_framework_rehearsal.py::test_both_workflows_pass_and_leave_nothing_behind` (new, #4438 T2, #4489 T3): the `mock` step, in child processes, with stand-in alert credentials and a throwaway home.

## Runs, 2026-11-01

- With `scaffold_tests.py` and `validate_tests_mechanical.py` set aside by a named stash and restored after: 6 of the new unit tests failed, and so did the integration test.
- `tools/rehearse_two_frameworks.py mock`, 3:07 AM Central: both workflows exit 0, both scaffolds written, snapshots byte-identical by `cmp`, and `alerts.jsonl` unchanged at 15 lines.
- `tools/rehearse_two_frameworks.py provision`, 3:07 AM Central: `poetry install` and `npm ci` done in a run's worktree; pytest 1 passed and Vitest 1 passed, each exit 0, with pytest in the fixture's own environment; worktree and environment removed.
- Earlier passes of `provision` found a fixture defect (no `pythonpath`), a cleanup defect (`poetry.lock` untracked), and #4490. The logs are posted on #3585 and #4438.
- All four tiers on this branch merged with `main` at `b5d1690b`: integration 65 passed and 7 skipped; e2e 19 passed; adversarial 1 skipped; unit 13510 passed, 66 skipped, 7 deselected, 7 xfailed in 8m 38s, after the last edit, an import reorder.
- `ruff check` on the three new Python files: all checks passed.
