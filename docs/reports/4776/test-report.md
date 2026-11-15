# Test report: #4776, #4777, and #4775 R1, R2, R4

## New tests

`tests/unit/test_assemblyzero_generate.py`, 31 tests, and two new classes in `tests/unit/test_new_repo_ubuntu_run.py`, 8 tests. Every path is temporary or another user's (`someone`); none spells the operator's own user folder, and none writes under a real Projects root or the real `~/.assemblyzero/config.json`.

| Test | Tests |
|---|---|
| #4775 T1 (R1), Ubuntu side | `TestInheritFromOnUbuntu`: `test_a_drive_spelling_opens_through_the_drive_mount` for `C:\`, `C:/`, `/c/` and `/mnt/c/`, each opening a temporary AssemblyZero's `.claude/templates` through a temporary drive mount; `test_an_ext4_spelling_opens_as_its_posix_path` for a POSIX path, `\\wsl.localhost\Ubuntu\...` and `//wsl.localhost/Ubuntu/...`; `test_the_default_mount_is_wsls`; `test_a_trailing_separator_is_dropped`; `test_a_relative_value_is_kept_as_written` |
| #4775 T1 (R1), Windows side | `TestInheritFromOnWindows`: `test_a_drive_spelling_becomes_the_drive_path` and `test_an_ext4_spelling_becomes_the_wsl_share` for the same seven spellings; `test_the_share_keeps_the_distro_the_file_names`; `test_a_drive_spelling_names_the_same_assemblyzero_on_both_sides` and `test_an_ext4_spelling_names_the_same_assemblyzero_on_both_sides`, which read the Windows result back on the Ubuntu side and open the temporary AssemblyZero |
| #4775 T2 (R2) | `TestInheritFromIsReadOnBothSides`: `test_assemblyzero_on_a_drive`, `test_assemblyzero_on_ext4`, `test_this_checkout_by_default` |
| #4776 T1 (R1) | `TestCleanupTemplateUnderAnExt4Root::test_the_cleanup_command_names_assemblyzeros_real_path`, with `inherit_from` as a POSIX path and as the WSL share: `main()` renders the real cleanup template for a repository under a temporary ext4-style root, and the command names the temporary AssemblyZero, with no `/../AssemblyZero` and no unsubstituted placeholder |
| #4776, the variable's spelling | `TestAssemblyZeroRootVariable`: the POSIX path on Ubuntu, `C:/...` and `//wsl.localhost/...` on Windows |
| #4776 T2 (R2) | `test_no_file_under_claude_reaches_assemblyzero_as_a_sibling`, over every tracked file under `.claude/` |
| #4777 T1 (R1) | `TestClaudeMdWindowsLine`: `test_an_ext4_path_is_the_wsl_share` (`/home/mcwiz/Projects/Foo` with `WSL_DISTRO_NAME=Ubuntu`), `test_a_drive_path_seen_from_ubuntu_is_its_drive_spelling` |
| #4777 T2 (R2) | `TestClaudeMdWindowsLine::test_a_windows_path_is_unchanged`, for a `C:\` path as written and as a `PureWindowsPath`; `test_create_claude_md_writes_the_content` |

The tests were written first and failed at collection, with no `inherit_from_path` to import, before the change.

## Not covered here

- #4775 T3 (R3, `--project` across roots) waits for its own change.
- No test runs the generator on a real Windows machine; the Windows side is tested through `windows=True`.

## Targeted runs, 2026-11-14

`tests/unit/test_assemblyzero_generate.py` with `tests/unit/test_new_repo_ubuntu_run.py`: `61 passed, 1 warning in 55.48s`. The wider targeted set (every `test_new_repo*.py`, the spelled-root guard, the tier guard, `test_project_json_example.py`, `test_scaffolder_lint_integration.py`, `test_assemblyzero_config_derived.py`) had not finished when this was written.

## Unit tier, 2026-11-14

Not yet run.
