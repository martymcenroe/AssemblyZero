# Test Report: the ledger records the testing package (#3806)

## Checks, run on the ledger after recording

- T1: Findings rows for `assemblyzero/workflows/testing/` number 354, counted with `grep -c` on the file.
- T2: read marks for the package number 64, counted the same way. Files still marked "not yet read": 355, which is 466 − 47 (`core/`) − 64.
- Coverage: the readers' file lists, deduplicated, equal `git ls-files assemblyzero/workflows/testing` exactly (`comm -3` prints nothing): 64 files, one of them not `.py`.
- `ledger_record.py` refuses an unparseable report line. It refused none.

## Unit tier

No code changed. The tier was run before the push anyway, on `0651c7eb` plus this change: 10997 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 28s.
