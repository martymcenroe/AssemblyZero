# Implementation Report: the implementation-spec workflow under standard 0034 (#3585 step 5, first half)

The rule is ADR 0236 and standard 0034. This branch takes the first half of `assemblyzero/workflows/implementation_spec/`: N3's route in `graph.py`, then `nodes/validate_completeness.py`, then `nodes/compile_manifest.py`. The module issues were deleted on 2026-10-30, so ledger 0908 names every site; line numbers are the ledger's, at `79e18ad1`.

## Modules

### graph.py: N3's errors reach HALT

`route_after_validation` keyed its halt on `completeness_cannot_check` alone, so `tools/audit_loud_failure.py` listed N3 as a node whose `error_message` no router sends to HALT. Its comment said `error_message` also carries a cap message on a grace revision that must still reach N2 (#2304). N3's code does not do that: it writes the cap message only when no grace is granted. The router now reads `error_message` first and halts on any value. A grace revision carries an empty `error_message`, so it still reaches N2. The `completeness_cannot_check` branch went, because `error_message` carries the same text; N3 still writes the field.

The ledger's two `graph.py` rows (265, an unknown human-gate decision; 513, N6's errors) were fixed by #3887 before this sweep reached the file. They are pinned by tests here.

Compliance: the one failure path touched is N3's error. It is loud (N3 prints an ERROR line for a check that cannot run), logged (the message names the check and the cause), stops (the router sends it to HALT), and alerts (HALT calls `alert_operator`).

Baseline: the entry `assemblyzero.workflows.implementation_spec.graph::N3_validate_completeness::unrouted_error::1` leaves.
