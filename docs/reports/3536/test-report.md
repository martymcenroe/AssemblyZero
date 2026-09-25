# Test Report — Derive the Projects root from the checkout instead of spelling it (#3536)

Backfilled 2026-09-25 after the merge, from PR #3544 (merge `888d759d`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

`tests/unit/test_assemblyzero_config_derived.py` (new): the derived defaults for a Windows drive, a `/mnt/c` path and an ext4 path.

## Results the PR reported

`poetry run pytest tests/unit/test_assemblyzero_config.py tests/unit/test_assemblyzero_config_derived.py`: 27 passed. `ruff check` on the changed files: two findings, both on lines the PR did not touch (`audit_fully_landed.py:76` E722, `assemblyzero-permissions.py:241` E741). The full unit suite ran in CI.

## Not verified for this backfill

- Nothing was re-run.
- The PR body does not state an old-code run for the new tests.
