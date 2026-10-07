# Implementation Report: the completeness gate halts when it cannot check (#3811, #3812, #3823, #3852)

Testing batch 1 of the #3581 sweep. It covers the 22 violations the sweep recorded in the completeness gate's three modules, and a defect found while fixing them.

## What changed

### `completeness/ast_analyzer.py` (#3811, 9 sites)

- **New `CompletenessGateError`.** The gate's single failure type, raised whenever it cannot certify what it was given.
- **`_parse`.** The five checks each caught `SyntaxError` and returned no issues. They now call `_parse`, which raises `CompletenessGateError` naming the file.
- **`run_ast_analysis`.** It used to skip, with a warning, a file it could not stat, one over `max_file_size_bytes`, one it could not read, and one that would not parse. Each now raises. Empty and non-Python files still pass over: there is nothing for these checks in them.
- The module's logger was used only by those warnings, and is removed.

### `completeness/report_generator.py` (#3812, 6 sites)

- **`extract_lld_requirements`.** It raises when the LLD cannot be read, has no Section 3, or yields no numbered requirement. Each used to return `[]`.
- **`prepare_review_materials`.** The "NO REQUIREMENTS" print is gone; extraction now raises instead. An implementation file it cannot read raises; it used to be skipped.
- **The report write.** A failed write used to be logged, with the unwritten path returned. It now raises.
- **`_find_reports_dir`.** With no project root above the LLD, it used to put `docs/reports/active` beside the LLD. It now raises.

### `nodes/completeness_gate.py` (#3823, 7 sites), with `graph.py` and `atlas.py`

- **The four broad handlers** (AST analysis, Layer 2 materials, report generation) and the two silent skips (no files, no LLD) are replaced:
  - The node catches only `CompletenessGateError`.
  - Through `_cannot_check`, it returns verdict BLOCK and an `error_message` naming the issue, the repository and the cause, logged at ERROR.
  - The router sends that to HALT, which alerts.
  - Any other exception propagates.
- **The iteration cap and the stagnation stop** used to route to END with no reason and no alert. They are now decided in the node (`_block_stop_reason`), which sets `error_message`, so they reach HALT. The router's END branch, its `"end"` mapping in `graph.py`, and the atlas's END successor are removed. The graph diagram is updated.

### Found by the full unit tier, and fixed here

- **The report's location.** `generate_implementation_report` now takes `repo_root` and writes to `<repo_root>/docs/reports/active`. It used to guess the project root by walking up from the LLD, and with no marker it wrote beside the LLD. `_find_reports_dir` is removed, and with it one #3812 site.
- **A relative LLD path.** The node resolves a relative LLD path against `repo_root`. Mock mode records the LLD relative to the repository, and the node checked it against the process's working directory, so it never existed: Layer 2 and the report were skipped without a word on every mock run.
- **Mock mode's LLD.** `load_lld` in mock mode now returns, as `lld_path`, the mock LLD it writes to the audit directory. The repository path it named was never written.
- **Registry.** `assemblyzero/core/gate_registry.py` gains the row `impl.completeness_gate_cannot_check` for the new halt site `_cannot_check`. Its `created_by` names the operator's ruling of 2026-10-06 accepting ADR 0236. `tests/fixtures/gate_registry_baseline.json` raises `impl` from 34 to 35 in this PR, as the ratchet requires, and `measured_against` is updated to the 146 halt sites and 97 gates `tools/audit_halt_sites.py --check` counts.

### #3852, found while doing the above

The router's stagnation check compared `completeness_issues` with `previous_completeness_issues`. The node writes both from the same list in one update, so every first BLOCK with an issue read as stagnant and the run ended. The N4 retry loop of #147 never ran.

`_block_stop_reason` compares this iteration's identities with the previous iteration's, read from state before the update replaces them.

### Baselines and ledger

- **Loud-failure baseline:** 329 to 326, the node's three swallowed handlers. `BASELINE_CEILING` is 326.
- **Fail-open baseline:** regenerated because its denominator moved, from 558 findings to 547 and from 438 frozen sites to 427. Nothing was added.
- **Ledger 0908:** the 22 sites are marked "FIXED in #3581 testing batch 1 (#3811)" by `mark_fixed.py`. The script refuses a site it cannot find exactly once.

## Behaviour this changes for a real run

- A run whose implementation has a file that does not parse now halts at N4b with the file named; it used to go on to N5.
- A first BLOCK now goes back to N4, as #147 intended, instead of ending the run.
- A BLOCK at the cap, or one that repeats, halts with a reason and an alert.
- The orchestrator already treated a BLOCK as a failure (#1779), so a pipeline run's outcome is unchanged. What changes is that the HALT record and the alert now exist.
