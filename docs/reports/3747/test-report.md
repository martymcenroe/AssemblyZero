# Test report: #3747

## New: `tests/unit/test_requirements_gate_reproduces.py` (10)

The gate runs against a scripted provider (one answer per call); filing and telemetry are recorded, not performed.

- `test_a_conflict_that_does_not_reproduce_neither_halts_nor_files`: two conflicts, then a consistent second answer: proceeds, files nothing, two calls, both conflicts printed as `not reproduced, not filed:`.
- `test_a_reproduced_conflict_halts_and_files_as_before`: the same two conflicts twice: halts with the `REQUIREMENTS CONFLICT:` message and files both.
- `test_only_the_reproduced_conflict_is_filed`: two conflicts, then one of them: files only the repeated one.
- `test_a_confirming_ask_with_no_verdict_halts_on_the_first_answer`: an unparseable second answer leaves both conflicts standing.
- `test_a_consistent_first_answer_asks_nothing_more`: one call, nothing filed.
- `test_the_same_pair_is_recognised_across_quotings` (4 cases: verbatim, order swapped, shorter span in different case, extra spacing and a longer span) and `test_a_different_pair_is_not_the_same_conflict`.

## Runs, 2026-10-07, Ubuntu (WSL)

- **The tests catch the old behaviour.** With only the gate change stashed (named path), 8 failed, 2 passed. The two that pass cover the paths meant to stay unchanged: a reproduced conflict still halts, and a consistent answer asks nothing more. With the change, 10 passed.
- The new file with the five existing gate files (`test_n0c_excludes_revision_history`, `test_n0c_unarticulated_conflict`, `test_requirements_gate_accepts_shapes`, `test_requirements_gate_escalation`, `test_requirements_gate_timeout`) and `test_fail_open_audit`, `test_gate_registry`, `test_emits_pairing`, `test_halt_site_renumbering`, `test_routing_policy`: 277 passed before the fail-open ruling comment; the two fail-open repo-gate tests pass after it and the baseline regeneration.
- `tools/audit_halt_sites.py --check`: PASS, 145 halt sites, every one registered.
- Full `tests/unit`: 10915 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 11s.
- `ruff check`: the gate module carries the same single finding as on `main`; the new test file has none.
