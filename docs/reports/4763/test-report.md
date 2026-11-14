# Test report: #4763

## Changed tests

- **T1 (R1, R4)**, in `tests/unit/test_new_repo_ubuntu_run.py`, class `TestResolveProjectPath`:
  - `test_a_configured_new_repo_root_is_where_it_builds`: with `new_repo_root` set to a temporary directory, `resolve_project_path()` returns `<tmp>/<name>`, asked for in this OS's spelling.
  - `test_with_no_config_file_it_builds_in_the_projects_root`: with no config file it returns `projects_root(fmt='auto')/<name>`, as before.
  - `test_a_file_holding_only_new_repo_root_is_honoured`: a real `AssemblyZeroConfig` reading a file that holds only `new_repo_root` loads it and builds there.
  - `test_a_config_file_that_is_not_json_stops_the_run_first`: with a config file of invalid JSON, `main()` with `--no-github` exits 1, stderr names the file, `run_command` is never called and no directory is made.
- **T2 (R2, R3)**, in the same file, `TestScaffoldUnderAnExt4Root::test_every_path_written_is_real_where_the_repository_is`, two cases (`in-wsl` with `WSL_DISTRO_NAME=Ubuntu`, `no-distro` with it unset). A real config on a temporary file points `new_repo_root` and `assemblyzero_root` at temporary directories, and `main()` scaffolds with `--no-github`, running only `git init` for real. No file written under the new repository, `.git/` aside, contains `/mnt/c/Users/mcwiz/Projects`, `/c/Users/mcwiz/Projects`, `C:\Users\mcwiz\Projects` or that spelling's JSON escape. `PROJECT_ROOT` and `TOOLS_DIR` in `.claude/project.json` name the temporary path, `PROJECT_ROOT_WINDOWS` is `\\wsl.localhost\Ubuntu\...` in WSL and the POSIX path without a distribution, and CLAUDE.md's "Project Root (Unix)" line names the temporary path. No file the scaffold copies from AssemblyZero tripped the walk. The class is skipped on Windows, where no ext4 root exists.
- **The default case (R4)**, `test_a_repository_on_a_windows_drive_keeps_its_drive_spellings`: for `/mnt/c/Users/mcwiz/Projects/Foo`, `project_json_content()` gives `PROJECT_ROOT` `/mnt/c/Users/mcwiz/Projects/Foo`, `TOOLS_DIR` `/mnt/c/Users/mcwiz/Projects/Foo/tools` and `PROJECT_ROOT_WINDOWS` `C:\Users\mcwiz\Projects\Foo`, with `WSL_DISTRO_NAME` set.
- **The setting**, in `tests/unit/test_assemblyzero_config_derived.py`:
  - `test_a_file_holding_only_new_repo_root_loads_and_keeps_every_default`: `load_error` is None and the three fleet keys keep their defaults in both formats.
  - `test_a_fleet_key_missing_a_format_is_rejected_and_named`: `load_error` names the file and `Path 'projects_root' missing 'windows' format`.
  - `test_a_new_repo_root_without_a_usable_format_is_rejected`, two cases: no format at all, and a format that is not a string.
  - `test_invalid_json_names_the_file_and_the_reason`: `load_error` starts with the path and gives the line and column.
  - `test_an_absent_file_is_no_error`.
  - `test_without_new_repo_root_it_is_the_projects_root`, two cases (no file, and a file setting only `projects_root`): `new_repo_root(fmt)` equals `projects_root(fmt)` for both formats.
- Mocks of `new_repo.config` in `tests/unit/test_new_repo.py`, `tests/unit/test_new_repo_ubuntu_run.py`, `tests/unit/test_new_repo_no_auto_review_caller.py` and `tests/unit/test_cerberus_after_auto_review.py` set `load_error = None` and `new_repo_root` in place of `projects_root` and `projects_root_unix`.

That is 15 new test cases.

## Not covered here

- **T3**, one throwaway repository created end to end on `/home/mcwiz/Projects`, makes a real GitHub repository and waits for the operator's word. It is tracked in #4764.
- The fleet-setting half of **R1**, `new_repo.py` reading the fleet's one Projects-root setting once it exists, is tracked in #4765.

## Implementation runs, 2026-11-14

On Ubuntu, Python 3.14, with `poetry run pytest`:

- The five files touched by the change, before the new tests: `169 passed, 1 warning in 324.76s (0:05:24)`.
- `tests/unit/test_new_repo_ubuntu_run.py` and `tests/unit/test_assemblyzero_config_derived.py` with the new tests: `36 passed, 1 warning in 69.92s (0:01:09)`.

## Unit tier, 2026-11-14

UNIT_TIER_RESULT
