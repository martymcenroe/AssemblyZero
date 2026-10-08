# Test Report: the requirements graph sends every error to HALT (#3864)

## Tests added: `tests/unit/test_requirements_graph_halts.py`

- N0b and Ponder errors halt, and a clean pass continues.
- An N1.5 error that is not a failed validation halts.
- **The regression guard:** a BLOCKED validation carrying its own `error_message` still loops back to N1 while iterations remain.
- In the compiled graph, N0b, Ponder, N2, N4 and N5 each have HALT as a successor.

## Tests changed: each pinned behaviour #3864 removes

- **`test_requirements_graph.py`:**
  - the review cap with a still-BLOCKED draft now halts; two tests, one with the default cap;
  - unknown and empty gate decisions halt;
  - the explicit `END` still ends, with new tests for both gates;
  - `route_after_finalize` halts on an error.
- **`test_open_questions_loop.py` and `test_issue_248.py`** (`test_t050`, `test_050`): the open-questions cap halts.
- **`test_finalize_repair_routing.py`:** the exhausted repair budget, and a non-validation finalize error, each route to HALT.
- **`test_loud_failure_check.py`:** `BASELINE_CEILING` 325 to 324.

## Runs, 2026-10-07

- **Integration, e2e and adversarial:** 64 passed, 19 passed, and 1 skipped.
- **The first full unit run:** 11,028 passed, 2 failed. The two failures were `test_issue_248.py::test_t050` and `::test_050`, which pinned the old open-questions cap. They were outside the `-k` selection used while developing, and are updated above.
- **The second full unit run,** on the final tree: 11,030 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 58s.
- **Audits:**
  - `tools/audit_halt_sites.py --check`: PASS;
  - `tools/audit_loud_failure.py --check`: PASS at 324;
  - `tools/audit_fail_open.py --check --strict`: PASS.
- **Lint:** `lint_vs_main.py` finds nothing new in the changed files.
