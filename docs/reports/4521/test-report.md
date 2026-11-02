# Test report: #4521, #4522, #4523, #4525

## Changed tests

`tests/unit/test_implementation_gate_defects.py` (new, 62 tests), by issue:

- #4525: real pytest on a failing lint test whose message ends with ruff's count, through the parser, the runner and the gate. Three failed tests count three, a collection error still counts, the closing line in each form pytest writes, and output with no closing line.
- #4521: the base's undeclared import passes, from `existing_content` and from disk. A new import the environment has passes, through a real probe of this interpreter, and one it lacks is refused. A first-party name is never passed by the environment. An environment that cannot answer, and a base that does not parse, stop the check. Six dynamic-import forms are refused, naming the line, and a family the file had, or the spec names, passes.
- #4522: hunks come from Section 6 alone. The real run's `step_minutes` line is reported by line, specified lines and a reworded line inside a hunk are not, a removal is, and a hunk with elided context still covers its lines. Through N4's report on a real git base, the advisory and the audit event are checked. Schema keywords: the real line refused, names and data never read as keywords, another draft's keyword refused, base and spec keys kept, non-schema JSON and JSON with comments left alone.
- #4523: a real `npm run lint` that fails routes to N4 and names the lint at the cap. No script, a passing lint, and no `package.json` are unaffected. N8.5 sends a lint failure on an adversarial file to N4, names it at the cap, and hands it to N4. A clean suite lands, a suite that cannot run halts, and a failing adversarial test stays as written. The built graph runs N8.5 between N8 and N9.

Existing tests changed:

- `test_impl_step_budget.py`: an iteration now costs 3 + 4 + 9 super-steps, and the cap sum counts the final-suite loop.
- `test_testing_graph_halts_through_halt.py`: N8.5 joins the routers that reach HALT.
- `test_node_modules_supply_nodes.py`: `schema_keywords` and `unrequested_changes` are declared helpers.
- `test_framework_integration.py`, `test_full_suite_gate_every_framework.py`: four green-path runner mocks say their lint passes.

## Runs, 2026-11-02

- Seen failing on `main` first: #4525 T1, `assert (1 + 10) == 1`, and #4521 T1, `Unresolvable imports: numpy (line 2)`.
- Unit tier, finished 2:15 AM Central, after the last code edit: 13800 passed, 66 skipped, 7 deselected, 7 xfailed in 22m 26s.
- Integration, e2e and adversarial tiers together, finished 2:18 AM Central: 84 passed, 7 skipped.
- `ruff check`: no changed file has more findings than on `main`.

## Mutations

Each defect was put back and the file restored: the base-import exemption removed, a failing adversarial test handed to N4, and a hunk's region ignored. All three were caught.
