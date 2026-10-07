# Test Report: ADR 0236 and ADR 0237 (#3579, #3582)

## Tests added or changed

None. This PR adds two decision records and no code. The tests the ADRs require land with the steps that implement them:
- #3583 adds the `ast` guard that ADR 0237 defines;
- #3580 adds the loud-failure check that ADR 0236 defines;
- #3724 and #3725 each carry their own tests.

## Runs, 2026-10-06

- Full `tests/unit` tier from the worktree: 10824 passed, 68 skipped, 7 deselected, 6 xfailed in 10m 49s.
- `tools/audit_fail_open.py --check --strict`: `PASS -- 309 files, 9515 sites examined, no new fail-open, denominator matches.`
- `tools/audit_halt_sites.py --check`: `PASS -- 179 files, 143 halt sites, every one registered`.
- `git grep -o "fail-open:" -- 'assemblyzero/*.py' 'tools/*.py'`: 130 tags in 50 files, unchanged by this PR.
