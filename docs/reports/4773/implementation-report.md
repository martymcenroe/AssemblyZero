# Implementation report: #4773

## The defect

`assemblyzero/core/projects_root.py` set `PROJECTS = REPO_ROOT.parent`, one folder. A repository under any other Projects root was invisible to every tool built on it.

## The module (R1, R2, R4, R5, R6)

`assemblyzero/core/projects_root.py` keeps `REPO_ROOT` and `spellings()`. The default for `spellings()` is now `REPO_ROOT.parent`, the value `PROJECTS` held before, so it reads no config.

- `CONFIG_PATH`, `PROJECTS_ROOTS_FILE_KEY`, `WSL_DISTRO = "Ubuntu"`, `DERIVED`: constants.
- `spell_root(root, windows)`: a root in Ubuntu's spelling, as one side writes it. On Windows, `/mnt/<d>/rest` becomes `<D>:/rest` and any other path becomes `//wsl.localhost/Ubuntu/rest`.
- `read_roots_setting(setting, windows=None)`: reads and validates a roots setting and returns its roots for one side. RuntimeError names the file and the reason.
- `projects_roots_file(windows=None)`: the pointer, read from the config for one side. It returns None when the config, the key or this side's format is absent. A broken config or pointer raises.
- `projects_roots(windows=None)`: the roots from the setting, or `[REPO_ROOT.parent]` with no pointer. A broken pointer raises, naming the config, the setting and the reason.
- `roots_source(windows=None)`: the setting's path, or `DERIVED`.
- `missing_roots(roots)`: the roots that are not existing directories.
- `repositories(roots=None)`: `(found, twice)`. A missing root raises first. With no pointer, it prints one notice line to stderr.
- `locate_repo(name, roots=None)`: the one copy, or `roots[0] / name`. Two copies raise. A missing root also raises, because a second copy could be under it.
- `PROJECTS_ROOTS` and `PROJECTS` are lazy attributes (PEP 562), read again on every access.

## The pointer (R1, R7)

`tools/assemblyzero_config.py` adds `PROJECTS_ROOTS_FILE_KEY` and validates it like `new_repo_root`. `projects_roots_file(fmt)` returns None when the key or the format is absent. It never falls back to the other OS's value.

## The program (R7)

`tools/set_projects_roots_file.py --file PATH [--apply]` follows `tools/set_new_repo_root.py`. The write, copy and prove steps are copied rather than shared. That model's unchanged test requires it to import only the standard library and the loader, and a shared module would break that test.

## Ruff

The changed files add no finding. The five that remain were already at a94a589f: `tools/assemblyzero_config.py` lines 88, 100 and 263, and `tests/unit/test_assemblyzero_config_derived.py` lines 12 and 13.
