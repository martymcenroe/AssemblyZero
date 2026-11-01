# Test report: #4490

## Changed tests

- `tests/unit/test_pytest_runs_in_the_target.py` (new):
  - `TestT1TheRunIsInTheTargetsEnvironment` (R1, AC1): `run_pytest`, the questions put to poetry, the runners and the E2E run all shed the virtualenv, and nothing else in a run starts pytest.
  - `TestTheTargetsOwnPytest` (R1): a target with no pytest halts and nothing runs, through all three call sites, and each way the question can fail is named.
  - `TestT2CoverageIsDecidedByTheTarget` (R2, AC2): the workflow's own `pytest_cov` does not satisfy the check. The target's interpreter is a real second one, built by `venv`, so that is measured.
  - `TestT3ATargetWithNoProjectOfItsOwn` (R3, AC3): a tool-only `pyproject.toml` and no `pyproject.toml` both halt, poetry is not asked, and a parent's project does not count.
- `tests/unit/conftest.py`: `target_can_run_pytest`, beside `coverage_as_reported`, for a test that fakes its pytest run and so has no environment to ask. `test_testing_workflow.py`, `test_e2e_validation_loud_failure.py`, `test_pytest_runs_at_vv.py` and `test_changed_line_coverage.py` use it.
- `tests/unit/test_verify_phases_loud_failure.py` and `test_failure_feedback_carries_reasons.py`: the two tests that pinned the old behaviour, the import in this process and the inherited environment.
- `tests/unit/test_mock_scaffolds_every_framework.py`: `step_provision` fails when a pytest proof did not hold, even with both suites green.

## Runs, 2026-11-01

- The tests cannot run on `main`, where `target_env.py` does not exist, so each defect was put back in turn and every file restored byte for byte: seven mutations, all caught. They were `run_pytest` inheriting the virtualenv (1 test), coverage asked of this process (9), no check for pytest (3), no check for a project (4), the questions to poetry inheriting the virtualenv (1), the E2E run inheriting it (1), and the runners inheriting it (1).
- `tools/rehearse_two_frameworks.py provision`, 8:17 AM Central, under AssemblyZero's virtualenv: `poetry install` and `npm ci` done; `run_pytest` listed no plugin and passed; coverage was refused naming pytest-cov; with the fixture's `coverage` group installed, coverage was measured, `coverage.json` written, and the one plugin listed was pytest-cov; Vitest passed; worktree and environment removed.
- `tools/rehearse_two_frameworks.py mock`, 8:17 AM Central: both workflows exit 0, both scaffolds written, snapshots identical.
- `run_pytest` on real targets under the same virtualenv: a tool-only `pyproject.toml`, no `pyproject.toml`, a project never installed, no pytest, and no pytest-cov each halted by name, and a target with pytest ran 1 test with no plugin listed.
- Unit tier, 8:39 AM Central, after the last code edit: 13542 passed, 66 skipped, 7 deselected, 7 xfailed in 8m 33s.
- Integration, e2e and adversarial tiers together, 8:41 AM Central, after the last code edit: 84 passed, 7 skipped, in 36 s.
- `ruff check`: nothing new. The changed files carry the same findings as `main`.

No real run was started on any target.
