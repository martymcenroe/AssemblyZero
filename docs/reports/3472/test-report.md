# Test Report — Scope ruff to Maintained Source (#3472)

## What This Change Is

Five lines of configuration in `pyproject.toml`. No Python changed, no import
moved, no runtime path touched. The tool it configures is not invoked by the
test suite or by CI.

No test is claimed. The check that matters is what the linter reports before and
after, and that was measured rather than predicted.

## Measured

Before, on `main` at `b4e67761`:

```
Found 737 errors.
```

After:

```
399  F401  unused-import
 90  F541  f-string-missing-placeholders
 58  E402  module-import-not-at-top-of-file
 53  F841  unused-variable
 16  F811  redefined-while-unused
  8  E731  lambda-assignment
  7  E741  ambiguous-variable-name
  4  E712  true-false-comparison
  1  E722  bare-except
Found 636 errors.
```

**The invalid-syntax row is gone** — 14 to 0 — and no other rule's count rose.
That is the property worth asserting: an exclusion that accidentally swallowed
maintained source would show up as a *drop* in some other rule's count, and none
dropped.

The paths still in scope confirm it from the other direction:

```
385  tests
131  assemblyzero
117  tools
  3  docs
```

`assemblyzero`, `tools` and `tests` are unchanged at 385/131/117. Only `docs`
moved, 104 to 3.

## The Prediction Was Wrong, Which Is Why It Was Measured

The issue predicted 633. The answer is 636. The prediction came from
`ruff check assemblyzero tools tests`, which enumerates three directories and so
cannot see anything outside them — the three extra are in `docs/temp/`, tracked
one-off scripts each carrying an unused import.

Recorded because the failure mode is the reusable part: a denominator derived
from a hand-listed path set is not the same measurement as one derived from the
tool's own scope, and only the second is the number a CI gate would enforce.

## Not Verified

**The suite was not re-run.** No Python changed. Running it would demonstrate
that editing a TOML config does not affect Python behaviour, which is not in
doubt.

**Nothing enforces the exclusion stays narrow.** A future edit could add paths
to `extend-exclude` and make the lint count fall without a single defect being
fixed — the exact move this change is careful not to make. No check would catch
that. It is worth a guard once the count reaches zero, which is #3471's closing
condition, and not before, since any guard written now would assert against a
number still in motion.
