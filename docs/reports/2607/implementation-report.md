# Implementation Report — Decision Tables Injected Mechanically (#2607)

## Issue Reference
[#2607: inject decision tables into derived artifacts mechanically — literals never travel through the drafter](https://github.com/martymcenroe/AssemblyZero/issues/2607)

## Scope: The LLD-Side Half

Split at the seam the issue names as natural — lld-side injection here, spec-side filed as **#2611** — rather than by shipping half a protection. The lld half is complete and independently verifiable against every clause of the acceptance.

## Files Changed
- `assemblyzero/workflows/requirements/table_injection.py` (new): the substrate.
- `assemblyzero/workflows/requirements/nodes/generate_draft.py`: injection applied after every draft; the prompt tells the drafter to write *around* the block.
- `tests/unit/test_table_injection.py` (new): 22 tests.

## The Two Design Questions, Answered With Evidence

**Is the #2533 manifest compiler's row parser the right shared substrate?** It already *is* shared — `assertion_manifest` imports `parse_tables` and `RawTable` from `requirements.form_check` and layers `is_criteria_table` on top. My #2608 diagnosis established the parser handles real state correctly (15 of 15 tables in the run-19 LLD, plus the source's nine-row table), so the failure was never parsing. This module reuses that pair and introduces **no third notion** of what a decision table is.

**Should injected regions be machine-owned?** Yes, and delivered by **re-assertion** rather than by pinning adjudication. On every round the canonical block is restored over whatever the draft holds. This is deliberately stronger than asking pinning to protect the region: pinning adjudicates a diff and can be argued with; re-assertion does not adjudicate, so pinning never has to reason about injected rows — which is what the issue asks for.

A test found this claim needed sharpening. My first fixture asserted pinning *fails* to protect the block; it does not — with an empty vocabulary pinning locks everything and already reverts the tamper. The real gap is conditional: **a verdict naming any token inside the block unlocks it**, correctly, by pinning's own rule that restructuring around a named item is the named item's business. A reviewer writing "the `Dial face` row is wrong" is enough. Both facts are now pinned as separate tests.

## Byte-Verbatim, And How

`RawTable.line_no` is the 1-based header index, so the source's own lines are **sliced** out of the issue body and re-emitted unchanged. Nothing is re-rendered from parsed cells — a cell round-trip would normalise padding and drop trailing whitespace, quietly becoming "modulo reformatting", a phrase that hides exactly the drift this exists to end.

**No reformatting is declared, because none happens.** Tests assert the en-dash in `0.12 R–0.25 R`, the `×` in `R = 0.40 × size`, and the separator padding `|----|` all survive.

## Verified Against The Real #331 State

Read-only against the preserved run-19 lineage:

| property | result |
|---|---|
| every sliced line present verbatim in the source | **true** |
| S1–S9 table byte-verbatim in the LLD | **true** |
| manifest on the real lossy draft, before | `applicable=False` (the #2608 defect) |
| manifest on the same draft, after injection | **`applicable=True`, 9 criteria** |
| in-block tamper of `R = 0.40` | reverted; canonical restored |
| drafter's own prose outside the block | untouched |
| `reassert` on a clean document | idempotent, no change |
| prose-only issue (control) | injects nothing, draft returned unchanged |

The success metric the issue names — the #2563 gate's firing rate on injected rows — is **zero**, asserted directly: the gate fires on the lossy fixture and returns `[]` once injected.

## Known Limitations

- Spec-side injection is #2611, which needs a source-of-truth ruling first (issue vs LLD) and should check whether the assertion manifest already discharges it.
- `_insertion_point` looks for the LLD's `## 3.` Requirements heading and appends otherwise. Placement is for the human reader; the compiler finds a criteria table anywhere, so the fallback is correct rather than degraded, and a test covers it.
- Re-assertion guards the machine-owned region, not the document. Literals the drafter restates in its own prose remain #2563's territory — deliberate, and tested.
