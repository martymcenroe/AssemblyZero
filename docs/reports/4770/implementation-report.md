# Implementation report: #4770

## The defect

Four tests in `tests/unit/test_new_repo_ubuntu_run.py::TestResolveProjectPath` read this machine's real `~/.assemblyzero/config.json` through the `new_repo.config` singleton, which loads at import:

- `test_real_config_gives_an_absolute_path_beside_this_checkout`
- `test_asks_for_the_spelling_of_this_os`
- `test_refuses_a_relative_root`
- `test_refuses_a_windows_root_resolved_against_the_cwd`

Since #4763, `resolve_project_path()` calls `new_repo_root()`, which reaches `projects_root()` only when the file sets no `new_repo_root`. Once the operator's file set it (#4768), the three tests that patch `projects_root` were bypassed, and the first one resolved to the configured root instead of the checkout's parent.

## The change

One autouse fixture on `TestResolveProjectPath`, `_no_machine_config`. It installs as `new_repo.config` a real `AssemblyZeroConfig` that reads an absent file under the test's `tmp_path`, using the file's existing `_real_config` helper. Every test in the class therefore starts from the defaults. A test that writes its own config file installs it over this one, as before.

No assertion changed, and no production code changed.
