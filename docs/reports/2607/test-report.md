# Test Report — Decision Tables Injected Mechanically (#2607)

## Issue Reference
[#2607](https://github.com/martymcenroe/AssemblyZero/issues/2607)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_table_injection.py` (new) | **22 passed** |
| with `test_completeness_pinning_deadlock.py`, `test_pinning_conservation.py`, `test_decision_table_survives.py`, `test_fail_open_audit.py` | **134 passed** |
| `tests/unit` (full) | see below |

The 134-test run is the one that matters for the instruction not to weaken #2558/#2562/#2606: the pinning fixtures are **untouched** and pass unchanged alongside the new work.

## The Acceptance, Clause By Clause

**"The #331 S1–S7 table derived under injection appears byte-verbatim modulo a declared mechanical reformatting (whatever is declared is tested)."**

No reformatting is declared, because none happens — the source's own lines are sliced, not re-rendered. Three tests pin the characters a cell round-trip would have destroyed: the en-dash in `0.12 R–0.25 R`, the `×` in `R = 0.40 × size`, and the separator padding `|----|`. A fourth asserts every emitted line appears verbatim in the source.

**"Zero conservation-gate losses on injected rows."** `test_the_conservation_gate_finds_nothing_on_injected_rows` asserts both halves: the #2563 gate **fires** on the lossy fixture (so the fixture reproduces the real defect) and returns **`[]`** on the injected one. Without the first assertion the second would prove nothing.

**"A later-round drafter revision cannot modify an injected row."** Four tests: an in-block edit is reverted; deleting the markers entirely restores the block; `reassert` is idempotent; repeated cycles accumulate no whitespace and never duplicate markers.

**"Prose-only requirements derive exactly as today."** Three control tests: no injection is built, the draft is returned byte-identical, and `reassert` is a no-op.

## A Wrong Claim The Tests Caught

My first pinning fixture asserted that pinning alone does not protect the injected block. It failed, correctly — with an empty vocabulary pinning locks everything and already reverts the tamper. The claim was wrong as written.

The corrected pair now records the true, more precise fact:

- `test_pinning_locks_the_block_when_nothing_names_it` — the ordinary round; pinning refuses the edit and records a refusal.
- `test_pinning_alone_leaves_a_gap_that_reassertion_closes` — a verdict naming any token inside the block (`dial face`) **unlocks** it, correctly, by pinning's own rule. Pinning then allows the edit; re-assertion restores it anyway, because it does not consult the vocabulary.

That second test carries a note telling a future reader that if the unlock stops happening, pinning changed and this is where to re-derive the claim.

## Cross-Gate Composition

Three tests assert the new machinery satisfies the gates that already exist, rather than bypassing them: the manifest compiles (9 criteria on the real source), #2563 finds nothing, and #2608's structure check passes. Injection is what makes those green by construction instead of by asking the drafter again.

## Real-State Verification

Beyond fixtures, the module was driven against the preserved run-19 lineage read-only, including the tamper case located by line number **inside** the machine-owned span — a document-wide tamper would have proved nothing, since `reassert` deliberately guards only the injected region.

## Regression Risk

`table_injection` is a new module. The only production wiring is in `generate_draft`: one `reassert` call on the lld path, and a prompt clause added only when the source actually carries a criteria table. An issue with no decision table takes neither branch, which is most issues — and is the control the suite pins.
