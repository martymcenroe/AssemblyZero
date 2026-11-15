# Implementation report: #4765, #4778, #4791

## What changed

`tools/new_repo.py`:

- Reads the fleet's Projects roots through `assemblyzero.core.projects_root` (imported as `fleet_roots`), once, after `resolve_project_path()` and before anything is created or audited. A broken config or pointer stops the run with `ERROR:` lines on stderr and exit 1.
- **#4765 R1.** `new_repo_root_refusal()`: when a setting lists the roots (`roots_source()` is not `DERIVED`), `new_repo_root` must be one of them, compared resolved on this side. Otherwise the run exits 1 naming `new_repo_root`, the setting and every root.
- **#4765 R2.** `held_name_refusal()`: after the existing "Directory already exists" check, `locate_repo()` looks for the name under every searched root. A copy under another root, a name under two roots, or a missing root exits 1 naming where.
- **#4765 R3.** With no pointer, R1 does not apply; the searched roots are the one derived root plus `new_repo_root` when it is another folder (`roots_to_search()`). `resolve_project_path()` is unchanged.
- **#4778.** `--audit` uses `audit_target()`: the one copy under any searched root is audited; a name under two roots is refused naming both copies; a name under none is reported naming every root searched.
- **#4791.** `_mint_github_app_jwt` is deleted. `run_pr_sentinel_check` calls `_github_app_jwt.mint_app_jwt`, imported as a module so a test patches it in one place.

`tools/_github_app_jwt.py`: its docstring no longer says new_repo.py keeps a copy.

Every refusal comes before `get_github_username()`, `run_command` and `_create_repo`, so nothing is created and GitHub is not called.

## Tests

`tests/unit/test_new_repo_ubuntu_run.py::TestProjectsRoots` (new): #4765 T1 (both halves), T2 (with and without a pointer), T3, a broken pointer, #4778 T1, T2, T3. The roots are temporary: `projects_root.CONFIG_PATH`, `REPO_ROOT` and `_windows` are patched as `tests/unit/test_projects_roots.py` patches them.

`tests/unit/test_new_repo.py`: T313 tests `_github_app_jwt.mint_app_jwt`; T316 and T317 patch `_github_app_jwt.mint_app_jwt`, and T316 asserts it minted the token the probe sent; T325 (new) fails if new_repo.py defines a JWT function or loads a private key again.

`tests/unit/test_new_repo_post_create_hooks.py`: the one patch target moved to `new_repo._github_app_jwt.mint_app_jwt`.

## Test isolation from this machine's roots

The tests that run `new_repo.main()` with a mocked `new_repo_root` used to read `projects_root.CONFIG_PATH` from the machine. They passed only because no pointer was set; once `paths.projects_roots_file` is set, R1 would refuse their temporary `new_repo_root`. That gap is closed in this change:

- `tests/unit/conftest.py` gains the plain fixture `temporary_projects_roots`. It points `projects_root.CONFIG_PATH` at a config path that does not exist (no pointer), points `REPO_ROOT` at an `AssemblyZero` folder in a fresh temporary folder (so the one derived root is temporary), and forces `_windows` to False, as `TestProjectsRoots.env` does. The folder comes from `tmp_path_factory`, outside the test's `tmp_path`, because `TestResolveProjectPath.test_refuses_a_relative_root` requires `tmp_path` empty. It is not autouse for the tree, because the tests of `projects_root` itself read the real `REPO_ROOT`.
- Each module whose tests run `main()` opts in with a module-level autouse fixture, `_projects_roots_are_temporary`: `test_new_repo.py`, `test_new_repo_post_create_hooks.py`, `test_new_repo_ubuntu_run.py`, `test_cerberus_after_auto_review.py` and `test_new_repo_no_auto_review_caller.py`. `test_new_repo_safety.py` runs `main()` only as far as argument parsing, before the roots are read, so it needs none. In `test_new_repo_ubuntu_run.py` the class fixture `TestProjectsRoots.env` runs after the module's and sets its own roots, which win.
- `test_new_repo.py::TestMainReadsTemporaryProjectsRoots` proves it: with the fixture in force the config is temporary and the roots are derived; with a config whose pointer names a setting that leaves `tmp_path` out, `main()` exits 1 naming the setting and builds nothing; with the fixture's config back, the same run builds under `tmp_path`.
