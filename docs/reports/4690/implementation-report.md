# Implementation report: #4690

A real implementation-spec run on a TypeScript target (a Vitest web suite beside a Python suite), on Python 3.14.4, printed `ERROR [N3] api_symbols_exist cannot resolve a standard-library base on this host: ... typing.TypedDict (it names a function, not a class)` and then passed the check. `typing.TypedDict` and `typing.NamedTuple` are functions that hand a subclass its real base through `__mro_entries__` (PEP 560), so `_resolve_stdlib_class` refused them, and the check passed while every method such a class inherits went unjudged.

## What changed

- R1, `_resolve_stdlib_class`: a standard-library name that is not a class but carries a callable `__mro_entries__` is resolved to a probe class built with `types.new_class("_InheritedSurfaceProbe", (base,))`. The probe's namespace gets `__module__`, which `NamedTuple`'s metaclass reads and `new_class` does not set. A `TypedDict` probe is a `dict` subclass, a `NamedTuple` probe a `tuple` subclass with `_asdict`. Only the standard library runs. A base that refuses a subclass returns a `_BaseResolutionFailure` naming the error.
- R2, `_inherited_surfaces` and `_flag_calls`: a class whose standard-library base cannot be resolved, and every spec class derived from it, is recorded in `blind_classes`. A call on a blind class that the check would otherwise judge (not in the allowlist or the builtin type methods) is collected in `unjudged_calls`. `check_api_symbols_exist` raises `CompletenessCannotCheck` when any is collected, naming the calls and the bases, as it already raises when N1 gathers no symbols (#3585).
- R3: an unresolvable base on a class that carries no judged call keeps today's ERROR line and details note (#3439).
- R4: a foreign base still abstains silently (#2839); `blind_classes` holds only standard-library failures.

## What did not change

`detect_unknown_method_calls`, the telemetry path, calls `_flag_calls` without `unjudged_calls` and behaves as before. No other check changed.

## The real spec

The spec that showed the ERROR, checked with `check_api_symbols_exist` against the 245 symbols `_extract_symbols_from_base` gathers from the target's `main`: on `main`, `passed: True` with the ERROR; with the change, `passed: True` with no ERROR, because `ObservationOutageDict(TypedDict)` now resolves.
