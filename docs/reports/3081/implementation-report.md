# Implementation Report: a Python suite and a Vitest suite are scaffolded, written, run and measured (#4244, #4243, #3081, #4245, #3065, #3067, #4246, #3089)

In progress. Each issue's section is written when its commit lands.

## #4244: N2 scaffolds every framework of the run

`scaffold_tests.py:1322-1332` (at `4ac9c81a`) read `framework_config`, the first framework, alone.

- `scaffold_tests` reads every framework of the run through `framework_ownership.run_frameworks`. With more than one, `_scaffold_every_framework` scaffolds each with its own scaffolder: the pytest scaffold through `_scaffold_python_tests`, the old body of `scaffold_tests` moved unchanged, and each JavaScript framework through `_scaffold_non_python_tests`.
- `generated_tests` stays the Python scaffold when pytest is one of the frameworks, because the pytest validator reads that key (#789).
- A framework whose scaffold cannot be built halts N2 through `_halt_scaffold_framework`, which names the framework and its directory (`vitest (web)`) and the cause, prints an ERROR line on stderr, and routes to HALT.
- A single-framework run takes the path it took before.
- The issue asks N2 to scaffold "the test files the LLD names". Neither scaffolder writes an LLD-named file: pytest's writes `tests/test_issue_<N>.py`, which N4, N4c and #2709 all key on, and the TypeScript one writes `issue_<N>.test.ts`. What changed is which frameworks get one, which is the defect the issue describes; the file names are as they were.

## #4243: a JavaScript scaffold is written in its framework's own directory

`scaffold_tests.py:1207-1214` wrote the Jest, Vitest or Playwright scaffold to `<root>/tests/` whatever the framework's `working_directory`.

- `scaffold_path_for` says where a framework's scaffold goes without touching the disk: pytest's is `tests/test_issue_<N>.py`, as before; a JavaScript framework's is `<its directory>/tests/issue_<N><ext>`, so Vitest in `web/` gets `web/tests/issue_<N>.test.ts`.
- `determine_test_file_path` asks the run's ownership rule who would run that path, among every framework of the run (`run_configs`, the state's `framework_configs`). A path no framework runs, a path another framework would run, or a `working_directory` outside the repository raises `ScaffoldPathError`, naming the path and the frameworks, before any directory is made. N2 halts on it through `_halt_scaffold_framework`, in a single-framework run as in a multi-framework one.
- "The test directory its config names" is not read. A Vitest, Jest or Playwright config is a JavaScript or TypeScript module, and the run does not evaluate one. The scaffold goes in `tests/` under the framework's directory, which each of the three runners' default test patterns collects; a project whose config narrows `include` or `testDir` elsewhere sends the red phase back to N2 with nothing collected, and the scaffold cap halts it.
- The ownership rule moved to `assemblyzero/workflows/testing/framework_ownership.py` (`run_frameworks`, `owner_of`), and `verify_phases._framework_legs` reads it from there, so N2 and the phases cannot disagree about who runs a file. Its messages are word for word what `_owner_of` printed.
