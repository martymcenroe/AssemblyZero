# Test Report: the loud-failure standard and its check (#3580)

## Tests added

`tests/unit/test_loud_failure_check.py`.

**T2, run against the whole tree in the unit tier:**
- `test_no_new_site`: every finding is in `tests/fixtures/loud_failure_baseline.json`.
- `test_no_fixed_site_left_in_the_baseline`: every baseline entry is still found, so a fix must shrink the baseline.
- `test_the_baseline_only_shrinks`: the entry count is at or under `BASELINE_CEILING`, which each #3581 batch lowers.
- `test_every_baseline_entry_names_the_sweep`: every entry's issue is #3581.
- `test_every_graph_module_is_listed`: every module under `assemblyzero/` that calls `StateGraph(` is in `GRAPH_BUILDERS`.

**T1, standard 0034's examples:**
- `test_a_swallowed_handler_is_found` (four non-compliant handlers). One of them hides a `raise` in a nested function; that case caught a real bug in the first version, which counted a nested function's `raise` as the handler's own.
- `test_a_loud_or_narrow_handler_passes` (four compliant handlers).
- `test_a_fail_open_tag_is_found_but_a_string_naming_it_is_not`.
- `test_keys_survive_an_unrelated_line_move`.
- `test_returns_error_and_routes_error_to_halt`.
- `test_scan_graphs_finds_only_the_unrouted_node`: a fixture `StateGraph` with one node routed to a real `create_halt_node` HALT, and one node on an unconditional edge. Only the second is reported.

## Runs, 2026-10-07

- `tests/unit/test_loud_failure_check.py`: 18 passed on the rebased tree, including `test_a_node_whose_source_cannot_be_read_stops_the_check`, added after the old fail-open audit caught `_function_tree` returning `None` on an unreadable function (now it raises `UnreadableGraphFunction`).
- Full `tests/unit` tier on the tree rebased onto `c51dbe84`, with the machine quiet: 10975 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 38s.
- `tools/audit_loud_failure.py --check`: `PASS -- 335 site(s), all in the baseline (#3581)`. Lineage archival (`tools/archive_worktree_lineage.py`) ran inside the worktree after the last test run and had nothing to stage.
- `tools/audit_fail_open.py --check --strict`: PASS (312 files, 9632 sites; the denominator moved with the new module; 438 frozen sites unchanged). `tools/audit_halt_sites.py --check`: PASS.
