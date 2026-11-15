# Test report: #4768

## New tests

`tests/unit/test_set_new_repo_root.py`, 23 tests. Each points `assemblyzero_config.CONFIG_PATH` at a file under `tmp_path`, patches `platform.system`, clears the loader's cached OS format, and patches `os.geteuid` to a non-root id. None reads or writes the real config file.

| Test | Tests in the file |
|---|---|
| T1 (R1, R2) | `test_a_dry_run_against_an_absent_file_writes_nothing_and_prints_the_plan`, `test_a_dry_run_against_an_existing_file_changes_nothing` |
| T2 (R1, R6, R7) | `test_apply_against_an_absent_file_writes_only_the_key_on_ubuntu`, `test_apply_against_an_absent_file_writes_the_windows_format_on_windows` |
| T3 (R3) | `test_apply_keeps_every_other_key_and_leaves_a_byte_identical_dated_copy`, for `unix` and `windows` |
| T4 (R4) | `test_running_as_root_is_refused`; `test_a_root_that_is_not_an_absolute_existing_directory_is_refused`, for a relative root, a missing one, a file and one holding `..`; `test_an_absent_root_is_refused_against_an_absent_file`; `test_a_config_file_the_loader_refuses_is_refused`, for invalid JSON, a file not in UTF-8, a file with no `paths`, a non-string value and a fleet key with one format |
| T5 (R5) | `test_a_second_apply_with_the_same_root_changes_nothing`, `test_a_trailing_slash_is_the_same_root` |
| T6 (R6) | `test_a_failed_proof_ends_failed_with_exit_1` (the proof's `new_repo_root` reports another root), `test_a_proof_that_finds_another_path_moved_ends_failed` |
| R7, and the limits | `test_the_header_gives_the_command_every_step_and_who_applies`, `test_the_program_deletes_nothing_and_imports_only_the_stdlib_and_the_loader` |

The tests were written first and failed at collection, with no module to import, before the program existed.

## Not covered here

- T7 (R8), the correction on #4763, is the coordinator's.
- No test runs the program on a real Windows machine; the `windows` format is tested with `platform.system` patched.

## Targeted runs, 2026-11-14

The new file with `test_no_spelled_projects_root.py`, `test_every_test_file_runs_in_a_tier.py` and `test_callback_and_docstring_symbols.py`: `57 passed, 1 warning in 72.41s (0:01:12)`.

## Unit tier, 2026-11-14

`poetry run pytest tests/unit/ -q --tb=short -v`, run directly rather than through test-gate (#4758):

`6 failed, 15207 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 1569.62s (0:26:09)`

The six failures are `tests/unit/test_pat_session_named_prompt.py::TestRealGpg`, four `test_the_right_passphrase_decrypts_with_no_box_from_gpg` cases, `test_a_wrong_passphrase_fails_cleanly` and `test_the_passphrase_is_never_in_argv_env_output_or_errors`. They are the failures #4766 tracks, in a file this change does not touch. No other test failed.
