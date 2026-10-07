# Test Report: the completeness gate halts when it cannot check (#3811, #3812, #3823, #3852)

## Tests added

- **`tests/unit/test_completeness_gate_halts.py`.** Each test runs the node and then the router:
  - no files, a missing LLD, a file that does not parse, review materials that cannot be prepared, and a report that cannot be written each return BLOCK with an `error_message` naming the issue, and route to HALT;
  - an unexpected `KeyError` propagates and is not swallowed;
  - a clean run still passes and writes its report.
- **`tests/unit/test_wave2_reliability.py::TestCompletenessGateStoresIssueIds`.** The node and the router together, on merged state:
  - `test_a_first_block_goes_back_to_n4` (#3852 T1);
  - `test_a_repeated_block_halts` (#3852 T2);
  - `test_node_stores_previous_issues`, now on a real LLD.
- **`tests/unit/test_completeness_gate.py`:**
  - `test_run_ast_analysis_raises_on_a_file_that_does_not_parse`;
  - `test_run_ast_analysis_raises_on_a_file_it_cannot_stat`;
  - `test_a_block_below_the_cap_records_no_reason`.

## Tests changed: each pinned a silent skip this batch removes

- `test_completeness_gate.py`:
  - `test_syntax_error_returns_empty` is now `test_syntax_error_raises`;
  - `test_max_iterations_ends` and `test_max_iterations_above_limit_ends` are now `test_max_iterations_halts`, parametrized over 3 and 4;
  - the three `test_extraction_*` tests now raise;
  - `test_review_materials_skips_missing_files` is now `test_review_materials_raise_on_a_missing_file`;
  - `test_run_ast_analysis_skips_large_files` is now `test_run_ast_analysis_raises_on_a_large_file`.
- `test_completeness_gate_reads_the_lld.py`: the spec is refused, and an empty extraction stops the review, where it used to print.
- `test_empty_branch_guard_clauses.py`: `TestFailOpenIsUntouched` is now `TestASyntaxErrorStopsTheCheck`.
- `test_wave2_reliability.py`: the identical-issues and cap tests assert a recorded reason and HALT.
- `test_zero_requirements_denominator.py`: the populated-set test supplies the LLD the gate now requires.
- `test_loud_failure_check.py`: `BASELINE_CEILING` 329 to 326.

## The #3852 defect, shown on the old code

`old_gate_first_block.py` loads `origin/main`'s `completeness_gate.py`, runs the node on a first BLOCK with one issue and no previous issues, then the router on the merged state. It printed:

```
[N4b] [STAGNANT] Same 1 completeness issues across 2 iterations. Halting.
main routes a first BLOCK to: end
```

`test_a_first_block_goes_back_to_n4` asserts `N4_implement_code` for the same input.

## Also changed after the first full tier

The first full unit run failed 12 tests. Every one was resolved by a fix in the code, recorded in the implementation report:
- **6 mock runs:** the LLD path named a file never written, and was checked against the working directory.
- **6 registry tests:** the new halt site had no row.

`test_completeness_gate.py`'s four report tests pass `repo_root`, and one asserts the exact report path.

## Runs, 2026-10-07

- **All four tiers on the final tree,** with the machine quiet:
  - unit: 11,009 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 25s;
  - integration: 64 passed, 7 skipped;
  - e2e: 19 passed;
  - adversarial: 1 skipped (its only test).
- `tools/audit_halt_sites.py --check`: PASS, 146 halt sites, every one registered.
- `lint_vs_main.py`: no `ruff` finding in the 13 changed files that main's versions lack.

- The 307 tests selected by `-k "completeness or wave2 or zero_requirements or testing_graph or empty_branch or step_budget or atlas"`: all pass.
- `tools/audit_loud_failure.py --check`: PASS at 326. `tools/audit_fail_open.py --check --strict`: PASS (9626 sites, denominator matches).
- `ruff check` on every changed file: no new finding. The remaining ones predate this change (#3804).
