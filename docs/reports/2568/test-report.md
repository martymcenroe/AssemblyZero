# Test Report — The Guard Interaction Matrix (#2568)

## Issue Reference
[#2568: guard-vs-guard is the emergent defect class -- an interaction invariant suite for mechanisms sharing an artifact](https://github.com/martymcenroe/AssemblyZero/issues/2568)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_interaction_matrix.py` (new) | **30 passed in 4.3s** |
| `tests/unit` (full) | see below |
| `ruff` on both new Python files | clean |

## The Lint Earned Its Place On First Run

It failed, correctly, four times before the matrix was complete:

1. **Two undeclared sweep sites** — `tools/speedrun_roll.py` and `tools/speedrun_new_attempt.py` call `classify_dirt`, `preserve_and_clear` and `is_pipeline_input`. These are where #2551 actually happened, and a matrix built by reading `assemblyzero/` alone had missed them.
2. **Two undeclared resume verifiers** — `tools/run_implement_from_lld.py` and `tools/run_implementation_spec_workflow.py` call `check_and_consume`.
3. **A dead signature** — `input_refs` was declared as a scan symbol and is called nowhere, so it contributed nothing. Removed.
4. **A missing standard** — `test_the_standard_documents_every_artifact` failed until `0030` existed and named every artifact and mechanism.

Every one of those is a hole a written-only matrix would have carried indefinitely.

## What Is Actually Pinned

**The checklist lint (4 parameterised groups).** Per artifact: no undeclared module touches it; every declared module exists; every signature is called somewhere; plus a global check that every `SCAN_EXEMPT` entry names a real file. The undeclared-module failure message names the module, the symbols it called, and both remedies (declare it, or exempt it with a reason).

**Cell completeness (5 parameterised groups).** Every mechanism pair has a cell; no cell has both a fixture and a non-interaction reason, or neither; every cell states an invariant of at least twenty characters; every named fixture file exists; no cell references a mechanism that does not exist.

The "both or neither" check is the load-bearing one — without it a cell could carry a fixture *and* a hand-waving reason, and read as ruled twice over.

**Substance (3).** All four of the campaign's named pairwise kills have cells, asserted individually by artifact and pair rather than by counting. At least half of all cells are fixture-backed, because a matrix of non-interaction reasons is a matrix that gave up. And the standard document must name every artifact and every mechanism — so the prose and the data cannot drift apart, which is the failure mode that made a written matrix worthless in the first place.

**Primitives (2).** `Cell.ruled()` rejects both-and-neither; `key()` is order-insensitive, so a cell written `(b, a)` is found when looked up as `(a, b)`.

## Coverage

3 artifacts, 11 mechanisms, 15 cells — 12 fixture-backed, 3 reasoned. The fourth artifact from the issue is absent by decision, named as absent in the standard with its reason, and filed as #2602.

## Regression Risk

Additive and inert at runtime: `interaction_matrix.py` is pure data plus two small helpers, imported only by its own test. No production path touches it. The standard is documentation. The only way this change can break anything is by failing its own lint, which is its purpose.
