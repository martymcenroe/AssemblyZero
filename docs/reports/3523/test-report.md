# Test Report — The fail-open denominator check leaves the PR gate for --check --strict (#3523)

Backfilled 2026-09-25 after the merge, from PR #3529 (merge `0bb5fa69`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New class `TestTheDenominatorLeftThePRGate` in `tests/unit/test_fail_open_audit.py`:

- `test_adding_a_function_passes_the_gate_without_touching_the_baseline`: builds a temporary tree, writes a baseline, adds a file with a function and no fail-open site, then shows `check()` passes, the baseline file is byte-identical, and strict mode reports `files_scanned` moving from 1 to 2.
- `test_strict_is_clean_on_the_tree_it_was_measured_against`
- `test_a_missing_denominator_is_drift_not_a_pass`
- `test_a_removed_baselined_site_is_still_stale`

`test_the_denominator_matches_what_it_was_measured_against` was replaced by `test_the_baseline_states_a_denominator`.

## Results the PR reported

All four new tests fail before the change, because `denominator_drift` did not exist. `tests/unit/test_fail_open_audit.py`: 57 passed. On the real tree, `--check --strict` printed `PASS -- 305 files, 9327 sites examined, no new fail-open, denominator matches.`

## Not verified for this backfill

- Nothing was re-run.
