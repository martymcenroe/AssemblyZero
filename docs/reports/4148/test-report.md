# Test Report: red-phase imports by defining module (#4148)

## New tests: `tests/unit/test_scaffold_imports_by_module.py` (9)

| Test | Issue test | Asserts |
|---|---|---|
| `test_t1_each_name_comes_from_its_defining_file` | T1 (R1) | `from pkg.a import format_x` and `from pkg.b import Widget`, and no line imports `Widget` from `pkg.a` |
| `test_t2_a_test_helper_is_copied_never_imported_from_the_implementation` | T2 (R2) | `make_config` is defined in the suite with its `import json`, no import line names it, and the file compiles |
| `test_t3_a_name_defined_in_two_files_stops_the_scaffold` | T3 (R3) | `ScaffoldImportError` naming the name and both files |
| `test_t3_a_name_defined_nowhere_stops_the_scaffold` | T3 (R3) | `ScaffoldImportError` for a name no planned file defines |
| `test_t3_an_add_file_whose_code_does_not_parse_stops_the_scaffold` | R3 | an Add file whose Section 6 does not parse stops the scaffold |
| `test_t4_the_suite_fails_at_collection_before_the_implementation` | T4 (R4) | `pytest --collect-only` on the T1 suite exits non-zero with `ModuleNotFoundError` |
| `test_t4_a_plan_of_only_modified_files_still_imports_an_added_module` | R4 | `import pkg.new` when no resolved module is an Add |
| `test_t5_boostgauge_2_imports_gauge_widget_from_gauge` | T5 | boostgauge #2's spec emits `from boostgauge.gauge import GaugeWidget`, and nothing from `boostgauge.formatters` names `GaugeWidget` or `get_test_config` |
| `test_section_6_is_read_per_file` | | `extract_plan_code` returns every planned file's code |

T5's spec is boostgauge's `docs/lineage/active/2-implspec/spec-0002-final-spec.md`, copied to `tests/fixtures/boostgauge-2-spec-0002-final-spec.md` because CI has no boostgauge checkout. boostgauge is public.

## Registry

New row `impl.scaffold_import_unresolved`, citing the operator's ADR 0236 acceptance. `impl` halt rows go from 36 to 37; #3725 took them from 35 to 36. The branch was fast-forwarded onto `main` after #3725 landed and the baseline regenerated, since the branch was unpushed at the time.

## Tiers (no speedrun roll running)

```
pytest tests -q                                   21 failed, 11615 passed, 66 skipped, 90 deselected, 6 xfailed
pytest -m "integration or e2e or adversarial"     83 passed, 7 skipped
```

The 21 failures are the same ones that fail on unchanged `main` on this machine, listed in PR #4149's test report. None of them is in the files this change touches.

## Audits

```
audit_loud_failure.py --check            PASS -- 318 site(s)
audit_fail_open.py --check --strict      PASS (regenerated: +1, the spec gate's handler, which returns a failed check)
audit_halt_sites.py --check --strict     PASS -- 152 halt sites, every one registered
```

## Lint

Ruff findings are unchanged against `origin/main` in every changed file, and the new test file has none.
