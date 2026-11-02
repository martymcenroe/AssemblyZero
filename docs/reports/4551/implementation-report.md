# Implementation report: #4551

An implementation-spec run on a TypeScript target halted at the iteration cap with class `unknown`. The reviewer asked for the Python placeholder tests of criteria rows 060 to 130 to be removed, because they were tautologies and the behaviour is tested in Vitest. `criteria_have_tests` read only Python `def test_` functions, so it then named the same eight criteria on every revision, although the spec carried a Vitest test for each, in Section 10.1 and in the diff of the planned `.test.ts` file.

## What changed

- R1, `typescript_bodies.py` and `criteria_coverage.py`: a TypeScript `it` or `test` call the spec carries joins on the REQ tags it cites, as a Python test does. The calls come from Section 10's TypeScript fences and from the TypeScript test files Section 6 plans (a subsection whose heading names a `.test.ts`, `.test.tsx`, `.spec.ts` or `.spec.tsx` file; a diff fence is read as its post-image, so a test the diff removes is not read). One fence reader now serves both these and the member check's Section 10 bodies, and the calls are found with the tree-sitter parser that check already used. A call whose callee carries `todo` or `skip` covers nothing; the titles of the `describe` calls holding a test count as its text. The complaint ends with a sentence saying both languages count, written without backticks or a section number so it adds no pinning token.
- R2, `validate_completeness.py`, `core/errors.py`, `core/halt_node.py`, `core/recovery_plan.py`: the cap halt for an identical complaint under pinning reversions carries `[RECURRENCE UNDER PINNING]` and a "Gate that blocked progress:" clause. It names the conservation gate when a conservation override refused a revision entire, and otherwise the completeness check, since with R3 a refused line answered no complaint. `classify_error` returns `completeness_recurrence_under_pinning`, checked before the patterns that read quoted text, and the recovery plan repeats the gate clause. The halt no longer calls this a deadlock of vocabularies.
- R3, `revision_pinning.py` and `generate_spec.py`: `complaint_answers` reads, from the round's completeness failures, the tokens `named_tokens` reads and the criterion keys they list. In `enforce_pinning`, a locked region whose revised lines carry one of those tokens, or cite one of those keys as a tag, answers a named complaint: it passes, it is not the regression class, and it is logged as `[PINNING] completeness answer passed`.
- `docs/standards/0029-defect-class-registry.md`: #4551 listed under class 3.

## What did not change

A criterion with no test in either language still fails. Section 3 excerpts are not tests the spec carries. Old-side naming, the conservation gate and the demanded-additions exemption are as they were, and a revised line that carries nothing a complaint names is still refused. The other halt shapes keep their wording and their class.

## The real draft

Every N3 completeness check, run without a model call on the halted draft, passes; `criteria_have_tests` reports 13/13 criteria across 28 tests, 16 of them TypeScript. The run's two pinning refusals were of lines the verdict named by section number, which pinning does not read: see #4552.
