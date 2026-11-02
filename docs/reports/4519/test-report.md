# Test report: #4519

## Changed tests

`tests/unit/test_spec_typescript_bodies.py` (new, 20 tests):

- Six compile with a real TypeScript 5, installed once per session into pytest's own temporary directory. T1: a read of a member the unchanged `Score` lacks is refused, naming the test, the member, the type and the declaring file. T2: the same read passes when the plan modifies that file. T3: a read of a member the type has passes. A name the plan adds, and a library type's missing member, are not faults. Nothing is left in the target.
- Four cover "not applicable" and "cannot check": no body, TypeScript not installed, no `tsconfig.json`, and no repo root.
- The rest need nothing: which fences are read, the title of the test holding a line, where a type is declared, the project and its compiler, which type names are looked up, and a compiler that exits 7 raising with no probe file left behind.

The real-compile tests skip where node and npm are absent, as on CI, and the rest run everywhere.

Existing tests changed:

- `test_check_classification.py`: the catalogue grows from 20 checks to 21.
- `test_completeness_message_addressability.py`: the check is declared as driven by its own test file, with the reason.

## Runs, 2026-11-02

- Unit tier, finished 2:15 AM Central: 13760 passed, 66 skipped, 7 deselected, 7 xfailed in 22m 41s.
- Integration, e2e and adversarial tiers together, finished 2:30 AM Central: 84 passed, 7 skipped.
- `ruff check`: no changed file has more findings than on `main`.
- The real case: the spec draft carrying `score.cost_usd` is refused, and the final draft passes.
