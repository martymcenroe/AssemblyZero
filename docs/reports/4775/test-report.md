# Test report: #4775 R3

T1 and T2 (R1, R2) landed in PR #4788; `docs/reports/4776/test-report.md` reports them. This change adds T3.

## New tests

`tests/unit/test_assemblyzero_generate.py`, class `TestProjectNameUnderEveryRoot`, 4 tests. The `two_roots` fixture points `projects_root.CONFIG_PATH` at a config under tmp_path, which points at a roots setting listing two temporary roots, and reads them as Ubuntu, as `tests/unit/test_projects_roots.py` does. No test reads the machine's real config or walks a real Projects root, and none spells the operator's own user folder. Each test runs `main()` against a temporary AssemblyZero holding one template.

| Test | Tests |
|---|---|
| #4775 T3 (R3), found under the second root | `test_a_name_held_only_under_the_second_root_is_found`: `--project Foo` with `Foo` only under the second root generates into that copy, and nothing appears under the first |
| #4775 T3 (R3), refused under two roots | `test_a_name_held_under_both_roots_is_refused`: exit 1, `ERROR:` with both copies' paths in the output, and neither copy gets a generated file |
| Not found | `test_a_name_under_neither_root_is_reported_not_found`: exit 1, `ERROR: Project directory not found: <first root>/Nope` |
| Absolute path | `test_an_absolute_path_is_used_as_given`: the name is under both roots, and an absolute path to a third copy generates into that copy only, with no refusal |

The class is skipped on Windows, where tmp_path is a drive path and the roots setting holds Ubuntu paths.

## Targeted run, 2026-11-15

`tests/unit/test_assemblyzero_generate.py`, `tests/unit/test_projects_roots.py` and `tests/unit/test_project_json_example.py`: `89 passed, 1 warning in 13.36s`.

## Unit tier, 2026-11-15

Run on Ubuntu with pytest directly: `6 failed, 15344 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 871.59s (0:14:31)`. The six failures are all `tests/unit/test_pat_session_named_prompt.py::TestRealGpg`, which fail on Ubuntu because gpg-agent cannot start in their GNUPGHOME (#4766). No other test failed.
