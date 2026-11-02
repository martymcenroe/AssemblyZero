# Test report: #4512, #4513, #4514, #4515, #4516, #4517

## Changed tests

`tests/unit/test_green_phase_real_run_defects.py` (new, 72 tests), by issue:

- #4512: the declaration reaches the prompt and the real call, a missing type is said to be missing, a type in the failing file is not repeated, a re-export is followed, a type alias ends at its semicolon, builtins are skipped, and the run's files are listed.
- #4513: the helper's four cases, and both paths through N4. The whole-file path is the one the real run took.
- #4514: each check refused and passed, a tool held in a variable, a filter that alternates, a spec that cannot emit fails all three, findings name their function, and `_run_checks` itself returns all three.
- #4515: a stall is flagged and recorded, the run goes on, a change clears it, and through `_verify_green_non_pytest` a typecheck stop reports no test count and the cap names the compiler error and the stall.
- #4516: the second framework runs, N4 and a halt hear from both, the ranking, and a framework that cannot start still halts.
- #4517: a real node of the built graph records itself, the halt reads it, and the cap has its own type.

Existing tests changed:

- `test_check_classification.py`: the catalogue grows from 17 checks to 20.
- `test_completeness_message_addressability.py`: the three checks are declared as driven elsewhere, with the reason.
- `test_changed_line_coverage.py`: `test_r2` gains `real_pytest`, because its target's pytest framework now runs. It never had to before.

## Runs, 2026-11-01

The last code edit was at 8:13 PM Central. Both tier runs came after it.

- Unit tier, finished 8:31 PM Central: 13738 passed, 66 skipped, 7 deselected, 7 xfailed in 17m 04s.
- Integration, e2e and adversarial tiers together, finished 8:33 PM Central: 84 passed, 7 skipped, in 1m 53s.
- `ruff check`: nothing new. The changed source files carry the same findings as `main`, and the new test file has none.

## Mutations

Each defect was put back in turn and every file restored byte for byte: 31 mutations, all caught.

The first attempt reported 27 of 27 and was worthless. One new test was already failing on clean code and `-x` stopped there, so most of those were that one failure, and one mutation was a syntax error. The script now refuses to run unless the baseline passes, and counts only a failed test as caught. The honest first result was 26 of 29. The three survivors showed:

- a test that used the edit-script path when the real defect was on the whole-file path;
- a test that called a helper nothing proved was wired in;
- a test whose input the regular expression never matched, which was also a real bug: the compiler opens TS2322 with a capital.

All three are repaired.

## Real runs

- T4 of #4512, one real call at 7:39 PM Central on the failure that stopped the run, `gemini-3.8-flash-high`, 11.6 s: one edit, `score.cost_usd` to `score.cost.value_usd`. The same failure drew `NO-EDIT` twice on the run. This is one call on one failure.
- The new checks on the real corrected spec: all five pass. Before correction they refused it.
- The corrected spec's tests against the code of the halted run: the test that had passed by skipping everything ran and found the real bug, `expected undefined to be 4533325.86`.

No full run has been made on this code yet. That comes next, and its result goes on the target's tracking issue.
