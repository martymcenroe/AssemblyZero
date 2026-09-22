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

## A Fourth Re-Export Site, Found by CI Rather Than by Reading

The sweep broke one test, and the break is the most useful thing in this change.

`assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` carries:

```python
# The three signature summarizers moved to core (Tiphys, #1688) ... The
# `_`-prefixed aliases preserve this module's historical import surface
from assemblyzero.core.interface_surface import (  # noqa: E402
    summarize_class as _summarize_class,
    summarize_function as _summarize_function,
    summarize_python_file as _summarize_python_file,
)
```

Two of the three are unused *within* the module. Ruff removed them and kept the
third, which is used internally. The result:

```
ImportError: cannot import name '_summarize_class' from
  assemblyzero.workflows.implementation_spec.nodes.analyze_codebase
```

in `test_spec_stage_aliases_are_the_core_functions`, whose docstring is *"The
move must be aliasing, not copying — one yardstick."* The test exists precisely
to assert that surface.

**The comment above the import said what it was for, and the `noqa` named E402
but not F401** — so nothing machine-readable told the sweep to stop. The same
one-rule-short mistake as the shim in #3480, in a different file.

Restored, with `# noqa: E402, F401` and a comment recording why, so the next
sweep has the signal this one lacked.

The lesson for the parent: three re-export sites were found by reading before
the sweep (#3479, #3480, `BATCH_SIZE`), and the fourth was found only by running
the whole suite. Reading found most of them; it did not find all of them.

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
