# Implementation report: #4763 (work in progress)

Status: in progress. This commit holds the code change; the new tests and the suite run are still to do.

| File | Change |
|---|---|
| `tools/assemblyzero_config.py` | New optional path key `new_repo_root` and method `new_repo_root(fmt)`, which returns `projects_root(fmt=fmt)` when the key is absent. Every `paths` key is now optional: an absent key takes its default. A fleet key that is present still needs both formats; `new_repo_root` needs at least one; every format carried must be a string. A non-object top level or `paths` is an error. A file that exists but is rejected sets `load_error` (path and reason); absent or valid leaves it `None`. Other tools keep falling back to defaults. |
| `tools/new_repo.py` | `resolve_project_path()` refuses when `config.load_error` is set ("Nothing was created") and otherwise uses `config.new_repo_root(fmt='auto')`, keeping the absolute-and-existing check and text. `PROJECT_ROOT`, `TOOLS_DIR` and the CLAUDE.md `Project Root (Unix)` line come from `_spellings(project_path)["unix"]`. New `windows_spelling()` gives `PROJECT_ROOT_WINDOWS`: the `C:\` spelling for a drive path, `\\wsl.localhost\<WSL_DISTRO_NAME>\...` for an ext4 path under WSL, the POSIX path when that variable is unset. `inherit_from` still names AssemblyZero's real location (`config.assemblyzero_root()`). |
| `tests/unit/test_new_repo.py`, `tests/unit/test_new_repo_ubuntu_run.py` | Mocks of `new_repo.config` set `load_error = None` and `new_repo_root`, the surface new_repo now reads. |

## Readers of `.claude/project.json`

- `tools/assemblyzero-generate.py` substitutes every key under `variables` into `{{KEY}}` placeholders. No template under `.claude/templates/` carries `{{PROJECT_ROOT_WINDOWS}}`, so today it substitutes the key nowhere. It reads `inherit_from` as the AssemblyZero location.
- `tools/new_repo.py`'s local check only parses the file as JSON.
- A tool in a private repository scans the file as text for stale names and does not interpret the key.

The WSL-share form was chosen as the preferred value.

## Still to do

New tests (T1, T2, default-case project.json, config decisions 2 and 3), the same mock update in `tests/unit/test_new_repo_no_auto_review_caller.py` and `tests/unit/test_cerberus_after_auto_review.py`, ruff, the unit tier, and the final reports.
