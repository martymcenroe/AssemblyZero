# Test report: #4690

## Unit

`tests/unit/test_api_symbols_pep560_bases.py`, 9 tests, and `TestTheSymbolCheck` in `tests/unit/test_validate_completeness_loud_failure.py`, 4 tests plus the 3 it already had.

- T1 (R1): `TestT1APep560BaseResolves`: `typing.TypedDict` and `typing.NamedTuple` resolve to a class; the TypedDict probe carries `setdefault`, `copy` and `items`; the NamedTuple probe carries `_asdict`; a spec with a TypedDict subclass calling `setdefault` and `copy`, and one with a NamedTuple subclass calling `_asdict`, pass with no ERROR on stderr or in the details.
- T2 (R2): `test_4690_an_unresolvable_base_that_hides_a_call_cannot_check`: `class Thing(ctypes.NoSuchBase)` calling `self.frobnicate_now()` raises `CompletenessCannotCheck` naming both. This replaces #3439's `test_3439_an_unresolvable_stdlib_base_is_named_at_error`, which pinned the pass. `TestADerivedClassInheritsTheBlindness`: a subclass of the blind class calling `frobnicate_later` raises too.
- T3 (R3): `test_4690_an_unresolvable_base_that_hides_nothing_is_named_at_error`: the same base on a class with no call returns, named at ERROR and in the details.
- T4 (R4): `TestT4AForeignBaseStillAbstains`: a `pydantic.BaseModel` subclass calling an unknown method passes with no ERROR.

Run against `main`'s code at `407faf68`, in a detached worktree with the two test files copied in: 7 failed, 9 passed. The NamedTuple `_asdict` probe test passes on `main` by accident, because `main` returns its failure record, itself a NamedTuple, whose `dir()` holds `_asdict`; the NamedTuple resolution and check tests fail there. With the change: 16 passed.

## Real spec

The spec that showed the ERROR passes with no ERROR, read only, as the implementation report says.

## Real calls

None.

## Lint

`ruff check` on the changed files adds no finding over `main`'s five in `validate_completeness.py` (I001, UP035, SIM114 and two PLW1510).

## Full suite

14,926 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed. The 18 are the set that fails on `main` without the change: 16 in `tests/test_auto_reviewer_wait_loop.py`, `tests/test_universal_claude_md.py::test_adr_references_resolve`, and one in `tests/integration/test_orchestrator_graph.py`.
