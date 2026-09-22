# Test Report — Declare the Shim's Public Surface (#3480)

## A New Test File, Because the Suite Could Not Have Caught This

```
poetry run pytest tests/unit/test_implement_code_shim_exports.py
5 passed
```

The issue said this change needed more than "the suite is green", and that was
the right call. The existing tests import a handful of names from the shim, so
they would catch the deletion of *those* — and say nothing about the other
thirty. A name dropped from `__all__` while still imported below, or promised in
`__all__` and absent, is an `ImportError` for a caller and invisible everywhere
else.

`tests/unit/test_implement_code_shim_exports.py` asserts the contract directly:

| test | property |
|---|---|
| `test_every_name_in_dunder_all_is_actually_importable` | `__all__` promises nothing the module lacks — the failure that would reach a caller |
| `test_dunder_all_has_no_duplicates` | the list is a set, so a merge cannot quietly double an entry |
| `test_the_names_tests_import_from_this_path_are_present` | the three private helpers tests rely on stay exported |
| `test_the_entry_point_is_exported` | `implement_code`, the name the docstring advertises, is present and callable |
| `test_star_import_yields_the_declared_surface` | `import *` yields exactly `__all__`, so the declaration is load-bearing rather than decorative |

The last one matters most: it proves `__all__` is doing work. Without it, the
list could drift from reality and every other assertion here would still pass.

## The Shim's Consumers Still Pass

```
poetry run pytest tests/unit -k "implement_code or progress_reporter"
132 passed, 10428 deselected
```

That selection covers all eight modules importing from the shim path:
`test_implement_code_context`, `_diff`, `_filetype`, `_path_validation`,
`_retry`, `_size_gate`, `_timeout`, and `test_progress_reporter`.

## Lint

`ruff check assemblyzero/workflows/testing/nodes/implement_code.py` →
**All checks passed!**, from 37 findings. Repo total 531 → 494, F401 395 → 358 —
exactly 37, no other rule moved.

## Not Verified

**The full suite was not re-run for this change.** It was for #3474, ten minutes
earlier in the same sequence; this change touches one module plus one new test
file, and the 132-test selection covers every consumer of that module. CI runs
the full tier on the PR and that is the governing check.

**Nothing asserts that `__all__` matches the import block above it.** The two
are maintained by hand and could drift — a name added to the import and not to
`__all__` would stop being re-exported by `import *` while still being
attribute-accessible, which is a quieter failure than the ones tested here. A
test comparing the two would need to parse the module's AST; worth doing, not
done, and named here rather than left implied.
