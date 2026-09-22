# Implementation Report — Treat Recorded Test Fixtures as Data (#3479)

Piece of #3471.

## The Change

One line of `[tool.ruff]` config, plus the comment explaining it:

```toml
extend-exclude = ["docs/lineage", "tests/fixtures/issue7_run*"]
```

## Why These Files Are Not Source

`tests/fixtures/issue7_run*/` is captured generator output — what the
scaffolding workflow emitted on the run named by the directory. Nothing imports
it. Five test modules read it **by path**, as text:

```python
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "issue7_run192332"
```

`test_generated_test_symbols.py`, `test_empty_branch_guard_clauses.py`,
`test_scaffold_emits_spec_bodies.py`, `test_scaffold_gates_see_stubs.py` and
`test_spec_stage_pair.py` all consume them that way, and they assert on the
**content** — which symbols a generated scaffold carries, whether guard clauses
are empty, whether stubs are visible.

Deleting an import line there edits the input a test measures. Best case the
test still passes while measuring something that never happened; worst case it
fails and invites someone to edit the fixture further until it passes.

Same objection as the lineage artifacts in #3472, with a sharper edge: those
were inert records, these are live test inputs.

## Effect, Measured

| | before | after |
|---|---|---|
| total | 546 | **531** |

The exclusion removes exactly 15 findings. Confirmed by pointing ruff at the two
directories explicitly, which overrides the exclusion:

```
6  F811  redefined-while-unused
5  E402  module-import-not-at-top-of-file
4  F401  unused-import
Found 15 errors.
```

## A Second Wrong Prediction, Same Cause

The issue predicted **542**. The answer is **531**.

The prediction counted only the four F401 findings, because F401 was the rule
being worked on. Those directories also held 5 E402 and 6 F811, which the
exclusion takes with them.

This is the same mistake as #3472, where 633 was predicted and 636 measured, and
the shape is identical: a number derived from a filtered view of the data
predicts a change to the whole. Recorded twice now because the correction is
cheap and the habit is not — the fix is to measure the total, never to subtract
a subset from it.

## The Exclusion Did Not Over-Match

`ruff check tests/fixtures` afterwards reports **All checks passed** — and that
is the right answer, not an over-match, because all 15 of that directory's
findings were inside the two recorded-run directories.

`tests/fixtures/` as a whole stays linted. It holds real importable helpers,
`tests/fixtures/scraper` among them, which is imported by a test for its pytest
fixtures. Only the `issue7_run*` directories are named.

## Running Total for #3471

737 → 636 (#3472) → 546 (#3474) → **531**.
