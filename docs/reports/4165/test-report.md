# Test Report: programs read the fleet's public identifiers from one file (#4165)

## `tests/unit/test_fleet_ids.py` (13)

| In the issue | Test |
|---|---|
| T1 (R2) | `test_t1_get_returns_each_listed_value` (7 values), `test_t1_an_unknown_key_raises_naming_the_known_ones` |
| T2 (R3) | `test_t2_no_program_in_tools_hard_codes_an_app_id`, `test_the_programs_that_need_the_ids_read_them` |
| T3 (R1) | `test_t3_no_value_is_shaped_like_a_credential` |
| R1 | `test_the_file_says_it_is_generated` |
| R4 | `test_the_sentinel_readme_cites_the_file` |

T2 lists untracked files as well as tracked ones, so a new tool is checked before it is committed. A test that listed only tracked files passed locally on a new file that still carried an App ID in its docstring, and failed once the file was committed.

The edited tools' own tests pass: `tests/unit/test_deploy_cerberus_secrets.py`, `tests/tools/test_sentinel_migrate.py`, `tests/tools/test_fleet_delete_pr_sentinel.py`.

## Unit suite, as CI runs it

```
tools/test-gate.py tests/unit/ (worktree, AssemblyZero's poetry environment)
7 failed, 11139 passed, 76 skipped, 7 deselected, 6 xfailed, 4 errors in 694.03s
```

The failures and errors are in `tests/unit/test_cascade_detector.py`, `test_issue_161.py`, `test_mine_verdict_patterns.py` and `test_open_questions_loop.py`. None of them touches this change, and the same 7 failures and 4 errors occur on unchanged `main` (`879f37cc`) on the same machine. CI on `main` passes, so they depend on this machine's environment.
