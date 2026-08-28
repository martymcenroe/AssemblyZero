# Implementation Report — The Guard Interaction Matrix (#2568)

## Issue Reference
[#2568: guard-vs-guard is the emergent defect class -- an interaction invariant suite for mechanisms sharing an artifact](https://github.com/martymcenroe/AssemblyZero/issues/2568)

## Files Changed
- `assemblyzero/core/interaction_matrix.py` (new): the matrix as data — artifacts, mechanisms, ruled cells.
- `docs/standards/0030-guard-interaction-matrix.md` (new): the written matrix.
- `tests/unit/test_interaction_matrix.py` (new): the checklist lint — 30 tests.

## The Central Decision: The Matrix Is Data

A matrix living only in prose goes stale the first time someone adds a mechanism. Here the artifacts, mechanisms and cells are Python, and the lint enforces three things a document cannot:

1. **No undeclared mechanism.** A module calling one of an artifact's signature symbols and appearing in no mechanism fails **by name**. This is the "new mechanism fails a checklist lint until it appears in the matrix" the issue asks for.
2. **No unruled cell.** Every mechanism pair is fixture-backed or marked non-interacting **with a reason**. `Cell.ruled()` rejects both-and-neither, so a cell cannot carry a fixture *and* a hand-wave.
3. **No phantom.** Declared modules and named fixtures must exist, and a signature symbol nothing calls fails as **dead** — a scan looking for a symbol that is never called is weaker than it looks, and that weakness would be invisible.

## What The Lint Found That Reading Did Not

Building the matrix from `assemblyzero/` alone produced a matrix that **missed the mechanism responsible for #2551**. Scanning `tools/` as well, the lint reported four undeclared modules:

- `tools/speedrun_roll.py`, `tools/speedrun_new_attempt.py` — calling `classify_dirt`, `preserve_and_clear`, `is_pipeline_input`. These are the **sweep sites**: where a launch decides what to clear, and where the 2026-08-27 kill happened.
- `tools/run_implement_from_lld.py`, `tools/run_implementation_spec_workflow.py` — calling `check_and_consume`. Where a resume actually verifies its contract.

Neither pair appears in the issue's proposed enumeration. That is the argument for a lint over a written list, and it is why `SCAN_ROOTS` includes `tools/`.

## Coverage

Three artifacts, 11 mechanisms, **15 ruled cells** — 12 fixture-backed, 3 reasoned non-interacting. All four of the campaign's named pairwise kills have cells, asserted directly by `test_the_campaigns_four_pairwise_failures_are_all_covered`.

A `test_most_cells_are_fixture_backed_not_reasoned_away` floor asserts at least half of all cells carry a fixture, because a matrix of non-interaction reasons is a matrix that gave up.

## Deliberately Incomplete

The issue names a fourth artifact — requirement/verdict state. It is **absent, and the standard says so with the reason**: its mechanisms are graph nodes reached through LangGraph routing rather than direct calls to a shared symbol, so the call-site scan that makes this lint honest cannot see them. Adding it with a weaker scan would produce a matrix that looks complete and enforces nothing, which is worse than an absent one because the green cells read as coverage.

Filed as #2602 with two candidate detection mechanisms and a recommendation to rule before building.

## Known Limitations

- Detection is call-site based, so a mechanism reaching an artifact purely through graph state is invisible to it (#2602).
- `SCAN_EXEMPT` carries two entries — the module that defines `is_pipeline_input`, and the golden-disaster corpus, which replays artifacts but never runs inside a roll. Each is listed with its reason and asserted to exist.
