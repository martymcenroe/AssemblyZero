# Test Report: N4.5 halts when the build hook fails (#3706)

Landed in the same PR as #3705; the full report is `docs/reports/3705/test-report.md`. The #3706 tests: `test_a_failed_hook_halts_with_its_exit_code`, `test_an_unreadable_config_halts` and `test_the_node_carries_no_fail_open_tag` in `tests/unit/test_mechanical_hooks.py`, and the `route_after_mechanical_hooks` assertions plus `N4_5_mechanical_hooks` in HALT's inbound set in `tests/unit/test_testing_graph_halts_through_halt.py`.
