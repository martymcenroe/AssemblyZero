# Test report: #4770

## T1

`poetry run pytest tests/unit/test_new_repo_ubuntu_run.py -q --tb=short`, on this machine with `~/.assemblyzero/config.json` setting `new_repo_root`: `22 passed, 1 warning in 11.55s`. The four tests named in the issue failed before the change, on the branch and on main at 94cc7239.

The fixture never reads the machine's file, so the result does not depend on whether that file exists. The file is the operator's, and it was not moved or removed to rerun the test without it.

## Unit tier, 2026-11-14

`poetry run pytest tests/unit/ -q --tb=short -v`, run directly rather than through test-gate (see #4758):

`6 failed, 15214 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1203.93s (0:20:03)`

The six are `tests/unit/test_pat_session_named_prompt.py::TestRealGpg`, which fail the same way on main; see #4766. No other test failed.

Ruff on `tests/unit/test_new_repo_ubuntu_run.py`: all checks passed.
