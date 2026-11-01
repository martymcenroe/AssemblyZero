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
