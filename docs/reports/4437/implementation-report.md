# Implementation report: #4437

## The test files an LLD names decide what scaffold, red and green use

`assemblyzero/workflows/testing/framework_detector.py`. `_lld_decides` treated an LLD that names a Python test exactly like one that names nothing, so `resolve_framework_dirs` returned every framework the project has. It now decides on the test files themselves:

- `named_test_files` reads every test file the LLD names, of either language, with the same tokenizer as `named_js_test_paths`. A glob names no file.
- An LLD that names a test file decides. An LLD that names none but declares a runner decides too, as before. Otherwise the project decides.
- `frameworks_named_by_lld`: once the LLD names test files, a keyword adds no framework. "The Vitest suite must keep passing" beside a Python test no longer brings Vitest in, and "pytest" in prose beside a Vitest path no longer brings pytest in. `*_test.py` now counts as a Python test.

## The full-suite gate runs every framework the project has

- `assemblyzero/workflows/testing/nodes/load_lld.py`: `_gate_only_configs` lists what the project has beyond the run's frameworks, for all three load paths, and the state carries it as `gate_only_framework_configs`. It carries the run's declared coverage target, as every framework does.
- `assemblyzero/workflows/testing/nodes/verify_phases.py`: N5 adds those frameworks as legs with no test file, through `_gate_only_legs`. N5 already treats such a leg correctly, so nothing new decides anything: its whole suite runs at the gate (#3087), it is judged on that suite if the run changed its source (#4436), and a runner that cannot start halts before any suite runs (#4236). A failure on it goes back to N4 like any other regression.
- N2, N2.5, the red phase and the implementer read `framework_configs` alone, so they never ask for a test in a framework the LLD did not name.

A checkpoint from before this change has no gate-only list and runs as it did.

## The log says which, and why

`_log_frameworks` writes two lines at N0 on every load path: the frameworks for scaffold, red and green, with the reason (`framework_source`), and the frameworks for the full-suite gate.

## Known consequence

A gate-only Vitest still needs its coverage provider, because `require_dependencies` asks for one, so a Python-only run on a target without it halts at N5 by name. Such a run needed the provider before this change too, because it was given Vitest. #4488 tracks dropping the demand for a framework that only runs its whole suite.
