# Test report: #3758

## New: `tests/unit/test_fresh_recheck_keeps_settled.py` (2)

`ensure_base(fresh=True)` with every collaborator stubbed: the gate answers `[committed LLD, untracked spec]` before the reset and `[committed LLD]` after it.

- `test_a_settled_artifact_the_reset_kept_is_not_a_finding`: the recheck finds the LLD settled; `ensure_base` returns the base, logs `BASE settled, preserved after reset:`, never logs `still dirty after reset`, and does not call `replace_or_refuse`.
- `test_an_unsettled_artifact_after_the_reset_still_counts`: the recheck finds it unsettled; `replace_or_refuse` receives it and the launch stops.

## Runs, 2026-10-07, Ubuntu (WSL)

- With the fix stashed (named path): the settled case fails, the unsettled case passes (its behaviour is meant to be unchanged). With the fix: 2 passed.
- `tools/audit_halt_sites.py --check`: PASS. `tests/unit/test_fail_open_audit.py`: 57 passed.
- Full `tests/unit`: 10950 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 11s.
- `ruff check`: `speedrun_roll.py` 37/37 against `main`; the new test file clean after `--fix` dropped a redundant `return None` from the `replace_or_refuse` stub (rerun: 2 passed).
