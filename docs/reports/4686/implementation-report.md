# Implementation report: #4686, #4687

An implementation run against a TypeScript target with two Vitest projects, the run's own in `web/` and a contributor kit in `<kit>/web/`, wrote all eight of its files (the two large ones by edit script, #4683) and passed the completeness gate, then halted at N5: the kit had no Vitest coverage provider. The run changed nothing in the kit, so the full-suite gate runs its suite once with no coverage, but `_preflight_legs` and `_full_suite_gate` both asked `require_dependencies()` for a provider (#4246). The run's log line also named one Vitest project where the gate held two (#4687).

## What changed

- #4686 R1, R4, the runners: `require_dependencies(measure_coverage=True)` on `BaseTestRunner`, `JestRunner`, `PlaywrightRunner` and `PytestRunner`. With `measure_coverage=False`, `JestRunner` asks a Vitest project for `vitest` and no provider; with `True`, for both, by the same check and message as before. The other three need nothing more for coverage.
- #4686 R2, `verify_phases._full_suite_gate`: asks with `measure_coverage=False`, because `run_tests(test_paths=None)` measures nothing.
- #4686 R3, `verify_phases._preflight_legs`: asks a leg with test files of this run for coverage, and a leg with none without it. A leg with no test file whose source the run changed is judged on coverage in `_verify_green_non_pytest`, which asks for its provider before it measures, as it did.
- #4687, `load_lld._frameworks_with_directories`: returns one label per project, spelled as `framework_label` spells them (`pytest`, `vitest (web)`), so both log lines name every project.

## What did not change

Which projects run, in which phase, and how each is judged. A provider is still required wherever coverage is measured: the red and green runs of a project with test files, and the green run of a project whose source the run changed.
