# Test Report — Treat Recorded Test Fixtures as Data (#3479)

## What This Change Is

One line of TOML. No Python changed. No test input changed — that is precisely
the point: this change exists so that a later change does not edit them.

No test is claimed. What is checkable is the exclusion's exact effect and that
it caught nothing it should not.

## What Was Verified

**1. The exclusion removes exactly 15 findings, and which ones.** Pointing ruff
at the two directories explicitly overrides the exclusion and enumerates them:

```
6  F811  redefined-while-unused
5  E402  module-import-not-at-top-of-file
4  F401  unused-import
Found 15 errors.
```

546 − 15 = 531, which is the measured total afterwards.

**2. It did not over-match.** `ruff check tests/fixtures` now reports
`All checks passed!`. That looks alarming and is correct: all 15 of that
directory's findings were inside the two recorded-run directories, so removing
them leaves nothing. The earlier per-directory breakdown showed `15 fixtures`,
which is the same number.

**3. Real fixture helpers are still linted.** The pattern names
`issue7_run*`, not `tests/fixtures`. `tests/fixtures/scraper` — imported by
`test_scraper_import_safety.py` for its pytest fixtures — remains in scope.

**4. The remaining distribution accounts for the total.**

```
366  tests
107  assemblyzero
 55  tools
  3  docs
Found 531 errors.
```

## The Prediction Was Wrong Again, and That Is the Finding Worth Keeping

Predicted 542, measured 531. The prediction subtracted only the 4 F401 findings,
because F401 was the rule under work; the directories also held 5 E402 and 6
F811.

Identical in shape to #3472's miss — 633 predicted, 636 measured. Both times a
number derived from a filtered view was used to predict a change to the whole.
Both times the measurement was cheap and was taken. The habit to fix is
predicting at all when `--statistics` is one command away.

## Not Verified

**The suite was not re-run.** No Python changed and no fixture byte moved. The
tests that read these directories read identical bytes before and after.

**Nothing enforces that the exclusion list stays honest.** Two entries now, both
argued in comments, but a third could be added tomorrow to make a number fall
without fixing anything. That guard belongs with the CI lint step at the end of
#3471, where there is a stable count to assert against.
