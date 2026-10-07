# Test Report: the ledger records requirements and implementation_spec (#3854)

## Checks, run on the ledger after recording

- **T1:** the Findings rows number 199 for `requirements/` and 158 for `implementation_spec/`, counted with `grep -c` on the file.
- **T2:** the read marks number 35 and 26.
- **Files still "not yet read":** 294, which is 466 − 47 (`core/`) − 64 (`testing/`) − 61.
- **Coverage:** for each package, the two readers' file lists together equal `git ls-files` for the package exactly (`comm -3` prints nothing).
- **Unparseable lines:** `ledger_record.py` refuses one, and refused none.
- **Line numbers:** neither package changed between `79e18ad1` and `origin/main` (`git diff --stat` is empty), so the numbers in the rows stand.

## Unit tier

No code changed. The tier ran anyway, on `e894b2bc` plus this change: 11,009 passed, 66 skipped, 7 deselected, 6 xfailed in 9m 8s.
