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

## Not done

The existing tests that run `new_repo.main()` with a mocked `new_repo_root` still read `projects_root.CONFIG_PATH` from the machine. With no pointer set today they pass. Once the operator sets `paths.projects_roots_file`, R1 will refuse their temporary `new_repo_root`; they need the roots patched as `TestProjectsRoots.env` does. Follow-up issue to be filed by the coordinator.
