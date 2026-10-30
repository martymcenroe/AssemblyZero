# Implementation Report: a Python suite and a Vitest suite are scaffolded, written, run and measured (#4244, #4243, #3081, #4245, #3065, #3067, #4246, #3089)

In progress. Each issue's section is written when its commit lands.

## #4244: N2 scaffolds every framework of the run

`scaffold_tests.py:1322-1332` (at `4ac9c81a`) read `framework_config`, the first framework, alone.

- `scaffold_tests` reads every framework of the run through `framework_ownership.run_frameworks`. With more than one, `_scaffold_every_framework` scaffolds each with its own scaffolder: the pytest scaffold through `_scaffold_python_tests`, the old body of `scaffold_tests` moved unchanged, and each JavaScript framework through `_scaffold_non_python_tests`.
- `generated_tests` stays the Python scaffold when pytest is one of the frameworks, because the pytest validator reads that key (#789).
- A framework whose scaffold cannot be built halts N2 through `_halt_scaffold_framework`, which names the framework and its directory (`vitest (web)`) and the cause, prints an ERROR line on stderr, and routes to HALT.
- A single-framework run takes the path it took before.
