# Implementation Report — The Manifest Abstain Carries Its Denominator (#2608)

## Issue Reference
[#2608: the assertion-manifest stage reads 'cannot see the table' as 'no table'](https://github.com/martymcenroe/AssemblyZero/issues/2608)

## The Diagnosis: Neither Enumerated Reading

Established against the preserved run-19 lineage before any code changed, driving the real parsers. [Posted to the issue first.](https://github.com/martymcenroe/AssemblyZero/issues/2608#issuecomment-5454081845)

**Reading 2 (parser brittleness) is refuted.** `parse_tables` found and parsed **all 15** tables in the LLD and the 1 in the source issue. `is_criteria_table` correctly returned False for all 15 — none carries both an ID and a binding column. There is no parse failure, so "found N tables, 0 parseable" would have been the wrong message.

**Reading 1 is literally true and its conclusion false.** The LLD carries no criteria decision table because the **derivation destroyed it**:

| artifact | tables | criteria tables | S-rows |
|---|---|---|---|
| `001-issue.md` (source) | 1 | **1 — nine rows, S1–S9, 3,539 chars** | S1…S9 |
| `002-draft.md` (first derivation) | 15 | **0** | **none at all** |
| `003-draft.md` (post-#2563 repair) | 15 | **0** | 7 bullets: S1–S6, S8 |
| `005-final.md` (passed lld) | 15 | **0** | 7 bullets |

S7 and S9 never returned; every assertion method was lost. `not applicable` was a misread of a **derivation failure** as an **absence**.

**Second finding: #2563's gate is shape-blind by construction.** It conserves literals, not structure. It fired five criticals, the drafter appended bullets carrying the missing numbers, and the gate went green with the table gone. That is why a table-less LLD reached the manifest stage with a green lld verdict.

## The Fix, In Two Seams

**1. The lld stage owes the existence check** (Ask item 2). `validate_decision_table_survives` sits beside `validate_assertion_literal_conservation` — the only place holding both source and derived document. A source criteria table with no counterpart in the LLD is an ERROR, named with the lost row IDs and the count of LLD tables searched.

Deliberately a **separate** check, not an extension: literals and shape are different conserved quantities. A test asserts the division of labour in both directions — the shape gate passes an LLD that keeps the table but sheds a literal, and the literal gate fires on exactly that case.

**2. The abstain carries its denominator and travels forward** (Ask item 4). `CompileResult` gains `tables_seen`, `abstained` and `denominator()`. Three outcomes now render distinctly:

- `0 tables in the document` — the ordinary non-visual issue, not an abstain.
- `15 table(s) parsed, 0 in the criteria shape` — **abstain**, announced as the #2533 protection being OFF.
- `9 criterion(s) compiled from 16 table(s)` — applicable.

The absence lands on state (`assertion_manifest_absent`, `_absence_reason`, `_abstained`), the gate node repeats the reason instead of a second reassuring "passing through", and the orchestrator's run record grows a **DECLARED FALL-THROUGHS** section — printed only when non-empty, so its presence is the signal.

Both fall-throughs carry `# fail-open:` declarations per the #2475 regime.

## Verified Against The Observed Case

Replayed on the real preserved pair:

- the lld stage now **fails**, naming all nine lost rows and the 15 tables searched;
- the compiler reports `abstained=True` with `15 table(s) parsed, 0 in the criteria shape`;
- **control 1** (source with no table): 0 errors, `abstained=False`, "0 tables in the document";
- **control 2** (LLD carrying the table): 0 errors, manifest compiles 9 criteria.

## Note On Process

The first full-suite run showed two failures in `inspect.getsource` tests. Cause: I edited `stages.py` while that background suite was running. A suite verdict binds only to the tree it read; the run was re-done on the settled tree rather than investigated as a defect.

## Known Limitations

The structure check requires the LLD to carry *a* criteria table, not that its rows match the source's one-for-one. A derivation that carries a table with only S1 would pass this check and be caught by #2563's literal gate instead. Row-level correspondence is #2607's territory — injection makes it moot.
