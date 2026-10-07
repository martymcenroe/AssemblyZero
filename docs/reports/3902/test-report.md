# Test Report: the ledger records the last 294 files (#3902)

## Checks, run on the ledger after recording

- **T1:** the Findings rows number 1,202 for `tools/` and 1,354 for `assemblyzero/`, counted with `grep -c` on the file. The `assemblyzero/` figure is 215 (`core/`) + 354 (testing) + 199 (requirements) + 158 (implementation_spec) + 177 + 251 (this PR). The total is 2,556.
- **T2:** rows still marked "not yet read": 0.
- **Coverage:** for each package, the readers' file lists together equal `git ls-files` for the package exactly (`comm -3` prints nothing), and the four `tools/` quarters overlap nowhere.
- **Verification:** every report passes `verify_findings.py` with no mismatch and no unparseable line.

## Unit tier

No code changed. The tier ran anyway, on `67a6a658` plus this change: 11,018 passed, 66 skipped, 7 deselected, 6 xfailed in 9m 27s.
