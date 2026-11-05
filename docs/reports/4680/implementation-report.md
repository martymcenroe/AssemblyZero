# Implementation report: #4680

An implementation run on a TypeScript target (a Vitest web suite beside a Python suite) halted at N1 before any test was written: "Only 5 scenario(s) for 10 requirement(s), coverage ratio 50% is below 100%". The spec's Section 10.1 carried 5 Python `def test_` functions and 8 Vitest `it` calls, one per criterion. N0 took the Python functions as the whole contract (#2316's preference for executable functions), so the Vitest half never reached N1.

## What changed

- R1, R2, `implementation_spec/typescript_bodies.py`: `section_ten_typescript_tests` returns the test calls in Section 10's TypeScript fences, split out of `spec_typescript_tests`, which now builds on it. The testing workflow reads this one and not Section 6's planned test files, which restate Section 10's calls: on the evidence spec, 8 in Section 10 and 16 counting Section 6.
- R1, R3, `testing/nodes/load_lld.py`: `scenarios_from_spec_typescript_tests` builds one scenario per running call, read by the #4551 reader, so N0 adds no second parser; `it.todo` and `.skip` are not tests. The title is the name and the description. The REQ tag is the first one the call's source cites that names an LLD requirement, else its first tag: the evidence spec titles each Vitest test by its criteria row (`REQ-070`) and cites the requirement (`REQ-6`) in its body, and on the first tag N1's coverage join covered 4 of 10 requirements.
- R1, R4, R5, `load_lld`: when the spec ships Python functions, N0 adds the TypeScript scenarios to `test_scenarios` and prints both counts. The tags are resolved once the requirements are read, after the print, so N0's output order is unchanged.
- `docs/standards/0029-defect-class-registry.md`: #4680 listed under class 3's variant, the check whose domain is narrower than the document's.

## What did not change

`spec_test_suite`, which the pytest scaffold emits verbatim, holds only the Python functions. A spec with no executable Python functions keeps the table path (R6). Python scenarios keep their first-tag `requirement_ref`. The Vitest scaffold still writes one failing placeholder per scenario; it now gets the spec's Vitest titles beside the Python names it was given before.

## The real spec

Read-only, through the same functions N0 and N1 call, on the halted run's spec and LLD: 5 Python and 8 TypeScript scenarios, 13 for 10 requirements; N1's mechanical gates return no error; `check_requirement_coverage` reports 10 of 10, which is N1's mechanical fast path.
