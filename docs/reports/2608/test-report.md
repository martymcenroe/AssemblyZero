# Test Report — The Manifest Abstain Carries Its Denominator (#2608)

## Issue Reference
[#2608](https://github.com/martymcenroe/AssemblyZero/issues/2608)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_decision_table_survives.py` (new) | **22 passed** |
| with `test_assertion_manifest.py`, `test_assertion_literal_conservation.py`, `test_fail_open_audit.py` | 106 passed |
| `tests/unit` (full, on the settled tree) | see below |

## The Acceptance, Replayed On Real Preserved State

Not fixtures alone — the real run-19 lineage, read-only, driving the real code:

```
manifest compiler:  applicable=False  tables_seen=15  abstained=True
                    "15 table(s) parsed, 0 in the criteria shape"
lld structure check: 1 ERROR — "the source issue carries a criteria decision
                    table (9 row(s): S1…S9) and the LLD carries none.
                    15 table(s) were parsed in the LLD…"
control 1 (no source table):  0 errors, abstained=False, "0 tables in the document"
control 2 (table carried):    0 errors, manifest compiles 9 criteria
```

That is the issue's acceptance in all three branches: this run fails naming what went wrong, a document genuinely outside the domain passes with its declaration, and a correct derivation compiles.

## What Is Pinned

**The structure check (8 tests).** The destroyed table is an ERROR naming the lost rows; the message carries what was searched; a carried table passes; a source with no table yields no checks; empty inputs yield no checks.

Two tests pin the **division of labour with #2563** in both directions, so the pair provably leaves no gap: the shape gate is blind to a shed literal *by design*, and the literal gate fires on exactly that case.

The load-bearing one is `test_bullets_satisfy_the_literal_gate_while_failing_this_one` — the measured run-19 condition as a fixture. It asserts `validate_assertion_literal_conservation` returns **`[]`** on the bullet-form LLD (reproducing the shape-blind green verdict) while the new check fires. My first draft of that fixture did **not** carry every literal, so the literal gate fired and the test failed honestly; the fixture was corrected to carry the assertion-method numbers, which is what the real drafter appended after its five criticals. Without that correction the test would have asserted a condition the run never had.

**The denominator (4 tests).** The three outcomes render distinctly, and `test_the_two_absences_are_distinguishable` asserts the point directly: both are `applicable=False`, and `abstained` and `denominator()` differ. Before #2608 they were one message.

**Forward travel (4 tests).** The abstain lands on state with the reason; the ordinary absence travels too but is not an abstain; the abstain prints as a protection being OFF; the ordinary absence does not.

**The run record (4 tests).** A passed stage with an abstain grows a `DECLARED FALL-THROUGHS` section; an ordinary run record has none, so the section's presence is itself the signal; `_declared_fallthroughs` maps sub-result to note and returns empty when nothing sat out.

**The gate (2 tests).** It repeats the abstain reason rather than printing a second reassuring "passing through"; a bare pass-through still works.

## A Process Note

The first full-suite run reported two failures, both `inspect.getsource` tests, both passing in isolation and together. Cause: `stages.py` was edited **while that background suite ran**. A suite verdict binds only to the tree it read, so the suite was re-run on the settled tree rather than the failures investigated as defects.

## Regression Risk

`tables_seen` defaults to 0, so any `CompileResult` built elsewhere keeps working. `notes` is written only when non-empty. The new lld check is additive and returns `[]` for every issue without a criteria decision table, which is most of them.
