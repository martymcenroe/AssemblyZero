# Implementation Report — Remove 358 Unused Imports (#3483)

Piece of #3471, and the end of the F401 work.

## The Change

```
ruff check . --select F401 --fix
Found 358 errors (355 fixed, 3 remaining)
```

193 files, 41 insertions, 354 deletions. The insertions are reflow — removing
one name from a multi-name parenthesized import rewrites the line.

Applied with `--select F401` rather than a blanket `--fix`, so the diff holds one
kind of change and a failure afterwards has one candidate cause.

## The Two Dangerous Shapes Were Removed From This Set First

This tranche is safe because the imports that must *not* be deleted were taken
out of scope before it ran:

- **Re-exports** — a name imported so callers can import it from here. Deleting
  one is an `ImportError` for a caller. Handled in #3480 with `__all__`.
- **Test data** — files read by path and asserted on. Deleting an import edits
  what a test measures. Handled in #3479 by excluding them.

## The Three Ruff Declined, Each Read Individually

Ruff is conservative in `__init__.py` and inside `try/except ImportError`, so it
left three. None was deleted on the strength of the rule alone.

**`implementation/__init__.py:53` — `BATCH_SIZE`.** Ruff's own message offers
"removing, adding to `__all__`, or using a redundant alias", which is the
re-export question. Traced: that file *has* an `__all__` and `BATCH_SIZE` is not
in it; `BATCH_SIZE` is defined in `orchestrator.py` and used only there; nothing
imports it from the package; and it is absent from the #3480 shim's `__all__`,
so the star import does not carry it. Genuinely unused. Removed.

**`test_validate_mechanical.py:20,27` — `extract_files_from_section`,
`ValidationError`.** These sit inside a TDD-era probe:

```python
# Import will fail until implementation exists - that's expected for TDD
try:
    from ...validate_mechanical import (...)
except ImportError:
    # Expected during TDD - tests will fail with import error
    pass
```

The module exists now, and the handler is `pass` — it swallows the error rather
than skipping, so the probe asserts nothing. The other names in the block are
used; these two are not. Removed.

## Effect

| | before | after |
|---|---|---|
| total | 494 | **123** |
| F401 | 358 | **0** |
| F811 | 10 | **0** |

F811 going to zero is a side effect worth naming: those ten were
redefined-while-unused, and removing the unused import removed the redefinition.
No F811-specific work was done or needed.

## Running Total for #3471

737 → 636 (#3472) → 546 (#3474) → 531 (#3479) → 494 (#3480) → **123**.

Remaining: F841 53, E402 50, E731 8, E741 7, E712 4, E722 1.
