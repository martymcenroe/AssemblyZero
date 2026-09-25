# Test Report — --mock drafts a valid LLD so a mock LLD run reaches review and finalize (#3533)

Backfilled 2026-09-25 after the merge, from PR #3534 (merge `51057e77`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_lld_mock_completes.py`:

- `test_a_mock_lld_run_reaches_finalize_and_writes_the_lld`: runs `tools/run_requirements_workflow.py` `main()` with `--type lld --mock` against a throwaway repo with a bare origin, and asserts exit 0, a written `LLD-042.md`, and no `MECHANICAL VALIDATION FAILED`.
- `test_the_default_mock_lld_drafter_is_mock_lld`
- `test_an_explicit_mock_draft_drafter_keeps_the_failing_draft`

## Results the PR reported

Against the old code, the first two fail; the first fails with the N1.5 halt. The third pins behaviour that is unchanged. With `tests/unit/test_requirements_nodes.py`: 101 passed. `tools/audit_fail_open.py --check` passed without touching the baseline.

## Not verified for this backfill

- Nothing was re-run.
