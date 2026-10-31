# Implementation Report: the testing graph and three of its nodes under standard 0034 (#3585 step 5, batch C)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-graph`, is batch C of the testing workflow's sweep: `assemblyzero/workflows/testing/graph.py` with its routers, and the nodes `load_lld.py`, `augment_tests.py` and `e2e_validation.py`. One commit per module, each ledger 0908 row fixed and tested, or kept and pinned. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### graph.py (15 ledger rows: 14 fixed, 1 fixed earlier by #3725 and pinned)

- **Every stop a router decides reaches HALT (232, 245, 318, 355, 438, 447, 451, 471, 478, 488, 513).** The iteration caps, the cost budget, the spent coverage attempts, a BLOCKED plan under the strict policy or out of revisions, an exhausted scaffold that named no reason, and a route a node did not name each ended the run at END, which writes no halt bundle and alerts no one; the stage then read the empty `error_message` as a pass. Each condition now lives in one `_stop_after_*` function. The router consults it and routes to HALT. The node in front of the router is wrapped by `_records_its_stop`, which applies the same function to the node's result and records the reason as `error_message` at ERROR on stderr, so HALT's alert carries it.
- **auto_mode no longer hides a failed gate (217, 227).** `--review none`, the default, sets `auto_mode`, under which an N1 error was ignored and a BLOCKED test plan was walked past to N2. Any error now halts; a BLOCKED plan is revised under auto as under the default policy and halts when the revisions are spent.
- **A failed checkpoint stops the run (128).** The wrapper printed the error and carried on. It now writes an ERROR line naming the checkpoint, node, worktree and issue, and raises `CheckpointFailed` from the cause. Both callers of the graph alert on it, so it does not alert a second time.
- **The adversarial review's halt is pinned (557).** #3725 already routes N7.5's recorded reason to HALT.
- **Structure.** The edge maps of N1, N2.5, N3, N5 and N6 lose their `end` entries, which nothing can take now, and `testing/atlas.py` follows. The gate registry names the twelve new halt sites; three new impl rows (`impl.coverage_augment_spent`, `impl.budget.cost`, `impl.route_unrecognised`) cite the operator's ruling of 2026-10-06, and the impl ratchet in `tests/fixtures/gate_registry_baseline.json` goes from 44 to 47.

### nodes/load_lld.py (18 ledger rows: 10 fixed, 8 compliant and pinned)

- **N0 stops on every input it cannot build from (896, 1001, 1146, 1182, 1224).** A spec with no APPROVED marker, no Section 10 test plan in the LLD or the spec, no requirements, or no files to implement, and in issue-only mode a body with no test plan or no files, each halts at N0 naming the source. Each used to be a warning or nothing, and the run spent its reviews before a later gate, or nothing, stopped it. `extract_files_to_modify` raises when there is no table or the table names no file; it returned an empty list.
- **An LLD that cannot be read or rebuilt halts (324, 325, 1164).** A rebuild from refs that raises is said at ERROR and raised as `LLDRebuildFailed`, and the fail-open tag is gone; an LLD found and unreadable halts naming the path and cause. Both used to print a WARN and go on with the spec standing in for the LLD. A clean miss is still the quiet answer for absence.
- **Section 10's reason is never hidden (202, 1180).** `extract_spec_test_functions` returns the reason beside the empty suite when Section 10 fails the structure rule, so "no executable functions" and "no test plan" read differently. It does not raise, because the spec workflow's completeness checks call it on drafts. N0 records each source's reason and prints the LLD's when the spec's Section 10 serves instead. The rule now lives in `spec_structure_error`, so neither path catches an exception.
- **Kept and pinned (835, 969, 972, 977, 983, 1099, 1136, 1142).** The ADR 0207 default target, and the halts the ledger found compliant.
- **Structure.** The halts go through `_halt_spec_unusable` and `_halt_input_unreadable`, registered under the existing rows `impl.lld_not_usable` and `impl.input_precondition`; no row is added. The `requirements_empty_reason` state key is no longer written.

## Compliance

Every failure path above meets the four properties of standard 0034: it writes an ERROR line on stderr naming what failed and its subject, it stops what depends on it (a HALT route, or a raise the entry point owns), and it alerts the operator, through HALT or through the caller's handler.
