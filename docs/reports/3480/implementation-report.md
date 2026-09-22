# Implementation Report — Declare the Shim's Public Surface (#3480)

Piece of #3471.

## The Problem

37 F401 findings — the largest concentration in the repo — were in one file,
`assemblyzero/workflows/testing/nodes/implement_code.py`. Its docstring explains
why:

> This module is a backward-compatibility shim. The implementation has been
> split into focused modules under the `implementation/` package.
> All public names are re-exported here so existing imports continue to work.

Every name it imports is unused *within* it by construction. Being importable
from this path is the module's only job — it exists because #655 split the
implementation into a package and the old import path had to keep working.

To a linter that reads as 37 dead imports, and the obvious fix is deletion.
Deletion would break the eight test modules that import from this path, and any
caller still on it, with an `ImportError` at runtime rather than anything caught
earlier.

## Why Ruff Still Reported Them

The author anticipated this. The star import carries `# noqa: F401, F403`. The
explicit re-export block carries `# noqa: F811` — which silences *redefinition*,
not *unused import*. The suppression named one rule short, so the 37 individual
names stayed flagged.

## The Change

`__all__`, listing the 37 names, with a comment explaining why the module looks
the way it does.

This is deliberately not a wider `noqa`. `__all__` states the contract in the
language rather than in a linter directive: it is what `import *` honours, it is
checkable by something other than ruff, and ruff treats its members as used as a
consequence rather than as an instruction.

The four private names are intentional. `_mock_implement_code`,
`_summarize_class` and `_summarize_function` are imported from this path by
tests today — verified, not assumed — so they are part of the surface however
unusual they look in an `__all__`.

## Effect

| | before | after |
|---|---|---|
| total | 531 | **494** |
| F401 | 395 | **358** |

`ruff check` on the file itself: **All checks passed!**

Exactly 37, matching the prediction — the first of these three scoping
predictions to land on the number, because this one counted the findings in the
file rather than subtracting a subset from a total.

## Running Total for #3471

737 → 636 (#3472) → 546 (#3474) → 531 (#3479) → **494**.
