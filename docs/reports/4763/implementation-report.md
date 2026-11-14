# Implementation report: #4763

## The defect

`tools/new_repo.py` put every new repository at `config.projects_root(fmt='auto') / name`. With no `~/.assemblyzero/config.json`, `projects_root` is the folder holding the AssemblyZero checkout, so on this machine every new repository landed in `/mnt/c/Users/mcwiz/Projects`, the Windows drive read over 9p, and none could start on Ubuntu's own ext4 disk. The scaffold also built `PROJECT_ROOT`, `TOOLS_DIR` and the CLAUDE.md "Project Root (Unix)" line from `projects_root_unix()` and the name, not from where the repository is, so a repository anywhere else would have named a path under the Projects root.

## The setting (R1, R4)

`tools/assemblyzero_config.py` gains an optional path key, `new_repo_root`, and a method `new_repo_root(fmt)`. With the key absent it returns exactly what `projects_root(fmt)` returns, so with no configuration nothing changes (R4). The key is separate from `projects_root` so a new repository can start on another disk while every tool that reads `projects_root` still sees the whole fleet. The fleet-wide half of R1, one Projects-root setting that every tool reads, is tracked in #4765; when it lands, `new_repo.py` reads that one.

Validation changed with it:

- Every `paths` key is now optional; an absent key takes its default. `REQUIRED_PATH_KEYS` is renamed `PATH_KEYS`.
- A fleet key that is present (`assemblyzero_root`, `projects_root`, `user_claude_dir`) still needs both the `windows` and the `unix` format.
- `new_repo_root` needs at least one format, because an ext4 path has no Windows spelling of its own.
- Every format a key carries must be a string, and a top level or `paths` that is not a JSON object is an error.

A new attribute, `load_error`, is `None` when the file is absent or valid. When the file exists but is not used (invalid JSON, not UTF-8, unreadable, or failing validation) it holds the file's path and the reason. Every other tool keeps falling back to the defaults as before.

## Where `new_repo.py` builds

`resolve_project_path()` raises `ValueError` naming `load_error` when it is set, and `main()` turns that into exit 1 before anything is created or any command runs. A file that exists but was rejected may have been meant to move the root, so building at the default instead would be a silent wrong. Otherwise the parent is `config.new_repo_root(fmt='auto')`, and the existing check that the root is absolute and exists is kept with its text.

## The paths written into the repository (R2, R3)

`PROJECT_ROOT`, `TOOLS_DIR` and the CLAUDE.md "Project Root (Unix)" line now come from `_spellings(project_path)["unix"]`, the repository's own location.

`PROJECT_ROOT_WINDOWS` comes from a new helper, `windows_spelling(path)`:

- a path on a Windows drive, `C:\...` or `/mnt/c/...`, gets its `C:\` spelling, as before;
- an ext4 path, with `WSL_DISTRO_NAME` set, gets `\\wsl.localhost\<distro>\...`, the share through which Windows reads it;
- with `WSL_DISTRO_NAME` unset there is no such share, and the POSIX path is kept.

### Readers of `.claude/project.json`

R2 asked for every reader before choosing between the WSL-share form and leaving the key out.

- `tools/assemblyzero-generate.py` substitutes every key under `variables` into `{{KEY}}` placeholders in the templates under `.claude/templates/`. No template there uses `{{PROJECT_ROOT_WINDOWS}}`, so no generated file carries the key today. It reads `inherit_from` as the AssemblyZero location.
- `tools/new_repo.py`'s own local check parses the file as JSON and reads no key's value.
- A tool in a private repository scans the file as text for stale names and does not interpret the key.

No reader requires the key, and none rejects the WSL-share form. The WSL-share form is therefore the preferred value, not a required one: it names a path Windows can open, where the POSIX path would not.

### Reading R3

R3 says nothing `new_repo.py` writes into a repository on ext4 names `/mnt/c/Users/mcwiz/Projects` or `C:\Users\mcwiz\Projects`. It is read as covering every path about the new repository. A pointer to AssemblyZero, such as `inherit_from` in `project.json`, names where AssemblyZero really is, from `config.assemblyzero_root()`. While AssemblyZero's checkout sits on the Windows drive, that pointer names the Windows drive, which is true. T2 points `assemblyzero_root` at a temporary directory, so its walk tests only the paths that follow the new repository.

## Tests

- `tests/unit/test_new_repo_ubuntu_run.py`: T1, T2 and the default case, listed in the test report.
- `tests/unit/test_assemblyzero_config_derived.py`: the setting, its validation and `load_error`.
- Mocks of `new_repo.config` in `tests/unit/test_new_repo.py`, `tests/unit/test_new_repo_ubuntu_run.py`, `tests/unit/test_new_repo_no_auto_review_caller.py` and `tests/unit/test_cerberus_after_auto_review.py` now set `load_error = None` and `new_repo_root`, the surface `new_repo.py` reads, in place of `projects_root` and `projects_root_unix`.

The first version of these tests spelled the operator's Projects root as string literals, which the spelled-root guard (`tests/unit/test_no_spelled_projects_root.py`, #3609) forbids in any tracked file under `tests/`. T2 now derives its forbidden strings from `assemblyzero_config.DEFAULTS["projects_root"]` and adds the guard's own `SPELLINGS`, and the default-case test uses another user's path on the Windows drive.

T3, the end-to-end run on `/home/mcwiz/Projects`, creates a real GitHub repository and waits for the operator; it is tracked in #4764.

## Ruff

`ruff check` on the seven changed files reports 37 errors on this branch and the same 37 on main (ed77a367), compared by file, rule and message. The change adds none. The one it first added, UP045 on the new `load_error` annotation, now reads `str | None`.
