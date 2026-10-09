# Implementation Report: the red-phase import names each module from the plan (#4148)

## The defect

`generate_spec_test_file_content` built one red-phase import from `_extract_impl_module`, the first Add file, for every implementation name the Section 10 bodies use. boostgauge #2's run 59 (`run-issue2-063235`) got:

```
from boostgauge.formatters import GaugeWidget, format_menu_label, format_tooltip_text, get_test_config  # noqa: F401
```

The spec defines `GaugeWidget` in `gauge.py`, and `get_test_config` in `tests/unit/test_gauge.py`. The implementer stubbed both into `formatters.py`, and the frozen suite tested the stub for five iterations.

## What landed, by requirement

| Requirement | Where |
|---|---|
| R1: each name from the plan file whose Section 6 defines it; one import line per module | `load_lld.extract_plan_code` reads each planned `.py` file's Section 6 code, returned as `plan_code` by `extract_spec_test_functions`, which both callers use (the scaffold node and the spec gate's `check_spec_test_functions_have_assertions`). `scaffold_tests.resolve_red_phase_imports` maps each unbound symbol to the file that defines it at module level (class, def or assignment) and groups names per module. |
| R2: a test-only helper is never imported from an implementation module | Choice: **copy**. The helper's definition is copied into the suite, along with the import lines from its own file that it needs (`get_test_config` brings `from boostgauge.config import AppConfig`). It is not imported from the test module, because the contract suite must not depend on another test file the implementer has yet to write, or on that file being importable. The choice is stated in `resolve_red_phase_imports`' docstring. |
| R3: a name in two files, or in none, stops loudly | `ScaffoldImportError` names the name and the files. An Add file whose Section 6 code does not parse also stops it, since its names cannot be read. The scaffold node returns it as `error_message`, with an ERROR line, and routes it to HALT. New gate row `impl.scaffold_import_unresolved`, citing the operator's ADR 0236 acceptance. The spec gate fails the check instead, so the drafter sees it while the spec can still change. |
| R4: at least one import names a module the plan adds | When no resolved module is an Add file, `import <first Add module>` is emitted as well. |

A suite whose state carries no `plan_code` (a state built before this change) keeps the old single-module behaviour. Every spec the extractor reads now carries it.

## Output on boostgauge #2's spec

```
from boostgauge.formatters import format_menu_label, format_tooltip_text  # noqa: F401
from boostgauge.gauge import GaugeWidget  # noqa: F401
from boostgauge.config import AppConfig

def get_test_config() -> AppConfig:
    ...
```
