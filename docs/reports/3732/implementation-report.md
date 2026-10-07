# Implementation report: #3732

## The checkpointed framework string is resolved before scaffolding

Since #3708 `load_lld` stores `framework_config` through `checkpoint_safe`, so `framework_config["framework"]` is the string `"pytest"`. `TestFramework` is a plain `Enum`, so `"pytest" != TestFramework.PYTEST`, and `scaffold_tests` compared the raw value to the enum: every pytest repository took the TypeScript path and died at N2 with `Cannot generate TS content for framework: pytest`. Found on boostgauge #2, run `run-issue2-230238` (2026-10-06 23:02 Central): LLD and spec passed, then the implementation stage failed three attempts in 20.9 s.

- `assemblyzero/workflows/testing/runner_registry.py`: new `resolve_framework(config) -> TestFramework | None`, beside `checkpoint_safe`, which produces the strings. An enum is returned as is; a string is looked up by value in a dict built from `TestFramework`; anything else, an unknown string, a missing key or no config is `None`. A dict lookup rather than `TestFramework(value)` inside `try`, so the move adds no fail-open handler. `checkpoint_safe`'s docstring no longer says every reader accepted the string; it names the resolver and the bug.
- `nodes/scaffold_tests.py`: resolves the framework before branching. A non-pytest framework takes `_scaffold_non_python_tests` with the enum put back into the config it passes on, because that path reads `.value` and calls `get_runner`, both of which need the enum.
- `nodes/verify_phases.py`: `_resolve_framework_enum` keeps its name and signature, for its callers and two tests that reach it, and delegates to `resolve_framework`.
- `nodes/validate_tests_mechanical.py`: the inline string-to-enum copy is replaced by `resolve_framework`.
- `tests/fixtures/fail_open_baseline.json`: regenerated with `tools/audit_fail_open.py --write-baseline`. Exactly two sites leave it, the two `except ValueError` handlers this change removed (`verify_phases.py::_resolve_framework_enum` and `validate_tests_mechanical.py::validate_tests_mechanical_node`); the totals fall from 9515 to 9512 sites and 557 to 555 findings.

Left as they are: the runners and `get_runner` compare against `TestFramework` members, but they only ever read configs the registry built, which carry the enum.
