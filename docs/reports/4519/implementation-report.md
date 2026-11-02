# Implementation report: #4519

#4514 proves a spec's Python test bodies before a run. Nothing read the TypeScript ones, so on a real run on a private target a body that read `score.cost_usd`, a member the target's `Score` lacks, reached the implementer, which copied it, and the run spent all three green iterations on the one line.

## The check

`check_spec_typescript_tests_read_real_members` is check 10f at the spec stage, classified a fact beside the #4514 checks. `typescript_bodies.py` does the work:

- `spec_typescript_bodies` reads each Section 10 fence tagged `typescript`, `ts` or `tsx` whose first line names its file, as `// web/tests/replay.test.ts (...)`.
- `project_of` finds the nearest `tsconfig.json` above that file, inside the repository. `typescript_compiler` finds the target's own installed `tsc` the way Node resolves a package.
- `missing_members` writes each body as a hidden file beside the file it names, so its relative imports resolve, plus a configuration that extends the project's own and compiles those bodies alone. It runs the compiler with `--pretty false` and removes both files before it returns.
- Of the compiler's output, only TS2339 and TS2551 are read: a property a type lacks. A finding fails the check when the type is a bare name, the target declares it (`declared_in`, by tree-sitter), and the plan changes none of the files that declare it.

A type the plan adds or modifies is left alone (R3). So is a type the target doesn't declare, such as a library's. A name the plan has yet to write can't be resolved, so the compiler reports it as a different error, which the check doesn't read.

## When it cannot check

A body that names no file, a file with no `tsconfig.json` above it, and a target that has not installed TypeScript are each "not applicable", and the details say which. A compiler that can't be started, that exits with a code `tsc` never uses, or that leaves a file that can't be removed raises `CompletenessCannotCheck`, because that can't be told from a pass.

## What is not checked

Only Section 10 bodies that name their file are compiled. A Section 6 diff to a test file isn't a whole file, and a body with no file can't be placed where its imports resolve. The compile reads the target's checkout rather than the base through git, because the compiler needs the project's configuration and `node_modules` on disk.

## The real case

The real spec draft that carried `score.cost_usd`, checked against a copy of the target's TypeScript project, fails, naming the test, `cost_usd`, `Score` and the one file that declares `Score`. The final draft, which reads `score.cost.value_usd`, passes.
